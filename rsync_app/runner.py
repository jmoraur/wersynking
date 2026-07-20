"""Sync runner: queues rsync jobs and runs them via QProcess.

Jobs are grouped by `destDeviceId` — one rsync at a time per device
(don't want two writers on the same disk), but separate devices run
in parallel. That matches the M3-redux scope rules:

- connection scope: 1 job → 1 device → sequential trivially.
- device scope: N jobs, all same device → sequential within.
- container / source scope: N jobs across K devices → K in parallel,
  sequential within each.

QML interop:

- `enqueue(jobs)` takes a JS array of `{argv, label, destDeviceId}`.
- `jobs()` returns a snapshot (no log payload — fetched on demand via
  `jobLog(id)` so we don't shovel the whole buffer through QVariant on
  every state change).
- `jobOutputAppended(id, text)` streams stdout/stderr incrementally.
- `runningChanged` fires whenever the active count may have shifted.
"""

from __future__ import annotations

from typing import Optional

from PySide6.QtCore import (
    QObject,
    QProcess,
    QTimer,
    Signal,
    Slot,
)


_TERMINATE_GRACE_MS = 2000

_TERMINAL_STATES = frozenset({"done", "failed", "cancelled"})


class _Job:
    __slots__ = (
        "id",
        "argv",
        "label",
        "dest_device_id",
        "state",
        "log",
        "exit_code",
        "process",
        "cancel_requested",
    )

    def __init__(
        self,
        job_id: int,
        argv: list[str],
        label: str,
        dest_device_id: int,
    ) -> None:
        self.id = job_id
        self.argv = list(argv)
        self.label = label
        self.dest_device_id = dest_device_id
        self.state = "pending"
        self.log = ""
        self.exit_code: Optional[int] = None
        self.process: Optional[QProcess] = None
        self.cancel_requested = False

    def snapshot(self) -> dict:
        return {
            "id": self.id,
            "argv": list(self.argv),
            "label": self.label,
            "destDeviceId": self.dest_device_id,
            "state": self.state,
            # QML can't represent Python None as a number; use -1 to
            # mean "not finished yet".
            "exitCode": -1 if self.exit_code is None else self.exit_code,
        }


class SyncRunner(QObject):
    jobsChanged = Signal()
    jobOutputAppended = Signal(int, str)
    jobStateChanged = Signal(int, str)
    runningChanged = Signal()

    def __init__(self, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._next_id = 1
        self._all: dict[int, _Job] = {}
        self._order: list[int] = []
        self._queues: dict[int, list[int]] = {}  # device_id → pending job ids
        self._active: dict[int, int] = {}        # device_id → running job id
        # fn(dest_device_id, argv) -> error string, or None to allow.
        # Queued jobs carry argvs resolved at confirm-time; the check runs
        # at start-time so a device that unmounted (or remounted elsewhere)
        # while the job waited fails loudly instead of writing to a stale
        # path on the root filesystem.
        self._pre_start_check = None

    def set_pre_start_check(self, fn) -> None:
        self._pre_start_check = fn

    # -- slots ---------------------------------------------------------

    @Slot("QVariantList")
    def enqueue(self, jobs: list) -> None:
        added = False
        for spec in jobs:
            argv = list(spec.get("argv") or [])
            if not argv:
                continue
            label = str(spec.get("label") or "")
            device_id = int(spec.get("destDeviceId") or 0)
            job = _Job(self._next_id, argv, label, device_id)
            self._next_id += 1
            self._all[job.id] = job
            self._order.append(job.id)
            self._queues.setdefault(device_id, []).append(job.id)
            added = True
        if added:
            self.jobsChanged.emit()
            self._pump()

    @Slot(int)
    def cancel(self, job_id: int) -> None:
        job = self._all.get(job_id)
        if job is None or job.state in _TERMINAL_STATES:
            return
        if job.state == "pending":
            queue = self._queues.get(job.dest_device_id) or []
            try:
                queue.remove(job_id)
            except ValueError:
                pass
            job.state = "cancelled"
            self.jobStateChanged.emit(job.id, job.state)
            self.jobsChanged.emit()
        else:  # running
            job.cancel_requested = True
            self._terminate(job)

    @Slot()
    def cancelAll(self) -> None:
        for job_id in list(self._all.keys()):
            self.cancel(job_id)

    @Slot()
    def clearFinished(self) -> None:
        keep: list[int] = []
        for job_id in self._order:
            job = self._all[job_id]
            if job.state in _TERMINAL_STATES:
                del self._all[job_id]
            else:
                keep.append(job_id)
        if len(keep) != len(self._order):
            self._order = keep
            self.jobsChanged.emit()

    @Slot(result="QVariantList")
    def jobs(self) -> list:
        return [self._all[jid].snapshot() for jid in self._order]

    @Slot(int, result=str)
    def jobLog(self, job_id: int) -> str:
        job = self._all.get(job_id)
        return job.log if job is not None else ""

    @Slot(result=int)
    def runningCount(self) -> int:
        return len(self._active)

    @Slot()
    def shutdown(self) -> None:
        """Terminate all in-flight jobs synchronously. Wired to aboutToQuit."""
        for job_id in list(self._active.values()):
            job = self._all.get(job_id)
            if job is None or job.process is None:
                continue
            job.cancel_requested = True
            job.process.terminate()
        for job_id in list(self._active.values()):
            job = self._all.get(job_id)
            if job is None or job.process is None:
                continue
            if not job.process.waitForFinished(_TERMINATE_GRACE_MS):
                job.process.kill()
                job.process.waitForFinished(500)

    # -- internals -----------------------------------------------------

    def _pump(self) -> None:
        """Start one job on every device queue that has free capacity."""
        prev_running = len(self._active)
        for device_id, queue in self._queues.items():
            if device_id in self._active:
                continue
            while queue:
                job_id = queue.pop(0)
                job = self._all[job_id]
                err = (
                    self._pre_start_check(job.dest_device_id, job.argv)
                    if self._pre_start_check is not None else None
                )
                if err is not None:
                    self._fail_pre_start(job, err)
                    continue
                self._active[device_id] = job_id
                self._start(job)
                break
        if len(self._active) != prev_running:
            self.runningChanged.emit()

    def _fail_pre_start(self, job: _Job, reason: str) -> None:
        text = f"[runner] not started: {reason}\n"
        job.log += text
        self.jobOutputAppended.emit(job.id, text)
        job.state = "failed"
        self.jobStateChanged.emit(job.id, job.state)
        self.jobsChanged.emit()

    def _start(self, job: _Job) -> None:
        proc = QProcess(self)
        proc.setProcessChannelMode(QProcess.ProcessChannelMode.MergedChannels)
        proc.setProgram(job.argv[0])
        proc.setArguments(job.argv[1:])
        proc.readyReadStandardOutput.connect(
            lambda jid=job.id: self._on_output(jid)
        )
        proc.finished.connect(
            lambda code, status, jid=job.id: self._on_finished(jid, code, status)
        )
        proc.errorOccurred.connect(
            lambda err, jid=job.id: self._on_error(jid, err)
        )
        job.process = proc
        job.state = "running"
        self.jobStateChanged.emit(job.id, job.state)
        self.jobsChanged.emit()
        proc.start()

    def _on_output(self, job_id: int) -> None:
        job = self._all.get(job_id)
        if job is None or job.process is None:
            return
        data = bytes(job.process.readAllStandardOutput())
        if not data:
            return
        text = data.decode("utf-8", errors="replace")
        job.log += text
        self.jobOutputAppended.emit(job.id, text)

    def _on_finished(
        self,
        job_id: int,
        exit_code: int,
        exit_status: QProcess.ExitStatus,
    ) -> None:
        job = self._all.get(job_id)
        if job is None:
            return
        # Drain whatever's left in the pipe before the process is gone.
        self._on_output(job_id)
        job.exit_code = exit_code
        if job.cancel_requested:
            job.state = "cancelled"
        elif (
            exit_status == QProcess.ExitStatus.NormalExit
            # 24 = "some source files vanished during transfer" — routine
            # when syncing a live directory; everything else was synced.
            # 23 (partial transfer due to errors) stays a failure.
            and exit_code in (0, 24)
        ):
            if exit_code == 24:
                note = (
                    "\n[runner] rsync exit code 24: some source files"
                    " vanished during the transfer (normal for a live"
                    " source); everything else was synced.\n"
                )
                job.log += note
                self.jobOutputAppended.emit(job.id, note)
            job.state = "done"
        else:
            job.state = "failed"
        job.process = None
        if self._active.get(job.dest_device_id) == job.id:
            del self._active[job.dest_device_id]
        self.jobStateChanged.emit(job.id, job.state)
        self.jobsChanged.emit()
        self.runningChanged.emit()
        self._pump()

    def _on_error(
        self, job_id: int, error: QProcess.ProcessError
    ) -> None:
        # Only FailedToStart needs handling here — other errors come
        # paired with a `finished` signal that does the bookkeeping.
        if error != QProcess.ProcessError.FailedToStart:
            return
        job = self._all.get(job_id)
        if job is None:
            return
        job.log += f"\n[runner] failed to start: {job.argv[0]}\n"
        self.jobOutputAppended.emit(job.id, job.log)
        job.exit_code = -1
        job.state = "failed"
        job.process = None
        if self._active.get(job.dest_device_id) == job.id:
            del self._active[job.dest_device_id]
        self.jobStateChanged.emit(job.id, job.state)
        self.jobsChanged.emit()
        self.runningChanged.emit()
        self._pump()

    def _terminate(self, job: _Job) -> None:
        if job.process is None:
            return
        proc = job.process
        proc.terminate()
        # Escalate to kill if SIGTERM didn't take after the grace period.
        QTimer.singleShot(
            _TERMINATE_GRACE_MS,
            lambda p=proc: (
                p.kill()
                if p.state() != QProcess.ProcessState.NotRunning
                else None
            ),
        )

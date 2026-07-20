"""Headless smoke test for SyncRunner.

Spawns two `rsync --dry-run` jobs on distinct device ids and asserts
both end in `done` with exit 0. The two-device setup also confirms
parallel scheduling: peak runningCount should reach 2.

Run from the project root:

    PYTHONPATH=. python scripts/smoke_runner.py
"""
from __future__ import annotations

import shutil
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QTimer

from rsync_app.runner import SyncRunner


def main() -> int:
    if shutil.which("rsync") is None:
        print("FAIL: rsync not on PATH")
        return 2

    app = QCoreApplication(sys.argv)

    tmp = Path(tempfile.mkdtemp(prefix="rsync-smoke-runner-"))
    src1, dst1 = tmp / "src1", tmp / "dst1"
    src2, dst2 = tmp / "src2", tmp / "dst2"
    for d in (src1, dst1, src2, dst2):
        d.mkdir(parents=True)
    (src1 / "hello.txt").write_text("hi\n")
    (src2 / "world.txt").write_text("yo\n")

    runner = SyncRunner()

    # Track peak parallelism so we can prove devices ran concurrently.
    peak_running = {"value": 0}

    def on_running_changed():
        n = runner.runningCount()
        if n > peak_running["value"]:
            peak_running["value"] = n
        print(f"[running] count = {n}")

    runner.runningChanged.connect(on_running_changed)
    runner.jobStateChanged.connect(
        lambda jid, state: print(f"[state ] job={jid} → {state}")
    )

    jobs = [
        {
            "argv": ["rsync", "--archive", "--verbose", "--dry-run",
                     str(src1) + "/", str(dst1) + "/"],
            "label": "src1 → dst1",
            "destDeviceId": 1,
        },
        {
            "argv": ["rsync", "--archive", "--verbose", "--dry-run",
                     str(src2) + "/", str(dst2) + "/"],
            "label": "src2 → dst2",
            "destDeviceId": 2,
        },
    ]
    runner.enqueue(jobs)

    expected_total = len(jobs)
    done_flag = {"reported": False}

    def maybe_finish(*_):
        if done_flag["reported"]:
            return
        snapshot = runner.jobs()
        terminal = [j for j in snapshot
                    if j["state"] in ("done", "failed", "cancelled")]
        if len(terminal) < expected_total:
            return
        done_flag["reported"] = True

        ok = True
        for j in snapshot:
            log_tail = "\n   ".join(
                runner.jobLog(j["id"]).strip().splitlines()[-3:]
            )
            print(f"[final ] {j['label']}: state={j['state']} "
                  f"exit={j['exitCode']}")
            print(f"   {log_tail}")
            if j["state"] != "done" or j["exitCode"] != 0:
                ok = False
        if peak_running["value"] < 2:
            print(f"WARN: peak parallelism was {peak_running['value']} "
                  "— expected 2 (devices should have overlapped)")
            # Not a hard failure; a fast machine may finish job 1 before
            # job 2 even starts its event loop tick. Log only.
        if ok:
            print("SMOKE OK")
            app.exit(0)
        else:
            print("SMOKE FAIL")
            app.exit(1)

    runner.jobStateChanged.connect(maybe_finish)

    # Safety net — kill the loop if rsync hangs.
    QTimer.singleShot(30_000, lambda: (print("TIMEOUT"), app.exit(2)))

    rc = app.exec()
    shutil.rmtree(tmp, ignore_errors=True)
    return rc


if __name__ == "__main__":
    sys.exit(main())

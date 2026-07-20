"""Suspend inhibition while sync jobs are running.

Holds a `systemd-inhibit ... sleep infinity` helper process for as long
as the runner has any active jobs. Releases (kills the helper) the
moment runningCount drops to 0. Only inhibits `sleep` — not `idle`, so
the display can still lock during a long sync.

Uses the `systemd-inhibit` CLI rather than QtDBus because PySide6 6.10's
QtDBus has known issues for our use case (see CLAUDE.md). Falls back
gracefully (no-op) if `systemd-inhibit` isn't on PATH.
"""

from __future__ import annotations

import shutil
import subprocess
from typing import Optional

from PySide6.QtCore import QObject, Slot


class SuspendInhibitor(QObject):
    def __init__(self, runner, parent: Optional[QObject] = None) -> None:
        super().__init__(parent)
        self._runner = runner
        self._proc: Optional[subprocess.Popen] = None
        self._available = shutil.which("systemd-inhibit") is not None
        if self._available:
            self._runner.runningChanged.connect(self._refresh)

    def isAvailable(self) -> bool:
        return self._available

    def isHeld(self) -> bool:
        return self._proc is not None

    def _refresh(self) -> None:
        running = self._runner.runningCount()
        if running > 0 and self._proc is None:
            self._acquire()
        elif running == 0 and self._proc is not None:
            self._release()

    def _acquire(self) -> None:
        try:
            self._proc = subprocess.Popen(
                [
                    "systemd-inhibit",
                    "--what=sleep",
                    "--who=We RSynk-ing",
                    "--why=Sync in progress",
                    "--mode=block",
                    "sleep", "infinity",
                ],
                stdin=subprocess.DEVNULL,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except OSError:
            self._proc = None

    def _release(self) -> None:
        proc = self._proc
        self._proc = None
        if proc is None:
            return
        try:
            proc.terminate()
            try:
                proc.wait(timeout=2)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait(timeout=1)
        except OSError:
            pass

    @Slot()
    def stop(self) -> None:
        self._release()

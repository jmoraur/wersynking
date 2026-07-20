"""Smoke: tray + notifications + suspend inhibition.

Boots a minimal Qt app with the runner + tray + inhibitor, enqueues two
short jobs (one success, one failure on distinct devices), and runs the
event loop until both are terminal.

Programmatic checks (printed to stdout):
  - QSystemTrayIcon available + tray.isVisible() after creation
  - inhibitor.isAvailable() (i.e. `systemd-inhibit` on PATH)
  - inhibitor.isHeld() goes True while jobs run, False after
  - per-job terminal states match expectations

Manual checks (eyes on screen):
  - tray icon appears with tooltip updating across "1 running · 1 queued",
    "1 running", "1 done · 1 failed"
  - one Information notification ("Sync done") and one Warning notification
    ("Sync failed (exit 1)") appear
  - while jobs are running, `systemd-inhibit --list` shows a row with
    Who=RsyncApp, What=sleep, Mode=block

Run via:  PYTHONPATH=. python scripts/smoke_tray.py
"""

from __future__ import annotations

import sys

from PySide6.QtCore import QTimer
from PySide6.QtWidgets import QApplication

from rsync_app.inhibitor import SuspendInhibitor
from rsync_app.runner import SyncRunner
from rsync_app.tray import TrayController


def main() -> int:
    app = QApplication(sys.argv)
    app.setOrganizationName("RsyncApp")
    app.setOrganizationDomain("rsync-app.local")
    app.setApplicationName("RsyncApp")
    # No QML window in this smoke; don't let Qt auto-quit on "no windows".
    app.setQuitOnLastWindowClosed(False)

    runner = SyncRunner()
    tray = TrayController(runner, window=None)
    inhibitor = SuspendInhibitor(runner)

    print(f"[smoke] tray available:      {tray._tray is not None}")
    print(f"[smoke] tray visible:        "
          f"{tray._tray.isVisible() if tray._tray else False}")
    print(f"[smoke] inhibitor available: {inhibitor.isAvailable()}")

    saw_inhibitor_held = {"v": False}

    def on_running_changed():
        running = runner.runningCount()
        held = inhibitor.isHeld()
        if held:
            saw_inhibitor_held["v"] = True
        print(f"[smoke] runningChanged: running={running} inhibitor_held={held}")

    runner.runningChanged.connect(on_running_changed)

    def on_state_changed(job_id, state):
        print(f"[smoke] jobStateChanged: id={job_id} state={state}")

    runner.jobStateChanged.connect(on_state_changed)

    runner.enqueue([
        {
            "argv": ["bash", "-c", "echo job1 start; sleep 3; echo job1 done"],
            "label": "Smoke job 1 (success)",
            "destDeviceId": 1,
        },
        {
            "argv": ["bash", "-c", "echo job2 start; sleep 4; echo job2 fail; exit 1"],
            "label": "Smoke job 2 (failure)",
            "destDeviceId": 2,
        },
    ])

    def check_done():
        if runner.runningCount() != 0:
            return
        snap = runner.jobs()
        if not snap:
            return
        if not all(j["state"] in ("done", "failed", "cancelled") for j in snap):
            return
        timer.stop()
        print("[smoke] ----- summary -----")
        for j in snap:
            print(f"[smoke]   {j['label']}: state={j['state']} exit={j['exitCode']}")
        print(f"[smoke] inhibitor held during run: {saw_inhibitor_held['v']}")
        print(f"[smoke] inhibitor held now:        {inhibitor.isHeld()}")
        print("[smoke] quitting in 5s (so you can see the notifications)")
        QTimer.singleShot(5000, app.quit)

    timer = QTimer()
    timer.setInterval(300)
    timer.timeout.connect(check_done)
    timer.start()

    app.aboutToQuit.connect(runner.shutdown)
    app.aboutToQuit.connect(tray.stop)
    app.aboutToQuit.connect(inhibitor.stop)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

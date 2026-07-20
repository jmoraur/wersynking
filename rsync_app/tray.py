"""System tray icon + desktop notifications.

The tray icon is always visible (per the user's choice in M6 planning).
Closing the main window quits the app like normal — the tray is a
status indicator + quick-access menu, not a hide-window target.

Notifications fire on every job's terminal transition:
- `done`     → short transient (5s)
- `failed`   → resident (0 = until-dismissed on KDE)
- `cancelled`→ silent (user-initiated, no notification needed)
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

from PySide6.QtCore import QObject, Slot
from PySide6.QtGui import QAction, QIcon
from PySide6.QtWidgets import QApplication, QMenu, QSystemTrayIcon


_BUNDLED_ICON = Path(__file__).resolve().parent / "icons" / "rsync-app.svg"


def _resolve_icon() -> QIcon:
    icon = QIcon.fromTheme("rsync-app")
    if not icon.isNull():
        return icon
    if _BUNDLED_ICON.exists():
        return QIcon(str(_BUNDLED_ICON))
    return QIcon()


class TrayController(QObject):
    def __init__(
        self,
        runner,
        window=None,
        parent: Optional[QObject] = None,
    ) -> None:
        super().__init__(parent)
        self._runner = runner
        self._window = window
        self._tray: Optional[QSystemTrayIcon] = None
        self._menu: Optional[QMenu] = None

        if not QSystemTrayIcon.isSystemTrayAvailable():
            return

        icon = _resolve_icon()
        self._tray = QSystemTrayIcon(icon, self)
        self._tray.setToolTip("We RSynk-ing — idle")

        menu = QMenu()
        act_show = QAction("Show window", menu)
        act_show.triggered.connect(self._show_window)
        act_cancel = QAction("Cancel all syncs", menu)
        act_cancel.triggered.connect(self._runner.cancelAll)
        act_quit = QAction("Quit", menu)
        qapp = QApplication.instance()
        if qapp is not None:
            act_quit.triggered.connect(qapp.quit)
        menu.addAction(act_show)
        menu.addAction(act_cancel)
        menu.addSeparator()
        menu.addAction(act_quit)
        self._tray.setContextMenu(menu)
        self._menu = menu

        self._tray.activated.connect(self._on_activated)
        self._runner.jobsChanged.connect(self._refresh_tooltip)
        self._runner.jobStateChanged.connect(self._on_state_changed)
        self._runner.runningChanged.connect(self._refresh_tooltip)

        self._tray.show()
        self._refresh_tooltip()

    @Slot()
    def stop(self) -> None:
        if self._tray is not None:
            self._tray.hide()

    # -- internals -----------------------------------------------------

    def _show_window(self) -> None:
        w = self._window
        if w is None:
            return
        if hasattr(w, "show"):
            w.show()
        if hasattr(w, "raise_"):
            w.raise_()
        if hasattr(w, "requestActivate"):
            w.requestActivate()

    def _on_activated(self, reason: QSystemTrayIcon.ActivationReason) -> None:
        # Left-click (Trigger) raises the window. Right-click opens the
        # context menu automatically.
        if reason == QSystemTrayIcon.ActivationReason.Trigger:
            self._show_window()

    def _refresh_tooltip(self) -> None:
        if self._tray is None:
            return
        running = queued = done = failed = 0
        for job in self._runner.jobs():
            state = job.get("state")
            if state == "running":
                running += 1
            elif state == "pending":
                queued += 1
            elif state == "done":
                done += 1
            elif state == "failed":
                failed += 1
        if not (running or queued or done or failed):
            self._tray.setToolTip("We RSynk-ing — idle")
            return
        parts = []
        if running:
            parts.append(f"{running} running")
        if queued:
            parts.append(f"{queued} queued")
        if done:
            parts.append(f"{done} done")
        if failed:
            parts.append(f"{failed} failed")
        self._tray.setToolTip("We RSynk-ing — " + " · ".join(parts))

    def _on_state_changed(self, job_id: int, state: str) -> None:
        if self._tray is None:
            return
        if state not in ("done", "failed"):
            return
        label = f"Job {job_id}"
        exit_code = -1
        for job in self._runner.jobs():
            if job.get("id") == job_id:
                label = job.get("label") or label
                exit_code = int(job.get("exitCode", -1))
                break
        if state == "done":
            self._tray.showMessage(
                "Sync done",
                label,
                QSystemTrayIcon.MessageIcon.Information,
                5000,
            )
        else:  # failed
            self._tray.showMessage(
                "Sync failed",
                f"{label} (exit {exit_code})",
                QSystemTrayIcon.MessageIcon.Warning,
                0,
            )

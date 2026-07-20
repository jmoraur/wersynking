import json
import subprocess

from PySide6.QtCore import QObject, QTimer, Signal, Slot

POLL_INTERVAL_MS = 2000


class MountWatcher(QObject):
    """Tracks filesystem mount state by UUID.

    Reads state by polling `lsblk --json` every POLL_INTERVAL_MS.
    Polling is used instead of UDisks2 D-Bus signals because PySide6
    6.10's QtDBus.connect() does not bind to Python @Slot-decorated
    methods — only to C++-registered metaobject slots.
    """

    changed = Signal()

    def __init__(self, parent: QObject | None = None):
        super().__init__(parent)
        self._state: dict[str, str] = {}
        self._timer = QTimer(self)
        self._timer.setInterval(POLL_INTERVAL_MS)
        self._timer.timeout.connect(self._refresh)
        self._refresh()
        self._timer.start()

    def state(self) -> dict[str, str]:
        return dict(self._state)

    def stop(self) -> None:
        """Stop polling. Wire to app.aboutToQuit."""
        self._timer.stop()

    @Slot()
    def refresh(self) -> None:
        self._refresh()

    def _refresh(self) -> None:
        new_state = self._query()
        if new_state != self._state:
            self._state = new_state
            self.changed.emit()

    @staticmethod
    def _query() -> dict[str, str]:
        result = subprocess.run(
            ["lsblk", "-lJn", "-o", "UUID,MOUNTPOINT"],
            capture_output=True, text=True, check=False,
        )
        if result.returncode != 0 or not result.stdout.strip():
            return {}
        data = json.loads(result.stdout)
        out: dict[str, str] = {}
        for dev in data.get("blockdevices", []):
            uuid = dev.get("uuid")
            mp = dev.get("mountpoint")
            if uuid and mp and not mp.startswith("["):
                out[uuid] = mp
        return out

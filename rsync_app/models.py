"""QAbstractListModel exposing the connections tree to QML.

Thin wrapper: the controller does the data shaping (DB + mounts +
probes join → row dicts), the model just turns that into a Qt model
with role names. `viewMode` switches between the dest-grouped and
source-grouped row sequences.
"""
from PySide6.QtCore import (
    Property, QAbstractListModel, QModelIndex, Qt, Signal, Slot,
)

from rsync_app.controllers import ConnectionsController
from rsync_app.db import Database
from rsync_app.mounts import MountWatcher
from rsync_app.probes import RemoteProbeWatcher


# Role schema. Order is irrelevant; numbers must be distinct
# Qt.UserRole offsets. Roles populated per row type — fields not
# relevant to a given row type return "" / -1 / False.
_ROLE_KEYS = (
    "rowType", "nodeId", "label", "depth",
    "aggregate", "liveness", "deviceKind", "mountpoint",
    "sourcePath", "destDisplay", "destSubpath",
    "canSync",
    "containerId", "deviceId", "sourceLabelId", "bindingId",
    "containerLabel",
)


class ConnectionsModel(QAbstractListModel):
    viewModeChanged = Signal()

    _ROLE_BASE = Qt.UserRole + 1

    def __init__(self, controller: ConnectionsController, db: Database,
                 mounts: MountWatcher, probes: RemoteProbeWatcher,
                 parent=None):
        super().__init__(parent)
        self._controller = controller
        self._db = db
        self._mounts = mounts
        self._probes = probes
        self._view_mode = "destination"
        self._items: list[dict] = []
        self._roles = {
            self._ROLE_BASE + i: key.encode()
            for i, key in enumerate(_ROLE_KEYS)
        }
        db.db_changed.connect(self.refresh)
        mounts.changed.connect(self.refresh)
        probes.changed.connect(self.refresh)
        self.refresh()

    # --- viewMode property ------------------------------------------------

    def _get_view_mode(self) -> str:
        return self._view_mode

    def _set_view_mode(self, mode: str) -> None:
        if mode == self._view_mode:
            return
        if mode not in ("destination", "source"):
            raise ValueError(f"viewMode must be destination|source, got {mode!r}")
        self._view_mode = mode
        self.viewModeChanged.emit()
        self.refresh()

    viewMode = Property(str, _get_view_mode, _set_view_mode,
                        notify=viewModeChanged)

    # --- QAbstractListModel API ------------------------------------------

    def roleNames(self):
        return dict(self._roles)

    def rowCount(self, parent=QModelIndex()):
        return 0 if parent.isValid() else len(self._items)

    def data(self, index, role):
        if not index.isValid() or not (0 <= index.row() < len(self._items)):
            return None
        key = self._roles.get(role)
        if key is None:
            return None
        item = self._items[index.row()]
        return item.get(key.decode(), "")

    # --- refresh ----------------------------------------------------------

    @Slot()
    def refresh(self) -> None:
        rows = (self._controller.byDestination()
                if self._view_mode == "destination"
                else self._controller.bySource())
        self.beginResetModel()
        self._items = rows
        self.endResetModel()

import sqlite3
from pathlib import Path

from PySide6.QtCore import QObject, QStandardPaths, Signal

from rsync_app.rsync import OPTIONS

_UNSET = object()

_BASELINE_OPT_COLS = tuple(o["key"] for o in OPTIONS if o["baseline"])

_BOOL_COLS = frozenset(o["key"] for o in OPTIONS)

# Complete defaults for a binding row minus the two FK columns.
# Option defaults come straight from the rsync catalog.
BINDING_DEFAULTS = {
    "dest_subpath": "",
    "path_mode": "contents",
    "chown_mode": "source",
    "chown_value": None,
    "chmod_value": None,
    **{o["key"]: int(o["default"]) for o in OPTIONS},
    "excludes": None,
    "rsh": None,
}

# Every writable bindings column, in schema order.
BINDING_COLS = ("source_label_id", "dest_device_id", *BINDING_DEFAULTS)

_OPT_COLS_SQL = ",\n    ".join(
    f"{o['key']} INTEGER NOT NULL DEFAULT {int(o['default'])} "
    f"CHECK ({o['key']} IN (0, 1))"
    for o in OPTIONS
)

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS source_labels (
    id    INTEGER PRIMARY KEY,
    label TEXT NOT NULL,
    path  TEXT NOT NULL UNIQUE
);

CREATE TABLE IF NOT EXISTS dest_containers (
    id    INTEGER PRIMARY KEY,
    label TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS dest_devices (
    id              INTEGER PRIMARY KEY,
    container_id    INTEGER NOT NULL
                    REFERENCES dest_containers(id) ON DELETE CASCADE,
    label           TEXT NOT NULL,
    kind            TEXT NOT NULL DEFAULT 'local'
                    CHECK (kind IN ('local', 'remote')),
    uuid            TEXT,
    network_target  TEXT,
    CHECK (
        (kind = 'local'  AND uuid IS NOT NULL AND network_target IS NULL) OR
        (kind = 'remote' AND network_target IS NOT NULL AND uuid IS NULL)
    ),
    UNIQUE (uuid)
);

CREATE TABLE IF NOT EXISTS bindings (
    id               INTEGER PRIMARY KEY,
    source_label_id  INTEGER NOT NULL
                     REFERENCES source_labels(id) ON DELETE CASCADE,
    dest_device_id   INTEGER NOT NULL
                     REFERENCES dest_devices(id) ON DELETE CASCADE,
    dest_subpath     TEXT NOT NULL DEFAULT '',
    path_mode        TEXT NOT NULL DEFAULT 'contents'
                     CHECK (path_mode IN ('contents', 'folder')),
    chown_mode       TEXT NOT NULL DEFAULT 'source'
                     CHECK (chown_mode IN ('source', 'dest')),
    chown_value      TEXT,
    chmod_value      TEXT,
    {_OPT_COLS_SQL},
    excludes         TEXT,
    rsh              TEXT,
    UNIQUE (source_label_id, dest_device_id, dest_subpath)
);
"""


def default_path() -> Path:
    base = Path(QStandardPaths.writableLocation(QStandardPaths.AppDataLocation))
    base.mkdir(parents=True, exist_ok=True)
    return base / "rsync.db"


def _coerce(col: str, value):
    if col in _BOOL_COLS and value is not None:
        return int(bool(value))
    return value


class Database(QObject):
    db_changed = Signal()

    def __init__(self, path: Path | None = None, parent=None):
        super().__init__(parent)
        self.path = path or default_path()
        self._conn = sqlite3.connect(str(self.path))
        self._conn.row_factory = sqlite3.Row
        self._conn.execute("PRAGMA foreign_keys = ON")
        self._conn.executescript(SCHEMA)
        self._migrate_baseline_opts()
        self._migrate_source_unique()
        self._conn.commit()

    def _migrate_baseline_opts(self) -> None:
        """Add the baseline-option columns to a pre-existing bindings table.

        `CREATE TABLE IF NOT EXISTS` won't touch an existing table, so a DB
        created before baseline options became editable lacks these columns.
        Add them DEFAULT 1, which makes existing bindings keep emitting the
        baseline flags exactly as before.
        """
        have = {row["name"] for row in
                self._conn.execute("PRAGMA table_info(bindings)")}
        for col in _BASELINE_OPT_COLS:
            if col not in have:
                self._conn.execute(
                    f"ALTER TABLE bindings ADD COLUMN {col} "
                    f"INTEGER NOT NULL DEFAULT 1 CHECK ({col} IN (0, 1))"
                )

    def _migrate_source_unique(self) -> None:
        """Move the UNIQUE constraint on source_labels from label to path.

        The source label became a non-unique *group* name (e.g. "Laptop");
        the folder shown next to it is derived from the path, so the path is
        what must be unique now ("one folder = one source"). A DB created
        under the old UNIQUE(label) schema is rebuilt in place, preserving
        ids and rows. Fresh DBs already match and are skipped.
        """
        unique_cols = set()
        for idx in self._conn.execute("PRAGMA index_list(source_labels)"):
            if idx["unique"]:
                info = self._conn.execute(
                    f"PRAGMA index_info('{idx['name']}')"
                ).fetchall()
                if len(info) == 1:
                    unique_cols.add(info[0]["name"])
        if unique_cols == {"path"}:
            return  # already the new shape

        # FK must be OFF to drop the referenced table without cascading into
        # bindings; the rename keeps the same table name so the FK stays valid.
        self._conn.commit()
        self._conn.execute("PRAGMA foreign_keys = OFF")
        self._conn.executescript(
            """
            CREATE TABLE source_labels_new (
                id    INTEGER PRIMARY KEY,
                label TEXT NOT NULL,
                path  TEXT NOT NULL UNIQUE
            );
            INSERT OR IGNORE INTO source_labels_new (id, label, path)
                SELECT id, label, path FROM source_labels;
            DROP TABLE source_labels;
            ALTER TABLE source_labels_new RENAME TO source_labels;
            """
        )
        self._conn.commit()
        self._conn.execute("PRAGMA foreign_keys = ON")

    # --- source_labels ------------------------------------------------------

    def add_source_label(self, *, label: str, path: str) -> int:
        cur = self._conn.execute(
            "INSERT INTO source_labels(label, path) VALUES (?, ?)",
            (label, path),
        )
        self._conn.commit()
        self.db_changed.emit()
        return cur.lastrowid

    def update_source_label(self, source_label_id: int, *,
                            label=_UNSET, path=_UNSET) -> None:
        changes = self._collect_changes(["label", "path"], locals())
        self._apply_update("source_labels", source_label_id, changes)

    def delete_source_label(self, source_label_id: int) -> None:
        self._conn.execute(
            "DELETE FROM source_labels WHERE id = ?", (source_label_id,)
        )
        self._conn.commit()
        self.db_changed.emit()

    def list_source_labels(self) -> list[dict]:
        return [
            dict(r) for r in self._conn.execute(
                "SELECT * FROM source_labels ORDER BY label"
            )
        ]

    # --- dest_containers ----------------------------------------------------

    def add_dest_container(self, *, label: str) -> int:
        cur = self._conn.execute(
            "INSERT INTO dest_containers(label) VALUES (?)", (label,)
        )
        self._conn.commit()
        self.db_changed.emit()
        return cur.lastrowid

    def update_dest_container(self, container_id: int, *, label=_UNSET) -> None:
        changes = self._collect_changes(["label"], locals())
        self._apply_update("dest_containers", container_id, changes)

    def delete_dest_container(self, container_id: int) -> None:
        self._conn.execute(
            "DELETE FROM dest_containers WHERE id = ?", (container_id,)
        )
        self._conn.commit()
        self.db_changed.emit()

    def list_dest_containers(self) -> list[dict]:
        return [
            dict(r) for r in self._conn.execute(
                "SELECT * FROM dest_containers ORDER BY label"
            )
        ]

    # --- dest_devices -------------------------------------------------------

    def add_dest_device(self, *, container_id: int, label: str, kind: str,
                        uuid: str | None = None,
                        network_target: str | None = None) -> int:
        cur = self._conn.execute(
            "INSERT INTO dest_devices("
            "container_id, label, kind, uuid, network_target"
            ") VALUES (?, ?, ?, ?, ?)",
            (container_id, label, kind, uuid, network_target),
        )
        self._conn.commit()
        self.db_changed.emit()
        return cur.lastrowid

    def update_dest_device(self, device_id: int, *,
                           container_id=_UNSET, label=_UNSET, kind=_UNSET,
                           uuid=_UNSET, network_target=_UNSET) -> None:
        changes = self._collect_changes(
            ["container_id", "label", "kind", "uuid", "network_target"],
            locals(),
        )
        self._apply_update("dest_devices", device_id, changes)

    def delete_dest_device(self, device_id: int) -> None:
        self._conn.execute(
            "DELETE FROM dest_devices WHERE id = ?", (device_id,)
        )
        self._conn.commit()
        self.db_changed.emit()

    def list_dest_devices(self, container_id: int | None = None) -> list[dict]:
        if container_id is None:
            rows = self._conn.execute(
                "SELECT * FROM dest_devices ORDER BY label"
            )
        else:
            rows = self._conn.execute(
                "SELECT * FROM dest_devices WHERE container_id = ? ORDER BY label",
                (container_id,),
            )
        return [dict(r) for r in rows]

    # --- bindings -----------------------------------------------------------

    def add_binding(self, values: dict) -> int:
        """Insert a binding. `values` maps column → value; unknown keys are
        ignored, missing option/config columns take the catalog defaults.
        Must include source_label_id and dest_device_id."""
        row = dict(BINDING_DEFAULTS)
        row.update({k: _coerce(k, v) for k, v in values.items()
                    if k in BINDING_COLS})
        if "source_label_id" not in row or "dest_device_id" not in row:
            raise ValueError(
                "binding needs source_label_id and dest_device_id"
            )
        cols = ", ".join(row)
        marks = ", ".join("?" * len(row))
        cur = self._conn.execute(
            f"INSERT INTO bindings({cols}) VALUES ({marks})",
            list(row.values()),
        )
        self._conn.commit()
        self.db_changed.emit()
        return cur.lastrowid

    def update_binding(self, binding_id: int, values: dict) -> None:
        """Update the given columns of a binding; unknown keys are ignored."""
        changes = {k: _coerce(k, v) for k, v in values.items()
                   if k in BINDING_COLS}
        self._apply_update("bindings", binding_id, changes)

    def delete_binding(self, binding_id: int) -> None:
        self._conn.execute("DELETE FROM bindings WHERE id = ?", (binding_id,))
        self._conn.commit()
        self.db_changed.emit()

    def list_bindings(self) -> list[dict]:
        return [dict(r) for r in self._conn.execute("SELECT * FROM bindings")]

    # --- helpers ------------------------------------------------------------

    @staticmethod
    def _collect_changes(cols: list[str], scope: dict) -> dict:
        changes = {}
        for col in cols:
            v = scope[col]
            if v is _UNSET:
                continue
            changes[col] = _coerce(col, v)
        return changes

    def _apply_update(self, table: str, row_id: int, changes: dict) -> None:
        if not changes:
            return
        sets = ", ".join(f"{c} = ?" for c in changes)
        self._conn.execute(
            f"UPDATE {table} SET {sets} WHERE id = ?",
            [*changes.values(), row_id],
        )
        self._conn.commit()
        self.db_changed.emit()

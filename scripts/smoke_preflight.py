"""Smoke driver for M6 Step 3 — pre-flight validation.

Seeds 4 bindings exercising clean / errors-only / warnings-only / mixed
states, then opens SyncConfirmDialog on each (single-mode) plus a
device-scope view (multi-mode), screenshotting each.

The MountWatcher is paused and its state forced to a known mapping so
the writable-dest check has a real temp directory to inspect. Probes
state is left empty (no remote bindings used).

Run from project root:
    PYTHONPATH=. python scripts/smoke_preflight.py
"""
import shutil
import sys
import tempfile
from pathlib import Path

from PySide6.QtCore import QObject, QTimer
from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication

from rsync_app.controllers import ConnectionsController
from rsync_app.db import Database
from rsync_app.models import ConnectionsModel
from rsync_app.mounts import MountWatcher
from rsync_app.probes import RemoteProbeWatcher
from rsync_app.runner import SyncRunner
from rsync_app.theme import ThemeBridge

OUT = Path("/tmp/rsync_app_smoke")
GOOD_DEST = Path("/tmp/preflight_smoke_dest_good")
GOOD_UUID = "ffffffff-ffff-ffff-ffff-pref0000good"
BAD_UUID  = "ffffffff-ffff-ffff-ffff-pref0000bad0"
MISSING_SRC = "/tmp/preflight_smoke_src_missing_xyz"


def main() -> int:
    OUT.mkdir(parents=True, exist_ok=True)
    GOOD_DEST.mkdir(parents=True, exist_ok=True)

    app = QApplication(sys.argv)
    app.setApplicationName("RsyncApp")
    QQuickStyle.setStyle("Fusion")

    db = Database()

    # Source labels. One exists, one doesn't.
    sid_ok = db.add_source_label(label="Photos-PREF",
                                 path=str(Path.home() / "Pictures"))
    sid_bad = db.add_source_label(label="Missing-PREF",
                                  path=MISSING_SRC)

    # Single container; two local devices — one "mounted" (via the
    # patched MountWatcher state), one not.
    cid = db.add_dest_container(label="PreflightSmoke-PREF")
    did_good = db.add_dest_device(container_id=cid, label="Backup-PREF",
                                  kind="local", uuid=GOOD_UUID)
    did_bad = db.add_dest_device(container_id=cid, label="Unmounted-PREF",
                                 kind="local", uuid=BAD_UUID)

    # Bindings — dest_subpath chosen to match the source basename so
    # W_BASENAME_MISMATCH doesn't fire on cases meant to demonstrate
    # other states cleanly. Source basename for sid_bad is the leaf of
    # MISSING_SRC, so dest_subpath matches that leaf.
    src_bad_leaf = Path(MISSING_SRC).name
    bid_clean = db.add_binding({
        "source_label_id": sid_ok, "dest_device_id": did_good,
        "dest_subpath": "Pictures",
    })
    bid_errors = db.add_binding({
        "source_label_id": sid_bad, "dest_device_id": did_bad,
        "dest_subpath": src_bad_leaf,
    })
    # path_mode='folder' skips the basename-mismatch check, so this
    # binding emits exactly two warnings (--delete + path-mode-folder).
    bid_warnings = db.add_binding({
        "source_label_id": sid_ok, "dest_device_id": did_good,
        "dest_subpath": "archive",
        "opt_delete": True, "path_mode": "folder",
    })
    bid_mixed = db.add_binding({
        "source_label_id": sid_bad, "dest_device_id": did_good,
        "dest_subpath": src_bad_leaf,
        "opt_delete": True,
    })

    watcher = MountWatcher()
    # Freeze a known mount state so the writability check sees our
    # tmpdir. Stop the polling timer first so the next _refresh()
    # doesn't clobber it back.
    watcher.stop()
    watcher._state = {GOOD_UUID: str(GOOD_DEST)}  # noqa: SLF001
    probes = RemoteProbeWatcher(db)
    runner = SyncRunner()
    controller = ConnectionsController(db, watcher, probes, runner)
    model = ConnectionsModel(controller, db, watcher, probes)

    engine = QQmlApplicationEngine()
    ctx = engine.rootContext()
    ctx.setContextProperty("connections", controller)
    ctx.setContextProperty("connectionsModel", model)
    ctx.setContextProperty("remoteProbes", probes)
    ctx.setContextProperty("syncRunner", runner)
    theme = ThemeBridge()
    ctx.setContextProperty("themeBridge", theme)
    engine.load(Path("rsync_app/qml/Main.qml").resolve())
    if not engine.rootObjects():
        print("ERROR: engine failed", file=sys.stderr)
        return 1

    win = engine.rootObjects()[0]
    rc = {"code": 0}

    def grab(name: str) -> None:
        path = OUT / f"{name}.png"
        ok = win.grabWindow().save(str(path))
        if not ok:
            rc["code"] = 2
            print(f"FAIL save {path}", file=sys.stderr)
        else:
            print(f"saved {path}")

    def find(name: str) -> QObject | None:
        return win.findChild(QObject, name)

    def open_dialog(name: str, props: dict | None = None) -> QObject | None:
        dlg = find(name)
        if dlg is None:
            print(f"ERROR: dialog {name!r} not found", file=sys.stderr)
            rc["code"] = 3
            return None
        if props:
            for k, v in props.items():
                dlg.setProperty(k, v)
        ok = dlg.metaObject().invokeMethod(dlg, "open")
        if not ok:
            print(f"ERROR: open() invoke failed on {name}", file=sys.stderr)
            rc["code"] = 4
        return dlg

    def close_dialog(dlg: QObject) -> None:
        if dlg is None:
            return
        dlg.metaObject().invokeMethod(dlg, "close")

    state = {"dlg": None}

    def open_single(name: str, bid: int):
        def _open():
            state["dlg"] = open_dialog("syncConfirmDialog",
                                       {"scopeKind": "connection",
                                        "scopeId": bid})
        return _open

    def open_multi(name: str):
        def _open():
            state["dlg"] = open_dialog("syncConfirmDialog",
                                       {"scopeKind": "device",
                                        "scopeId": did_good})
        return _open

    def close_current():
        close_dialog(state["dlg"])
        state["dlg"] = None

    steps: list = [
        ("preflight_01_single_clean",        open_single("clean",    bid_clean)),
        ("__close",                          close_current),
        ("preflight_02_single_errors_only",  open_single("errors",   bid_errors)),
        ("__close",                          close_current),
        ("preflight_03_single_warnings",     open_single("warnings", bid_warnings)),
        ("__close",                          close_current),
        ("preflight_04_single_mixed",        open_single("mixed",    bid_mixed)),
        ("__close",                          close_current),
        # Device-scope view — bid_clean + bid_warnings + bid_mixed all
        # share did_good (bid_errors is on did_bad). The card-per-binding
        # layout exercises errors + warnings + clean in one screenshot.
        ("preflight_05_multi_mixed",         open_multi("device")),
        ("__close",                          close_current),
    ]

    DELAY_MS = 500
    idx = {"i": 0}

    def cleanup_and_exit():
        for bid in (bid_clean, bid_errors, bid_warnings, bid_mixed):
            try:
                db.delete_binding(bid)
            except Exception:
                pass
        for d in db.list_dest_devices():
            if d["label"].endswith("-PREF"):
                db.delete_dest_device(d["id"])
        try:
            db.delete_dest_container(cid)
        except Exception:
            pass
        for sid in (sid_ok, sid_bad):
            try:
                db.delete_source_label(sid)
            except Exception:
                pass
        shutil.rmtree(GOOD_DEST, ignore_errors=True)
        app.exit(rc["code"])

    def tick():
        if idx["i"] >= len(steps):
            cleanup_and_exit()
            return
        label, action = steps[idx["i"]]
        idx["i"] += 1
        action()
        def after():
            if not label.startswith("__"):
                grab(label)
            tick()
        QTimer.singleShot(DELAY_MS, after)

    QTimer.singleShot(800, tick)
    app.aboutToQuit.connect(probes.stop)
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())

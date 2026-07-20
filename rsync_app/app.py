import os
import sys
from pathlib import Path

# Qt's on-disk QML cache is keyed by source path + mtime, and rpmbuild
# normalizes installed-file mtimes to the spec's newest changelog date —
# so two same-day releases collide and the cache serves the PREVIOUS
# version's UI on top of the new backend (bit us on v0.1.0→v0.2.0 and
# again on v0.2.0→v0.3.0; see tasks/lessons.md "Packaging / Qt runtime").
# The app is a dozen small QML files; recompiling at launch costs a few
# tens of ms. Must be set before any QtQml import creates an engine.
os.environ.setdefault("QML_DISABLE_DISK_CACHE", "1")

from PySide6.QtQml import QQmlApplicationEngine
from PySide6.QtQuickControls2 import QQuickStyle
from PySide6.QtWidgets import QApplication

from rsync_app.controllers import ConnectionsController
from rsync_app.db import Database
from rsync_app.inhibitor import SuspendInhibitor
from rsync_app.models import ConnectionsModel
from rsync_app.mounts import MountWatcher
from rsync_app.probes import RemoteProbeWatcher
from rsync_app.runner import SyncRunner
from rsync_app.theme import ThemeBridge
from rsync_app.tray import TrayController


def run() -> int:
    # QApplication (not QGuiApplication) because Qt.labs.platform.FolderDialog
    # uses Qt Widgets under the hood for the native KDE folder picker.
    app = QApplication(sys.argv)
    app.setOrganizationName("RsyncApp")
    app.setOrganizationDomain("rsync-app.local")
    app.setApplicationName("RsyncApp")
    # Wayland app_id → desktop-file association (icon + window grouping).
    # Distinct from the QSettings names above, which stay "RsyncApp" so the
    # existing config/DB paths keep working.
    app.setDesktopFileName("wersynking")
    QQuickStyle.setStyle("Fusion")
    theme = ThemeBridge()

    db = Database()
    watcher = MountWatcher()
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
    ctx.setContextProperty("themeBridge", theme)
    engine.load(Path(__file__).parent / "qml" / "Main.qml")
    if not engine.rootObjects():
        return 1
    window = engine.rootObjects()[0]

    tray = TrayController(runner, window)
    inhibitor = SuspendInhibitor(runner)

    app.aboutToQuit.connect(watcher.stop)
    app.aboutToQuit.connect(probes.stop)
    app.aboutToQuit.connect(runner.shutdown)
    app.aboutToQuit.connect(tray.stop)
    app.aboutToQuit.connect(inhibitor.stop)
    return app.exec()

from PySide6.QtCore import Property, QObject, QSettings, Qt, Signal, Slot
from PySide6.QtGui import QGuiApplication

_SCHEMES = {
    "system": Qt.ColorScheme.Unknown,  # Unknown clears the override
    "light": Qt.ColorScheme.Light,
    "dark": Qt.ColorScheme.Dark,
}


class ThemeBridge(QObject):
    """Explicit light/dark/system theme mode.

    Applies the persisted mode at startup and on change via
    QStyleHints.setColorScheme; the platform theme then swaps the
    application palette, which SystemPalette (Theme.qml) and the Fusion
    controls both follow.
    """

    modeChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        mode = str(QSettings().value("ui/themeMode", "system"))
        self._mode = mode if mode in _SCHEMES else "system"
        self._apply()

    def _apply(self) -> None:
        QGuiApplication.styleHints().setColorScheme(_SCHEMES[self._mode])

    def _get_mode(self) -> str:
        return self._mode

    @Slot(str)
    def setMode(self, mode: str) -> None:
        if mode not in _SCHEMES or mode == self._mode:
            return
        self._mode = mode
        self._apply()
        QSettings().setValue("ui/themeMode", mode)
        self.modeChanged.emit()

    mode = Property(str, _get_mode, notify=modeChanged)

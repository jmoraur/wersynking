from PySide6.QtCore import Property, QObject, QSettings, Qt, Signal, Slot
from PySide6.QtGui import QColor, QGuiApplication, QPalette
from PySide6.QtWidgets import QApplication

_SCHEMES = {
    "system": Qt.ColorScheme.Unknown,  # Unknown clears the override
    "light": Qt.ColorScheme.Light,
    "dark": Qt.ColorScheme.Dark,
}

# Qt's generic light/dark palettes, captured role-by-role (see tasks/lessons.md
# "Theme switching"): (role, active+inactive color, disabled color). Hardcoded
# because we can't rely on QStyleHints.setColorScheme to produce them — the
# KDE platform theme (plasma-integration 6.7 + Qt 6.11) ignores the request,
# so ThemeBridge sets the application palette itself.
_LIGHT = [
    ("WindowText", "#000000", "#bebebe"),
    ("Button", "#efefef", "#efefef"),
    ("Light", "#ffffff", "#ffffff"),
    ("Midlight", "#cacaca", "#cacaca"),
    ("Dark", "#9f9f9f", "#bebebe"),
    ("Mid", "#b8b8b8", "#b8b8b8"),
    ("Text", "#000000", "#bebebe"),
    ("BrightText", "#ffffff", "#ffffff"),
    ("ButtonText", "#000000", "#bebebe"),
    ("Base", "#ffffff", "#efefef"),
    ("Window", "#efefef", "#efefef"),
    ("Shadow", "#767676", "#b1b1b1"),
    ("Highlight", "#308cc6", "#919191"),
    ("HighlightedText", "#ffffff", "#ffffff"),
    ("Link", "#0000ff", "#0000ff"),
    ("LinkVisited", "#ff00ff", "#ff00ff"),
    ("AlternateBase", "#f7f7f7", "#f7f7f7"),
    ("ToolTipBase", "#ffffdc", "#ffffdc"),
    ("ToolTipText", "#000000", "#000000"),
    ("PlaceholderText", "#000000", "#000000"),
    ("Accent", "#308cc6", "#919191"),
]
_DARK = [
    ("WindowText", "#fcfcfc", "#525860"),
    ("Button", "#292c30", "#292c30"),
    ("Light", "#151618", "#151618"),
    ("Midlight", "#1f2124", "#1f2124"),
    ("Dark", "#525860", "#525860"),
    ("Mid", "#373b40", "#373b40"),
    ("Text", "#fcfcfc", "#525860"),
    ("BrightText", "#ffffff", "#ffffff"),
    ("ButtonText", "#fcfcfc", "#525860"),
    ("Base", "#141618", "#292c30"),
    ("Window", "#202326", "#292c30"),
    ("Shadow", "#767676", "#b1b1b1"),
    ("Highlight", "#3daee9", "#373b40"),
    ("HighlightedText", "#fcfcfc", "#1f2124"),
    ("Link", "#1d99f3", "#1d99f3"),
    ("LinkVisited", "#9b59b6", "#9b59b6"),
    ("AlternateBase", "#1d1f22", "#1d1f22"),
    ("ToolTipBase", "#292c30", "#292c30"),
    ("ToolTipText", "#fcfcfc", "#fcfcfc"),
    ("PlaceholderText", "#000000", "#000000"),
    ("Accent", "#308cc6", "#919191"),
]


def _build(spec: list[tuple[str, str, str]]) -> QPalette:
    pal = QPalette()
    for role_name, normal, disabled in spec:
        role = getattr(QPalette.ColorRole, role_name)
        color = QColor(normal)
        pal.setColor(QPalette.ColorGroup.Active, role, color)
        pal.setColor(QPalette.ColorGroup.Inactive, role, color)
        pal.setColor(QPalette.ColorGroup.Disabled, role, QColor(disabled))
    return pal


class ThemeBridge(QObject):
    """Explicit light/dark/system theme mode.

    Sets the application palette directly (light/dark hardcoded above,
    system = the platform palette captured at startup); SystemPalette
    (Theme.qml) and the Fusion controls follow the application palette.
    QStyleHints.setColorScheme is still requested for platforms that
    honor it, but is NOT relied upon: with system Qt + plasma-integration
    the request is silently ignored (verified 2026-07-21).

    Must be constructed before the QML engine loads, so the first frame
    already has the final palette.
    """

    modeChanged = Signal()

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        # Pristine platform palette (e.g. Breeze), before any override.
        self._system_palette = QPalette(QGuiApplication.palette())
        mode = str(QSettings().value("ui/themeMode", "system"))
        self._mode = mode if mode in _SCHEMES else "system"
        self._apply()

    def _apply(self) -> None:
        QGuiApplication.styleHints().setColorScheme(_SCHEMES[self._mode])
        if self._mode == "light":
            QApplication.setPalette(_build(_LIGHT))
        elif self._mode == "dark":
            QApplication.setPalette(_build(_DARK))
        else:
            QApplication.setPalette(self._system_palette)

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

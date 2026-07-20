pragma Singleton
import QtQuick

// Design tokens for the whole app. Surfaces track the system palette so
// KDE light/dark themes both work; status hues are fixed per lightness.
QtObject {
    id: theme

    readonly property SystemPalette pal: SystemPalette {
        colorGroup: SystemPalette.Active
    }

    readonly property bool dark: pal.window.hslLightness < 0.5

    // Surfaces & text (palette-driven)
    readonly property color windowBg: pal.window
    readonly property color surface: pal.base
    readonly property color surfaceAlt: pal.alternateBase
    readonly property color textColor: pal.text
    readonly property color accent: pal.highlight
    readonly property color onAccent: pal.highlightedText

    // Brand red — the "RSynk" part of the wordmark.
    readonly property color brand: dark ? "#f85149" : "#cf222e"

    // Status hues — chosen to read on both light and dark surfaces.
    readonly property color ok: dark ? "#3fb950" : "#1a7f37"
    readonly property color warn: dark ? "#d29922" : "#9a6700"
    readonly property color error: dark ? "#f85149" : "#cf222e"
    readonly property color running: dark ? "#58a6ff" : "#0969da"
    readonly property color idle: dark ? "#8b949e" : "#6e7781"

    // Hairlines / hover washes
    readonly property color border: dark ? Qt.rgba(1, 1, 1, 0.13)
                                         : Qt.rgba(0, 0, 0, 0.16)
    readonly property color hoverBg: tint(textColor, dark ? 0.09 : 0.06)
    readonly property color pressBg: tint(textColor, dark ? 0.16 : 0.12)

    function tint(c, alpha) { return Qt.rgba(c.r, c.g, c.b, alpha) }

    // Type scale (body text stays at the system default size)
    readonly property int fsSmall: 11
    readonly property int fsMono: 12
    readonly property int fsHeading: 16
    readonly property string mono: "monospace"

    // Spacing / radii
    readonly property int s1: 4
    readonly property int s2: 8
    readonly property int s3: 12
    readonly property int s4: 16
    readonly property int s5: 24
    readonly property int radius: 5

    // Tree row metrics
    readonly property int rowHeader: 42
    readonly property int rowDevice: 38
    readonly property int rowConnection: 34
}

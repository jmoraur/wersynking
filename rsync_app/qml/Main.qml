import QtCore
import QtQuick
import QtQuick.Controls

import "./pages"
import "./components"

ApplicationWindow {
    id: window
    width: 1100
    height: 720
    visible: true
    title: "WeRSynking"

    // Qt Quick Controls resolve their colors from the platform theme, which
    // (on KDE) ignores the application palette ThemeBridge sets — so the
    // selected mode must cascade from the root window explicitly. SystemPalette
    // does track the application palette, so every control follows it via
    // these bindings, live on mode changes.
    palette.window: Theme.pal.window
    palette.windowText: Theme.pal.windowText
    palette.base: Theme.pal.base
    palette.alternateBase: Theme.pal.alternateBase
    palette.text: Theme.pal.text
    palette.button: Theme.pal.button
    palette.buttonText: Theme.pal.buttonText
    palette.highlight: Theme.pal.highlight
    palette.highlightedText: Theme.pal.highlightedText
    palette.light: Theme.pal.light
    palette.midlight: Theme.pal.midlight
    palette.mid: Theme.pal.mid
    palette.dark: Theme.pal.dark
    palette.shadow: Theme.pal.shadow
    palette.placeholderText: Theme.pal.placeholderText
    palette.disabled.windowText: Theme.palDisabled.windowText
    palette.disabled.text: Theme.palDisabled.text
    palette.disabled.buttonText: Theme.palDisabled.buttonText
    palette.disabled.base: Theme.palDisabled.base
    palette.disabled.highlight: Theme.palDisabled.highlight
    palette.disabled.highlightedText: Theme.palDisabled.highlightedText

    Settings {
        category: "window"
        property alias x: window.x
        property alias y: window.y
        property alias width: window.width
        property alias height: window.height
        property alias visibility: window.visibility
    }

    Component.onCompleted: _ensureOnScreen()

    function _ensureOnScreen() {
        const screens = Qt.application.screens
        for (let i = 0; i < screens.length; i++) {
            const s = screens[i]
            if (window.x >= s.virtualX && window.x < s.virtualX + s.width
                && window.y >= s.virtualY && window.y < s.virtualY + s.height) {
                return
            }
        }
        window.x = Screen.virtualX + (Screen.width - window.width) / 2
        window.y = Screen.virtualY + (Screen.height - window.height) / 2
    }

    ConnectionsPage {
        anchors.fill: parent
    }
}

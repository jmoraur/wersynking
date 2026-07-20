import QtQuick
import QtQuick.Controls

// ComboBox whose dropdown never grows past `maxPopupHeight`. The default
// ComboBox caps its popup to the *window* height, so a long list (many
// mounted drives, many containers) opening from a field low in a tall or
// maximized window overflows off the bottom of the screen — the lower
// items are rendered outside the window and can't be scrolled into view.
// Capping the popup to a modest height keeps it on-screen and lets the
// inner ListView scroll instead. Drop-in replacement for ComboBox.
ComboBox {
    id: control
    property int maxPopupHeight: 280
    Component.onCompleted: popup.height = Qt.binding(function() {
        return Math.min(popup.contentItem.implicitHeight + 2, control.maxPopupHeight)
    })
}

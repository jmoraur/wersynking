import QtQuick
import QtQuick.Controls

// Compact flat icon button for row / inline actions. Icons come from the
// freedesktop theme (Breeze on this machine) via icon.name; `tip` shows
// as a tooltip since there is no text.
ToolButton {
    id: btn

    property string tip: ""
    // danger → hover tints the glyph red (delete); accent → glyph uses
    // the highlight color while enabled (primary run actions).
    property bool danger: false
    property bool accent: false

    implicitWidth: 28
    implicitHeight: 28
    icon.width: 16
    icon.height: 16
    icon.color: !enabled ? Theme.tint(Theme.textColor, 0.35)
              : danger && hovered ? Theme.error
              : accent ? Theme.accent
              : Theme.textColor
    display: AbstractButton.IconOnly

    ToolTip.visible: hovered && tip !== ""
    ToolTip.delay: 500
    ToolTip.text: tip

    background: Rectangle {
        radius: Theme.radius
        color: btn.down ? Theme.pressBg
             : btn.hovered && btn.enabled ? Theme.hoverBg
             : "transparent"
    }
}

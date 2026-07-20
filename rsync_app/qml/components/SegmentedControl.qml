import QtQuick
import QtQuick.Controls

// Exclusive pill selector. `model` is a list of {value, label}; `value`
// is the selected entry. Stateless by design: clicking only emits
// activated(value) and the caller owns the state — this dodges the
// checkable/checked binding-loss trap documented in lessons.md.
Rectangle {
    id: control

    property var model: []
    property string value: ""
    signal activated(string newValue)

    implicitWidth: row.implicitWidth + 8
    implicitHeight: 30
    radius: Theme.radius + 2
    color: Theme.tint(Theme.textColor, Theme.dark ? 0.08 : 0.05)

    Row {
        id: row
        anchors.centerIn: parent
        spacing: 2

        Repeater {
            model: control.model

            delegate: Rectangle {
                id: seg
                required property var modelData
                readonly property bool selected:
                    modelData.value === control.value

                width: segLabel.implicitWidth + 22
                height: 24
                radius: Theme.radius
                color: selected ? Theme.accent
                     : segHover.hovered ? Theme.hoverBg
                     : "transparent"

                Label {
                    id: segLabel
                    anchors.centerIn: parent
                    text: seg.modelData.label
                    color: seg.selected ? Theme.onAccent : Theme.textColor
                    opacity: seg.selected ? 1.0 : 0.85
                }

                HoverHandler { id: segHover }
                TapHandler {
                    onTapped: control.activated(seg.modelData.value)
                }
            }
        }
    }
}

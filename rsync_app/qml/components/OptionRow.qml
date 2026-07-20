import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// One rsync toggle on a single compact line: checkbox, long flag name
// (monospace), dim description. The whole line is clickable; the full
// description shows as a tooltip when elided.
//
// The parent owns the value: the row emits toggled(value) and renders
// `checked` from outside. The Binding element (not a plain declarative
// binding) keeps the CheckBox tracking external changes even after the
// user has clicked it — a user click writes to CheckBox.checked, which
// would sever a plain binding and leave the box stale on dialog reload.
RowLayout {
    id: row

    property string flag: ""
    property string description: ""
    property bool checked: false
    signal toggled(bool value)

    spacing: Theme.s2

    CheckBox {
        id: cb
        padding: 2
        onToggled: row.toggled(cb.checked)
    }

    Binding {
        target: cb
        property: "checked"
        value: row.checked
    }

    Label {
        text: row.flag
        font.family: Theme.mono
        font.pixelSize: Theme.fsMono
        TapHandler { onTapped: row.toggled(!row.checked) }
    }

    Label {
        id: descLabel
        text: row.description
        opacity: 0.55
        font.pixelSize: Theme.fsSmall
        elide: Text.ElideRight
        Layout.fillWidth: true

        ToolTip.visible: descHover.hovered && truncated
        ToolTip.delay: 500
        ToolTip.text: row.description

        HoverHandler { id: descHover }
        TapHandler { onTapped: row.toggled(!row.checked) }
    }
}

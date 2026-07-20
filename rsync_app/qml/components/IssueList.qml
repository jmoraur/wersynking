import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Pre-flight issue list. Errors are red and block the run; warnings are
// amber and each carries an "I understand" checkbox when `ackable`.
// `acks` maps issue index → bool for THIS list; the caller composes
// dialog-wide keys itself.
ColumnLayout {
    id: list

    property var issues: []
    property bool ackable: true
    property var acks: ({})
    signal ackToggled(int index, bool checked)

    spacing: Theme.s1

    Repeater {
        model: list.issues

        delegate: RowLayout {
            id: issueRow
            required property var modelData
            required property int index
            readonly property bool isError: modelData.severity === "error"

            Layout.fillWidth: true
            spacing: Theme.s2

            Label {
                text: issueRow.isError ? "✕" : "!"
                color: issueRow.isError ? Theme.error : Theme.warn
                font.bold: true
                Layout.alignment: Qt.AlignTop
            }

            Label {
                text: issueRow.modelData.message
                color: issueRow.isError ? Theme.error : Theme.warn
                wrapMode: Text.Wrap
                font.pixelSize: Theme.fsSmall
                Layout.fillWidth: true
            }

            CheckBox {
                id: ackBox
                visible: !issueRow.isError && list.ackable
                text: "I understand"
                font.pixelSize: Theme.fsSmall
                onToggled: list.ackToggled(issueRow.index, ackBox.checked)
            }

            Binding {
                target: ackBox
                property: "checked"
                value: !!list.acks[issueRow.index]
            }
        }
    }
}

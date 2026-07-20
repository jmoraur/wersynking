import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

// Dest-container dialog. Single label field — containers are pure
// grouping, no other metadata. Reachable from the container row's
// edit button and from inline-create in DeviceForm / ConnectionForm.
Dialog {
    id: dlg
    modal: true
    title: dlg.containerId === -1 ? "New destination container"
                                  : "Edit destination container"
    standardButtons: Dialog.Save | Dialog.Cancel
    width: 460

    property int containerId: -1
    property string initialLabel: ""

    signal acceptedWithId(int newId)

    onAboutToShow: {
        labelField.text = dlg.initialLabel
        labelField.forceActiveFocus()
    }

    onAccepted: {
        const label = labelField.text.trim()
        if (!label) return
        let newId = dlg.containerId
        if (dlg.containerId === -1) {
            newId = connections.addDestContainer(label)
        } else {
            connections.updateDestContainer(dlg.containerId, label)
        }
        dlg.acceptedWithId(newId)
    }

    contentItem: ColumnLayout {
        spacing: Theme.s2

        SectionLabel { text: "CONTAINER LABEL" }
        TextField {
            id: labelField
            Layout.fillWidth: true
            placeholderText: "e.g. HDD case 1, Unraid server"
        }

        Label {
            Layout.fillWidth: true
            wrapMode: Text.Wrap
            opacity: 0.55
            font.pixelSize: Theme.fsSmall
            text: "A container groups physical destination devices " +
                  "(drives, servers) that belong together. No path of its own."
        }
    }
}

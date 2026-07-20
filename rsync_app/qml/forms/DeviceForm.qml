import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

// Destination-device dialog. Identity only — no rsync options here
// (those live on the binding). Kind picks the second half of the form:
// local → UUID dropdown; remote → network_target + reachability test.
//
// Modes: deviceId === -1 → add, else → edit.
// Kind is frozen in edit mode — a different UUID/target is effectively
// a different drive; delete-and-recreate instead.
Dialog {
    id: dlg
    modal: true
    title: dlg.deviceId === -1 ? "New destination device"
                               : "Edit destination device"
    standardButtons: Dialog.Save | Dialog.Cancel
    width: 580

    // Inputs.
    property int deviceId: -1
    property int initialContainerId: -1   // preselect (e.g. from row context)
    property string initialKind: "local"
    property string initialLabel: ""
    property string initialUuid: ""
    property string initialNetworkTarget: ""

    signal acceptedWithId(int newId)

    // Snapshot of container list refreshed every open.
    property var _containers: []
    property string _kind: "local"
    property string _selectedUuid: ""
    property string _probeResult: ""

    function _refreshContainers(preselectId) {
        _containers = connections.pickableContainers()
        containerCombo.currentIndex =
            _containers.findIndex(c => c.id === preselectId)
    }

    function _refreshUuids(preselectUuid) {
        const list = connections.unassignedUuids()
        // In edit mode, include the device's current UUID as a fixed
        // entry so it remains visible/selected even though it's "taken".
        if (dlg.deviceId !== -1 && preselectUuid
                && !list.some(x => x.uuid === preselectUuid)) {
            list.unshift({ uuid: preselectUuid, mountpoint: "(current)" })
        }
        uuidCombo.model = list
        const idx = list.findIndex(x => x.uuid === preselectUuid)
        uuidCombo.currentIndex = idx
        _selectedUuid = idx === -1 ? "" : preselectUuid
    }

    onAboutToShow: {
        _kind = dlg.initialKind || "local"
        labelField.text = dlg.initialLabel
        networkTargetField.text = dlg.initialNetworkTarget
        _probeResult = ""
        _refreshContainers(dlg.initialContainerId)
        _refreshUuids(dlg.initialUuid)
        labelField.forceActiveFocus()
    }

    onAccepted: {
        const containerId = containerCombo.currentValue
        const label = labelField.text.trim()
        if (containerId === undefined || containerId === null || !label)
            return
        const draft = {
            container_id: containerId,
            label: label,
            kind: _kind,
            uuid: _kind === "local" ? _selectedUuid : "",
            network_target: _kind === "remote"
                            ? networkTargetField.text.trim() : "",
        }
        if (_kind === "local" && !draft.uuid) return
        if (_kind === "remote" && !draft.network_target) return
        let newId = dlg.deviceId
        if (dlg.deviceId === -1) {
            newId = connections.addDestDevice(draft)
        } else {
            connections.updateDestDevice(dlg.deviceId, draft)
        }
        dlg.acceptedWithId(newId)
    }

    contentItem: ColumnLayout {
        spacing: Theme.s2

        SectionLabel { text: "CONTAINER" }
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.s1

            ScrollComboBox {
                id: containerCombo
                Layout.fillWidth: true
                model: dlg._containers
                textRole: "label"
                valueRole: "id"
                displayText: currentIndex === -1
                             ? "— select a container —"
                             : currentText
            }
            RowActionButton {
                icon.name: "list-add"
                tip: "New container"
                onClicked: childContainerForm.open()
            }
        }

        SectionLabel {
            text: "KIND"
            Layout.topMargin: Theme.s1
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.s2

            SegmentedControl {
                // Kind is identity; don't flip post-create.
                enabled: dlg.deviceId === -1
                opacity: enabled ? 1.0 : 0.5
                model: [
                    {value: "local", label: "Local (physical drive)"},
                    {value: "remote", label: "Remote (over SSH)"},
                ]
                value: dlg._kind
                onActivated: v => dlg._kind = v
            }
            Label {
                visible: dlg.deviceId !== -1
                text: "kind can't change after creation"
                opacity: 0.5
                font.pixelSize: Theme.fsSmall
            }
            Item { Layout.fillWidth: true }
        }

        SectionLabel {
            text: "DEVICE LABEL"
            Layout.topMargin: Theme.s1
        }
        TextField {
            id: labelField
            Layout.fillWidth: true
            placeholderText: dlg._kind === "local"
                             ? "e.g. Backup-1"
                             : "e.g. unraid /mnt/user"
        }

        // Local branch ----------------------------------------------------
        SectionLabel {
            text: "FILESYSTEM UUID  ·  mounted drives"
            visible: dlg._kind === "local"
            Layout.topMargin: Theme.s1
        }
        ScrollComboBox {
            id: uuidCombo
            visible: dlg._kind === "local"
            Layout.fillWidth: true
            textRole: "uuid"
            valueRole: "uuid"
            displayText: currentIndex === -1
                         ? "— select a mounted drive —"
                         : (model[currentIndex].uuid
                            + "   " + model[currentIndex].mountpoint)
            delegate: ItemDelegate {
                width: uuidCombo.width
                contentItem: Column {
                    Label {
                        text: modelData.uuid
                        font.family: Theme.mono
                        font.pixelSize: Theme.fsMono
                    }
                    Label {
                        text: modelData.mountpoint
                        opacity: 0.65
                        font.pixelSize: Theme.fsSmall
                    }
                }
            }
            onActivated: dlg._selectedUuid = currentValue || ""
        }
        Label {
            visible: dlg._kind === "local" && uuidCombo.count === 0
            opacity: 0.6
            font.italic: true
            wrapMode: Text.Wrap
            Layout.fillWidth: true
            text: "No unregistered drives are currently mounted. Plug one in, " +
                  "wait a couple of seconds, and reopen this dialog."
        }

        // Remote branch ---------------------------------------------------
        SectionLabel {
            text: "NETWORK TARGET  ·  rsync syntax: user@host:/base/path"
            visible: dlg._kind === "remote"
            Layout.topMargin: Theme.s1
        }
        TextField {
            id: networkTargetField
            visible: dlg._kind === "remote"
            Layout.fillWidth: true
            placeholderText: "user@nas:/mnt/backup"
            font.family: Theme.mono
            font.pixelSize: Theme.fsMono
        }
        RowLayout {
            visible: dlg._kind === "remote"
            Layout.fillWidth: true
            spacing: Theme.s2

            Button {
                text: "Test connection"
                enabled: networkTargetField.text.trim().length > 0
                onClicked: {
                    dlg._probeResult = "probing…"
                    dlg._probeResult = remoteProbes.probeTarget(
                        networkTargetField.text.trim(), 22)
                }
            }
            Label {
                text: dlg._probeResult === "live"        ? "✓ reachable"
                    : dlg._probeResult === "unreachable" ? "✕ unreachable (port 22)"
                    : dlg._probeResult === "probing…"    ? "probing…"
                                                         : ""
                color: dlg._probeResult === "live" ? Theme.ok
                     : dlg._probeResult === "unreachable" ? Theme.error
                     : Theme.textColor
            }
        }
    }

    // Inline-create child for the container picker. Self-contained.
    ContainerForm {
        id: childContainerForm
        onAcceptedWithId: function(newId) {
            dlg._refreshContainers(newId)
        }
    }
}

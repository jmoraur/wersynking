import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Qt.labs.platform as Labs
import "../components"

// Binding (= "connection") form. Owns the live rsync preview at the
// bottom and three inline-create child dialogs (source / container /
// device) so the user never has to leave this dialog.
//
// State lives in one `draft` map mirroring the bindings columns; every
// change goes through set(), which reassigns the map so all bindings
// (options, preview) re-evaluate. Option toggles render from
// connections.optionCatalog() — no flag is spelled in QML.
//
// Modes: bindingId === -1 → add, else → edit.
// Initial source/device prefills support the row-level shortcuts:
//   "+ new connection" from the toolbar → no prefill
//   "+ add connection" on a device row  → initialDeviceId set
Dialog {
    id: dlg
    modal: true
    title: dlg.bindingId === -1 ? "New connection" : "Edit connection"
    standardButtons: Dialog.Save | Dialog.Cancel
    // Width set directly — implicitWidth on the contentItem collapses or
    // loops on Fusion (see lessons).
    width: 780
    height: Math.min(parent ? parent.height - 40 : 740, 740)

    property int bindingId: -1
    property int initialSourceId: -1
    property int initialDeviceId: -1

    signal acceptedWithId(int newId)

    // The whole binding row as one map (column → value). Ids are 0 when
    // unset so the controller treats the draft as incomplete.
    property var draft: ({})
    property int _containerId: -1
    property string _sourcePath: ""
    property string _browseWarning: ""

    // Snapshots from the controller, refreshed each open + after
    // inline-create.
    property var _catalog: []
    property var _sources: []
    property var _containers: []
    property var _devices: []

    // Live mountpoint of the selected device, "" unless it's a local disk
    // mounted right now. Drives the dest-subpath "Browse…" button.
    readonly property string _destMountpoint:
        (draft.dest_device_id || 0) > 0
        ? connections.deviceMountpoint(draft.dest_device_id)
        : ""

    function set(key, value) {
        const d = Object.assign({}, draft)
        d[key] = value
        draft = d
    }

    function _refreshSources(preselectId) {
        _sources = connections.pickableSources()
        const idx = _sources.findIndex(s => s.id === preselectId)
        sourceCombo.currentIndex = idx
        set("source_label_id", idx === -1 ? 0 : preselectId)
        _syncSourcePath()
    }

    function _syncSourcePath() {
        const hit = _sources.find(s => s.id === (draft.source_label_id || 0))
        _sourcePath = hit ? hit.path : ""
    }

    function _refreshContainers(preselectId) {
        _containers = connections.pickableContainers()
        const idx = _containers.findIndex(c => c.id === preselectId)
        containerCombo.currentIndex = idx
        _containerId = idx === -1 ? -1 : preselectId
        _refreshDevices(draft.dest_device_id || 0)
    }

    function _refreshDevices(preselectId) {
        if (_containerId <= 0) {
            _devices = []
            deviceCombo.currentIndex = -1
            set("dest_device_id", 0)
            return
        }
        _devices = connections.pickableDevices(_containerId)
        const idx = _devices.findIndex(d => d.id === preselectId)
        deviceCombo.currentIndex = idx
        set("dest_device_id", idx === -1 ? 0 : preselectId)
    }

    function _defaults() {
        const d = {
            source_label_id: 0, dest_device_id: 0, dest_subpath: "",
            path_mode: "contents", chown_mode: "source",
            chown_value: "", chmod_value: "", excludes: "", rsh: "",
        }
        for (const o of _catalog) d[o.key] = o.default ? 1 : 0
        return d
    }

    function _loadTextFields() {
        subpathField.text = draft.dest_subpath || ""
        chownField.text = draft.chown_value || ""
        chmodField.text = draft.chmod_value || ""
        excludesArea.text = draft.excludes || ""
        rshField.text = draft.rsh || ""
    }

    function _loadForAdd() {
        draft = _defaults()
        _loadTextFields()
        _refreshSources(dlg.initialSourceId)
        if (dlg.initialDeviceId > 0) {
            const dev = connections.getDestDevice(dlg.initialDeviceId)
            _refreshContainers(dev && dev.container_id ? dev.container_id : -1)
            _refreshDevices(dlg.initialDeviceId)
        } else {
            _refreshContainers(-1)
        }
    }

    function _loadForEdit() {
        const b = connections.getBinding(dlg.bindingId)
        if (!b || !b.id) return
        const d = _defaults()
        for (const k in d) {
            if (b[k] !== undefined && b[k] !== null) d[k] = b[k]
        }
        draft = d
        _loadTextFields()
        _refreshSources(b.source_label_id)
        const dev = connections.getDestDevice(b.dest_device_id)
        _refreshContainers(dev && dev.container_id ? dev.container_id : -1)
        _refreshDevices(b.dest_device_id)
    }

    onAboutToShow: {
        _catalog = connections.optionCatalog()
        _browseWarning = ""
        if (dlg.bindingId === -1) _loadForAdd()
        else _loadForEdit()
    }

    onAccepted: {
        if (!(draft.source_label_id > 0) || !(draft.dest_device_id > 0))
            return
        let newId = dlg.bindingId
        if (dlg.bindingId === -1) {
            newId = connections.addBinding(draft)
        } else {
            connections.updateBinding(dlg.bindingId, draft)
        }
        dlg.acceptedWithId(newId)
    }

    contentItem: ScrollView {
        clip: true
        contentWidth: availableWidth

        ColumnLayout {
            width: parent.width
            spacing: Theme.s3

            // ---- Source | Destination side-by-side panels -------------
            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.s3

                GroupBox {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1   // equal split
                    Layout.alignment: Qt.AlignTop
                    title: "Source"

                    ColumnLayout {
                        anchors.fill: parent
                        spacing: Theme.s2

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: Theme.s1

                            ScrollComboBox {
                                id: sourceCombo
                                Layout.fillWidth: true
                                model: dlg._sources
                                textRole: "display"
                                valueRole: "id"
                                displayText: currentIndex === -1
                                             ? "— pick a source —" : currentText
                                onActivated: {
                                    dlg.set("source_label_id", currentValue || 0)
                                    dlg._syncSourcePath()
                                }
                            }
                            RowActionButton {
                                icon.name: "list-add"
                                tip: "New source"
                                onClicked: {
                                    childSourceForm.sourceLabelId = -1
                                    childSourceForm.initialLabel = ""
                                    childSourceForm.initialPath = ""
                                    childSourceForm.open()
                                }
                            }
                            RowActionButton {
                                icon.name: "document-edit"
                                tip: "Edit selected source"
                                enabled: (dlg.draft.source_label_id || 0) > 0
                                onClicked: {
                                    const row = connections.getSourceLabel(
                                        dlg.draft.source_label_id)
                                    if (!row.id) return
                                    childSourceForm.sourceLabelId = row.id
                                    childSourceForm.initialLabel = row.label || ""
                                    childSourceForm.initialPath = row.path || ""
                                    childSourceForm.open()
                                }
                            }
                        }

                        Label {
                            Layout.fillWidth: true
                            elide: Text.ElideMiddle
                            opacity: 0.65
                            font.family: Theme.mono
                            font.pixelSize: Theme.fsMono
                            text: (dlg.draft.source_label_id || 0) > 0
                                  ? dlg._sourcePath
                                  : "—"
                        }

                        RowLayout {
                            Layout.fillWidth: true
                            spacing: Theme.s2
                            Label { text: "Path mode"; opacity: 0.75 }
                            SegmentedControl {
                                model: [
                                    {value: "contents", label: "contents/"},
                                    {value: "folder", label: "folder"},
                                ]
                                value: dlg.draft.path_mode || "contents"
                                onActivated: v => dlg.set("path_mode", v)
                            }
                            Label {
                                text: dlg.draft.path_mode === "folder"
                                      ? "copies the folder itself"
                                      : "copies what's inside"
                                opacity: 0.5
                                font.pixelSize: Theme.fsSmall
                                Layout.fillWidth: true
                                elide: Text.ElideRight
                            }
                        }
                    }
                }

                GroupBox {
                    Layout.fillWidth: true
                    Layout.preferredWidth: 1   // equal split
                    Layout.alignment: Qt.AlignTop
                    title: "Destination"

                    GridLayout {
                        anchors.fill: parent
                        columns: 2
                        columnSpacing: Theme.s2
                        rowSpacing: Theme.s2

                        Label { text: "Container"; opacity: 0.75 }
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
                                             ? "— pick a container —" : currentText
                                onActivated: {
                                    dlg._containerId = currentValue || -1
                                    dlg._refreshDevices(-1)
                                }
                            }
                            RowActionButton {
                                icon.name: "list-add"
                                tip: "New container"
                                onClicked: {
                                    childContainerForm.containerId = -1
                                    childContainerForm.initialLabel = ""
                                    childContainerForm.open()
                                }
                            }
                            RowActionButton {
                                icon.name: "document-edit"
                                tip: "Edit selected container"
                                enabled: dlg._containerId > 0
                                onClicked: {
                                    const row = connections.getDestContainer(
                                        dlg._containerId)
                                    if (!row.id) return
                                    childContainerForm.containerId = row.id
                                    childContainerForm.initialLabel = row.label || ""
                                    childContainerForm.open()
                                }
                            }
                        }

                        Label { text: "Device"; opacity: 0.75 }
                        RowLayout {
                            Layout.fillWidth: true
                            spacing: Theme.s1

                            ScrollComboBox {
                                id: deviceCombo
                                Layout.fillWidth: true
                                enabled: dlg._containerId > 0
                                model: dlg._devices
                                textRole: "label"
                                valueRole: "id"
                                displayText: !enabled
                                             ? "— pick a container first —"
                                             : (currentIndex === -1
                                                ? "— pick a device —"
                                                : currentText)
                                onActivated: {
                                    dlg.set("dest_device_id", currentValue || 0)
                                    dlg._browseWarning = ""
                                }
                            }
                            RowActionButton {
                                icon.name: "list-add"
                                tip: "New device"
                                enabled: dlg._containerId > 0
                                onClicked: {
                                    childDeviceForm.deviceId = -1
                                    childDeviceForm.initialContainerId = dlg._containerId
                                    childDeviceForm.initialKind = "local"
                                    childDeviceForm.initialLabel = ""
                                    childDeviceForm.initialUuid = ""
                                    childDeviceForm.initialNetworkTarget = ""
                                    childDeviceForm.open()
                                }
                            }
                            RowActionButton {
                                icon.name: "document-edit"
                                tip: "Edit selected device"
                                enabled: (dlg.draft.dest_device_id || 0) > 0
                                onClicked: {
                                    const row = connections.getDestDevice(
                                        dlg.draft.dest_device_id)
                                    if (!row.id) return
                                    childDeviceForm.deviceId = row.id
                                    childDeviceForm.initialContainerId = row.container_id || -1
                                    childDeviceForm.initialKind = row.kind || "local"
                                    childDeviceForm.initialLabel = row.label || ""
                                    childDeviceForm.initialUuid = row.uuid || ""
                                    childDeviceForm.initialNetworkTarget = row.network_target || ""
                                    childDeviceForm.open()
                                }
                            }
                        }

                        Label {
                            text: "Subpath"
                            opacity: 0.75
                            Layout.alignment: Qt.AlignTop
                        }
                        ColumnLayout {
                            Layout.fillWidth: true
                            spacing: 2

                            RowLayout {
                                Layout.fillWidth: true
                                spacing: Theme.s1

                                TextField {
                                    id: subpathField
                                    Layout.fillWidth: true
                                    placeholderText: "(empty = device root)"
                                    onTextChanged: dlg.set("dest_subpath", text)
                                }
                                RowActionButton {
                                    icon.name: "folder-open"
                                    tip: (dlg.draft.dest_device_id || 0) <= 0
                                         ? "Pick a device first"
                                         : (dlg._destMountpoint === ""
                                            ? "Browsing needs a local device that's mounted now"
                                            : "Browse the device")
                                    enabled: dlg._destMountpoint !== ""
                                    onClicked: destFolderDialog.open()
                                }
                            }
                            Label {
                                Layout.fillWidth: true
                                visible: dlg._browseWarning !== ""
                                text: dlg._browseWarning
                                color: Theme.error
                                font.pixelSize: Theme.fsSmall
                                wrapMode: Text.Wrap
                            }
                        }
                    }
                }
            }

            // ---- Ownership & permissions ------------------------------
            SectionLabel {
                text: "OWNERSHIP & PERMISSIONS"
                Layout.topMargin: Theme.s1
            }

            RowLayout {
                Layout.fillWidth: true
                spacing: Theme.s2

                SegmentedControl {
                    model: [
                        {value: "source", label: "Use source values"},
                        {value: "dest", label: "Force dest values"},
                    ]
                    value: dlg.draft.chown_mode || "source"
                    onActivated: v => dlg.set("chown_mode", v)
                }
                Item { Layout.fillWidth: true }
            }

            GridLayout {
                visible: dlg.draft.chown_mode === "dest"
                Layout.fillWidth: true
                columns: 2
                columnSpacing: Theme.s3
                rowSpacing: 2

                Label { text: "--chown"; font.family: Theme.mono; font.pixelSize: Theme.fsMono }
                Label { text: "--chmod"; font.family: Theme.mono; font.pixelSize: Theme.fsMono }
                TextField {
                    id: chownField
                    Layout.fillWidth: true
                    placeholderText: "user:group  e.g. nobody:users"
                    onTextChanged: dlg.set("chown_value", text)
                }
                TextField {
                    id: chmodField
                    Layout.fillWidth: true
                    placeholderText: "e.g. D775,F664"
                    onTextChanged: dlg.set("chmod_value", text)
                }
            }

            // ---- Options (catalog-driven) -----------------------------
            OptionsEditor {
                Layout.fillWidth: true
                Layout.topMargin: Theme.s1
                catalog: dlg._catalog
                values: dlg.draft
                onOptionToggled: (key, v) => dlg.set(key, v)
            }

            // ---- Excludes + rsh ---------------------------------------
            SectionLabel {
                text: "EXCLUDES  ·  one pattern per line"
                Layout.topMargin: Theme.s1
            }
            ScrollView {
                Layout.fillWidth: true
                Layout.preferredHeight: 72

                TextArea {
                    id: excludesArea
                    placeholderText: ".cache/\n*.tmp"
                    onTextChanged: dlg.set("excludes", text)
                    font.family: Theme.mono
                    font.pixelSize: Theme.fsMono
                    wrapMode: TextEdit.NoWrap
                }
            }

            SectionLabel { text: "--rsh OVERRIDE  ·  optional" }
            TextField {
                id: rshField
                Layout.fillWidth: true
                placeholderText: "ssh -p 2222 -i ~/.ssh/key"
                onTextChanged: dlg.set("rsh", text)
                font.family: Theme.mono
                font.pixelSize: Theme.fsMono
            }

            // ---- Live preview -----------------------------------------
            SectionLabel {
                text: "COMMAND PREVIEW"
                Layout.topMargin: Theme.s1
            }
            CommandPreview {
                Layout.fillWidth: true
                argv: connections.previewCommand(dlg.draft)
            }
        }
    }

    // ---- Dest-folder browser ------------------------------------------
    // The dest subpath is relative to the device's mountpoint, so we root
    // the picker at the live mountpoint and store back only the part below
    // it. Picking outside the device is rejected with an inline warning.
    Labs.FolderDialog {
        id: destFolderDialog
        title: "Choose destination folder on the device"
        currentFolder: {
            const base = dlg._destMountpoint.replace(/\/+$/, "")
            const sub = (dlg.draft.dest_subpath || "").replace(/^\/+/, "")
            return "file://" + (sub ? base + "/" + sub : base)
        }
        onAccepted: {
            const url = folder.toString()
            const picked = url.startsWith("file://") ? url.slice(7) : url
            const base = dlg._destMountpoint.replace(/\/+$/, "")
            if (picked === base) {
                subpathField.text = ""
                dlg._browseWarning = ""
            } else if (picked.startsWith(base + "/")) {
                subpathField.text = picked.slice(base.length + 1)
                dlg._browseWarning = ""
            } else {
                dlg._browseWarning =
                    "That folder is outside the selected device — pick a folder under " + base
            }
        }
    }

    // ---- Inline-create child dialogs ----------------------------------
    SourceLabelForm {
        id: childSourceForm
        onAcceptedWithId: function(newId) { dlg._refreshSources(newId) }
    }
    ContainerForm {
        id: childContainerForm
        onAcceptedWithId: function(newId) { dlg._refreshContainers(newId) }
    }
    DeviceForm {
        id: childDeviceForm
        onAcceptedWithId: function(newId) { dlg._refreshDevices(newId) }
    }
}

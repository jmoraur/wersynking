import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import "../components"

// Confirmation + per-run override dialog for the sync buttons.
//
// Two modes driven by scopeKind:
//
//   - "connection" → single editable mode. The binding row is copied
//     into a `draft` map at open; toggles apply to this run only.
//     Preview + pre-flight recompute live off the draft.
//
//   - "device" | "container" | "source" → read-only multi-binding
//     summary. Each card shows source → dest, the literal rsync
//     command and its pre-flight issues. Unreachable or error-carrying
//     bindings are excluded from the run; warnings need a per-issue
//     "I understand" ack.
//
// connections.runSync(jobs) hands `[{argv, label, destDeviceId}]` to
// the runner, which groups by device and runs in parallel across
// devices (sequential within each).
Dialog {
    id: dlg
    modal: true
    title: "Sync — confirm"
    standardButtons: Dialog.NoButton
    width: 780
    height: Math.min(parent ? parent.height - 40 : 660, 660)

    // --- Inputs (set via openFor) --------------------------------------
    property string scopeKind: ""
    property int    scopeId: -1

    // Snapshot of bindings under the scope (read once at open).
    property var _bindings: []
    // Single-mode per-run draft (same shape as ConnectionForm.draft).
    property var draft: ({})
    property var _catalog: []

    readonly property bool _isSingle: scopeKind === "connection"

    // Per-(bindingId, issueIdx) "I understand" state. bindingId = -1
    // is reserved for the single-mode draft. Reset on every open so
    // re-opening the same scope after a Cancel re-requires consent.
    property var _acks: ({})

    // Single-mode pre-flight recomputes whenever the draft changes.
    readonly property var _singleIssues:
        dlg._isSingle ? connections.preflightDraft(dlg.draft) : []

    function set(key, value) {
        const d = Object.assign({}, draft)
        d[key] = value
        draft = d
    }

    // Convenience entry point — snapshot work happens in onAboutToShow so
    // callers that go through setProperty(...) + open() (e.g. the smoke
    // driver) take the same path.
    function openFor(kind, id) {
        scopeKind = kind
        scopeId = id
        open()
    }

    onAboutToShow: {
        _acks = ({})
        _catalog = connections.optionCatalog()
        _bindings = connections.bindingsForScope(scopeKind, scopeId)
        if (_isSingle) {
            const b = connections.getBinding(scopeId)
            const d = {
                source_label_id: 0, dest_device_id: 0, dest_subpath: "",
                path_mode: "contents", chown_mode: "source",
                chown_value: "", chmod_value: "", excludes: "",
            }
            for (const o of _catalog) d[o.key] = o.default ? 1 : 0
            for (const k in d) {
                if (b[k] !== undefined && b[k] !== null) d[k] = b[k]
            }
            draft = d
            excludesArea.text = d.excludes || ""
            ownershipEditor.load()
        }
    }

    // --- ack bookkeeping ------------------------------------------------
    function _ackKey(bindingId, idx) { return bindingId + ":" + idx }

    function _setAck(bindingId, idx, checked) {
        const copy = Object.assign({}, dlg._acks)
        copy[dlg._ackKey(bindingId, idx)] = !!checked
        dlg._acks = copy
    }

    // Index-keyed ack map for one binding's IssueList.
    function _acksFor(bindingId) {
        const out = {}
        const prefix = bindingId + ":"
        for (const k in dlg._acks) {
            if (k.startsWith(prefix)) out[k.slice(prefix.length)] = dlg._acks[k]
        }
        return out
    }

    function _hasErrors(issues) {
        return (issues || []).some(i => i.severity === "error")
    }

    function _warningsAcked(bindingId, issues) {
        for (let i = 0; i < (issues || []).length; i++) {
            if (issues[i].severity === "warning"
                && !dlg._acks[dlg._ackKey(bindingId, i)]) {
                return false
            }
        }
        return true
    }

    // --- run computation --------------------------------------------------
    function _commandsToRun() {
        if (_isSingle) {
            if (_hasErrors(_singleIssues)) return []
            if (!_warningsAcked(-1, _singleIssues)) return []
            const argv = connections.previewCommand(draft)
            if (argv.length === 0) return []
            const b = _bindings.length === 1 ? _bindings[0] : null
            return [{
                argv: argv,
                label: b ? ((b.sourceDisplay || b.sourceLabel) + " → "
                            + (b.destFull || b.destLabel))
                         : "sync",
                destDeviceId: draft.dest_device_id,
            }]
        }
        const out = []
        for (const b of _bindings) {
            if (!b.destReachable) continue
            if (_hasErrors(b.issues)) continue
            if (!_warningsAcked(b.id, b.issues)) continue
            out.push({
                argv: b.command,
                label: (b.sourceDisplay || b.sourceLabel) + " → "
                       + (b.destFull || b.destLabel),
                destDeviceId: b.destDeviceId,
            })
        }
        return out
    }

    function _runnableCount() {
        return _bindings.filter(
            b => b.destReachable && !_hasErrors(b.issues)).length
    }

    function _scopeHeader() {
        if (scopeKind === "connection") return "Sync one connection"
        if (scopeKind === "device")     return "Sync all on this device"
        if (scopeKind === "container")  return "Sync all in this container"
        if (scopeKind === "source")     return "Sync all from this source"
        return "Sync"
    }

    contentItem: ColumnLayout {
        spacing: Theme.s3

        // --- Header --------------------------------------------------
        RowLayout {
            Layout.fillWidth: true

            Label {
                text: dlg._scopeHeader()
                font.weight: Font.Bold
                font.pixelSize: Theme.fsHeading
                Layout.fillWidth: true
            }
            Rectangle {
                visible: !dlg._isSingle && dlg._bindings.length > 0
                implicitWidth: countLabel.implicitWidth + 14
                implicitHeight: 18
                radius: 9
                color: Theme.tint(Theme.textColor, 0.08)

                Label {
                    id: countLabel
                    anchors.centerIn: parent
                    text: dlg._runnableCount() + " of "
                          + dlg._bindings.length + " can run"
                    font.pixelSize: Theme.fsSmall
                    opacity: 0.75
                }
            }
        }

        Label {
            visible: dlg._bindings.length === 0
            Layout.fillWidth: true
            text: "No connections to run under this scope."
            opacity: 0.6
        }

        // --- Multi-binding read-only summary ------------------------
        ScrollView {
            visible: !dlg._isSingle && dlg._bindings.length > 0
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true

            ColumnLayout {
                width: dlg.availableWidth - 20
                spacing: Theme.s2

                Repeater {
                    model: dlg._bindings

                    delegate: Rectangle {
                        id: bindingCard
                        required property var modelData

                        Layout.fillWidth: true
                        implicitHeight: cardCol.implicitHeight + 2 * Theme.s2
                        radius: Theme.radius
                        color: Theme.surface
                        border.width: 1
                        border.color: Theme.border
                        opacity: modelData.destReachable ? 1.0 : 0.55

                        ColumnLayout {
                            id: cardCol
                            anchors.fill: parent
                            anchors.margins: Theme.s2
                            spacing: Theme.s1

                            RowLayout {
                                Layout.fillWidth: true

                                Label {
                                    text: (bindingCard.modelData.sourceDisplay
                                           || bindingCard.modelData.sourceLabel)
                                          + "  →  "
                                          + (bindingCard.modelData.destFull
                                             || bindingCard.modelData.destLabel)
                                    font.weight: Font.DemiBold
                                    elide: Text.ElideRight
                                    Layout.fillWidth: true
                                }
                                Label {
                                    visible: !bindingCard.modelData.destReachable
                                    text: "skipped — unreachable"
                                    color: Theme.error
                                    font.italic: true
                                    font.pixelSize: Theme.fsSmall
                                }
                            }

                            Label {
                                text: Sh.quote(bindingCard.modelData.command)
                                wrapMode: Text.Wrap
                                font.family: Theme.mono
                                font.pixelSize: Theme.fsMono
                                opacity: 0.7
                                Layout.fillWidth: true
                            }

                            IssueList {
                                Layout.fillWidth: true
                                Layout.topMargin: (bindingCard.modelData.issues
                                                   || []).length > 0 ? 2 : 0
                                issues: bindingCard.modelData.issues || []
                                acks: dlg._acksFor(bindingCard.modelData.id)
                                onAckToggled: (idx, checked) => dlg._setAck(
                                    bindingCard.modelData.id, idx, checked)
                            }
                        }
                    }
                }
            }
        }

        // --- Single-binding editable view ---------------------------
        ScrollView {
            visible: dlg._isSingle && dlg._bindings.length > 0
            Layout.fillWidth: true
            Layout.fillHeight: true
            clip: true

            ColumnLayout {
                width: dlg.availableWidth - 20
                spacing: Theme.s3

                // Resolved source / dest at the top.
                GridLayout {
                    Layout.fillWidth: true
                    columns: 2
                    columnSpacing: Theme.s2
                    rowSpacing: 2

                    Label { text: "Source"; opacity: 0.6 }
                    Label {
                        text: dlg._bindings.length === 1
                              ? (dlg._bindings[0].sourceDisplay
                                 || dlg._bindings[0].sourceLabel)
                                + "   " + dlg._bindings[0].sourcePath
                              : ""
                        elide: Text.ElideMiddle
                        Layout.fillWidth: true
                    }
                    Label { text: "Destination"; opacity: 0.6 }
                    Label {
                        text: dlg._bindings.length === 1
                              ? (dlg._bindings[0].destFull
                                 || dlg._bindings[0].destLabel)
                                + "   " + dlg._bindings[0].destDisplay
                              : ""
                        elide: Text.ElideMiddle
                        Layout.fillWidth: true
                    }
                }

                // Path mode + ownership — per-run overrides.
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
                    Item { Layout.fillWidth: true }
                }

                OwnershipEditor {
                    id: ownershipEditor
                    Layout.fillWidth: true
                    values: dlg.draft
                    onFieldChanged: (key, v) => dlg.set(key, v)
                }

                OptionsEditor {
                    Layout.fillWidth: true
                    catalog: dlg._catalog
                    values: dlg.draft
                    onOptionToggled: (key, v) => dlg.set(key, v)
                }

                SectionLabel { text: "SKIP LIST  ·  one per line" }
                ScrollView {
                    Layout.fillWidth: true
                    Layout.preferredHeight: 60

                    TextArea {
                        id: excludesArea
                        placeholderText: ".cache/\n*.tmp"
                        onTextChanged: dlg.set("excludes", text)
                        font.family: Theme.mono
                        font.pixelSize: Theme.fsMono
                        wrapMode: TextEdit.NoWrap
                    }
                }

                SectionLabel {
                    visible: dlg._singleIssues.length > 0
                    text: "PRE-FLIGHT CHECKS"
                }
                IssueList {
                    Layout.fillWidth: true
                    issues: dlg._singleIssues
                    acks: dlg._acksFor(-1)
                    onAckToggled: (idx, checked) => dlg._setAck(-1, idx, checked)
                }

                SectionLabel { text: "COMMAND PREVIEW" }
                CommandPreview {
                    Layout.fillWidth: true
                    argv: connections.previewCommand(dlg.draft)
                    placeholder: "(command unavailable — source or dest missing)"
                }
            }
        }

        // --- Footer --------------------------------------------------
        RowLayout {
            Layout.fillWidth: true
            Layout.topMargin: Theme.s1

            Label {
                visible: dlg._isSingle
                text: "Per-run changes don't persist to the connection."
                opacity: 0.55
                font.pixelSize: Theme.fsSmall
            }
            Item { Layout.fillWidth: true }
            Button {
                text: "Cancel"
                onClicked: dlg.reject()
            }
            Button {
                text: "Run sync"
                highlighted: true
                enabled: dlg._commandsToRun().length > 0
                onClicked: {
                    connections.runSync(dlg._commandsToRun())
                    dlg.accept()
                }
            }
        }
    }
}

import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Catalog-driven rsync toggle editor: renders the baseline and extra
// option groups from connections.optionCatalog() so the flag list only
// exists in Python. `values` is the caller's draft map (opt_* → 0/1);
// changes are emitted, never written back directly.
ColumnLayout {
    id: editor

    property var catalog: []      // [{key, flag, description, baseline, default}]
    property var values: ({})
    signal optionToggled(string key, int value)

    spacing: 2

    SectionLabel { text: "DEFAULT OPTIONS  ·  on unless unticked" }

    Repeater {
        model: editor.catalog.filter(o => o.baseline)
        delegate: OptionRow {
            required property var modelData
            Layout.fillWidth: true
            flag: modelData.flag
            description: modelData.description
            checked: !!editor.values[modelData.key]
            onToggled: v => editor.optionToggled(modelData.key, v ? 1 : 0)
        }
    }

    SectionLabel {
        text: "EXTRA OPTIONS"
        Layout.topMargin: Theme.s3
    }

    Repeater {
        model: editor.catalog.filter(o => !o.baseline)
        delegate: OptionRow {
            required property var modelData
            Layout.fillWidth: true
            flag: modelData.flag
            description: modelData.description
            checked: !!editor.values[modelData.key]
            onToggled: v => editor.optionToggled(modelData.key, v ? 1 : 0)
        }
    }
}

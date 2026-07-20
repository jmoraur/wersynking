import QtQuick
import QtQuick.Controls
import QtQuick.Layouts
import Qt.labs.platform as Labs
import "../components"

// Source-label dialog. Two fields: a group label (e.g. "Laptop") and the
// absolute laptop path it points to. The source is shown as
// "<group> > <folder>", where the folder is the path's last segment — so
// one group repeats across folders (Laptop > Videos, Laptop > Music).
//
// Modes: sourceLabelId === -1 → add, else → edit.
// Emits acceptedWithId(int newId) so callers (e.g. ConnectionForm's
// source picker) can re-select the freshly-created label.
Dialog {
    id: dlg
    modal: true
    title: dlg.sourceLabelId === -1 ? "New source" : "Edit source"
    standardButtons: Dialog.Save | Dialog.Cancel
    width: 520

    property int sourceLabelId: -1
    property string initialLabel: ""
    property string initialPath: ""

    signal acceptedWithId(int newId)

    onAboutToShow: {
        labelField.text = dlg.initialLabel
        pathField.text = dlg.initialPath
        labelField.forceActiveFocus()
    }

    onAccepted: {
        const label = labelField.text.trim()
        const path = pathField.text.trim()
        if (!label || !path) return
        let newId = dlg.sourceLabelId
        if (dlg.sourceLabelId === -1) {
            newId = connections.addSourceLabel(label, path)
        } else {
            connections.updateSourceLabel(dlg.sourceLabelId, label, path)
        }
        dlg.acceptedWithId(newId)
    }

    contentItem: ColumnLayout {
        spacing: Theme.s2

        SectionLabel { text: "GROUP LABEL  ·  repeats across folders" }
        TextField {
            id: labelField
            Layout.fillWidth: true
            placeholderText: "e.g. Laptop"
        }

        SectionLabel {
            text: "PATH  ·  absolute, on this laptop"
            Layout.topMargin: Theme.s1
        }
        RowLayout {
            Layout.fillWidth: true
            spacing: Theme.s1

            TextField {
                id: pathField
                Layout.fillWidth: true
                placeholderText: "/home/me/Videos"
                font.family: Theme.mono
                font.pixelSize: Theme.fsMono
            }
            RowActionButton {
                icon.name: "folder-open"
                tip: "Browse…"
                onClicked: folderDialog.open()
            }
        }

        Label {
            Layout.fillWidth: true
            Layout.topMargin: Theme.s1
            opacity: 0.65
            text: {
                const g = labelField.text.trim()
                const folder = pathField.text.trim()
                                        .replace(/\/+$/, "").split("/").pop()
                if (g && folder) return "Shows as:  " + g + " > " + folder
                return "Shows as:  " + (g || folder || "—")
            }
        }
    }

    Labs.FolderDialog {
        id: folderDialog
        title: "Choose source folder"
        // `currentFolder` pre-positions; reading `folder` after accept gives
        // the user's pick. (Lessons: don't write to `folder` — silent no-op.)
        currentFolder: pathField.text
                       ? "file://" + pathField.text
                       : Labs.StandardPaths.writableLocation(Labs.StandardPaths.HomeLocation)
        onAccepted: {
            const url = folder.toString()
            pathField.text = url.startsWith("file://") ? url.slice(7) : url
        }
    }
}

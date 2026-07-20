import QtQuick
import QtQuick.Controls
import QtQuick.Layouts

// Small uppercase kicker used to separate form sections without
// wrapping everything in GroupBox chrome.
Label {
    Layout.fillWidth: true
    font.pixelSize: Theme.fsSmall
    font.bold: true
    font.letterSpacing: 0.8
    opacity: 0.55
    text: ""
}

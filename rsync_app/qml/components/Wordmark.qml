import QtQuick
import QtQuick.Controls

// The app wordmark: "WeRsyncing" with the "Rsync" part in brand red.
Label {
    textFormat: Text.StyledText
    text: "We<font color=\"" + Theme.brand + "\">Rsync</font>ing"
    color: Theme.textColor
    font.pixelSize: Theme.fsHeading
    font.bold: true
}

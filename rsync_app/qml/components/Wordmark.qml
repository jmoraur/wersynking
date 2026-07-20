import QtQuick
import QtQuick.Controls

// The app wordmark: "WeRSynking" with the "RSynk" part in brand red.
Label {
    textFormat: Text.StyledText
    text: "We<font color=\"" + Theme.brand + "\">RSynk</font>ing"
    color: Theme.textColor
    font.pixelSize: Theme.fsHeading
    font.bold: true
}

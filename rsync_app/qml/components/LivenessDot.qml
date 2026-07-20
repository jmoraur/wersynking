import QtQuick
import QtQuick.Controls

// Status dot for device/connection rows. States mirror the controller:
// live | not_mounted | unreachable | pending.
Rectangle {
    id: dot

    property string liveness: ""

    width: 9
    height: 9
    radius: 4.5
    color: liveness === "live" ? Theme.ok
         : liveness === "unreachable" ? Theme.error
         : liveness === "not_mounted" ? Theme.idle
         : Theme.warn   // pending

    ToolTip.visible: hover.hovered
    ToolTip.delay: 400
    ToolTip.text: liveness === "live" ? "Reachable"
                : liveness === "unreachable" ? "Unreachable"
                : liveness === "not_mounted" ? "Not mounted"
                : "Probe pending"

    HoverHandler { id: hover }
}

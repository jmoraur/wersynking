#!/usr/bin/env bash
# Dev-install: launcher entry that runs the app from this git checkout.
# (The RPM install ships packaging/wersynking.desktop instead, which
# uses the installed `wersynking` entry point and needs no Path=.)
set -euo pipefail

SRC=$(cd "$(dirname "$0")/.."; pwd)

# Derive a checkout-bound desktop file from the packaged one: swap the
# entry-point Exec for `python -m rsync_app` anchored at this checkout.
mkdir -p "$HOME/.local/share/applications"
sed -e 's|^Exec=.*|Exec=python -m rsync_app|' \
    -e '/^TryExec=/d' \
    -e "/^Exec=/a Path=$SRC" \
    "$SRC/packaging/wersynking.desktop" \
    > "$HOME/.local/share/applications/wersynking.desktop"
install -Dm644 "$SRC/packaging/icons/rsync-app.svg" \
        "$HOME/.local/share/icons/hicolor/scalable/apps/rsync-app.svg"

update-desktop-database "$HOME/.local/share/applications" 2>/dev/null || true
gtk-update-icon-cache -f -t "$HOME/.local/share/icons/hicolor" 2>/dev/null || true

echo "Installed."
echo "If KRunner doesn't pick it up immediately, log out + back in once."

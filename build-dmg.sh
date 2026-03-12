#!/bin/bash
set -e

APP_NAME="Termikita"
DMG_NAME="${APP_NAME}.dmg"
DIST_DIR="dist"
APP_PATH="${DIST_DIR}/${APP_NAME}.app"
DMG_PATH="${DIST_DIR}/${DMG_NAME}"
DMG_TEMP="${DIST_DIR}/${APP_NAME}-temp.dmg"
STAGING_DIR="${DIST_DIR}/dmg-staging"
VOL_PATH="/Volumes/${APP_NAME}"

# Verify .app exists
if [ ! -d "$APP_PATH" ]; then
    echo "Error: ${APP_PATH} not found. Run 'python setup.py py2app' first."
    exit 1
fi

# Clean previous artifacts
rm -f "$DMG_PATH" "$DMG_TEMP"
rm -rf "$STAGING_DIR"

# Create staging directory with .app and Applications symlink
mkdir -p "$STAGING_DIR"
cp -R "$APP_PATH" "$STAGING_DIR/"
ln -s /Applications "$STAGING_DIR/Applications"

# Create writable DMG
hdiutil create -volname "$APP_NAME" \
    -srcfolder "$STAGING_DIR" \
    -ov -format UDRW \
    "$DMG_TEMP"

rm -rf "$STAGING_DIR"

# Mount writable DMG
hdiutil attach "$DMG_TEMP" -mountpoint "$VOL_PATH" -noverify

# Apply Finder layout
osascript <<'APPLESCRIPT'
tell application "Finder"
    tell disk "Termikita"
        open
        delay 1
        set current view of container window to icon view
        set toolbar visible of container window to false
        set statusbar visible of container window to false
        set bounds of container window to {200, 200, 740, 540}
        set theViewOptions to icon view options of container window
        set arrangement of theViewOptions to not arranged
        set icon size of theViewOptions to 128
        set position of item "Applications" to {140, 170}
        set position of item "Termikita.app" to {400, 170}
        update without registering applications
        close
    end tell
end tell
APPLESCRIPT

sync
sleep 2

# Detach — find the correct device for our mount point
DEVICE=$(hdiutil info | grep -B 20 "$VOL_PATH" | grep '/dev/disk' | tail -1 | awk '{print $1}')
hdiutil detach "$DEVICE" -force 2>/dev/null || hdiutil detach "$VOL_PATH" -force

# Convert to compressed read-only
hdiutil convert "$DMG_TEMP" -format UDZO -o "$DMG_PATH"
rm -f "$DMG_TEMP"

echo "Created: ${DMG_PATH}"

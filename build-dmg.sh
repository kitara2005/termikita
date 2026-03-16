#!/bin/bash
set -e

APP_NAME="Termikita"
DMG_NAME="${APP_NAME}.dmg"
DIST_DIR="dist"
APP_PATH="${DIST_DIR}/${APP_NAME}.app"
DMG_PATH="${DIST_DIR}/${DMG_NAME}"
DMG_TEMP="${DIST_DIR}/${APP_NAME}-temp.dmg"
STAGING_DIR="${DIST_DIR}/dmg-staging"

# Verify .app exists
if [ ! -d "$APP_PATH" ]; then
    echo "Error: ${APP_PATH} not found. Run 'python setup.py py2app' first."
    exit 1
fi

# Detach any existing Termikita volumes to avoid conflicts
echo "Cleaning stale mounts..."
for dev in $(hdiutil info 2>/dev/null | grep -B 20 "/Volumes/${APP_NAME}" | grep '/dev/disk.*s[0-9]' | awk '{print $1}'); do
    hdiutil detach "$dev" -force 2>/dev/null || true
done

# Clean previous artifacts
rm -f "$DMG_PATH" "$DMG_TEMP"
rm -rf "$STAGING_DIR"

# Create staging directory with .app and Applications symlink
mkdir -p "$STAGING_DIR"
cp -R "$APP_PATH" "$STAGING_DIR/"
ln -s /Applications "$STAGING_DIR/Applications"

# Verify symlink was created
if [ ! -L "$STAGING_DIR/Applications" ]; then
    echo "Error: Failed to create Applications symlink"
    exit 1
fi
echo "Staging: .app + Applications symlink ready"

# Create writable DMG from staging
hdiutil create -volname "$APP_NAME" \
    -srcfolder "$STAGING_DIR" \
    -ov -format UDRW -fs HFS+ \
    "$DMG_TEMP"

rm -rf "$STAGING_DIR"

# Mount writable DMG — capture actual mount point
MOUNT_OUTPUT=$(hdiutil attach "$DMG_TEMP" -noverify -nobrowse)
MOUNT_POINT=$(echo "$MOUNT_OUTPUT" | grep -o '/Volumes/.*' | head -1)
DEVICE=$(echo "$MOUNT_OUTPUT" | grep '/dev/disk' | head -1 | awk '{print $1}')

echo "Mounted at: $MOUNT_POINT (device: $DEVICE)"

# Verify Applications symlink exists in mounted DMG
if [ ! -L "$MOUNT_POINT/Applications" ]; then
    echo "Warning: Applications symlink missing from DMG, recreating..."
    ln -s /Applications "$MOUNT_POINT/Applications"
fi

# Apply Finder layout via AppleScript using actual volume name
VOL_NAME=$(basename "$MOUNT_POINT")
osascript <<APPLESCRIPT
tell application "Finder"
    tell disk "$VOL_NAME"
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
        set position of item "${APP_NAME}.app" to {400, 170}
        update without registering applications
        close
    end tell
end tell
APPLESCRIPT

sync
sleep 2

# Detach using captured device
hdiutil detach "$DEVICE" -force

# Convert to compressed read-only
hdiutil convert "$DMG_TEMP" -format UDZO -o "$DMG_PATH"
rm -f "$DMG_TEMP"

echo "Created: ${DMG_PATH}"

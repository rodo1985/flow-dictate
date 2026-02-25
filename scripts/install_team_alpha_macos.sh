#!/usr/bin/env zsh
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This installer only supports macOS."
  exit 1
fi

if ! command -v xcode-select >/dev/null 2>&1; then
  echo "xcode-select is required. Install Xcode Command Line Tools first."
  exit 1
fi

if ! xcode-select -p >/dev/null 2>&1; then
  echo "Xcode Command Line Tools are not configured. Run: xcode-select --install"
  exit 1
fi

if ! command -v uv >/dev/null 2>&1; then
  echo "uv is required. Install with: brew install uv"
  exit 1
fi

if ! command -v swift >/dev/null 2>&1; then
  echo "Swift toolchain is required. Install Xcode Command Line Tools first."
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
APP_PATH="/Applications/FlowDictate.app"
APP_CONTENTS_PATH="${APP_PATH}/Contents"
APP_MACOS_PATH="${APP_CONTENTS_PATH}/MacOS"
APP_RESOURCES_PATH="${APP_CONTENTS_PATH}/Resources"
STAGING_ROOT="$(mktemp -d "/tmp/flow-dictate-app.XXXXXX")"
STAGING_APP_PATH="${STAGING_ROOT}/FlowDictate.app"
STAGING_CONTENTS_PATH="${STAGING_APP_PATH}/Contents"
STAGING_MACOS_PATH="${STAGING_CONTENTS_PATH}/MacOS"
STAGING_RESOURCES_PATH="${STAGING_CONTENTS_PATH}/Resources"

cleanup() {
  rm -rf "${STAGING_ROOT}"
}
trap cleanup EXIT

run_privileged() {
  if [[ -w "/Applications" ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

echo "Syncing Python dependencies with uv..."
cd "${REPO_ROOT}"
uv sync

echo "Building FlowDictateApp (release)..."
swift build --package-path "${REPO_ROOT}/macos/FlowDictateApp" -c release

echo "Creating staging app bundle..."
mkdir -p "${STAGING_MACOS_PATH}" "${STAGING_RESOURCES_PATH}"

cat > "${STAGING_CONTENTS_PATH}/Info.plist" <<PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN"
  "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
  <key>CFBundleExecutable</key>
  <string>FlowDictateLauncher</string>
  <key>CFBundleIdentifier</key>
  <string>ai.flowdictate.desktop</string>
  <key>CFBundleName</key>
  <string>FlowDictate</string>
  <key>CFBundlePackageType</key>
  <string>APPL</string>
  <key>CFBundleIconFile</key>
  <string>AppIcon.icns</string>
  <key>CFBundleShortVersionString</key>
  <string>0.1.0</string>
  <key>LSMinimumSystemVersion</key>
  <string>13.0</string>
</dict>
</plist>
PLIST

cp "${REPO_ROOT}/macos/FlowDictateApp/.build/release/FlowDictateApp" \
  "${STAGING_MACOS_PATH}/FlowDictateApp"

echo "Generating app icon..."
ICON_SOURCE_PNG="${STAGING_RESOURCES_PATH}/AppIcon-1024.png"
ICONSET_DIR="${STAGING_ROOT}/AppIcon.iconset"
ICON_ICNS_PATH="${STAGING_RESOURCES_PATH}/AppIcon.icns"
mkdir -p "${ICONSET_DIR}"

cat > "${STAGING_ROOT}/generate_logo.swift" <<'SWIFT'
import AppKit

let outputPath = CommandLine.arguments[1]
let canvasSize: CGFloat = 1024
let image = NSImage(size: NSSize(width: canvasSize, height: canvasSize))
image.lockFocus()

let baseRect = NSRect(x: 0, y: 0, width: canvasSize, height: canvasSize)
let backgroundPath = NSBezierPath(
    roundedRect: baseRect,
    xRadius: 220,
    yRadius: 220
)

let gradient = NSGradient(
    colors: [
        NSColor(calibratedRed: 0.08, green: 0.42, blue: 0.78, alpha: 1.0),
        NSColor(calibratedRed: 0.05, green: 0.23, blue: 0.55, alpha: 1.0)
    ]
)!
gradient.draw(in: backgroundPath, angle: 290)

if let symbol = NSImage(systemSymbolName: "mic.fill", accessibilityDescription: nil) {
    let config = NSImage.SymbolConfiguration(pointSize: 520, weight: .bold)
    let configuredSymbol = symbol.withSymbolConfiguration(config) ?? symbol
    let symbolRect = NSRect(
        x: (canvasSize - 520) / 2,
        y: (canvasSize - 560) / 2,
        width: 520,
        height: 560
    )
    NSColor.white.set()
    configuredSymbol.draw(in: symbolRect)
}

let ringPath = NSBezierPath(
    roundedRect: NSRect(x: 42, y: 42, width: 940, height: 940),
    xRadius: 190,
    yRadius: 190
)
NSColor.white.withAlphaComponent(0.18).setStroke()
ringPath.lineWidth = 12
ringPath.stroke()

image.unlockFocus()

guard
    let tiff = image.tiffRepresentation,
    let bitmap = NSBitmapImageRep(data: tiff),
    let pngData = bitmap.representation(using: .png, properties: [:])
else {
    throw NSError(
        domain: "FlowDictateIcon",
        code: 1,
        userInfo: [NSLocalizedDescriptionKey: "Failed to encode app icon PNG."]
    )
}

try pngData.write(to: URL(fileURLWithPath: outputPath))
SWIFT

swift "${STAGING_ROOT}/generate_logo.swift" "${ICON_SOURCE_PNG}"

sips -z 16 16 "${ICON_SOURCE_PNG}" --out "${ICONSET_DIR}/icon_16x16.png" >/dev/null
sips -z 32 32 "${ICON_SOURCE_PNG}" --out "${ICONSET_DIR}/icon_16x16@2x.png" >/dev/null
sips -z 32 32 "${ICON_SOURCE_PNG}" --out "${ICONSET_DIR}/icon_32x32.png" >/dev/null
sips -z 64 64 "${ICON_SOURCE_PNG}" --out "${ICONSET_DIR}/icon_32x32@2x.png" >/dev/null
sips -z 128 128 "${ICON_SOURCE_PNG}" --out "${ICONSET_DIR}/icon_128x128.png" >/dev/null
sips -z 256 256 "${ICON_SOURCE_PNG}" --out "${ICONSET_DIR}/icon_128x128@2x.png" >/dev/null
sips -z 256 256 "${ICON_SOURCE_PNG}" --out "${ICONSET_DIR}/icon_256x256.png" >/dev/null
sips -z 512 512 "${ICON_SOURCE_PNG}" --out "${ICONSET_DIR}/icon_256x256@2x.png" >/dev/null
sips -z 512 512 "${ICON_SOURCE_PNG}" --out "${ICONSET_DIR}/icon_512x512.png" >/dev/null
sips -z 1024 1024 "${ICON_SOURCE_PNG}" --out "${ICONSET_DIR}/icon_512x512@2x.png" >/dev/null
iconutil -c icns "${ICONSET_DIR}" -o "${ICON_ICNS_PATH}"

cat > "${STAGING_MACOS_PATH}/FlowDictateLauncher" <<LAUNCHER
#!/usr/bin/env zsh
set -euo pipefail

export PATH="/opt/homebrew/bin:/usr/local/bin:\$PATH"
export FLOW_DICTATE_REPO_ROOT="${REPO_ROOT}"
exec "\$(cd "\$(dirname "\$0")" && pwd)/FlowDictateApp"
LAUNCHER

chmod +x "${STAGING_MACOS_PATH}/FlowDictateLauncher" "${STAGING_MACOS_PATH}/FlowDictateApp"

echo "Deploying app to ${APP_PATH}..."
# Replace any running binary before copying the new bundle to avoid stale
# in-memory code paths after reinstall.
pkill -x "FlowDictateApp" >/dev/null 2>&1 || true
# Ensure stale daemon workers from older app sessions do not keep running in
# parallel with the newly launched app.
pkill -f "flow-dictate daemon --output active-app" >/dev/null 2>&1 || true
sleep 1
run_privileged rm -rf "${APP_PATH}"
run_privileged cp -R "${STAGING_APP_PATH}" "/Applications/"

echo "Installation complete."
echo "Open ${APP_PATH} from Finder or run: open \"${APP_PATH}\""

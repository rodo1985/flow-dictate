#!/usr/bin/env zsh
set -euo pipefail

if [[ "$(uname -s)" != "Darwin" ]]; then
  echo "This uninstaller only supports macOS."
  exit 1
fi

APP_PATH="/Applications/FlowDictate.app"
APP_BUNDLE_ID="ai.flowdictate.desktop"

run_privileged() {
  if [[ -w "/Applications" ]]; then
    "$@"
  else
    sudo "$@"
  fi
}

if [[ -d "${APP_PATH}" ]]; then
  # Stop any running menu-bar instance before deleting bundle files so users
  # never end up with an orphaned process from a previous install.
  pkill -x "FlowDictateApp" >/dev/null 2>&1 || true
  # Stop daemon workers launched by previous app instances to avoid duplicate
  # hotkey listeners after reinstall.
  pkill -f "flow-dictate daemon --output active-app" >/dev/null 2>&1 || true
  sleep 1
  run_privileged rm -rf "${APP_PATH}"
  echo "Removed ${APP_PATH}"
else
  echo "No installation found at ${APP_PATH}"
fi

# Reset persisted app preferences so reinstall provides a true clean setup.
defaults delete "${APP_BUNDLE_ID}" >/dev/null 2>&1 || true
echo "Cleared saved preferences for ${APP_BUNDLE_ID}"

echo "Uninstall complete."

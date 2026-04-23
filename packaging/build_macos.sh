#!/bin/zsh
set -euo pipefail

PROJECT_DIR="$(cd "$(dirname "$0")/.." && pwd)"
APP_NAME="Nova Image Scout"
ICON_NAME="NovaImageScout"
DIST_DIR="$PROJECT_DIR/dist"
ARTIFACTS_DIR="$PROJECT_DIR/artifacts/macos"
GENERATED_DIR="$PROJECT_DIR/packaging/generated"
STAGE_DIR="$GENERATED_DIR/dmg-stage"
DMG_NAME="NovaImageScout-macOS.dmg"
PYTHON_BIN="${PYTHON_BIN:-python3}"
CODE_SIGN_IDENTITY="${CODE_SIGN_IDENTITY:--}"
NOTARY_PROFILE="${NOTARY_PROFILE:-}"
export PYINSTALLER_CONFIG_DIR="$PROJECT_DIR/packaging/generated/pyinstaller-config"
export PYTHONPYCACHEPREFIX="${PYTHONPYCACHEPREFIX:-/tmp/nova_pycache}"
export MPLCONFIGDIR="$PROJECT_DIR/packaging/generated/mplconfig"
export XDG_CACHE_HOME="$PROJECT_DIR/packaging/generated/cache"

cd "$PROJECT_DIR"

require_command() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "Missing required command: $1"
    exit 1
  }
}

require_command "$PYTHON_BIN"
require_command hdiutil
require_command install_name_tool
require_command tesseract
require_command brew

if ! "$PYTHON_BIN" -c "import PyInstaller" >/dev/null 2>&1; then
  echo "PyInstaller is missing. Installing build tooling..."
  "$PYTHON_BIN" -m pip install --upgrade pip
  "$PYTHON_BIN" -m pip install -r "$PROJECT_DIR/packaging/requirements-build.txt"
fi

rm -rf "$GENERATED_DIR" "$PROJECT_DIR/build" "$DIST_DIR/$APP_NAME" "$DIST_DIR/$APP_NAME.app" "$DIST_DIR/$DMG_NAME" "$ARTIFACTS_DIR"
mkdir -p "$GENERATED_DIR"
mkdir -p "$ARTIFACTS_DIR"

"$PYTHON_BIN" "$PROJECT_DIR/packaging/generate_icon.py"
"$PYTHON_BIN" "$PROJECT_DIR/packaging/generate_auth_config_bundle.py"
"$PYTHON_BIN" "$PROJECT_DIR/packaging/vendor_tesseract_runtime.py"
"$PYTHON_BIN" -m PyInstaller --clean --noconfirm "$PROJECT_DIR/nova_image_scout.spec"

APP_PATH="$DIST_DIR/$APP_NAME.app"
DMG_PATH="$DIST_DIR/$DMG_NAME"

if [[ ! -d "$APP_PATH" ]]; then
  echo "Build failed: $APP_PATH was not created."
  exit 1
fi

if [[ "$CODE_SIGN_IDENTITY" == "-" ]]; then
  codesign --force --deep --sign - "$APP_PATH"
else
  codesign --force --deep --options runtime --timestamp --sign "$CODE_SIGN_IDENTITY" "$APP_PATH"
fi
codesign --verify --deep --strict "$APP_PATH"

rm -rf "$STAGE_DIR"
mkdir -p "$STAGE_DIR"
ditto "$APP_PATH" "$STAGE_DIR/$APP_NAME.app"
ln -s /Applications "$STAGE_DIR/Applications"

hdiutil create -volname "$APP_NAME" -srcfolder "$STAGE_DIR" -ov -format UDZO "$DMG_PATH"

if [[ "$CODE_SIGN_IDENTITY" != "-" ]]; then
  codesign --force --sign "$CODE_SIGN_IDENTITY" "$DMG_PATH"
fi

if [[ -n "$NOTARY_PROFILE" && "$CODE_SIGN_IDENTITY" != "-" ]]; then
  xcrun notarytool submit "$DMG_PATH" --keychain-profile "$NOTARY_PROFILE" --wait
  xcrun stapler staple "$APP_PATH"
  xcrun stapler staple "$DMG_PATH"
fi

echo
echo "Build complete."
echo "App bundle: $APP_PATH"
echo "DMG:        $DMG_PATH"
echo "Icon:       $GENERATED_DIR/$ICON_NAME.icns"

rm -rf "$ARTIFACTS_DIR/$APP_NAME.app"
ditto "$APP_PATH" "$ARTIFACTS_DIR/$APP_NAME.app"
cp -f "$DMG_PATH" "$ARTIFACTS_DIR/$DMG_NAME"
echo "Artifacts:  $ARTIFACTS_DIR"

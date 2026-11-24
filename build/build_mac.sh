#!/usr/bin/env bash
# Build EmailTool.app and EmailTool.dmg. Must be run on a Mac.
set -euo pipefail
cd "$(dirname "$0")/.."

[[ "$(uname)" == "Darwin" ]] || { echo "Run this on macOS."; exit 1; }

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-dev.txt

pytest -q

rm -rf dist
pyinstaller --noconfirm --workpath build/pyi EmailTool.spec

# Optional signing + notarization (needs Apple Developer account):
#   codesign --deep --force --options runtime --sign "Developer ID Application: NAME (TEAMID)" dist/EmailTool.app
#   ditto -c -k --keepParent dist/EmailTool.app EmailTool.zip
#   xcrun notarytool submit EmailTool.zip --keychain-profile "notary" --wait
#   xcrun stapler staple dist/EmailTool.app

command -v create-dmg >/dev/null || brew install create-dmg
rm -f EmailTool.dmg
create-dmg \
  --volname "EmailTool" \
  --window-size 540 340 \
  --icon "EmailTool.app" 130 150 \
  --app-drop-link 410 150 \
  EmailTool.dmg dist/EmailTool.app

echo "Done: EmailTool.dmg"

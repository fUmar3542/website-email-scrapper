#!/usr/bin/env bash
# Build WebsiteScrapper.app and WebsiteScrapper.dmg. Must be run on a Mac.
set -euo pipefail
cd "$(dirname "$0")/.."

[[ "$(uname)" == "Darwin" ]] || { echo "Run this on macOS."; exit 1; }

python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -r requirements-dev.txt

python -m pytest -q

rm -rf dist
pyinstaller --noconfirm --workpath build/pyi WebsiteScrapper.spec

# Optional signing + notarization (needs Apple Developer account):
#   codesign --deep --force --options runtime --sign "Developer ID Application: NAME (TEAMID)" dist/WebsiteScrapper.app
#   ditto -c -k --keepParent dist/WebsiteScrapper.app WebsiteScrapper.zip
#   xcrun notarytool submit WebsiteScrapper.zip --keychain-profile "notary" --wait
#   xcrun stapler staple dist/WebsiteScrapper.app

command -v create-dmg >/dev/null || brew install create-dmg
rm -f WebsiteScrapper.dmg
create-dmg \
  --volname "WebsiteScrapper" \
  --window-size 540 340 \
  --icon "WebsiteScrapper.app" 130 150 \
  --app-drop-link 410 150 \
  WebsiteScrapper.dmg dist/WebsiteScrapper.app

echo "Done: WebsiteScrapper.dmg"

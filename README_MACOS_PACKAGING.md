# macOS Packaging

This project includes a full local packaging pipeline for building:

- `Nova Image Scout.app`
- `NovaImageScout-macOS.dmg`

## What gets bundled

- Python runtime through PyInstaller
- PyQt6 UI dependencies
- OpenCV, NumPy, TensorFlow, and related Python packages
- `pytesseract`
- Native `tesseract` executable plus its Homebrew-linked libraries
- `tessdata` OCR language files from the build machine

## Build command

Run:

```bash
./packaging/build_macos.sh
```

Output:

- App bundle: `dist/Nova Image Scout.app`
- DMG: `dist/NovaImageScout-macOS.dmg`

## Optional signing and notarization

Ad-hoc signing is used by default so the bundle is internally consistent, but that is not enough for frictionless internet distribution.

For a web-downloadable release without Gatekeeper warnings, build with a real Apple Developer ID certificate and notarize the DMG:

```bash
export CODE_SIGN_IDENTITY="Developer ID Application: Your Name (TEAMID1234)"
export NOTARY_PROFILE="your-notarytool-profile"
./packaging/build_macos.sh
```

The script will:

1. Sign the `.app`
2. Build the `.dmg`
3. Submit the DMG with `notarytool`
4. Staple the notarization ticket back onto the app and DMG

## Important limitation

If you do **not** use a real Developer ID certificate plus notarization, macOS users downloading the DMG from the internet may still see an "unidentified developer" warning the first time they open it. The local build pipeline is ready for proper signing, but Apple account credentials are still required for a completely frictionless public release.

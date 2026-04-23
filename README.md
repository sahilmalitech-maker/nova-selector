# Nova Image Scout

Nova Image Scout is a desktop app for sorting and pulling photos out of large image libraries.

You can search by name, lift text from screenshots, match visually similar images, and run a culling pass to split a shoot into final selects and rejects.

## Download

Get the latest public builds from the [releases page](https://github.com/sahilmalitech-maker/nova-selector/releases/latest).

## What It Does

- Finds photos by filename or keyword, even when names are inconsistent
- Extracts search terms from screenshots with OCR
- Matches reference images against a source folder by visual similarity
- Copies matched files into a destination folder and exports a report
- Runs a culling workflow that ranks photos into `SELECT` and `REJECT`

## Platforms

- Windows installer
- macOS DMG

## Run From Source

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Create a local auth config file:

```bash
copy nova_scout_app\auth\auth_config.example.json nova_scout_app\auth\auth_config.local.json
```

Fill in your Firebase app settings and Google desktop OAuth client ID, then start the app:

```bash
python nova_image_scout.py
```

## Build Notes

- `packaging/build_windows.bat` creates the Windows app bundle
- `packaging/build_windows_installer.bat` creates the Windows installer
- `packaging/build_macos.sh` creates the macOS app bundle and DMG

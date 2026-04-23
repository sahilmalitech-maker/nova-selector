# Nova Image Scout

Nova Image Scout is a private AI-powered desktop application for photographers, editors, and creative teams who need to find the right image fast and reduce large shoots into final selects.

It combines image retrieval, OCR-assisted search, visual similarity matching, and photographer-style culling inside a polished PyQt desktop workflow for Windows and macOS.

## What The Software Does

- Searches large image libraries by fuzzy filename matching, even when names contain typos, missing extensions, or slight variations.
- Pulls search terms directly from screenshots using OCR, then turns that text into clean search queries automatically.
- Matches reference images visually using embedding-based similarity search instead of relying only on filenames.
- Copies confident matches into a destination folder and generates a readable report of what was found, copied, or missed.
- Runs a separate Culling AI mode that reviews an entire shoot and classifies frames into final `SELECT` and `REJECT` groups.
- Supports Google Sign-In for session access while keeping the actual image analysis and matching logic local to the desktop app.

## How The AI Works

Nova Image Scout uses several AI-assisted layers together:

- OCR with Tesseract extracts text from screenshots and cleans it before matching.
- Fuzzy text matching compares user queries against normalized filenames and ranks typo-tolerant candidates.
- Visual search uses CLIP when available, falls back to MobileNetV2 when needed, and then falls back again to an OpenCV descriptor when heavyweight models are unavailable.
- Culling AI scores sharpness, exposure, contrast, noise, subject presence, eye visibility, composition, distractions, and duplicate-like similarity before assigning final keep/reject decisions.
- Adaptive preference learning stores local culling preferences so repeated workflows can better reflect a photographer's style over time.

## Main Workflows

### 1. Smart Match

Use text queries, OCR-imported screenshot text, reference images, or a mix of all three.

The app scans the source library, finds confident filename matches, compares visual references against the image library, resolves the strongest unique image per reference, and copies final matches into the destination folder.

### 2. Photographer Culling AI

Use this mode when you want Nova to review an entire shoot and produce final `SELECT` and `REJECT` decisions.

The culling pipeline analyzes:

- focus and blur
- exposure and dynamic range
- eyes and face visibility
- composition and detail distribution
- background distractions
- relative similarity between neighboring or duplicate-like frames

It then opens a results window and produces an exportable report summarizing the culling decisions.

## Platform Builds

This project already contains packaging for both supported desktop targets:

- Windows: folder build in `artifacts/windows/Nova Image Scout/`
- macOS: DMG build in `artifacts/macos/NovaImageScout-macOS.dmg`

Important release note for Windows:

- Do not upload only `Nova Image Scout.exe` by itself.
- The Windows app depends on the adjacent `_internal/` folder created by PyInstaller.
- The correct downloadable Windows release asset is a ZIP of the entire `Nova Image Scout` folder.

Important release note for GitHub:

- Build artifacts are intentionally not committed to git in this repository.
- The private GitHub repository should contain the source code and packaging scripts.
- GitHub release assets follow repository visibility, so assets in a private repo are not public downloads.
- To keep source code private while sharing installers publicly, use a second public downloads repo or another public file host for the `.exe` installer and `.dmg`.

## Current Packaging Notes

- `packaging/build_windows.bat` builds the Windows desktop bundle.
- `packaging/build_windows_installer.bat` builds an Inno Setup installer that installs into `Program Files` and can create a desktop shortcut.
- `packaging/build_macos.sh` builds the macOS app bundle and DMG.
- `README_MACOS_PACKAGING.md` includes the macOS signing and notarization notes.

The current Windows bundle is very large because it packages OCR, TensorFlow, CLIP-related runtime dependencies, and other native libraries together. If GitHub release upload limits become a problem, the Windows package should be slimmed down before distribution.

## Run From Source

Install the runtime dependencies:

```bash
python -m pip install -r requirements.txt
```

Create a local auth config file from the example before using Google Sign-In:

```bash
copy nova_scout_app\auth\auth_config.example.json nova_scout_app\auth\auth_config.local.json
```

Then fill in your Firebase and Google OAuth desktop-app credentials in the local file, or provide them through environment variables.

Start the desktop app:

```bash
python nova_image_scout.py
```

## Repository Layout

- `nova_scout_app/` - application code, UI, workers, authentication, matching, OCR, visual search, and culling logic
- `packaging/` - Windows and macOS packaging scripts plus generated icons/runtime helpers
- `artifacts/` - local build outputs for distribution
- `nova_image_scout.py` - desktop launcher entry point

## Suggested GitHub Repo Description

Private AI-powered desktop app for image retrieval, OCR-assisted search, visual similarity matching, and photographer-grade photo culling.

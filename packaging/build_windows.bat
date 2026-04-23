@echo off
setlocal enabledelayedexpansion

set "PROJECT_DIR=%~dp0.."
for %%I in ("%PROJECT_DIR%") do set "PROJECT_DIR=%%~fI"

set "APP_NAME=Nova Image Scout"
set "DIST_DIR=%PROJECT_DIR%\dist"
set "BUILD_DIR=%PROJECT_DIR%\build"
set "GENERATED_DIR=%PROJECT_DIR%\packaging\generated"
set "ARTIFACTS_DIR=%PROJECT_DIR%\artifacts\windows"
set "PYTHON_BIN=%PYTHON_BIN%"
if "%PYTHON_BIN%"=="" set "PYTHON_BIN=python"

where "%PYTHON_BIN%" >nul 2>nul
if errorlevel 1 (
  echo Missing Python interpreter: %PYTHON_BIN%
  exit /b 1
)

pushd "%PROJECT_DIR%"

%PYTHON_BIN% -c "import PyInstaller" >nul 2>nul
if errorlevel 1 (
  echo PyInstaller is missing. Installing build tooling...
  %PYTHON_BIN% -m pip install --upgrade pip
  %PYTHON_BIN% -m pip install -r "%PROJECT_DIR%\packaging\requirements-build.txt"
)

if exist "%GENERATED_DIR%" rmdir /s /q "%GENERATED_DIR%"
if exist "%BUILD_DIR%" rmdir /s /q "%BUILD_DIR%"
if exist "%DIST_DIR%\%APP_NAME%" rmdir /s /q "%DIST_DIR%\%APP_NAME%"
if exist "%ARTIFACTS_DIR%" rmdir /s /q "%ARTIFACTS_DIR%"

mkdir "%GENERATED_DIR%"
mkdir "%ARTIFACTS_DIR%"

%PYTHON_BIN% "%PROJECT_DIR%\packaging\generate_icon.py"
%PYTHON_BIN% "%PROJECT_DIR%\packaging\vendor_tesseract_runtime_windows.py"
%PYTHON_BIN% -m PyInstaller --clean --noconfirm "%PROJECT_DIR%\nova_image_scout.windows.spec"

if not exist "%DIST_DIR%\%APP_NAME%" (
  echo Build failed: %DIST_DIR%\%APP_NAME% was not created.
  popd
  exit /b 1
)

xcopy "%DIST_DIR%\%APP_NAME%" "%ARTIFACTS_DIR%\%APP_NAME%\" /E /I /Y >nul

echo.
echo Windows build complete.
echo Output folder: %ARTIFACTS_DIR%\%APP_NAME%
echo.
call "%PROJECT_DIR%\packaging\build_windows_installer.bat"
if errorlevel 1 (
  echo Installer build skipped or failed. The portable app folder is still ready.
)

popd
exit /b 0

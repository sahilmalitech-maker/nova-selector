@echo off
setlocal enabledelayedexpansion

set "PROJECT_DIR=%~dp0.."
for %%I in ("%PROJECT_DIR%") do set "PROJECT_DIR=%%~fI"

set "APP_NAME=Nova Image Scout"
set "APP_DIR=%PROJECT_DIR%\artifacts\windows\%APP_NAME%"
set "SCRIPT_PATH=%PROJECT_DIR%\packaging\nova_image_scout_installer.iss"
set "ISCC_BIN="

if not exist "%APP_DIR%\Nova Image Scout.exe" (
  echo Missing Windows app bundle: %APP_DIR%
  echo Run packaging\build_windows.bat first.
  exit /b 1
)

if exist "%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe" set "ISCC_BIN=%ProgramFiles(x86)%\Inno Setup 6\ISCC.exe"
if not defined ISCC_BIN if exist "%ProgramFiles%\Inno Setup 6\ISCC.exe" set "ISCC_BIN=%ProgramFiles%\Inno Setup 6\ISCC.exe"
if not defined ISCC_BIN for %%I in (ISCC.exe) do set "ISCC_BIN=%%~$PATH:I"

if not defined ISCC_BIN (
  echo Inno Setup 6 compiler was not found.
  echo Install Inno Setup 6, then run this script again to create the installer.
  exit /b 1
)

if not exist "%SCRIPT_PATH%" (
  echo Missing installer script: %SCRIPT_PATH%
  exit /b 1
)

echo Building Windows installer with Inno Setup...
"%ISCC_BIN%" "%SCRIPT_PATH%"
if errorlevel 1 exit /b 1

echo.
echo Installer build complete.
echo Output folder: %PROJECT_DIR%\artifacts\windows-installer
exit /b 0

@echo off
REM Build backend HHZDataService.exe - must run on Windows (PyInstaller cannot cross-compile).
REM Prerequisite: Python 3.10+ installed and added to PATH.
setlocal
cd /d "%~dp0.."

if not exist "Workbench\data\app.db" (
    echo [data] Workbench\data\app.db not found, package without bundled initial database
) else (
    echo [data] Bundling Workbench\data\app.db into HHZDataService.exe
)

echo [1/4] Building workbench frontend (Workbench\web\dist\workbench.html)
cd Workbench\web
call npm run build
if errorlevel 1 exit /b 1
cd ..\..

echo [2/4] Installing backend dependencies + PyInstaller
cd Workbench
python -m pip install -r requirements.txt pyinstaller
if errorlevel 1 exit /b 1

echo [3/4] Packaging HHZDataService.exe
pyinstaller hhz-data-service.spec --clean --noconfirm
if errorlevel 1 exit /b 1

if not exist "..\release" mkdir "..\release"
copy /Y "dist\HHZDataService.exe" "..\release\HHZDataService.exe"
if errorlevel 1 exit /b 1

echo [4/4] Generating NSIS installer (auto firewall rule TCP 8000)
cd ..
node scripts\build-backend-installer.mjs
if errorlevel 1 exit /b 1

echo.
echo Done: release\HHZDataService.exe
echo       release\HHZDataService Setup <version>.exe (installer, auto firewall)
endlocal

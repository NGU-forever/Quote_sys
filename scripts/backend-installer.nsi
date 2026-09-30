; HHZDataService - master device data service installer (NSIS / Unicode)
;
; Features:
;   1. Install HHZDataService.exe to the selected directory;
;   2. Automatically allow Windows firewall: TCP 8000 inbound (private+public profile);
;   3. Create Start Menu / Desktop shortcuts and register uninstall entry;
;   4. On uninstall, remove firewall rule, shortcuts and install directory.
;
; Build params (all overridable via command line /D):
;   APP_VERSION   version, used in names and uninstall registry (default 2.0.0)
;   SRC_EXE       source exe path (default ..\release\HHZDataService.exe)
;   SETUP_FILE    installer output path (default ..\release\HHZDataService Setup <version>.exe)
;
; Normal build: node scripts/build-backend-installer.mjs (auto-locates makensis and version).
Unicode true

!include "MUI2.nsh"
!include "x64.nsh"

; ---------------- Compile-time params ----------------
!ifndef APP_VERSION
  !define APP_VERSION "2.0.0"
!endif
!ifndef SRC_EXE
  !define SRC_EXE "..\release\HHZDataService.exe"
!endif
!ifndef SETUP_FILE
  !define SETUP_FILE "..\release\HHZDataService Setup ${APP_VERSION}.exe"
!endif

!define PRODUCT_NAME "HHZDataService"
!define PRODUCT_EXE "HHZDataService.exe"
!define FIREWALL_RULE "HHZ Data Service (8000)"
!define FIREWALL_PORT "8000"
!define UNINSTALL_KEY "Software\Microsoft\Windows\CurrentVersion\Uninstall\${PRODUCT_NAME}"
!define AUTOSTART_KEY "Software\Microsoft\Windows\CurrentVersion\Run"

; ---------------- Basic info ----------------
Name "${PRODUCT_NAME} ${APP_VERSION}"
OutFile "${SETUP_FILE}"
RequestExecutionLevel admin
SetCompressor /SOLID lzma
InstallDir "$PROGRAMFILES64\${PRODUCT_NAME}"
InstallDirRegKey HKLM "${UNINSTALL_KEY}" "InstallLocation"

; ---------------- Pages ----------------
!define MUI_ABORTWARNING
!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!define MUI_FINISHPAGE_RUN "$INSTDIR\${PRODUCT_EXE}"
!define MUI_FINISHPAGE_RUN_TEXT "启动 HHZDataService (托盘后台服务)"
!insertmacro MUI_PAGE_FINISH

!insertmacro MUI_LANGUAGE "SimpChinese"
!insertmacro MUI_LANGUAGE "English"

; ---------------- Init: 64-bit only, switch to 64-bit registry view ----------------
Function .onInit
  ${IfNot} ${RunningX64}
    MessageBox MB_ICONSTOP|MB_OK "HHZDataService requires 64-bit Windows. Setup aborted."
    Abort
  ${EndIf}
  SetRegView 64
FunctionEnd

; ---------------- Install ----------------
Section "Main program (with firewall rule TCP 8000)" SecMain
  ; Close existing instance if running to prevent file lock and port 8000 conflict
  DetailPrint "Closing any running ${PRODUCT_NAME}..."
  nsExec::Exec 'taskkill /F /IM ${PRODUCT_EXE}'
  Sleep 500

  SetOutPath "$INSTDIR"
  File "/oname=${PRODUCT_EXE}" "${SRC_EXE}"
  WriteUninstaller "$INSTDIR\Uninstall.exe"

  ; Firewall: delete same-name rule first to avoid duplicates/residue, then add (TCP 8000 inbound, private+public profile).
  ; Rule name matches scripts/allow-firewall.ps1, idempotent on rerun.
  DetailPrint "Adding firewall rule: TCP ${FIREWALL_PORT} inbound (private+public profile)..."
  nsExec::ExecToLog 'netsh advfirewall firewall delete rule name="${FIREWALL_RULE}"'
  nsExec::ExecToStack 'netsh advfirewall firewall add rule name="${FIREWALL_RULE}" dir=in action=allow protocol=TCP localport=${FIREWALL_PORT} profile=private,public'
  Pop $0
  ${If} $0 != 0
    MessageBox MB_ICONEXCLAMATION|MB_OK "Failed to add firewall rule. If clients cannot connect, run scripts\allow-firewall.ps1 as administrator."
  ${EndIf}

  ; Uninstall registry entries
  WriteRegStr HKLM "${UNINSTALL_KEY}" "DisplayName" "${PRODUCT_NAME}"
  WriteRegStr HKLM "${UNINSTALL_KEY}" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKLM "${UNINSTALL_KEY}" "Publisher" "HHZ"
  WriteRegStr HKLM "${UNINSTALL_KEY}" "DisplayIcon" "$INSTDIR\${PRODUCT_EXE}"
  WriteRegStr HKLM "${UNINSTALL_KEY}" "InstallLocation" "$INSTDIR"
  WriteRegStr HKLM "${UNINSTALL_KEY}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegDWORD HKLM "${UNINSTALL_KEY}" "NoModify" 1
  WriteRegDWORD HKLM "${UNINSTALL_KEY}" "NoRepair" 1

  ; Shortcuts (all users: Start Menu + Desktop)
  SetShellVarContext all
  CreateDirectory "$SMPROGRAMS\${PRODUCT_NAME}"
  CreateShortcut "$SMPROGRAMS\${PRODUCT_NAME}\${PRODUCT_NAME}.lnk" "$INSTDIR\${PRODUCT_EXE}"
  CreateShortcut "$SMPROGRAMS\${PRODUCT_NAME}\Uninstall ${PRODUCT_NAME}.lnk" "$INSTDIR\Uninstall.exe"
  CreateShortcut "$DESKTOP\${PRODUCT_NAME}.lnk" "$INSTDIR\${PRODUCT_EXE}"
SectionEnd

; ---------------- Uninstall ----------------
Section "Uninstall"
  ; Terminate running instance if any
  nsExec::Exec 'taskkill /F /IM ${PRODUCT_EXE}'
  Sleep 500

  ; Remove firewall rule created by installer
  nsExec::ExecToLog 'netsh advfirewall firewall delete rule name="${FIREWALL_RULE}"'

  ; Clean autostart residue (if tray autostart was enabled)
  DeleteRegValue HKCU "${AUTOSTART_KEY}" "${PRODUCT_NAME}"

  ; Shortcuts
  SetShellVarContext all
  Delete "$SMPROGRAMS\${PRODUCT_NAME}\${PRODUCT_NAME}.lnk"
  Delete "$SMPROGRAMS\${PRODUCT_NAME}\Uninstall ${PRODUCT_NAME}.lnk"
  RMDir "$SMPROGRAMS\${PRODUCT_NAME}"
  Delete "$DESKTOP\${PRODUCT_NAME}.lnk"

  ; Uninstall registry entry and install directory
  DeleteRegKey HKLM "${UNINSTALL_KEY}"
  RMDir /r "$INSTDIR"
SectionEnd

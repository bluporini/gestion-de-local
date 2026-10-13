; ============================================================================
; installer.iss
; Instalador de GestionDeLocal con Inno Setup
;
; Requisitos:
;   - Inno Setup 6.x (https://jrsoftware.org/isinfo.php)
;   - Tener a mano el GestionDeLocal.exe generado por PyInstaller (--onefile)
;   - Ajustar las rutas/nombres marcados con TODO
;
; Que hace:
;   1. Instala GestionDeLocal.exe (y updater.exe si lo tenes como binario separado)
;      en Program Files.
;   2. Copia updater_config.json junto a updater.exe. Lo genera el workflow
;      con un token de SOLO LECTURA sobre el repo privado de releases,
;      que solo contiene binarios.
;      Tambien borra la variable de entorno GITHUB_TOKEN que dejaban las
;      versiones anteriores del instalador.
;   3. Crea accesos directos en Escritorio y Menu Inicio.
;   4. Al finalizar, ofrece ejecutar la app (que se auto-abre en el navegador,
;      ver auto_open_browser_snippet.py).
;
;
; IMPORTANTE (seguridad): todo lo que va dentro del instalador lo puede
; leer cualquiera que lo tenga. El unico token permitido es el de solo
; lectura del repo de releases; nunca uno con acceso al repo de codigo.
; ============================================================================

#define MyAppName "GestionDeLocal"
; Reemplazado automaticamente por el workflow de GitHub Actions con el
; valor real de version.json (mismo mecanismo que GitHubToken mas abajo).
; Para compilar en local, reemplazar a mano por la version real antes de
; correr ISCC.exe (no versionar ese cambio).
#define MyAppVersion "__APP_VERSION_PLACEHOLDER__"
#define MyAppPublisher "Tu Empresa"
#define MyAppExeName "GestionDeLocal.exe"    ; TODO: nombre real de tu exe onefile
#define MyUpdaterExeName "updater.exe"  ; TODO: si el updater es un exe aparte

[Setup]
AppId={{71001978-8501-4FF6-87BC-A4EFE19AB058}}  ; TODO: generar un GUID propio (Tools > Generate GUID en Inno Setup)
AppName={#MyAppName}
AppVersion={#MyAppVersion}
AppPublisher={#MyAppPublisher}
DefaultDirName={autopf}\{#MyAppName}
DefaultGroupName={#MyAppName}
DisableProgramGroupPage=yes
OutputDir=dist_installer
OutputBaseFilename={#MyAppName}_Setup_{#MyAppVersion}
Compression=lzma2
SolidCompression=yes
WizardStyle=modern
; No requiere admin porque la variable de entorno se guarda a nivel usuario:
PrivilegesRequired=lowest
; Avisa a Windows que cambiaron las variables de entorno (por el borrado
; de GITHUB_TOKEN en [Registry]).
ChangesEnvironment=yes
ArchitecturesInstallIn64BitMode=x64compatible
SetupIconFile=GestionDeLocal.ico

[Languages]
Name: "spanish"; MessagesFile: "compiler:Languages\Spanish.isl"

[Files]
; TODO: ajustar rutas de origen segun donde tengas los binarios compilados
Source: "dist\{#MyAppExeName}"; DestDir: "{app}"; Flags: ignoreversion
Source: "dist\{#MyUpdaterExeName}"; DestDir: "{app}"; Flags: ignoreversion
; Generado por el workflow (no esta en git). En un build local sin este
; archivo el instalador igual compila, pero el updater no va a funcionar.
Source: "dist\updater_config.json"; DestDir: "{app}"; Flags: ignoreversion skipifsourcedoesntexist
Source: "..\version.json"; DestDir: "{app}"; Flags: ignoreversion
Source: "GestionDeLocal.ico"; DestDir: "{app}"; Flags: ignoreversion

[Icons]
Name: "{group}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\GestionDeLocal.ico"
Name: "{autodesktop}\{#MyAppName}"; Filename: "{app}\{#MyAppExeName}"; IconFilename: "{app}\GestionDeLocal.ico"

[Run]
Filename: "{app}\{#MyAppExeName}"; Description: "Ejecutar {#MyAppName}"; Flags: nowait postinstall skipifsilent

[Registry]
; Borra el GITHUB_TOKEN que guardaban las versiones anteriores del
; instalador (token ya revocado; el updater no la lee).
Root: HKCU; Subkey: "Environment"; ValueType: none; ValueName: "GITHUB_TOKEN"; \
    Flags: deletevalue

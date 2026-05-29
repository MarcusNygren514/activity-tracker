; Activity Tracker â€“ Inno Setup installer script
; Installerar till C:\Program Files\ActivityTracker\
; Skapar autostart-post som pekar pÃ¥ den nya exe:n
; RÃ¶r INTE datafÃ¶ldern C:\Users\{user}\activity_tracker\

#define AppName "Activity Tracker"
#define AppVersion "v0.20b"
#define AppPublisher "Oaks"
#define AppExeName "ActivityTracker.exe"
#define SourceDir "C:\activity_tracker\build\dist\ActivityTracker"

[Setup]
AppId={{F3A2B1C4-9E7D-4F6A-B8C3-2D1E5F7A9B0C}
AppName={#AppName}
AppVersion={#AppVersion}
AppPublisher={#AppPublisher}
DefaultDirName={autopf}\ActivityTracker
DisableProgramGroupPage=yes
OutputDir=C:\activity_tracker\build\installer
OutputBaseFilename=ActivityTracker_Setup_{#AppVersion}
SetupIconFile=C:\activity_tracker\activity_tracker.ico
Compression=lzma2/ultra64
SolidCompression=yes
WizardStyle=modern
PrivilegesRequired=admin
CloseApplications=no
RestartApplications=no
RestartIfNeededByRun=no
UninstallDisplayIcon={app}\{#AppExeName}

[Languages]
Name: "swedish"; MessagesFile: "compiler:Languages\Swedish.isl"

[Messages]
WelcomeLabel2=Detta installerar [name/ver] pÃ¥ din dator.%n%nOm Activity Tracker redan kÃ¶rs, stÃ¤ng den via tray-ikonen innan du fortsÃ¤tter.%n%nKlicka pÃ¥ NÃ¤sta fÃ¶r att fortsÃ¤tta.

[Files]
; Kopiera hela dist-mappen
Source: "{#SourceDir}\*"; DestDir: "{app}"; Flags: ignoreversion recursesubdirs createallsubdirs

[Icons]
; Startmeny
Name: "{autoprograms}\{#AppName}"; Filename: "{app}\{#AppExeName}"
; Skrivbordsikon (valfri â€“ kommentera ut om du inte vill ha den)
; Name: "{autodesktop}\{#AppName}"; Filename: "{app}\{#AppExeName}"

[Registry]
; Autostart fÃ¶r aktuell anvÃ¤ndare â€“ startar utan admin
Root: HKCU; Subkey: "Software\Microsoft\Windows\CurrentVersion\Run"; ValueType: string; ValueName: "ActivityTracker"; ValueData: """{app}\{#AppExeName}"""; Flags: uninsdeletevalue

[Run]
; Starta appen direkt efter installationen (inte som admin â€“ kÃ¶r som den inloggade anvÃ¤ndaren)
Filename: "{app}\{#AppExeName}"; Description: "Starta Activity Tracker nu"; Flags: nowait postinstall skipifsilent runasoriginaluser

[UninstallRun]
; StÃ¤ng appen innan avinstallation
Filename: "taskkill.exe"; Parameters: "/f /im {#AppExeName}"; Flags: runhidden; RunOnceId: "KillApp"

[InstallDelete]
; Ta bort gamla startfiler vid installation
Type: files; Name: "{userstartup}\ActivityTracker.bat"
Type: files; Name: "{userstartup}\ActivityTracker.exe"

[UninstallDelete]
; LÃ¤mna kvar datafÃ¶ldern (C:\Users\{user}\activity_tracker\) â€“ rÃ¶r ej!


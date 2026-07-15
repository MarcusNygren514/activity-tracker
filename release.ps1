# release.ps1 – Bygger och publicerar en ny version av Activity Tracker
# Användning: .\release.ps1
# Krav: Python (med PyInstaller), Inno Setup 6, gh CLI inloggad

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$ISCC       = "C:\Program Files (x86)\Inno Setup 6\ISCC.exe"
$ROOT       = "C:\dev\verktyg\activity_tracker"
$ISS        = "$ROOT\build\ActivityTracker.iss"
$CLAUDE_MD  = "$ROOT\CLAUDE.md"
$CHANGELOG  = "$ROOT\CHANGELOG.md"
$MANUAL     = "$ROOT\MANUAL.md"
$SPEC       = "$ROOT\build\ActivityTracker.spec"

# ── 1. Läs version ur web_app.py ────────────────────────────────────────────
$versionLine = Select-String -Path "$ROOT\web_app.py" -Pattern '^VERSION\s*=\s*"(.+)"' | Select-Object -First 1
if (-not $versionLine) { Write-Error "Hittar ingen VERSION-rad i web_app.py"; exit 1 }
$VERSION = $versionLine.Matches[0].Groups[1].Value
Write-Host "Version: $VERSION" -ForegroundColor Cyan

# ── 2. Kontrollera att CHANGELOG har en "(ej släppt)"-post ──────────────────
$clContent = Get-Content $CHANGELOG -Raw
if ($clContent -notmatch "## $([regex]::Escape($VERSION)) \(ej sl") {
    Write-Error "CHANGELOG.md saknar '## $VERSION (ej slappt)' - lagg till releaseposter forst"
    exit 1
}

# ── 3. Uppdatera datum i CHANGELOG ──────────────────────────────────────────
$today = Get-Date -Format "yyyy-MM-dd"
$clContent = $clContent -replace "## $([regex]::Escape($VERSION)) \(ej sl[^)]+\)", "## $VERSION ($today)"
Set-Content $CHANGELOG $clContent -Encoding UTF8
Write-Host "CHANGELOG.md: datum satt till $today" -ForegroundColor Green

# ── 4. Uppdatera version i ActivityTracker.iss ──────────────────────────────
$issContent = Get-Content $ISS -Raw
$issContent = $issContent -replace '#define AppVersion ".*?"', "#define AppVersion `"$VERSION`""
Set-Content $ISS $issContent -Encoding UTF8
Write-Host "ActivityTracker.iss: version uppdaterad" -ForegroundColor Green

# ── 5a. Uppdatera version i MANUAL.md ───────────────────────────────────────
$manContent = Get-Content $MANUAL -Raw
$manContent = $manContent -replace '> Senast uppdaterad: v[^\n]+', "> Senast uppdaterad: $VERSION ($today)"
Set-Content $MANUAL $manContent -Encoding UTF8
Write-Host "MANUAL.md: version uppdaterad" -ForegroundColor Green

# ── 5b. Uppdatera version i CLAUDE.md ───────────────────────────────────────
$mdContent = Get-Content $CLAUDE_MD -Raw
$mdContent = $mdContent -replace '`v[^`]+`\s*\(släppt [^)]+\)', "``$VERSION`` (släppt $today)"
Set-Content $CLAUDE_MD $mdContent -Encoding UTF8
Write-Host "CLAUDE.md: version uppdaterad" -ForegroundColor Green

# ── 6. Git commit ────────────────────────────────────────────────────────────
Set-Location $ROOT
git add web_app.py CHANGELOG.md CLAUDE.md MANUAL.md "build\ActivityTracker.iss"
git add -u
$commitMsg = "Releaseförberedelser $VERSION ($today)"
git commit -m $commitMsg
Write-Host "Commit skapad: $commitMsg" -ForegroundColor Green

git push origin master
Write-Host "Pushad till origin/master" -ForegroundColor Green

# ── 7. PyInstaller ───────────────────────────────────────────────────────────
Write-Host "Bygger exe med PyInstaller..." -ForegroundColor Cyan
python -m PyInstaller $SPEC --distpath "$ROOT\build\dist" --workpath "$ROOT\build\work" --noconfirm
if ($LASTEXITCODE -ne 0) { Write-Error "PyInstaller misslyckades"; exit 1 }
Write-Host "PyInstaller klar" -ForegroundColor Green

# ── 8. Inno Setup ────────────────────────────────────────────────────────────
Write-Host "Bygger installer med Inno Setup..." -ForegroundColor Cyan
& $ISCC $ISS
if ($LASTEXITCODE -ne 0) { Write-Error "Inno Setup misslyckades"; exit 1 }
$installer = "$ROOT\build\installer\ActivityTracker_Setup_$VERSION.exe"
if (-not (Test-Path $installer)) { Write-Error "Installerfil saknas: $installer"; exit 1 }
$sizeMB = [math]::Round((Get-Item $installer).Length / 1MB, 1)
Write-Host "Installer klar: $installer ($sizeMB MB)" -ForegroundColor Green

# ── 9. Git-tagg ──────────────────────────────────────────────────────────────
git tag $VERSION
git push origin $VERSION
Write-Host "Tagg $VERSION pushad" -ForegroundColor Green

# ── 10. GitHub Release ───────────────────────────────────────────────────────
Write-Host "Skapar GitHub Release..." -ForegroundColor Cyan

# Hämta releasenotes ur CHANGELOG (allt under versionsrubriken fram till nästa ##)
$clLines   = Get-Content $CHANGELOG
$inSection = $false
$notes     = @()
foreach ($line in $clLines) {
    if ($line -match "^## $([regex]::Escape($VERSION))") { $inSection = $true; continue }
    if ($inSection -and $line -match "^## ") { break }
    if ($inSection) { $notes += $line }
}
$releaseNotes = ($notes | Where-Object { $_ -ne "" }) -join "`n"

$assetLabel = "ActivityTracker_Setup_$VERSION.exe"
gh release create $VERSION "$installer#$assetLabel" --title $VERSION --notes $releaseNotes

Write-Host ""
Write-Host "Klar! $VERSION publicerad:" -ForegroundColor Cyan
Write-Host "https://github.com/MarcusNygren514/activity-tracker/releases/tag/$VERSION"

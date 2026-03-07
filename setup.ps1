# Talon Pack Setup Script (PowerShell)
# Adds the tpack function and optional tab completion to your PowerShell profile.

$ErrorActionPreference = "Stop"

function Write-Info($msg)    { Write-Host $msg -ForegroundColor Cyan }
function Write-Success($msg) { Write-Host $msg -ForegroundColor Green }
function Write-Warn($msg)    { Write-Host $msg -ForegroundColor Yellow }
function Write-Err($msg)     { Write-Host $msg -ForegroundColor Red }

function Confirm-Prompt($msg) {
    $response = Read-Host "$msg [Y/n]"
    return ($response -eq '' -or $response -match '^[yY]')
}

# --- Detect paths ---
$talonPython = "C:\Program Files\Talon\python.exe"
$tpackScript = "$env:APPDATA\talon\talon-pack\tpack.py"

if (-not (Test-Path $talonPython)) {
    Write-Warn "Talon Python not found at '$talonPython'"
    Write-Warn "You may need to adjust the path manually after setup"
}

if (-not (Test-Path $tpackScript)) {
    Write-Warn "tpack.py not found at '$tpackScript'"
}

$profilePath = $PROFILE

Write-Host ""
Write-Info "Talon Pack Setup (PowerShell)"
Write-Host ([string]::new([char]0x2500, 36))
Write-Host ""
Write-Info "Profile: $profilePath"
Write-Host ""

# --- Check what already exists ---
$hasFunction = $false
$hasCompletion = $false

if (Test-Path $profilePath) {
    $content = Get-Content $profilePath -Raw -ErrorAction SilentlyContinue
    if ($content -match 'function tpack\b') { $hasFunction = $true }
    if ($content -match '# --- tpack tab completion ---') { $hasCompletion = $true }
}

if ($hasFunction -and $hasCompletion) {
    Write-Success "Already set up! Function and tab completion found in $profilePath"
    Write-Host ""
    return
}

# --- Create profile if needed ---
if (-not (Test-Path $profilePath)) {
    $profileDir = Split-Path $profilePath -Parent
    if (-not (Test-Path $profileDir)) {
        New-Item -ItemType Directory -Path $profileDir -Force | Out-Null
    }
    New-Item -ItemType File -Path $profilePath -Force | Out-Null
}

# Save backup for diff
$backup = [System.IO.Path]::GetTempFileName()
Copy-Item $profilePath $backup

# --- Function ---
if ($hasFunction) {
    Write-Success "tpack function already exists in profile (skipping)"
    Write-Host ""
} else {
    $functionBlock = @"

# --- tpack function ---
function tpack { & "$talonPython" "$tpackScript" @args }
# --- end tpack function ---
"@

    Write-Host "The following will be added to " -NoNewline
    Write-Host $profilePath -ForegroundColor White -NoNewline
    Write-Host ":"
    Write-Host ""
    Write-Host "  function tpack { & `"$talonPython`" `"$tpackScript`" @args }" -ForegroundColor Green
    Write-Host ""

    if (Confirm-Prompt "Add function?") {
        Add-Content -Path $profilePath -Value $functionBlock
        Write-Success "Function added."
    } else {
        Write-Info "Function skipped."
    }
    Write-Host ""
}

# --- Tab completion ---
if ($hasCompletion) {
    Write-Success "Tab completion already exists in profile (skipping)"
    Write-Host ""
} else {
    if (Confirm-Prompt "Add tab completion?") {
        $completionBlock = @'

# --- tpack tab completion ---
Register-ArgumentCompleter -CommandName tpack -ScriptBlock {
    param($wordToComplete, $commandAst, $cursorPosition)
    $commands = @(
        'info', 'patch', 'minor', 'major', 'version',
        'install', 'update', 'outdated', 'sync',
        'pip', 'generate', 'help'
    )
    $generateTypes = @(
        'manifest', 'version', 'readme', 'shields',
        'duplicate-check', 'install-block'
    )
    $pipCmds = @('add', 'remove', 'list')
    $flags = @(
        '--dry-run', '--yes', '-y', '-v', '--verbose',
        '--no-manifest', '--no-version', '--no-readme',
        '--no-shields', '--no-duplicate-check', '--help'
    )

    $tokens = $commandAst.ToString() -split '\s+'
    $position = $tokens.Count

    if ($position -le 1 -or ($position -eq 2 -and $wordToComplete)) {
        ($commands + $flags) | Where-Object { $_ -like "$wordToComplete*" } |
            ForEach-Object { [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_) }
    } elseif ($tokens[1] -eq 'generate') {
        $generateTypes | Where-Object { $_ -like "$wordToComplete*" } |
            ForEach-Object { [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_) }
    } elseif ($tokens[1] -eq 'pip') {
        $pipCmds | Where-Object { $_ -like "$wordToComplete*" } |
            ForEach-Object { [System.Management.Automation.CompletionResult]::new($_, $_, 'ParameterValue', $_) }
    }
}
# --- end tpack tab completion ---
'@
        Add-Content -Path $profilePath -Value $completionBlock
        Write-Success "Tab completion added."
    }
    Write-Host ""
}

# --- Show diff ---
$oldContent = Get-Content $backup -ErrorAction SilentlyContinue
$newContent = Get-Content $profilePath -ErrorAction SilentlyContinue

if ($null -eq $oldContent) { $oldContent = @() }
if ($null -eq $newContent) { $newContent = @() }

$diff = Compare-Object -ReferenceObject $oldContent -DifferenceObject $newContent -PassThru

if ($diff) {
    Write-Host ""
    Write-Info "Changes made to ${profilePath}:"
    Write-Host ([string]::new([char]0x2500, 36))
    foreach ($line in $newContent) {
        if ($line -notin $oldContent) {
            Write-Host "+ $line" -ForegroundColor Green
        } else {
            Write-Host "  $line"
        }
    }
    Write-Host ([string]::new([char]0x2500, 36))

    Write-Host ""
    Write-Info "Run this to activate:"
    Write-Host ""
    Write-Host "  . `$PROFILE" -ForegroundColor White
    Write-Host ""
} else {
    Write-Info "No changes were made."
}

Remove-Item $backup -ErrorAction SilentlyContinue

Write-Host ""
Write-Success "Setup complete! Try: tpack --help"
Write-Host ""

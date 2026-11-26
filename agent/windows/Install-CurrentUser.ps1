# Explicit per-user provisioning; -Check is read-only, -Install installs Python and agent.
[CmdletBinding()]
param(
    [switch]$Install,
    [string]$BootstrapPath = ''
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (-not $BootstrapPath) {
    $BootstrapPath = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) 'Bootstrap.ps1'
}
$user = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$session = [Diagnostics.Process]::GetCurrentProcess().SessionId
$interactive = [Environment]::UserInteractive -and $session -gt 0
$root = Join-Path $env:LOCALAPPDATA 'LunexPCControl'
$python = Get-Command python3.14 -ErrorAction SilentlyContinue
$launcher = Get-Command py -ErrorAction SilentlyContinue
$localPython = Join-Path $env:LOCALAPPDATA 'Programs\Python\Python314\python.exe'
$has314 = [bool]$python -or (Test-Path -LiteralPath $localPython -PathType Leaf)
if (-not $has314 -and $launcher) {
    $versions = (& py -0p 2>$null | Out-String)
    $has314 = ($LASTEXITCODE -eq 0 -and $versions -match '-V:3\.14')
}
$git = [bool](Get-Command git -ErrorAction SilentlyContinue)
$ssh = [bool](Get-Command ssh -ErrorAction SilentlyContinue)
[pscustomobject]@{
    Account = $user
    SessionId = $session
    Interactive = [bool]$interactive
    Python314Available = [bool]$has314
    GitAvailable = $git
    OpenSSHAvailable = $ssh
    UserInstallRoot = $root
    InstallRequested = [bool]$Install
} | Format-List
if (-not $Install) {
    Write-Output 'Read-only check completed. To install for the CURRENT user, rerun with -Install.'
    exit 0
}
if (-not $interactive) {
    throw 'Install-CurrentUser -Install must run in the intended interactive Windows user session.'
}
if (-not $git -or -not $ssh) {
    throw 'Git and OpenSSH must be available before provisioning.'
}
if (-not (Test-Path -LiteralPath $BootstrapPath -PathType Leaf)) {
    throw 'Missing local Bootstrap.ps1. Verify this repository checkout first.'
}
if (-not $has314) {
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if (-not $winget) { throw 'winget unavailable; install Python 3.14 manually for this account.' }
    & $winget.Source install --id Python.Python.3.14 --exact --scope user --silent --disable-interactivity --accept-source-agreements --accept-package-agreements --no-upgrade
    if ($LASTEXITCODE -ne 0) { throw 'Per-user Python installation failed' }
}
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $BootstrapPath -Install
if ($LASTEXITCODE -ne 0) { throw 'Agent installation failed' }
Write-Output 'Current-user agent dependencies provisioned. No agent started; no autostart configured.'

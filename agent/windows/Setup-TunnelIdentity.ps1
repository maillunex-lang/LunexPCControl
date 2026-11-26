# Per-user SSH identity. Never uses or modifies the default SSH key directory.
[CmdletBinding()]
param(
    [string]$ScriptPath = ''
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (-not $ScriptPath) {
    $ScriptPath = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) 'provision_device_tunnel.py'
}
$session = [Diagnostics.Process]::GetCurrentProcess().SessionId
if (-not [Environment]::UserInteractive -or $session -le 0) {
    throw 'Run only in the intended interactive Windows user session'
}
$root = Join-Path $env:LOCALAPPDATA 'LunexPCControl'
$python = Join-Path $root '.venv\Scripts\python.exe'
$folder = Join-Path $root 'ssh'
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw 'Install the per-user Windows-MCP environment first'
}
if (-not (Test-Path -LiteralPath $ScriptPath -PathType Leaf)) {
    throw 'Missing tunnel identity script'
}
New-Item -ItemType Directory -Path $folder -Force | Out-Null
# Prevent a different interactive user from reading the unencrypted key file.
$account = [Security.Principal.WindowsIdentity]::GetCurrent().Name
& icacls.exe $folder /inheritance:r /grant:r "$($account):(OI)(CI)F" 'SYSTEM:(OI)(CI)F' | Out-Null
if ($LASTEXITCODE -ne 0) { throw 'Could not restrict SSH identity folder ACL' }
$export = 'C:\Users\Public\LunexPCControl-device.pub'
$trustedHostKey = 'C:\Users\Public\LunexPCControl-vps-hostkey.pub'
if (Test-Path -LiteralPath $trustedHostKey -PathType Leaf) {
    & $python $ScriptPath --folder $folder --public-export $export --host-key-file $trustedHostKey
} else {
    & $python $ScriptPath --folder $folder --public-export $export
}
if ($LASTEXITCODE -ne 0) { throw 'SSH key provisioning failed' }
Write-Output 'SSH identity prepared for current user. No connection opened.'

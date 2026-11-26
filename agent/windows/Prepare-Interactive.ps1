# Read-only interactive-session preflight. No software installs, no secrets, no agent start.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$account = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$sessionId = [Diagnostics.Process]::GetCurrentProcess().SessionId
$interactive = [Environment]::UserInteractive -and $sessionId -gt 0
$root = Join-Path $env:LOCALAPPDATA 'LunexPCControl'
$agent = Join-Path $root '.venv\Scripts\windows-mcp.exe'
$py = Get-Command py -ErrorAction SilentlyContinue
$git = Get-Command git -ErrorAction SilentlyContinue
$ssh = Get-Command ssh -ErrorAction SilentlyContinue
$explorer = @(Get-Process explorer -ErrorAction SilentlyContinue | Where-Object { $_.SessionId -eq $sessionId }).Count -gt 0
[pscustomobject]@{
    Account = $account
    SessionId = $sessionId
    InteractiveSession = [bool]$interactive
    ExplorerInSession = [bool]$explorer
    PythonLauncherAvailable = [bool]$py
    GitAvailable = [bool]$git
    OpenSSHAvailable = [bool]$ssh
    AgentPresentForThisUser = [bool](Test-Path -LiteralPath $agent -PathType Leaf)
    UserInstallRoot = $root
} | Format-List

# Read-only diagnostics. Run in the SAME Windows account/session as the intended desktop agent.
[CmdletBinding()]
param(
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA 'LunexPCControl'),
    [ValidateRange(1024,65535)][int]$AgentPort = 18789
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$sessionId = [Diagnostics.Process]::GetCurrentProcess().SessionId
$account = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$interactive = [Environment]::UserInteractive -and $sessionId -gt 0
$explorerSession = @(Get-Process explorer -ErrorAction SilentlyContinue |
    Where-Object { $_.SessionId -eq $sessionId }).Count -gt 0
$exe = Join-Path $InstallRoot '.venv\Scripts\windows-mcp.exe'
$agentInstalled = Test-Path -LiteralPath $exe -PathType Leaf
$listener = @(Get-NetTCPConnection -LocalPort $AgentPort -State Listen -ErrorAction SilentlyContinue)
$remoteListener = @($listener | Where-Object { $_.LocalAddress -notin @('127.0.0.1','::1') }).Count -gt 0
[pscustomobject]@{
    Account = $account
    SessionId = $sessionId
    InteractiveSession = [bool]$interactive
    ExplorerInSession = [bool]$explorerSession
    AgentInstalledForThisUser = [bool]$agentInstalled
    AgentPath = $exe
    PortInUse = [bool]($listener.Count -gt 0)
    NonLoopbackListener = [bool]$remoteListener
    ReadyForScreenshotTest = [bool]($interactive -and $explorerSession -and $agentInstalled -and -not $listener.Count)
} | Format-List

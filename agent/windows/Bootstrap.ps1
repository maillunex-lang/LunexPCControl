# LunexPCControl Windows agent bootstrap.
# Run from an interactive user desktop session. No automatic installation occurs
# unless explicitly requested with -Install. Do not store credentials in this file.
[CmdletBinding()]
param(
    [switch]$Install,
    [switch]$Start,
    [string]$InstallRoot = (Join-Path $env:LOCALAPPDATA "LunexPCControl"),
    [string]$UpstreamRepository = "https://github.com/CursorTouch/Windows-MCP.git",
    [string]$UpstreamCommit = "3333dbdac75ea3cae2a1eea00dccb207db9c5e4d",
    [ValidateRange(1024,65535)][int]$AgentPort = 18789
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
function Find-Python314 {
    $launcher = Get-Command py -ErrorAction SilentlyContinue
    if ($launcher) {
        # Native py.exe may emit a non-terminating PowerShell error in 5.1.
        # Check installed interpreters before probing a specific version.
        $versions = (& py -0p 2>$null | Out-String)
        if ($LASTEXITCODE -eq 0 -and $versions -match '-V:3\.14') {
            $candidate = (& py -3.14 -c "import sys;print(sys.executable)" 2>$null)
            if ($LASTEXITCODE -eq 0 -and $candidate) {
                return [string]($candidate | Select-Object -First 1)
            }
        }
    }
    $python = Get-Command python3.14 -ErrorAction SilentlyContinue
    if ($python) { return $python.Source }
    return $null
}
function Require-InteractiveDesktop {
    if (-not [Environment]::UserInteractive) {
        throw 'Agent must be started in an interactive user session.'
    }
}
function Get-State {
    $py = Find-Python314
    $git = Get-Command git -ErrorAction SilentlyContinue
    $ssh = Get-Command ssh -ErrorAction SilentlyContinue
    [pscustomobject]@{
        Python314Available = [bool]$py
        PythonExecutable = $py
        GitAvailable = [bool]$git
        OpenSSHAvailable = [bool]$ssh
        InstallRoot = $InstallRoot
        AgentPort = $AgentPort
        UpstreamCommit = $UpstreamCommit
        ReadyToInstall = [bool]($py -and $git -and $ssh)
    }
}
$state = Get-State
if (-not $Install -and -not $Start) {
    $state | Format-List
    exit 0
}
Require-InteractiveDesktop
if (-not $state.ReadyToInstall) {
    throw 'Prerequisites missing: require Python 3.14+, Git and OpenSSH. No system Python changes were made.'
}
$repoDir = Join-Path $InstallRoot "upstream"
$venvDir = Join-Path $InstallRoot ".venv"
if ($Install) {
    New-Item -ItemType Directory -Path $InstallRoot -Force | Out-Null
    if (Test-Path $repoDir) {
        throw "Existing checkout detected at $repoDir. Refusing to overwrite it."
    }
    & git clone --no-checkout -- $UpstreamRepository $repoDir
    if ($LASTEXITCODE -ne 0) { throw 'Clone failed' }
    & git -C $repoDir checkout --detach $UpstreamCommit
    if ($LASTEXITCODE -ne 0) { throw 'Pinned checkout failed' }
    & $state.PythonExecutable -m venv $venvDir
    if ($LASTEXITCODE -ne 0) { throw 'Virtualenv creation failed' }
    $pip = Join-Path $venvDir "Scripts\python.exe"
    & $pip -m pip install --disable-pip-version-check $repoDir
    if ($LASTEXITCODE -ne 0) { throw 'Isolated package installation failed' }
    Write-Output "Installed isolated agent dependencies at $InstallRoot"
}
if ($Start) {
    if (-not (Test-Path (Join-Path $venvDir "Scripts\windows-mcp.exe"))) {
        throw 'Agent not installed; run Bootstrap.ps1 -Install explicitly first.'
    }
    if (-not $env:WINDOWS_MCP_AUTH_KEY -or $env:WINDOWS_MCP_AUTH_KEY.Length -lt 24) {
        throw 'Set WINDOWS_MCP_AUTH_KEY securely for the current process before starting.'
    }
    $env:ANONYMIZED_TELEMETRY = 'false'
    $agent = Join-Path $venvDir "Scripts\windows-mcp.exe"
    & $agent serve --transport streamable-http --host 127.0.0.1 --port $AgentPort
    if ($LASTEXITCODE -ne 0) { throw 'Windows-MCP exited with a failure' }
}

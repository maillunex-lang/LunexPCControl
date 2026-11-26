# REL-01 interactive per-user supervisor. Deliberately no autostart until approved.
# Handles an interactive Windows MCP agent and outbound SSH reverse tunnel.
[CmdletBinding()]
param(
    [ValidateSet('Check','Run')][string]$Mode = 'Check',
    [ValidateRange(2,120)][int]$RetrySeconds = 10,
    [ValidateRange(1,30)][int]$MaxRetries = 8,
    [string]$InstallRoot = '',
    [switch]$StopOnDisconnect
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
if (-not $InstallRoot) {
    $InstallRoot = Join-Path $env:LOCALAPPDATA 'LunexPCControl'
}
$supervisorIdentity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$session = [Diagnostics.Process]::GetCurrentProcess().SessionId
$isInteractive = [Environment]::UserInteractive -and $session -gt 0
$agent = Join-Path $InstallRoot '.venv\Scripts\windows-mcp.exe'
$sshTunnel = Join-Path (Split-Path -Parent $MyInvocation.MyCommand.Path) 'Start-ReverseTunnel.ps1'
$identity = Join-Path $InstallRoot 'ssh\id_ed25519'
$hostsFile = Join-Path $InstallRoot 'ssh\known_hosts'
$agentPresent = Test-Path -LiteralPath $agent -PathType Leaf
$tunnelScriptPresent = Test-Path -LiteralPath $sshTunnel -PathType Leaf
$identityPresent = Test-Path -LiteralPath $identity -PathType Leaf
$hostsPresent = Test-Path -LiteralPath $hostsFile -PathType Leaf
if ($Mode -eq 'Check') {
    [pscustomobject]@{
        Account = $supervisorIdentity
        SessionId = $session
        Interactive = $isInteractive
        AgentInstalled = $agentPresent
        TunnelScriptAvailable = $tunnelScriptPresent
        TunnelIdentityAvailable = $identityPresent
        PinnedHostKeyAvailable = $hostsPresent
        EligibleForRun = ($isInteractive -and $agentPresent -and $tunnelScriptPresent -and $identityPresent -and $hostsPresent)
        AutoStartConfiguredByThisScript = $false
    } | Format-List
    return
}
if (-not $isInteractive) { throw 'Refusing to run agent outside the logged-in interactive Windows user session' }
if (-not ($agentPresent -and $tunnelScriptPresent -and $identityPresent -and $hostsPresent)) {
    throw 'Agent, tunnel script, or pinned SSH credentials missing; run Check first'
}
# Never spawn any shell or arbitrary command through this supervisor.
$processes = [System.Collections.Generic.List[System.Diagnostics.Process]]::new()
try {
    $retry = 0
    while ($retry -lt $MaxRetries) {
        $agentProcess = Start-Process -FilePath $agent -ArgumentList @(
            'serve','--transport','streamable-http','--host','127.0.0.1','--port','18789','--tools','Screenshot','ControlStatus','--control-policy','strict'
        ) -PassThru -WindowStyle Hidden
        $processes.Add($agentProcess)
        $listening = $false
        for ($probe = 0; $probe -lt 10; $probe++) {
            if ($agentProcess.HasExited) { break }
            try {
                $client = New-Object System.Net.Sockets.TcpClient
                try {
                    $connected = $client.ConnectAsync('127.0.0.1',18789).Wait(1000)
                    if ($connected -and $client.Connected) { $listening = $true; break }
                } finally { $client.Dispose() }
            } catch {}
            Start-Sleep -Milliseconds 500
        }
        if ($agentProcess.HasExited -or -not $listening) {
            $retry++
            Write-Warning "Windows MCP was not ready before tunnel establishment (attempt $retry)"
            if (-not $agentProcess.HasExited) { Stop-Process -Id $agentProcess.Id -ErrorAction SilentlyContinue }
            if ($retry -lt $MaxRetries) { Start-Sleep -Seconds $RetrySeconds }
            continue
        }
        $tunnelProcess = Start-Process -FilePath 'powershell.exe' -ArgumentList @(
            '-NoProfile','-ExecutionPolicy','Bypass','-File', ('"' + $sshTunnel + '"')
        ) -PassThru -WindowStyle Hidden
        $processes.Add($tunnelProcess)
        try {
            while (-not $tunnelProcess.HasExited -and -not $agentProcess.HasExited) {
                Start-Sleep -Seconds 3
            }
        }
        finally {
            if (-not $tunnelProcess.HasExited) { Stop-Process -Id $tunnelProcess.Id -ErrorAction SilentlyContinue }
            if (-not $agentProcess.HasExited) { Stop-Process -Id $agentProcess.Id -ErrorAction SilentlyContinue }
        }
        $retry++
        if ($StopOnDisconnect) { break }
        Write-Warning "Agent/tunnel disconnected; retry attempt $retry of $MaxRetries"
        if ($retry -lt $MaxRetries) { Start-Sleep -Seconds $RetrySeconds }
    }
}
finally {
    # Kill only child processes that were created by this supervisor.
    foreach ($child in $processes) {
        try {
            if (-not $child.HasExited) { Stop-Process -Id $child.Id -ErrorAction SilentlyContinue }
        } catch {}
    }
}

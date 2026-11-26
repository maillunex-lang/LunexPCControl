# REL-01 interactive per-user supervisor. Deliberately no autostart until approved.
# Handles an interactive Windows MCP agent and outbound SSH reverse tunnel.
[CmdletBinding()]
param(
    [ValidateSet('Check','Run')][string]$Mode = 'Check',
    [ValidateRange(2,120)][int]$RetrySeconds = 5,
    [ValidateRange(0,30)][int]$MaxRetries = 0,
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
$authFile = Join-Path $InstallRoot 'integration\upstream.key'
$authFilePresent = Test-Path -LiteralPath $authFile -PathType Leaf
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
        PrivateMcpCredentialAvailable = $authFilePresent
        EligibleForRun = ($isInteractive -and $agentPresent -and $tunnelScriptPresent -and $identityPresent -and $hostsPresent -and $authFilePresent)
        AutoStartConfiguredByThisScript = $false
        RetryMode = $(if ($MaxRetries -eq 0) { 'unlimited, until stopped' } else { "capped at $MaxRetries" })
        OutboundOnly = $true
        DynamicClientIpSupported = $true
    } | Format-List
    return
}
if (-not $isInteractive) { throw 'Refusing to run agent outside the logged-in interactive Windows user session' }
if (-not ($agentPresent -and $tunnelScriptPresent -and $identityPresent -and $hostsPresent -and $authFilePresent)) {
    throw 'Agent, tunnel script, pinned SSH identity or private MCP credential missing; run Check first'
}
if ((Get-Item -LiteralPath $authFile).Attributes -band [IO.FileAttributes]::ReparsePoint) {
    throw 'Refusing redirected MCP credential file'
}
# The sole credential source is an ACL-restricted file in the interactive
# user's profile. Never put the plaintext token on a process command line.
$key = [IO.File]::ReadAllText($authFile).Trim()
if ($key.Length -lt 32 -or $key.Length -gt 128 -or $key -notmatch '^[A-Za-z0-9_-]+$') {
    throw 'Malformed private MCP credential'
}
if (Get-NetTCPConnection -LocalPort 18789 -State Listen -ErrorAction SilentlyContinue) {
    throw 'Local MCP port 18789 is already bound; refusing duplicate instance'
}
$existingTunnel = @(Get-CimInstance Win32_Process -Filter 'name="ssh.exe"' -ErrorAction SilentlyContinue |
    Where-Object { $_.SessionId -eq $session -and
      $_.CommandLine -like '*lunexpc-tunnel@195.216.188.80*' -and
      $_.CommandLine -like '*127.0.0.1:23789:127.0.0.1:18789*' })
if ($existingTunnel.Count -gt 0) { throw 'A matching SSH tunnel is already running in this Windows session' }
# The tunnel is not opened until an unauthenticated request is rejected.
function Test-McpAuthentication {
    $req = [System.Net.HttpWebRequest]::Create('http://127.0.0.1:18789/mcp')
    $req.Method = 'POST'
    $req.Timeout = 6000
    $req.ContentType = 'application/json'
    $req.Accept = 'application/json, text/event-stream'
    $body = '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-06-18","capabilities":{},"clientInfo":{"name":"lunexpc-auth-probe","version":"1"}}}'
    $bytes = [Text.Encoding]::UTF8.GetBytes($body)
    $req.ContentLength = $bytes.Length
    $stream = $req.GetRequestStream()
    try { $stream.Write($bytes, 0, $bytes.Length) } finally { $stream.Dispose() }
    try {
        $response = $req.GetResponse()
        try { return $false } finally { $response.Dispose() }
    } catch [Net.WebException] {
        $response = $_.Exception.Response
        if ($null -eq $response) { throw }
        try { return ([int]$response.StatusCode -eq 401) }
        finally { $response.Dispose() }
    }
}
# Never spawn any shell or arbitrary command through this supervisor.
$processes = [System.Collections.Generic.List[System.Diagnostics.Process]]::new()
$priorAuth = [Environment]::GetEnvironmentVariable('WINDOWS_MCP_AUTH_KEY', 'Process')
function Get-RetryDelay([int]$attempt) {
    # Bounded exponential backoff makes router failover and dynamic IP
    # changes recover without flooding the remote SSH service.
    $power = [Math]::Min([Math]::Max($attempt - 1, 0), 5)
    return [int][Math]::Min(120, $RetrySeconds * [Math]::Pow(2, $power))
}
function Stop-OwnedTunnel {
    # We checked no matching SSH tunnel existed before launching ours.
    # Windows PowerShell can exit before its spawned ssh.exe child.
    $owned = @(Get-CimInstance Win32_Process -Filter 'name="ssh.exe"' -ErrorAction SilentlyContinue |
        Where-Object { $_.SessionId -eq $session -and
            $_.CommandLine -like '*lunexpc-tunnel@195.216.188.80*' -and
            $_.CommandLine -like '*127.0.0.1:23789:127.0.0.1:18789*' })
    foreach ($entry in $owned) {
        Stop-Process -Id $entry.ProcessId -Force -ErrorAction SilentlyContinue
    }
}
function Stop-SupervisedTree([System.Diagnostics.Process]$child) {
    if ($null -eq $child) { return }
    try {
        if (-not $child.HasExited) {
            & taskkill.exe /PID ([string]$child.Id) /T /F 2>$null | Out-Null
        }
    } catch {}
}
try {
    $env:WINDOWS_MCP_AUTH_KEY = $key
    $retry = 0
    while ($MaxRetries -eq 0 -or $retry -lt $MaxRetries) {
        $agentProcess = Start-Process -FilePath $agent -ArgumentList @(
            'serve','--transport','streamable-http','--host','127.0.0.1','--port','18789','--tools','Screenshot,ControlStatus','--control-policy','balanced'
        ) -PassThru -WindowStyle Hidden
        $processes.Add($agentProcess)
        $listening = $false
        for ($probe = 0; $probe -lt 45; $probe++) {
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
            $failure = if ($agentProcess.HasExited) { "process exited with code $($agentProcess.ExitCode)" } else { 'port 18789 did not become ready' }
            Write-Warning "Windows MCP was not ready ($failure; attempt $retry)"
            Stop-SupervisedTree $agentProcess
            if ($MaxRetries -eq 0 -or $retry -lt $MaxRetries) {
                Start-Sleep -Seconds (Get-RetryDelay $retry)
            }
            continue
        }
        # A successful TCP connection is not proof of authentication.
        if (-not (Test-McpAuthentication)) {
            throw 'Windows MCP accepted unauthenticated initialize; refusing tunnel'
        }
        $shellExecutable = Join-Path $PSHOME 'powershell.exe'
        $tunnelProcess = Start-Process -FilePath $shellExecutable -ArgumentList @(
            '-NoProfile','-ExecutionPolicy','Bypass','-File', ('"' + $sshTunnel + '"')
        ) -PassThru -WindowStyle Hidden
        $processes.Add($tunnelProcess)
        $connectionStarted = Get-Date
        try {
            while (-not $tunnelProcess.HasExited -and -not $agentProcess.HasExited) {
                Start-Sleep -Seconds 3
            }
        }
        finally {
            Stop-SupervisedTree $tunnelProcess
            Stop-OwnedTunnel
            Stop-SupervisedTree $agentProcess
        }
        if ($StopOnDisconnect) { break }
        # Healthy sessions reset the failure counter. Network changes,
        # sleep/wake and a new DHCP address do not consume a finite budget.
        $connectedSeconds = ((Get-Date) - $connectionStarted).TotalSeconds
        if ($connectedSeconds -gt 90) { $retry = 0 }
        $retry++
        Write-Warning "Agent/tunnel disconnected; retry attempt $retry"
        if ($MaxRetries -eq 0 -or $retry -lt $MaxRetries) {
            Start-Sleep -Seconds (Get-RetryDelay $retry)
        }
    }
}
finally {
    # Kill only process trees started by this supervisor, including child
    # ssh.exe spawned by powershell.exe; never leave detached SSH tunnels.
    foreach ($child in $processes) { Stop-SupervisedTree $child }
    Stop-OwnedTunnel
    [Environment]::SetEnvironmentVariable('WINDOWS_MCP_AUTH_KEY', $priorAuth, 'Process')
    $key = $null
}

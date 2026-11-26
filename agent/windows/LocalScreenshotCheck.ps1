# Explicit temporary screenshot-only MCP self-test. No persisted credentials/screenshots.
[CmdletBinding()]
param([ValidateRange(1024,65535)][int]$AgentPort=18789)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$sessionId=[Diagnostics.Process]::GetCurrentProcess().SessionId
if (-not [Environment]::UserInteractive -or $sessionId -le 0) {
    throw 'Requires an interactive Windows session; Session 0 is prohibited.'
}
$root=Join-Path $env:LOCALAPPDATA 'LunexPCControl'
$exe=Join-Path $root '.venv\Scripts\windows-mcp.exe'
$py=Join-Path $root '.venv\Scripts\python.exe'
$client=Join-Path $PSScriptRoot 'smoke_screenshot.py'
if(-not(Test-Path -LiteralPath $exe -PathType Leaf) -or -not(Test-Path -LiteralPath $py -PathType Leaf) -or -not(Test-Path -LiteralPath $client -PathType Leaf)) {
    throw 'Missing current-user MCP executable or smoke test.'
}
if(Get-NetTCPConnection -LocalPort $AgentPort -State Listen -ErrorAction SilentlyContinue) {
    throw 'MCP test port already in use. Refusing to connect to an unknown process.'
}
$previousKey=[Environment]::GetEnvironmentVariable('WINDOWS_MCP_AUTH_KEY','Process')
$previousTelemetry=[Environment]::GetEnvironmentVariable('ANONYMIZED_TELEMETRY','Process')
$secret=[Convert]::ToBase64String((1..48 | ForEach-Object { Get-Random -Minimum 0 -Maximum 256 } | ForEach-Object {[byte]$_}))
$env:WINDOWS_MCP_AUTH_KEY=$secret
$env:ANONYMIZED_TELEMETRY='false'
$proc=$null
try {
    $proc=Start-Process -FilePath $exe -ArgumentList @('serve','--transport','streamable-http','--host','127.0.0.1','--port',([string]$AgentPort),'--tools','Screenshot','--control-policy','strict') -PassThru -WindowStyle Hidden
    $ready=$false
    for($i=0;$i -lt 30;$i++) {
        if($proc.HasExited) { throw ('Agent exited before becoming ready: '+$proc.ExitCode) }
        if(Get-NetTCPConnection -LocalAddress '127.0.0.1' -LocalPort $AgentPort -State Listen -ErrorAction SilentlyContinue) {$ready=$true;break}
        Start-Sleep -Milliseconds 500
    }
    if(-not $ready) {throw 'Agent did not open loopback MCP port'}
    & $py $client --endpoint ('http://127.0.0.1:'+ $AgentPort +'/mcp')
    if($LASTEXITCODE -ne 0) {throw 'Screenshot MCP smoke test failed'}
    Write-Output 'LOCAL-MCP-SCREENSHOT-CHECK=PASS'
} finally {
    if($proc -and -not $proc.HasExited){Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue}
    [Environment]::SetEnvironmentVariable('WINDOWS_MCP_AUTH_KEY',$previousKey,'Process')
    [Environment]::SetEnvironmentVariable('ANONYMIZED_TELEMETRY',$previousTelemetry,'Process')
}

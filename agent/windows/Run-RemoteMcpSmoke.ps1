# Supervised Windows MCP endpoint + reverse SSH test.
# No persistent bearer tokens, no Windows service, no autostart.
[CmdletBinding()]
param(
 [ValidateRange(1,120)][int]$DurationSeconds=100
)
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$session=[Diagnostics.Process]::GetCurrentProcess().SessionId
if(-not [Environment]::UserInteractive -or $session -le 0) {
 throw 'Run in intended interactive Windows session, not Session 0'
}
$root=Join-Path $env:LOCALAPPDATA 'LunexPCControl'
$agent=Join-Path $root '.venv\Scripts\windows-mcp.exe'
$ssh=Get-Command ssh.exe -ErrorAction Stop
$identity=Join-Path $root 'ssh\id_ed25519'
$known=Join-Path $root 'ssh\known_hosts'
if(-not (Test-Path $agent) -or -not (Test-Path $identity) -or -not (Test-Path $known)) {
 throw 'Missing installed MCP agent or registered SSH device identity'
}
if(Get-NetTCPConnection -LocalPort 18789 -State Listen -ErrorAction SilentlyContinue) {
 throw 'Local Windows-MCP port already in use'
}
$incoming=Join-Path $root 'integration\upstream.key'
if(-not(Test-Path -LiteralPath $incoming -PathType Leaf)) {
 throw 'Test credential not yet provisioned for this Windows user'
}
$key=(Get-Content -LiteralPath $incoming -Raw).Trim()
if($key.Length -lt 32){throw 'Invalid temporary test key'}
$prev=[Environment]::GetEnvironmentVariable('WINDOWS_MCP_AUTH_KEY','Process')
$prevTelemetry=[Environment]::GetEnvironmentVariable('ANONYMIZED_TELEMETRY','Process')
$env:WINDOWS_MCP_AUTH_KEY=$key
$env:ANONYMIZED_TELEMETRY='false'
$proc=$null
$tunnel=$null
try {
 $proc=Start-Process -FilePath $agent -ArgumentList @('serve','--transport','streamable-http','--host','127.0.0.1','--port','18789','--tools','Screenshot','--control-policy','strict') -WindowStyle Hidden -PassThru
 $ready=$false
 for($i=0;$i -lt 45;$i++){
  if($proc.HasExited){throw ('Agent exited '+$proc.ExitCode)}
  if(Get-NetTCPConnection -LocalAddress '127.0.0.1' -LocalPort 18789 -State Listen -ErrorAction SilentlyContinue){$ready=$true;break}
  Start-Sleep -Milliseconds 500
 }
 if(-not $ready){throw 'Windows agent did not start'}
 $forward='127.0.0.1:23789:127.0.0.1:18789'
 $sshArgs=@('-F','none','-o','BatchMode=yes','-o','PreferredAuthentications=publickey','-o','PasswordAuthentication=no',
 '-o','KbdInteractiveAuthentication=no','-o','StrictHostKeyChecking=yes','-o','UpdateHostKeys=no',
 '-o',"UserKnownHostsFile=$known",'-o','GlobalKnownHostsFile=NUL','-o','IdentitiesOnly=yes',
 '-o','HostKeyAlgorithms=rsa-sha2-512,rsa-sha2-256','-o','ExitOnForwardFailure=yes',
 '-o','ConnectTimeout=10','-o','ServerAliveInterval=20','-o','ServerAliveCountMax=3',
 '-i',$identity,'-N','-T','-R',$forward,'lunexpc-tunnel@195.216.188.80')
 $tunnel=Start-Process -FilePath $ssh.Source -ArgumentList $sshArgs -WindowStyle Hidden -PassThru
 # The tunnel's ssh process staying alive is not proof of the remote listener.
 # The VPS test runner separately verifies localhost:23789 before probing MCP.
 Start-Sleep -Seconds 3
 if($tunnel.HasExited){throw ('Reverse tunnel exited '+$tunnel.ExitCode)}
 Write-Output 'REMOTE-MCP-WINDOWS-READY'
 Start-Sleep -Seconds $DurationSeconds
} finally {
 if($tunnel -and -not $tunnel.HasExited){Stop-Process -Id $tunnel.Id -Force -ErrorAction SilentlyContinue}
 if($proc -and -not $proc.HasExited){Stop-Process -Id $proc.Id -Force -ErrorAction SilentlyContinue}
 [Environment]::SetEnvironmentVariable('WINDOWS_MCP_AUTH_KEY',$prev,'Process')
 [Environment]::SetEnvironmentVariable('ANONYMIZED_TELEMETRY',$prevTelemetry,'Process')
 Remove-Item -LiteralPath $incoming -Force -ErrorAction SilentlyContinue
}

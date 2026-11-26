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
if(@(Get-CimInstance Win32_Process -Filter 'name="ssh.exe"' |
    Where-Object { $_.SessionId -eq $session -and
      $_.CommandLine -like '*lunexpc-tunnel@195.216.188.80*' -and
      $_.CommandLine -like '*127.0.0.1:23789:127.0.0.1:18789*' }).Count -gt 0) {
 throw 'Existing device tunnel in this session; refusing to overwrite it'
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
 # Windows-MCP's console launcher can spawn a separate python.exe.
 # Terminate the child process tree, not just the launcher process.
 foreach($child in @($tunnel,$proc)) {
  if($null -ne $child) {
   try { & taskkill.exe /PID ([string]$child.Id) /T /F 2>$null | Out-Null }
   catch { }
  }
 }
 # Verify matching processes in THIS desktop session and stop any launcher
 # children that detached from the original process tree.
 $mcpPort=Get-NetTCPConnection -LocalPort 18789 -State Listen -ErrorAction SilentlyContinue
 foreach($listener in @($mcpPort)) {
  if($null -eq $listener){continue}
  $ps=Get-CimInstance Win32_Process -Filter ('ProcessId='+$listener.OwningProcess) -ErrorAction SilentlyContinue
  if($ps -and $ps.SessionId -eq $session -and
     $ps.CommandLine -like '*LunexPCControl*windows-mcp.exe*' -and
     $ps.CommandLine -like '*--port 18789*') {
   Stop-Process -Id $ps.ProcessId -Force -ErrorAction SilentlyContinue
  }
 }
 $tunnels=@(Get-CimInstance Win32_Process -Filter 'name="ssh.exe"' -ErrorAction SilentlyContinue |
  Where-Object { $_.SessionId -eq $session -and
   $_.CommandLine -like '*lunexpc-tunnel@195.216.188.80*' -and
   $_.CommandLine -like '*127.0.0.1:23789:127.0.0.1:18789*' })
 foreach($sshProcess in $tunnels) {
  Stop-Process -Id $sshProcess.ProcessId -Force -ErrorAction SilentlyContinue
 }
 [Environment]::SetEnvironmentVariable('WINDOWS_MCP_AUTH_KEY',$prev,'Process')
 [Environment]::SetEnvironmentVariable('ANONYMIZED_TELEMETRY',$prevTelemetry,'Process')
 Remove-Item -LiteralPath $incoming -Force -ErrorAction SilentlyContinue
 Write-Output 'REMOTE-MCP-CLEANUP-COMPLETE'
}

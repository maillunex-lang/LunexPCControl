# Foreground-only, pinned-host outbound reverse tunnel. Ctrl+C stops the tunnel.
[CmdletBinding()]
param(
    [ValidateRange(20000,29999)][int]$RemotePort=23789,
    [ValidateRange(1024,65535)][int]$LocalPort=18789,
    [string]$VpsHost='195.216.188.80',
    [string]$TunnelUser='lunexpc-tunnel'
)
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$sessionId = [Diagnostics.Process]::GetCurrentProcess().SessionId
if (-not [Environment]::UserInteractive -or $sessionId -le 0) {
    throw 'Tunnel must run in the intended interactive Windows user session'
}
if ($VpsHost -ne '195.216.188.80' -or $TunnelUser -ne 'lunexpc-tunnel' -or $RemotePort -ne 23789 -or $LocalPort -ne 18789) {
    throw 'Device tunnel parameters differ from enrolled fixed port and host'
}
$ssh = Get-Command ssh.exe -ErrorAction Stop
$root = Join-Path $env:LOCALAPPDATA 'LunexPCControl\ssh'
$identity = Join-Path $root 'id_ed25519'
$knownHosts = Join-Path $root 'known_hosts'
if (-not (Test-Path -LiteralPath $identity -PathType Leaf) -or -not (Test-Path -LiteralPath $knownHosts -PathType Leaf)) {
    throw 'Pinned VPS host key or device identity missing; run Setup-TunnelIdentity.ps1 first'
}
Write-Output 'Connecting outbound SSH tunnel. Remote listener restricted to VPS 127.0.0.1.'
Write-Output 'Press Ctrl+C to close tunnel; no autostart or firewall configuration is changed.'
$forward = '127.0.0.1:' + $RemotePort + ':127.0.0.1:' + $LocalPort
& $ssh.Source -F none -o BatchMode=yes -o PreferredAuthentications=publickey -o PasswordAuthentication=no -o KbdInteractiveAuthentication=no -o StrictHostKeyChecking=yes -o UpdateHostKeys=no -o "UserKnownHostsFile=$knownHosts" -o GlobalKnownHostsFile=NUL -o IdentitiesOnly=yes -o "HostKeyAlgorithms=rsa-sha2-512,rsa-sha2-256" -o ExitOnForwardFailure=yes -o ConnectTimeout=10 -o ServerAliveInterval=20 -o ServerAliveCountMax=3 -i $identity -N -T -R $forward "$TunnelUser@$VpsHost"
if ($LASTEXITCODE -ne 0) {
    throw "SSH tunnel exited with code $LASTEXITCODE"
}

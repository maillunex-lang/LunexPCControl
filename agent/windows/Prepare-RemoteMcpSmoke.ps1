# Interactive-only decrypt of a sealed short-lived MCP credential.
# Neither the secret nor the private X25519 key is sent to Termalin or logged.
[CmdletBinding()]
param()
Set-StrictMode -Version Latest
$ErrorActionPreference='Stop'
$session=[Diagnostics.Process]::GetCurrentProcess().SessionId
if(-not [Environment]::UserInteractive -or $session -le 0){
 throw 'This must be run in the intended interactive Windows desktop'
}
$root=Join-Path $env:LOCALAPPDATA 'LunexPCControl'
$dir=Join-Path $root 'integration'
$private=Join-Path $root 'seal\seal-private.pem'
$python=Join-Path $root '.venv\Scripts\python.exe'
$tool='C:\Users\Public\Open-SealedToken.py'
$sealed='C:\Users\Public\LunexPCControl-live-sealed.json'
$output=Join-Path $dir 'upstream.key'
foreach($p in @($private,$python,$tool,$sealed)){
 if(-not(Test-Path -LiteralPath $p -PathType Leaf)){throw 'Required input missing'}
}
if(Test-Path -LiteralPath $output){throw 'Existing MCP credential; refusing overwrite'}
New-Item -ItemType Directory -Path $dir -Force | Out-Null
$acct=[Security.Principal.WindowsIdentity]::GetCurrent().Name
& icacls.exe $dir /inheritance:r /grant:r "$($acct):(OI)(CI)F" 'SYSTEM:(OI)(CI)F' | Out-Null
if($LASTEXITCODE -ne 0){throw 'Unable to restrict credential folder ACL'}
& $python $tool --private $private --envelope $sealed --output $output --quiet
if($LASTEXITCODE -ne 0){throw 'Credential decryption failed'}
Write-Output 'REMOTE-MCP-CREDENTIAL-READY (private user profile; no key printed)'

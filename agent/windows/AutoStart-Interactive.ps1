# Opt-in per-user login autostart. Does not run from Session 0 or as SYSTEM.
# At Windows login, the existing outbound-only supervisor reconnects as needed.
[CmdletBinding()]
param([ValidateSet('Check','Install','Disable')][string]$Mode = 'Check')
Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'
$taskName = 'LunexPCControl Interactive Agent'
$root = Join-Path $env:LOCALAPPDATA 'LunexPCControl\rel01'
$supervisor = Join-Path $root 'Agent-Supervisor.ps1'
$identity = [Security.Principal.WindowsIdentity]::GetCurrent().Name
$session = [Diagnostics.Process]::GetCurrentProcess().SessionId
$interactive = [Environment]::UserInteractive -and $session -gt 0
$existing = Get-ScheduledTask -TaskName $taskName -ErrorAction SilentlyContinue
if ($Mode -eq 'Check') {
    [pscustomobject]@{
        User = $identity
        InteractiveSession = $interactive
        SupervisorPresent = (Test-Path -LiteralPath $supervisor -PathType Leaf)
        TaskInstalled = [bool]$existing
        TaskState = $(if($existing){[string]$existing.State}else{'not-installed'})
        Mode = 'LoginOnly; never Session0 or SYSTEM'
    } | Format-List
    return
}
if (-not $interactive) { throw 'Autostart setup must run under the desktop user, not a service or SSH session' }
if (-not (Test-Path -LiteralPath $supervisor -PathType Leaf)) {
    throw 'Supervisor is not installed for the current Windows user'
}
if ($Mode -eq 'Disable') {
    if ($null -eq $existing) { throw 'No installed task' }
    Disable-ScheduledTask -TaskName $taskName | Out-Null
    Write-Output 'LunexPCControl login autostart disabled for this user'
    return
}
if ($null -ne $existing) { throw 'Task already exists; refusing overwrite' }
$ps = Join-Path $PSHOME 'powershell.exe'
$argument = '-NoProfile -NonInteractive -ExecutionPolicy Bypass -WindowStyle Hidden -File "' + $supervisor + '" -Mode Run -MaxRetries 0'
$action = New-ScheduledTaskAction -Execute $ps -Argument $argument -WorkingDirectory $root
$trigger = New-ScheduledTaskTrigger -AtLogOn -User $identity
$principal = New-ScheduledTaskPrincipal -UserId $identity -LogonType Interactive -RunLevel Limited
$settings = New-ScheduledTaskSettingsSet -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) -StartWhenAvailable -AllowStartIfOnBatteries -DontStopIfGoingOnBatteries
Register-ScheduledTask -TaskName $taskName -Description 'Owner-approved LunexPCControl outbound connection after interactive Windows sign-in' -Action $action -Trigger $trigger -Principal $principal -Settings $settings | Out-Null
Write-Output 'LunexPCControl will reconnect after the current user signs in to Windows; no public Windows port opened'

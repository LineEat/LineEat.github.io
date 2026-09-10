# 註冊 / 移除 Windows 工作排程：每天 10:30、15:30、19:30 執行 capture_notes.py
# （管理員傍晚就會刪掉當天貼文，所以最後一次要在 20:00 前）
# 用法：  .\schedule_task.ps1          註冊
#         .\schedule_task.ps1 -Remove  移除
param([switch]$Remove)

$TaskName = "LineEat-CaptureNotes"
$Root     = Split-Path -Parent $MyInvocation.MyCommand.Path
$Python   = (Get-Command python).Source
$Script   = Join-Path $Root "capture_notes.py"

if ($Remove) {
    Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false -ErrorAction SilentlyContinue
    Unregister-ScheduledTask -TaskName "LineEat-OrganizeInbox" -Confirm:$false -ErrorAction SilentlyContinue
    Write-Host "已移除 $TaskName 與 LineEat-OrganizeInbox"
    exit
}

$action   = New-ScheduledTaskAction -Execute $Python -Argument "`"$Script`"" -WorkingDirectory $Root
$triggers = @(
    (New-ScheduledTaskTrigger -Daily -At 10:30),
    (New-ScheduledTaskTrigger -Daily -At 15:30),
    (New-ScheduledTaskTrigger -Daily -At 19:30)
)
# 必須以「目前登入的使用者、互動式」執行，腳本才看得到桌面上的 LINE 視窗
$principal = New-ScheduledTaskPrincipal -UserId "$env:USERDOMAIN\$env:USERNAME" -LogonType Interactive -RunLevel Limited
$settings  = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 10) -MultipleInstances IgnoreNew

Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $triggers -Principal $principal -Settings $settings -Force | Out-Null
Write-Host "已註冊 $TaskName：每天 10:30、15:30、19:30 執行 $Script"

# 第二個工作：每天 19:45 用 Claude Code 無人值守整理 inbox（見 organize_inbox.ps1）
$OrgName   = "LineEat-OrganizeInbox"
$OrgScript = Join-Path $Root "organize_inbox.ps1"
$pwsh      = (Get-Command pwsh -ErrorAction SilentlyContinue).Source
if (-not $pwsh) { $pwsh = (Get-Command powershell).Source }
$orgAction = New-ScheduledTaskAction -Execute $pwsh -Argument "-NoProfile -ExecutionPolicy Bypass -File `"$OrgScript`"" -WorkingDirectory $Root
$orgTrig   = New-ScheduledTaskTrigger -Daily -At 19:45
$orgSet    = New-ScheduledTaskSettingsSet -StartWhenAvailable -ExecutionTimeLimit (New-TimeSpan -Minutes 40) -MultipleInstances IgnoreNew
Register-ScheduledTask -TaskName $OrgName -Action $orgAction -Trigger $orgTrig -Principal $principal -Settings $orgSet -Force | Out-Null
Write-Host "已註冊 $OrgName：每天 19:45 執行 $OrgScript"

# 無人值守整理 inbox：由工作排程每天 19:45 執行（在最後一次截圖之後）。
# 用 Claude Code 命令列的 -p 模式，照專案 CLAUDE.md 的「整理 inbox」步驟：
# 讀截圖 → 更新 data/trucks.csv 與 summary.md → 裁圖到 docs/img → build 網站 → git push。
# 結果與費用寫進 organize.log。inbox 沒有新截圖就直接結束。
$ErrorActionPreference = "Continue"
if (-not $env:PATHEXT) { $env:PATHEXT = ".COM;.EXE;.BAT;.CMD;.PS1" }   # 環境太乾淨時 PowerShell 會不認得 .exe
$Root = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $Root
$log = Join-Path $Root "organize.log"
$stamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"

$manifests = Get-ChildItem (Join-Path $Root "inbox") -Filter "*_manifest.json" -ErrorAction SilentlyContinue
if (-not $manifests) { Add-Content $log "$stamp inbox 沒有新截圖，略過"; exit 0 }

# PowerShell 不能把 claude.cmd 接在管線裡，直接呼叫套件內的 claude.exe
$cli = Join-Path $env:APPDATA "npm\node_modules\@anthropic-ai\claude-code\bin\claude.exe"
if (-not (Test-Path $cli)) { Add-Content $log "$stamp 找不到 Claude Code CLI：$cli（請 npm install -g @anthropic-ai/claude-code）"; exit 1 }

$prompt = "整理 inbox。這是無人值守執行，不要提問，照 CLAUDE.md 的步驟做完，最後把第 7 步的回報寫成幾行文字。"
$allowed = "Read,Edit,Write,Glob,Grep,Bash(python:*),Bash(git:*),Bash(mv:*),Bash(cp:*),Bash(mkdir:*),Bash(rmdir:*),Bash(ls:*),Bash(cat:*),Bash(rm:*),Bash(head:*),Bash(tail:*),Bash(wc:*)"

# 保險：整理前備份資料表（本機、不進版控，保留最近 60 份），並記下列數
$csv = Join-Path $Root "data\trucks.csv"
$bakDir = Join-Path $Root "data\backups"; New-Item -ItemType Directory -Force $bakDir | Out-Null
Copy-Item $csv (Join-Path $bakDir ("trucks_" + (Get-Date -Format "yyyyMMdd_HHmm") + ".csv"))
Get-ChildItem $bakDir -Filter "trucks_*.csv" | Sort-Object Name -Descending | Select-Object -Skip 60 | Remove-Item
function CsvRows($p) { (python -c "import csv,sys;print(sum(1 for _ in csv.DictReader(open(sys.argv[1],encoding='utf-8'))))" $p 2>$null) -as [int] }
$rowsBefore = CsvRows $csv

Add-Content $log "$stamp 開始整理（$($manifests.Count) 次抓取，資料表 $rowsBefore 列）"
[Console]::OutputEncoding = [System.Text.Encoding]::UTF8
$out = & $cli -p $prompt --allowedTools $allowed --permission-prompts none --max-turns 120 --output-format json 2>&1 | Out-String
try {
    $j = $out | ConvertFrom-Json
    Add-Content $log ("{0} 結束 is_error={1} turns={2} cost_usd={3}`n{4}`n" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $j.is_error, $j.num_turns, $j.total_cost_usd, $j.result)
} catch {
    Add-Content $log ("{0} 無法解析輸出：`n{1}`n" -f (Get-Date -Format "yyyy-MM-dd HH:mm:ss"), $out)
}
$rowsAfter = CsvRows $csv
if ($rowsAfter -lt $rowsBefore) {
    Add-Content $log ("!!! 警告：資料表從 {0} 列變成 {1} 列，可能被誤刪。備份在 {2}，可用 git log 比對後還原。`n" -f $rowsBefore, $rowsAfter, $bakDir)
} else {
    Add-Content $log ("資料表 {0} → {1} 列`n" -f $rowsBefore, $rowsAfter)
}

# LineEat — 南軟園區餐車記事本自動整理

網站：https://man-chen-tw.github.io/LineEat/ （GitHub Pages，來源 main 分支 `/docs`）

## 一次性設定
1. 安裝相依套件：
   ```
   pip install pywinauto pillow
   ```
2. 在 LINE 電腦版把「南軟二期餐車市集」社群**以獨立視窗開著**（點聊天室右上角的「開新視窗」）。
   它可以被其他視窗蓋住，但不要最小化、不要關掉；LINE 重開後要再開一次。
3. 手動跑一次確認：
   ```
   python capture_notes.py
   ```
   正常會看到 LINE 視窗閃一下（約半秒），約一分鐘後 `inbox/` 出現 `日期_時間_pNN.png` 與 manifest。

## 排程（每天自動跑）
管理員傍晚就會刪掉當天的餐車貼文（實測 9/10 的貼文在 20:00 前後消失），餐車多在前一晚或當天早上發文，
所以排 10:30、15:30、19:30 各跑一次；重複抓到的貼文整理時會自動去重。
用系統管理員 PowerShell 執行 `schedule_task.ps1` 即可註冊工作排程；移除用 `schedule_task.ps1 -Remove`。

## 整理資料
截圖累積在 `inbox/` 之後，在 Claude Code 說「整理 inbox」，結果會寫進 `data/trucks.csv` 和 `data/summary.md`，
處理過的截圖移到 `archive/`。

## 美食網站
`python build_site.py` 會把 `data/trucks.csv` 做成單頁網站 `docs/index.html`，有搜尋與類別篩選。
`docs/` 是 GitHub Pages 的發布資料夾，`git push` 之後約一分鐘網站就更新。

## 已知限制
- 只能抓「記事本列表」看得到的內容；長文被「顯示更多」截斷的部分不會展開。
- 圖片是列表縮圖（寬 428px），DM 上的小字可能讀不清楚，但貼文文字通常已包含日期、時間、地點與價格。
- 螢幕解析度或 LINE 介面改版可能讓按鈕定位失效，看 `capture.log` 就知道卡在哪一步。

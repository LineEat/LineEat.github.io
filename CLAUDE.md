# LineEat — 南軟園區餐車 DM 整理

## 背景
資料來源是 LINE 社群「南軟二期餐車市集」的記事本，餐車每天貼當日/隔日的營業資訊（文字 + DM 圖）。
LINE 對社群與記事本都沒有 API，本機資料庫和圖片快取皆加密，所以用 `capture_notes.py`
做桌面自動化：把記事本視窗逐頁截圖存進 `inbox/`，再由 Claude 用圖片辨識抽出結構化資料。
管理員傍晚就會刪掉當天的餐車貼文（實測 20:00 前後消失），排程每天 10:30、15:30、19:30 各抓一次。

## 資料夾
- `capture_notes.py`  截圖腳本（細節見檔頭註解）。`python capture_notes.py`
- `capture.log`       腳本執行紀錄
- `inbox/`            待處理截圖：`YYYY-MM-DD_HHMM_pNN.png`（同一次抓取的連續頁，相鄰頁有重疊）+ `_manifest.json`
- `archive/YYYY-MM/`  已處理的截圖
- `data/trucks.csv`   主資料表，每個餐車每個營業日一列
- `data/summary.md`   由 CSV 產生的人類可讀整理

## 使用者說「整理 inbox」時的步驟
1. 讀 `inbox/` 裡每個 manifest，依 `pages` 順序 Read 該次抓取的所有截圖（可平行）。
2. 每則貼文抽出：營業日期、餐車名、類別（便當/小吃/飲料/甜點/其他）、品項與價格、地點、時段、
   預訂方式（若有）、貼文相對時間（例如「39分鐘前」→ 換算成絕對時間，以 manifest 的 captured_at 為基準）。
   - 貼文文字是主要來源；DM 圖上的價格表若看得清楚也一併記錄。
   - 相鄰截圖會重疊，同一則貼文只記一次（以餐車名 + 營業日期為鍵）。
   - 被「顯示更多」截斷的內容不用猜，留空並在 notes 註明「內容截斷」。
   - 置頂的公告貼文（二期小秘書、主辦等非餐車貼文）跳過。
3. 追加到 `data/trucks.csv`（UTF-8，欄位含逗號要加引號）。同一餐車同一營業日已存在就更新而不重複。
   `source_image` 填該貼文第一次出現的截圖歸檔後相對路徑。
3a. 圖片：對每次抓取跑 `python crop_images.py <資料夾> <時間戳> <暫存資料夾>`，它會裁出每則貼文的 DM 區塊
   （只含圖片，不含名稱與留言）。逐一 Read 確認是哪台餐車，優先用沒標「被頁緣切到」的版本，
   存成 `docs/img/<營業日>_<餐車英文slug>.jpg`（JPEG 品質 85），並在 CSV 的 `images` 欄填 `img/檔名`（多張用「；」分隔）。
   公告類的白色卡片不是 DM，跳過。
4. 把該次抓取的截圖與 manifest 移到 `archive/YYYY-MM/`。
5. 重新產生 `data/summary.md`：
   - 「餐車總覽」：每個餐車一節，出現次數、常見品項、價格帶、常出現的星期與時段。
   - 「近期行程」：最近 7 天依營業日期列出（含未來日期，餐車常提前一天預告）。
6. 執行 `python build_site.py` 重新產生 `docs/index.html`，然後 `git add -A && git commit && git push`，
   GitHub Pages 會自動更新。
7. 回報處理了幾次抓取、幾則貼文、新增/更新幾列、哪些欄位不確定。

## 網站
- `build_site.py` 讀 `data/trucks.csv` 產生單頁網站 `docs/index.html`（搜尋 + 類別篩選 + 依營業日分組，今天/明天標色）。
- `docs/` 是 GitHub Pages 的發布來源（main 分支 /docs）。資料直接嵌在頁面裡，改 CSV 後一定要重跑 build 再 push。
- `inbox/`、`archive/`、`capture.log` 在 .gitignore 裡：截圖含社群成員名稱與頭像，不要推上公開 repo。

## 慣例
- 餐車名以貼文者顯示名稱為準，去掉「-小幫手」「/落地攤」之類後綴；同一餐車寫法不同要統一成已存在的名稱。
- 價格只記數字，例如 `雞腿便當 120`；多個品項用「；」分隔。
- 不要修改 archive 內既有檔案。

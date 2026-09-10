"""
crop_images.py — 從同一次抓取的記事本截圖裡，找出每則貼文的 DM 圖片區塊並裁下來。

用法：python crop_images.py <截圖資料夾> <抓取時間戳> [輸出資料夾]
  例：python crop_images.py archive/2026-09 2026-09-10_2020 docs/img/tmp
輸出：<輸出資料夾>/<時間戳>_imgNN.png 與 <時間戳>_crops.json（每塊來自哪一頁、y 範圍、是否被頁緣切到）
裁出的區塊只含圖片本身，不含發文者名稱、文字與留言。相鄰頁重疊時同一區塊會出現兩次，
以縮圖指紋去重並優先保留沒被切到的版本。
"""
import os, sys, json, glob
from PIL import Image

HEADER = 60          # 記事本視窗標題列高度（列表從這裡開始）
FOOT = 90            # 底部避開 + 按鈕
LIST_X0, LIST_X1 = 16, 411   # 貼文內容的左右邊界（428 寬視窗）
PHOTO_ROW = 0.35     # 一列裡「非背景像素」比例超過這個值就視為圖片列
MIN_H = 90

def load_pages(folder, stamp):
    files = sorted(glob.glob(os.path.join(folder, f"{stamp}_p*.png")))
    return [(os.path.basename(f), Image.open(f).convert("RGB")) for f in files]

def find_image_blocks(img):
    bg = img.getpixel((4, img.height // 2))
    px = img.load()
    def is_photo(p): return abs(p[0] - bg[0]) + abs(p[1] - bg[1]) + abs(p[2] - bg[2]) > 90
    n_cols = len(range(LIST_X0, LIST_X1, 3))
    rows = [sum(1 for x in range(LIST_X0, LIST_X1, 3) if is_photo(px[x, y])) / n_cols for y in range(img.height)]
    blocks, y0 = [], None
    for y, r in enumerate(rows + [0]):
        if r > PHOTO_ROW and y0 is None: y0 = y
        elif r <= PHOTO_ROW and y0 is not None:
            blocks.append((y0, y)); y0 = None
    merged = []                                   # 圖片格子之間 2-4px 的縫要併回去
    for b in blocks:
        if merged and b[0] - merged[-1][1] <= 8: merged[-1] = (merged[-1][0], b[1])
        else: merged.append(b)
    out = []
    for (a, b) in merged:
        a, b = max(a, HEADER), min(b, img.height - FOOT)
        if b - a >= MIN_H: out.append((a, b))
    return out

def fingerprint(crop):
    return crop.convert("L").resize((16, 16)).tobytes()

def fp_close(f1, f2, tol=14):
    return sum(abs(a - b) for a, b in zip(f1, f2)) / len(f1) < tol

def main():
    folder, stamp = sys.argv[1], sys.argv[2]
    outdir = sys.argv[3] if len(sys.argv) > 3 else os.path.join(folder, "crops")
    os.makedirs(outdir, exist_ok=True)
    pages = load_pages(folder, stamp)
    if not pages: print("沒有截圖"); return 1
    found = []                                    # dict: crop, fp, cut, page, y0, y1
    for name, img in pages:
        for (y0, y1) in find_image_blocks(img):
            crop = img.crop((LIST_X0, y0, LIST_X1, y1))
            cut = y0 <= HEADER + 8 or y1 >= img.height - FOOT - 1   # 列表頂端有幾 px 邊距，貼著就是被切到
            cand = {"crop": crop, "fp": fingerprint(crop), "cut": cut, "page": name, "y0": y0, "y1": y1}
            dup = next((f for f in found if abs(f["y1"] - f["y0"] - (y1 - y0)) < 40 and fp_close(f["fp"], cand["fp"])), None)
            if dup is None:
                found.append(cand)
            elif dup["cut"] and not cut:          # 之前那份被切到、這份完整 → 換成這份
                dup.update(cand)
    meta = []
    for i, f in enumerate(found):
        fn = f"{stamp}_img{i:02d}.png"; f["crop"].save(os.path.join(outdir, fn))
        meta.append({"file": fn, "page": f["page"], "y0": f["y0"], "y1": f["y1"], "h": f["y1"] - f["y0"], "cut": f["cut"]})
        print(f"  {fn}  {f['page']} y={f['y0']}-{f['y1']} ({f['y1'] - f['y0']}px){'  [被頁緣切到]' if f['cut'] else ''}")
    with open(os.path.join(outdir, f"{stamp}_crops.json"), "w", encoding="utf-8") as fh:
        json.dump(meta, fh, ensure_ascii=False, indent=1)
    print(f"{len(meta)} 個圖片區塊 → {outdir}")
    return 0

if __name__ == "__main__":
    sys.exit(main())

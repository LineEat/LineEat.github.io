"""
capture_notes.py — 自動把 LINE 社群「記事本」逐頁截圖存到 inbox/

原理：LINE 電腦版是 Qt 程式，記事本沒有 API、本機資料庫與圖片快取都加密，所以用桌面自動化：
  1. 找到社群的聊天視窗（該聊天室要以獨立視窗開著，可被其他視窗蓋住，不可最小化）
  2. 借用前景權限（AttachThreadInput）把聊天視窗提到前面，點右上角「記事本」圖示，
     立刻把前景還給原本的程式 → LINE 視窗會閃一下約半秒
  3. 記事本視窗（SquarePostListWindow）調成 428x1000（LINE 允許的最大寬度）、壓到 z-order 最底層
  4. 捲到最頂，往下逐頁 PrintWindow 截圖（被蓋住也能截），直到畫面不再變化
  5. 關掉記事本視窗、游標放回原位、寫 manifest

用法：python capture_notes.py            → 存到 inbox/<日期>_<時間>_pNN.png
      python capture_notes.py --keep     → 截完不關記事本視窗
"""
import ctypes, os, sys, time, hashlib, json, datetime
from ctypes import wintypes
from PIL import Image
from pywinauto import Desktop

COMMUNITY = "餐車市集"          # 聊天視窗標題包含的關鍵字
ROOT = os.path.dirname(os.path.abspath(__file__))
INBOX = os.path.join(ROOT, "inbox")
LOGFILE = os.path.join(ROOT, "capture.log")
WIN_W, WIN_H = 428, 1000          # 記事本視窗大小（寬度上限 428）
TICKS_PER_PAGE = 4                # 每頁往下捲幾格滾輪（4 格約 2/3 頁，保留重疊）
MAX_PAGES = 60

user32 = ctypes.windll.user32; gdi32 = ctypes.windll.gdi32; k32 = ctypes.windll.kernel32
WM_CLOSE, WM_MOUSEWHEEL = 0x0010, 0x020A
SWP_NOSIZE, SWP_NOMOVE, SWP_NOZORDER, SWP_NOACTIVATE = 0x0001, 0x0002, 0x0004, 0x0010
# HWND_TOPMOST 等是負數；不宣告 argtypes 的話 ctypes 會把它們當 32 位元 int 傳成無效 HWND
user32.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int, ctypes.c_int, ctypes.c_int, ctypes.c_int, wintypes.UINT]
HWND_BOTTOM = wintypes.HWND(1)

class BMI(ctypes.Structure):
    _fields_ = [("biSize", wintypes.DWORD), ("biWidth", ctypes.c_long), ("biHeight", ctypes.c_long),
                ("biPlanes", wintypes.WORD), ("biBitCount", wintypes.WORD), ("biCompression", wintypes.DWORD),
                ("biSizeImage", wintypes.DWORD), ("biXPelsPerMeter", ctypes.c_long), ("biYPelsPerMeter", ctypes.c_long),
                ("biClrUsed", wintypes.DWORD), ("biClrImportant", wintypes.DWORD)]

def log(*a):
    line = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S ") + " ".join(str(x) for x in a)
    print(line, flush=True)
    with open(LOGFILE, "a", encoding="utf-8") as f: f.write(line + "\n")

def printwindow(hwnd):
    """截整個視窗（含被其他視窗遮住的部分）。視窗必須在螢幕內，否則 DWM 不會重繪。"""
    r = wintypes.RECT(); user32.GetWindowRect(hwnd, ctypes.byref(r)); w, h = r.right - r.left, r.bottom - r.top
    hdc = user32.GetWindowDC(hwnd); mdc = gdi32.CreateCompatibleDC(hdc)
    bmp = gdi32.CreateCompatibleBitmap(hdc, w, h); gdi32.SelectObject(mdc, bmp)
    user32.PrintWindow(hwnd, mdc, 2)  # PW_RENDERFULLCONTENT
    bmi = BMI(); bmi.biSize = ctypes.sizeof(BMI); bmi.biWidth = w; bmi.biHeight = -h; bmi.biPlanes = 1; bmi.biBitCount = 32
    buf = ctypes.create_string_buffer(w * h * 4); gdi32.GetDIBits(mdc, bmp, 0, h, buf, ctypes.byref(bmi), 0)
    img = Image.frombuffer("RGB", (w, h), buf, "raw", "BGRX", 0, 1)
    gdi32.DeleteObject(bmp); gdi32.DeleteDC(mdc); user32.ReleaseDC(hwnd, hdc)
    return img

def list_region(img):
    # 只比對列表區域（避開標題列、右下角有動畫的 + 按鈕），縮小成灰階讓比對容忍小幅回彈
    return img.crop((0, 60, img.width - 80, img.height - 90)).convert("L").resize((87, 212))

def img_hash(img):
    return hashlib.md5(list_region(img).tobytes()).hexdigest()

def similar(a, b, tol=6.0):
    """兩張截圖的列表區域平均像素差小於 tol 就視為同一畫面（捲到底會回彈十幾 px）。"""
    if a is None or b is None: return False
    pa, pb = list_region(a).tobytes(), list_region(b).tobytes()
    return sum(abs(x - y) for x, y in zip(pa, pb)) / len(pa) < tol

def line_toplevels():
    """Win32 列舉 LINE 的可見頂層視窗（pywinauto 的 Desktop.windows() 會漏掉記事本視窗）。"""
    hwnds = []
    PROC = ctypes.WINFUNCTYPE(ctypes.c_bool, wintypes.HWND, wintypes.LPARAM)
    def cb(h, _):
        cls = ctypes.create_unicode_buffer(64); user32.GetClassNameW(h, cls, 64)
        if user32.IsWindowVisible(h) and cls.value.startswith("Qt") and "QWindowIcon" in cls.value:
            hwnds.append(h)
        return True
    user32.EnumWindows(PROC(cb), 0)
    return hwnds

def find_window(cls, title_sub=None):
    for h in line_toplevels():
        try:
            w = Desktop(backend="uia").window(handle=h).wrapper_object()
            if w.class_name() == cls and (title_sub is None or title_sub in w.window_text()):
                return w
        except Exception:
            pass
    return None

def wheel(hwnd, ticks):
    """用 WM_MOUSEWHEEL 訊息捲動（不需要前景、不動滑鼠）。正數往上。"""
    r = wintypes.RECT(); user32.GetWindowRect(hwnd, ctypes.byref(r))
    x, y = (r.left + r.right) // 2, (r.top + r.bottom) // 2
    user32.PostMessageW(hwnd, WM_MOUSEWHEEL, (120 * ticks) << 16, (y << 16) | (x & 0xffff))

def owner_of_point(x, y):
    h = user32.WindowFromPoint(wintypes.POINT(x, y))
    return user32.GetAncestor(h, 2) if h else 0   # GA_ROOT

def activate(hwnd):
    """背景程序沒有前景權限，SetForegroundWindow/HWND_TOPMOST 都會被系統忽略；
    借用目前前景視窗的輸入執行緒（AttachThreadInput）後就能切換。回傳原本的前景視窗。"""
    prev = user32.GetForegroundWindow()
    prev_tid = user32.GetWindowThreadProcessId(prev, None); my_tid = k32.GetCurrentThreadId()
    user32.AttachThreadInput(my_tid, prev_tid, True)
    try:
        user32.BringWindowToTop(hwnd); user32.SetForegroundWindow(hwnd)
    finally:
        user32.AttachThreadInput(my_tid, prev_tid, False)
    time.sleep(0.4)
    return prev

def open_notes(chat):
    """點聊天視窗右上角的記事本圖示，回傳記事本視窗 wrapper。"""
    cr = chat.rectangle()
    btns = [b for b in chat.descendants(class_name="LcButton")
            if cr.top + 30 < b.rectangle().top < cr.top + 80 and b.rectangle().right > cr.right - 130]
    btns.sort(key=lambda b: b.rectangle().left)
    if len(btns) < 2:
        log("找不到記事本按鈕（標題列右側按鈕數 < 2）"); return None
    btn = btns[-2]                      # 由左到右：搜尋、聊天、記事本、選單 → 倒數第二顆
    cur = wintypes.POINT(); user32.GetCursorPos(ctypes.byref(cur))
    prev = activate(chat.handle)
    try:
        br = btn.rectangle(); cx, cy = (br.left + br.right) // 2, (br.top + br.bottom) // 2
        if owner_of_point(cx, cy) != chat.handle:
            log("聊天視窗提到前景後按鈕仍被蓋住，放棄點擊"); return None
        btn.click_input(); time.sleep(0.3)
    finally:
        user32.SetCursorPos(cur.x, cur.y)
        if prev and prev != chat.handle:
            activate(prev)              # 把前景還給使用者原本在用的程式
    for _ in range(20):
        time.sleep(0.5)
        n = find_window("SquarePostListWindow")
        if n: return n
    log("點了記事本按鈕但視窗沒有出現"); return None

def main():
    keep = "--keep" in sys.argv
    os.makedirs(INBOX, exist_ok=True)
    chat = find_window("ChatWindow", COMMUNITY)
    if not chat:
        log(f"找不到標題含「{COMMUNITY}」的聊天視窗。請在 LINE 把該社群以獨立視窗開著（可被蓋住，不要最小化）。"); return 2
    if user32.IsIconic(chat.handle):
        user32.ShowWindow(chat.handle, 4)   # SW_SHOWNOACTIVATE
        time.sleep(1)

    notes = find_window("SquarePostListWindow")
    if notes:                               # 舊視窗先關掉，重開才會拿到最新貼文
        user32.PostMessageW(notes.handle, WM_CLOSE, 0, 0); time.sleep(1.5)
    notes = open_notes(chat)
    if not notes:
        return 4
    H = notes.handle
    sw = user32.GetSystemMetrics(0)
    user32.SetWindowPos(H, HWND_BOTTOM, sw - WIN_W - 20, 40, WIN_W, WIN_H, SWP_NOACTIVATE)   # 螢幕內、最底層
    time.sleep(3.0)                          # 等圖片載入

    for _ in range(8): wheel(H, 10); time.sleep(0.25)   # 捲到最頂
    time.sleep(1.5)

    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M")
    files, recent = [], []                   # recent: 最近三張截圖
    for i in range(MAX_PAGES):
        img = printwindow(H)
        if any(similar(img, r) for r in recent):
            break                            # 跟最近幾張幾乎一樣 = 捲不動了 = 到底
        p = os.path.join(INBOX, f"{stamp}_p{len(files):02d}.png"); img.save(p); files.append(p)
        recent = (recent + [img])[-3:]
        wheel(H, -TICKS_PER_PAGE); time.sleep(1.8)

    if not keep:
        user32.PostMessageW(H, WM_CLOSE, 0, 0)
    with open(os.path.join(INBOX, f"{stamp}_manifest.json"), "w", encoding="utf-8") as f:
        json.dump({"captured_at": stamp, "community": chat.window_text(),
                   "pages": [os.path.basename(p) for p in files]}, f, ensure_ascii=False, indent=1)
    log(f"完成：{len(files)} 頁 → {INBOX}")
    return 0

if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as e:
        log("錯誤:", repr(e)); sys.exit(1)

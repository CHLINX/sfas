#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read the public v2.62 ZIP on a temporary GitHub Actions branch; never modify main.

GitHub ZIP 讀取標準流程：
1. 核對 repository、分支、完整檔名與 GitHub 顯示大小。
2. 若 connector 無法直接讀 ZIP 二進位，不要求使用者重傳。
3. 只從獨立暫存分支透過 Actions 執行本工具。
4. Python 下載並核對大小，解析 ZIP 內 TXT／CSV／JSON。
5. 只把必要摘要輸出至 job log；若截斷，縮小輸出再執行。
6. 不修改 main，不寫回或變更來源 ZIP。
"""
import csv, io, json, urllib.request, zipfile
from urllib.parse import quote
from pathlib import PurePosixPath

REPO = "CHLINX/sso"
REF = "main"
PATH = "SSO_v2.62_前瞻影子驗證規格封存結果_20261029_165713.zip"
EXPECTED_SIZE = 9039
URL = "https://raw.githubusercontent.com/" + REPO + "/" + quote(REF, safe="") + "/" + quote(PATH, safe="")

def log(s=""):
    print(s, flush=True)

def decode(b):
    for enc in ("utf-8-sig","utf-8","cp950","big5"):
        try: return b.decode(enc)
        except UnicodeDecodeError: pass
    return b.decode("utf-8", errors="replace")

log("看股最速適 v2.62 規格 ZIP 讀取｜唯讀")
log(f"來源：{REPO} @ {REF} / {PATH}")
log(f"預期大小：{EXPECTED_SIZE:,} bytes")
req = urllib.request.Request(URL, headers={"User-Agent":"sso-v262-zip-reader/1.0"})
with urllib.request.urlopen(req, timeout=120) as res:
    data = res.read()
log(f"實際下載大小：{len(data):,} bytes")
if len(data) != EXPECTED_SIZE:
    raise RuntimeError(f"ZIP 大小不符：預期 {EXPECTED_SIZE:,}，實際 {len(data):,}")
if not zipfile.is_zipfile(io.BytesIO(data)):
    raise RuntimeError("下載內容不是有效 ZIP")
zf = zipfile.ZipFile(io.BytesIO(data))
infos = [x for x in zf.infolist() if not x.is_dir()]
log(f"ZIP 內檔案數：{len(infos)}")
for x in infos:
    log(f"  {x.filename} | 解壓大小={x.file_size:,} bytes")

for info in infos:
    name = info.filename.lower()
    raw = zf.read(info)
    if name.endswith((".txt",".md")):
        content = decode(raw)
        log(f"\n===== 文字文件：{info.filename} =====")
        log(content[:16000] if len(content) <= 16000 else content[:12000] + "\n...（中段省略）...\n" + content[-2000:])
    elif name.endswith(".json"):
        try:
            obj = json.loads(decode(raw))
            pretty = json.dumps(obj, ensure_ascii=False, indent=2)
            log(f"\n===== JSON：{info.filename} =====")
            log(pretty[:16000] if len(pretty) <= 16000 else pretty[:15000] + "\n...（JSON 後段省略）...")
        except Exception as exc:
            log(f"JSON 解析失敗：{info.filename}；{exc}")
    elif name.endswith(".csv"):
        text = decode(raw)
        rows = list(csv.reader(io.StringIO(text)))
        log(f"\n===== CSV：{info.filename} =====")
        log(f"資料列數={max(0,len(rows)-1)}；欄位數={len(rows[0]) if rows else 0}")
        if rows:
            log("欄位：" + " | ".join(rows[0]))
            for r in rows[1: min(6,len(rows))]:
                log(" | ".join(r))
            if len(rows)>6:
                log(f"其餘 {len(rows)-6:,} 列略過")
log("\nv2.62 ZIP 內容讀取完成；main 未修改。")

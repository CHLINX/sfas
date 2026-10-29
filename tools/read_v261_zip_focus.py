#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read v2.61 public result ZIP through temporary GitHub Actions; never change main.

GitHub ZIP 讀取標準流程：
1. 先核對 repository、分支、完整檔名與 GitHub 顯示大小。
2. 公開 ZIP 二進位無法直接讀取時，不要求使用者重傳。
3. 從已核對的 main 提交建立獨立暫存分支，只於暫存分支新增 reader 和 workflow。
4. Actions 使用 Python 下載、核對大小、解壓並讀取 TXT/CSV。
5. 用 job log 取回精簡輸出；如截斷，縮小範圍後重跑。
6. 不修改 main，不改動來源 ZIP。
"""
import csv, io, zipfile, urllib.request, statistics
from urllib.parse import quote
from collections import Counter, defaultdict

REPO = "CHLINX/sso"
REF = "main"
PATH = "SSO_v2.61_訊號日極端日穩健性診斷結果_20261029_084332.zip"
EXPECTED_SIZE = 29432
URL = "https://raw.githubusercontent.com/" + REPO + "/" + quote(REF, safe="") + "/" + quote(PATH, safe="")

def log(s=""):
    print(s, flush=True)

def text_bytes(b):
    for enc in ("utf-8-sig", "utf-8", "cp950", "big5"):
        try: return b.decode(enc)
        except UnicodeDecodeError: pass
    return b.decode("utf-8", errors="replace")

def read_csv(zf, info):
    return list(csv.DictReader(io.StringIO(text_bytes(zf.read(info)))))

def find_col(cols, *parts):
    return next((c for c in cols if all(p in c for p in parts)), None)

def show(row, keys=None):
    keys = keys or list(row.keys())
    return " | ".join(f"{k}={row.get(k, '')}" for k in keys if k in row)

log("看股最速適 v2.61 ZIP 詳讀｜唯讀")
log(f"來源：{REPO} @ {REF} / {PATH}")
log(f"預期大小：{EXPECTED_SIZE:,} bytes")
req = urllib.request.Request(URL, headers={"User-Agent":"sso-v261-zip-reader/1.0"})
with urllib.request.urlopen(req, timeout=120) as res:
    data = res.read()
log(f"實際下載大小：{len(data):,} bytes")
if len(data) != EXPECTED_SIZE:
    raise RuntimeError(f"大小不符：預期 {EXPECTED_SIZE:,}，實際 {len(data):,}")
if not zipfile.is_zipfile(io.BytesIO(data)):
    raise RuntimeError("下載內容不是有效 ZIP")
zf = zipfile.ZipFile(io.BytesIO(data))
infos = [x for x in zf.infolist() if not x.is_dir()]
log(f"ZIP 檔案數：{len(infos)}")
for i in infos: log(f"  {i.filename} | {i.file_size:,} bytes")

for info in infos:
    if info.filename.lower().endswith(".txt"):
        report = text_bytes(zf.read(info))
        log("\\n===== 報告判讀與限制段 =====")
        lines = report.splitlines()
        selected = []
        active = False
        for line in lines:
            if line.startswith("二、主要假設") or line.startswith("三、解讀提醒"):
                active = True
            if active: selected.append(line)
            if active and line.startswith("四、輸出檔案"): break
        log("\\n".join(selected)[:14000])

summary_info = next((x for x in infos if x.filename.endswith("v2.61_訊號日穩健性摘要.csv")), None)
if summary_info:
    rows = read_csv(zf, summary_info)
    log(f"\\n===== 摘要表：{len(rows)} 列 =====")
    if rows:
        cols = list(rows[0])
        log("欄位：" + " | ".join(cols))
        hcol = find_col(cols, "持有期間H") or find_col(cols,"持有期間")
        costcol = find_col(cols,"成本情境")
        scopecol = find_col(cols,"區段口徑")
        timecol = find_col(cols,"時間切片") or find_col(cols,"時期")
        log("前 2 列供欄位辨識：")
        for r in rows[:2]: log(show(r))
        targets = []
        for r in rows:
            h = (r.get(hcol,"") if hcol else "").replace("H","").strip()
            if h not in {"3","5","10"}: continue
            if costcol and "一般" not in r.get(costcol,""): continue
            if scopecol and "僅同區段" not in r.get(scopecol,""): continue
            targets.append(r)
        log(f"一般成本／僅同區段 H3-H5-H10：{len(targets)} 列")
        keys = [
            timecol,hcol,costcol,scopecol,
            find_col(cols,"活躍日平均"),find_col(cols,"活躍日中位數"),
            find_col(cols,"活躍日P5"),find_col(cols,"活躍日勝率"),
            find_col(cols,"活躍日虧損率"),find_col(cols,"剔除最佳活躍日後平均"),
            find_col(cols,"剔除最差活躍日後平均"),find_col(cols,"剔除最佳與最差各一日後平均"),
            find_col(cols,"逐一剔除一日後平均仍為正的比例"),
            find_col(cols,"最佳一日占所有正報酬日合計"),
            find_col(cols,"最差一日占所有虧損日絕對值合計"),
            find_col(cols,"前10名日平均"),
            find_col(cols,"策略減前10名平均日差_全訊號日"),
            find_col(cols,"策略活躍日減前10名平均日差_活躍日")
        ]
        keys=[k for k in keys if k]
        for r in sorted(targets, key=lambda x: ((x.get(timecol,"") or ""), (x.get(hcol,"") or ""))):
            log(show(r, keys))

extreme_info = next((x for x in infos if x.filename.endswith("v2.61_極端訊號日明細.csv")), None)
if extreme_info:
    rows = read_csv(zf, extreme_info)
    log(f"\\n===== 極端訊號日明細：{len(rows)} 列 =====")
    if rows:
        cols = list(rows[0])
        log("欄位：" + " | ".join(cols))
        for r in rows[:2]: log("例列：" + show(r))
        hcol = find_col(cols,"持有期間H") or find_col(cols,"持有期間")
        costcol = find_col(cols,"成本情境")
        scopecol = find_col(cols,"區段口徑")
        timecol = find_col(cols,"時間切片") or find_col(cols,"時期")
        rolecol = next((c for c in cols if any(t in c for t in ("極端類型","日類型","剔除情境","事件"))), None)
        datecol = find_col(cols,"訊號日期") or find_col(cols,"日期")
        retcol = next((c for c in cols if ("報酬" in c and any(t in c for t in ("策略","組合","日均")) and "基準" not in c)), None)
        if retcol is None: retcol = find_col(cols,"策略日報酬")
        log(f"識別欄位：H={hcol}, cost={costcol}, scope={scopecol}, period={timecol}, role={rolecol}, date={datecol}, return={retcol}")
        # Compact target detail. These records reveal which dates dominate the sensitivity.
        target = []
        for r in rows:
            h = (r.get(hcol,"") if hcol else "").replace("H","").strip()
            if h not in {"3","5","10"}: continue
            if costcol and "一般" not in r.get(costcol,""): continue
            if scopecol and "僅同區段" not in r.get(scopecol,""): continue
            if rolecol and not any(t in r.get(rolecol,"") for t in ("最佳","最差","剔除")): continue
            target.append(r)
        log(f"篩選後極端明細列數：{len(target)}")
        for r in target[:40]:
            log(show(r, [c for c in (timecol,hcol,costcol,scopecol,rolecol,datecol,retcol) if c]))
        # Group underlying dates for target horizon/cost/scope.
        if datecol and retcol and hcol:
            for period_name in ("全期參考","早期60%","中期20%","後期20%"):
                for h in ("3","5","10"):
                    sub = []
                    for r in target:
                        hh=(r.get(hcol,"") or "").replace("H","").strip()
                        if hh==h and (not timecol or r.get(timecol)==period_name):
                            try: val=float(r.get(retcol,""))
                            except (ValueError,TypeError): continue
                            sub.append((val,r.get(datecol,"")))
                    if sub:
                        sub.sort()
                        log(f"{period_name} H{h} extremes={[(round(v,6),d) for v,d in (sub[:2]+sub[-2:])]}")

cost_info = next((x for x in infos if x.filename.endswith("v2.61_一般成本與壓力成本比較.csv")), None)
if cost_info:
    rows = read_csv(zf, cost_info)
    log(f"\\n===== 一般／壓力成本比較：{len(rows)} 列 =====")
    if rows:
        cols = list(rows[0])
        log("欄位：" + " | ".join(cols))
        for r in rows:
            vals = " ".join(str(v) for v in r.values())
            if "後期20%" in vals and any(f"H{h}" in vals for h in (3,5,10)):
                log(show(r, cols[:min(20,len(cols))]))
log("\\n讀取完成；只讀公開 ZIP，未修改 main。")

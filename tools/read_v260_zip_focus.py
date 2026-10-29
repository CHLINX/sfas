#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read v2.60 public ZIP from a temporary GitHub Actions branch; never modify main.

GitHub ZIP 讀取標準流程:
1. Verify repository, ref, full filename, and expected size.
2. If the connector cannot read the binary ZIP, do not ask the user to re-upload.
3. Run this Python reader only on an independent temporary branch via GitHub Actions.
4. Verify ZIP size, parse TXT/CSV, and emit a focused job-log summary.
5. Keep main untouched; if logs truncate, narrow output and rerun.
"""
import csv
import io
import statistics
import urllib.request
import zipfile
from urllib.parse import quote
from collections import Counter, defaultdict

REPO = "CHLINX/sso"
REF = "main"
PATH = "SSO_v2.60_訊號日層級穩定性診斷結果_20261029_082147.zip"
EXPECTED_SIZE = 589833
URL = "https://raw.githubusercontent.com/" + REPO + "/" + quote(REF, safe="") + "/" + quote(PATH, safe="")

def log(value=""):
    print(value, flush=True)

def decode(data):
    for enc in ("utf-8-sig", "utf-8", "cp950", "big5"):
        try:
            return data.decode(enc)
        except UnicodeDecodeError:
            pass
    return data.decode("utf-8", errors="replace")

def read_csv(zf, info):
    return list(csv.DictReader(io.StringIO(decode(zf.read(info)))))

def pick_col(cols, *terms):
    for c in cols:
        if all(t in c for t in terms):
            return c
    return None

def show_row(row, ordered=None):
    keys = ordered or list(row.keys())
    return " | ".join(f"{k}={row.get(k, '')}" for k in keys if k in row)

log("看股最速適 v2.60 ZIP 詳讀｜只讀／暫存分支")
log(f"來源：{REPO} @ {REF} / {PATH}")
log(f"預期大小：{EXPECTED_SIZE:,} bytes")
req = urllib.request.Request(URL, headers={"User-Agent": "sso-v260-zip-reader/1.0"})
with urllib.request.urlopen(req, timeout=120) as response:
    data = response.read()
log(f"實際下載大小：{len(data):,} bytes")
if len(data) != EXPECTED_SIZE:
    raise RuntimeError(f"ZIP 大小不符：預期 {EXPECTED_SIZE:,}，實際 {len(data):,}")
if not zipfile.is_zipfile(io.BytesIO(data)):
    raise RuntimeError("下載內容不是有效 ZIP")
zf = zipfile.ZipFile(io.BytesIO(data))
infos = [x for x in zf.infolist() if not x.is_dir()]
log(f"ZIP 內檔案數：{len(infos)}")
for info in infos:
    log(f"  {info.filename} | {info.file_size:,} bytes")

for info in infos:
    if info.filename.lower().endswith(".txt") and "報告" in info.filename:
        report = decode(zf.read(info))
        lines = report.splitlines()
        log("\\n===== 報告方法限制與判讀段落 =====")
        show = []
        active = False
        for line in lines:
            if line.startswith("二、主要假設") or line.startswith("三、成本與區段") or line.startswith("四、判讀規則"):
                active = True
            if active:
                show.append(line)
            if active and line.startswith("五、輸出檔案"):
                break
        log("\\n".join(show)[:14000])

summary_info = next((x for x in infos if x.filename.endswith("v2.60_訊號日穩定性摘要.csv")), None)
if summary_info:
    rows = read_csv(zf, summary_info)
    log(f"\\n===== 日穩定性摘要檢核：{len(rows)} rows =====")
    if rows:
        cols = list(rows[0].keys())
        log("欄位：" + " | ".join(cols))
        for row in rows[:2]:
            log("例列：" + show_row(row))
        # Main hypothesis: general cost, same-section only, H3/H5/H10, all period slices.
        time_col = pick_col(cols, "時間切片") or pick_col(cols, "時期")
        h_col = pick_col(cols, "持有期間H") or pick_col(cols, "持有期間")
        cost_col = pick_col(cols, "成本情境")
        scope_col = pick_col(cols, "區段口徑")
        hyp_col = next((c for c in cols if "情境" in c and c not in (time_col, scope_col, cost_col)), None)
        filt = []
        for row in rows:
            h = (row.get(h_col, "") or "").strip().upper().replace("H","") if h_col else ""
            cost = row.get(cost_col, "") if cost_col else ""
            scope = row.get(scope_col, "") if scope_col else ""
            hyp = row.get(hyp_col, "") if hyp_col else ""
            if h in {"3","5","10"} and (not cost_col or "一般" in cost) and (not scope_col or "僅同區段" in scope) and (not hyp_col or ("高潛力" in hyp and ("正預測" in hyp or "大於0" in hyp or "淨報酬大於0" in hyp))):
                filt.append(row)
        log(f"主假設篩選列數：{len(filt)}")
        keys = [
            time_col,h_col,cost_col,scope_col,hyp_col,
            pick_col(cols,"訊號日"),pick_col(cols,"有選股"),
            pick_col(cols,"活躍交易日均"),pick_col(cols,"活躍交易日勝率"),
            pick_col(cols,"活躍交易日虧損率"),pick_col(cols,"策略日均"),
            pick_col(cols,"策略最差日"),pick_col(cols,"最差日"),
            pick_col(cols,"日報酬P5"),pick_col(cols,"平均日差"),
            pick_col(cols,"共同可觀測日")
        ]
        keys = [k for k in keys if k]
        for row in filt:
            log(show_row(row, keys))
        if not filt:
            log("主假設篩選結果為空；列印摘要全部資料供辨識（最多 64 列）。")
            for row in rows[:64]:
                log(show_row(row))

highlight_info = next((x for x in infos if x.filename.endswith("v2.60_H3_H5_H10重點彙整.csv")), None)
if highlight_info:
    rows = read_csv(zf, highlight_info)
    log(f"\\n===== H3/H5/H10 重點彙整：{len(rows)} rows =====")
    if rows:
        cols = list(rows[0].keys())
        log("欄位：" + " | ".join(cols))
        for row in rows[:2]:
            log("例列：" + show_row(row))
        # Focus late split; only report a compact selection.
        for row in rows:
            vals = " ".join(str(v) for v in row.values())
            if "後期20%" in vals and any(f"H{h}" in vals for h in (3,5,10)):
                log(show_row(row, cols[:min(len(cols), 18)]))

daily_info = next((x for x in infos if x.filename.endswith("v2.60_訊號日組合報酬明細.csv")), None)
if daily_info:
    rows = read_csv(zf, daily_info)
    log(f"\\n===== 訊號日組合明細獨立檢核：{len(rows)} rows =====")
    if rows:
        cols = list(rows[0].keys())
        log("欄位：" + " | ".join(cols))
        for row in rows[:2]:
            log("例列：" + show_row(row))
        # Identify major fields dynamically and test activity concentration by signal date.
        period_col = pick_col(cols, "時間切片")
        h_col = pick_col(cols, "持有期間H") or pick_col(cols, "持有期間")
        cost_col = pick_col(cols, "成本情境")
        scope_col = pick_col(cols, "區段口徑")
        type_col = next((c for c in cols if any(t in c for t in ("組合類型","報酬類型","基準類型","策略或基準","序列類型"))), None)
        date_col = pick_col(cols, "訊號日期") or pick_col(cols,"日期")
        ret_col = next((c for c in cols if ("組合" in c and "報酬" in c) or c in ("策略日報酬","日組合報酬","組合淨報酬")), None)
        active_col = next((c for c in cols if "有選股" in c or "活躍" in c), None)
        log(f"識別欄位：period={period_col}, H={h_col}, cost={cost_col}, scope={scope_col}, type={type_col}, date={date_col}, return={ret_col}, activity={active_col}")
        if period_col and h_col and cost_col and scope_col and date_col:
            counts = defaultdict(list)
            for row in rows:
                h = (row.get(h_col,"") or "").strip().upper().replace("H","")
                if h not in {"3","5","10"}: continue
                if "一般" not in (row.get(cost_col) or "") or "僅同區段" not in (row.get(scope_col) or ""): continue
                key = (row.get(period_col,""),h,row.get(type_col,"") if type_col else "unknown")
                counts[key].append(row)
            for key, arr in sorted(counts.items()):
                dates = [x.get(date_col,"") for x in arr if x.get(date_col,"")]
                unique_dates = len(set(dates))
                active = None
                if active_col:
                    active = sum(1 for x in arr if str(x.get(active_col,"")).lower() in {"true","1","yes","是"})
                log(f"{key}: rows={len(arr)}, unique_dates={unique_dates}, active_flag_true={active}")
log("\\nZIP 讀取與重點核對完成；未修改 main。")

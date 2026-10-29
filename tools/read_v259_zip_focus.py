#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read v2.59 public result ZIP through GitHub Actions; never modify main."""
import csv, io, zipfile, urllib.request, statistics
from urllib.parse import quote
from collections import Counter, defaultdict
from datetime import date

REPO = "CHLINX/sso"
REF = "main"
PATH = "SSO_v2.59_時間切分穩定性診斷結果_20261029_080204.zip"
EXPECTED_SIZE = 225716
URL = "https://raw.githubusercontent.com/" + REPO + "/" + quote(REF, safe="") + "/" + quote(PATH, safe="")

def log(s=""):
    print(s, flush=True)

def parse_date(v):
    v = (v or "").strip()[:10].replace("/", "-")
    try:
        return date.fromisoformat(v)
    except Exception:
        return None

def as_num(v):
    v = (v or "").strip().replace(",", "")
    if not v or v.upper() in {"NA", "N/A", "NAN", "NONE", "NULL", "-"}:
        return None
    is_pct = "%" in v
    v = v.replace("%", "")
    try:
        x = float(v)
        return x
    except Exception:
        return None

def first_col(cols, predicates):
    for c in cols:
        if all(p in c for p in predicates):
            return c
    return None

log("看股最速適 v2.59 ZIP 詳讀｜暫存分支／只讀")
log(f"來源：{REPO} @ {REF} / {PATH}")
log(f"預期大小：{EXPECTED_SIZE:,} bytes")
req = urllib.request.Request(URL, headers={"User-Agent":"sso-v259-zip-reader/1.0"})
with urllib.request.urlopen(req, timeout=120) as res:
    data = res.read()
log(f"HTTP 下載大小：{len(data):,} bytes")
if len(data) != EXPECTED_SIZE:
    raise RuntimeError(f"大小不符：{len(data)} != {EXPECTED_SIZE}")
if not zipfile.is_zipfile(io.BytesIO(data)):
    raise RuntimeError("下載資料不是有效 ZIP")
zf = zipfile.ZipFile(io.BytesIO(data))
infos = [i for i in zf.infolist() if not i.is_dir()]
log(f"ZIP 內容檔案數：{len(infos)}")
for i in infos:
    log(f"  {i.filename} | {i.file_size:,} bytes")

report_files = [i for i in infos if i.filename.lower().endswith(".txt")]
for info in report_files:
    txt = zf.read(info).decode("utf-8-sig", errors="replace")
    log(f"\n===== 報告重點：{info.filename} =====")
    # Print the core interpretive sections, not the entire lengthy report.
    lines = txt.splitlines()
    keep = []
    active = False
    for line in lines:
        if any(mark in line for mark in ("二、主要研究假設", "六、判讀與後續限制", "五、候選狀態與旗標注意事項")):
            active = True
        if active:
            keep.append(line)
        if active and line.startswith("七、輸出檔案"):
            break
    log("\n".join(keep)[:16000] if keep else txt[:9000])

summary_info = next((i for i in infos if i.filename.endswith("v2.59_時間切分情境彙總.csv")), None)
if summary_info:
    rows = list(csv.DictReader(io.StringIO(zf.read(summary_info).decode("utf-8-sig", errors="replace"))))
    log(f"\n情境彙總列數：{len(rows):,}")
    if rows:
        log("情境彙總欄位：" + " | ".join(rows[0].keys()))
        # Print only the exact target hypothesis at general cost / same-section scope.
        chosen = [
            row for row in rows
            if row.get("情境") == "高潛力且預測淨報酬大於0"
            and row.get("成本情境") == "一般股票基準成本"
            and row.get("區段口徑") == "僅同區段"
        ]
        log(f"主要研究假設（一般成本／僅同區段）彙總列：{len(chosen)}")
        for row in chosen:
            keys = ("時間切片", "持有期間H", "選中筆數", "有效淨報酬筆數", "平均淨報酬",
                    "淨報酬中位數", "淨勝率", "最差單筆淨報酬", "最佳單筆淨報酬",
                    "有選中股票的訊號日期數", "候選訊號日期數", "有選股訊號日比例")
            log(" | ".join(f"{k}={row.get(k, '')}" for k in keys if k in row))

detail_info = next((i for i in infos if i.filename.endswith("v2.59_高潛力正預測逐筆明細.csv")), None)
if detail_info:
    raw = zf.read(detail_info).decode("utf-8-sig", errors="replace")
    records = list(csv.DictReader(io.StringIO(raw)))
    log(f"\n===== 逐筆明細獨立檢核：{detail_info.filename} =====")
    log(f"明細列數：{len(records):,}")
    if records:
        cols = list(records[0].keys())
        log("欄位：" + " | ".join(cols))
        log("前 2 筆：" + repr(records[:2])[:5000])
        hcol = first_col(cols, ["持有期間"]) or next((c for c in cols if c.strip().upper() in {"H","持有H"}), None)
        dcol = first_col(cols, ["訊號日期"]) or first_col(cols, ["日期"])
        scol = first_col(cols, ["股票代號"]) or first_col(cols, ["代號"])
        ccol = first_col(cols, ["成本情境"])
        scopecol = first_col(cols, ["區段口徑"])
        rcol = next((c for c in cols if c == "實際淨報酬"), None) or first_col(cols, ["實際","淨報酬"])
        log(f"識別欄位：H={hcol}; date={dcol}; stock={scol}; cost={ccol}; scope={scopecol}; net={rcol}")
        if ccol:
            log("成本情境值：" + repr(Counter((r.get(ccol) or "") for r in records)))
        if scopecol:
            log("區段口徑值：" + repr(Counter((r.get(scopecol) or "") for r in records)))
        filt = records
        if ccol:
            vals = {r.get(ccol,"") for r in filt}
            general = [r for r in filt if "一般" in (r.get(ccol) or "")]
            if general: filt = general
        if scopecol:
            same = [r for r in filt if "同區段" in (r.get(scopecol) or "")]
            if same: filt = same
        log(f"一般成本／同區段篩選後列數：{len(filt):,}")
        parsed = []
        raw_nums = []
        for r in filt:
            dt = parse_date(r.get(dcol, "")) if dcol else None
            h = (r.get(hcol, "") or "").strip() if hcol else "NA"
            val = as_num(r.get(rcol, "")) if rcol else None
            if val is not None: raw_nums.append(val)
            if dt is None:
                period = "日期無法解析"
            elif dt <= date(2024,1,3):
                period = "早期60%"
            elif dt <= date(2025,6,4):
                period = "中期20%"
            else:
                period = "後期20%"
            parsed.append((period,h,dt,r,val))
        # v2.59 source stores percentage points if magnitudes are commonly above 1;
        # otherwise treat numeric returns as fractional rates.
        scale = 100.0 if raw_nums and sorted(abs(x) for x in raw_nums)[int(0.95*(len(raw_nums)-1))] <= 1.0 else 1.0
        log(f"報酬欄原始數值尺度換算係數：{scale:g}（結果以百分比呈現）")
        groups = defaultdict(list)
        for period,h,dt,r,val in parsed:
            groups[(period,h)].append((dt,r,val))
        log("\n一般成本／同區段：各時期 × H 的逐筆分布")
        for period in ("早期60%","中期20%","後期20%","日期無法解析"):
            for h in ("1","3","5","10"):
                arr = groups.get((period,h), [])
                vals = [v for _,_,v in arr if v is not None]
                if not arr and not vals: continue
                pct = sorted(v*scale for v in vals)
                mean = sum(pct)/len(pct) if pct else None
                med = statistics.median(pct) if pct else None
                win = sum(v>0 for v in vals)/len(vals)*100 if vals else None
                def f(x): return "NA" if x is None else f"{x:.2f}%"
                tickers = Counter((r.get(scol) or "NA") for _,r,v in arr) if scol else Counter()
                top_ticker = tickers.most_common(1)[0] if tickers else ("NA",0)
                log(f"{period} H{h}: rows={len(arr)}, valid={len(vals)}, mean={f(mean)}, median={f(med)}, win={f(win)}, best={f(max(pct) if pct else None)}, worst={f(min(pct) if pct else None)}, top_stock={top_ticker[0]}({top_ticker[1]} rows)")
        # Count unique signal dates and concentration: multiple stocks on one date are not independent time samples.
        log("\\n===== 訊號日集中度（一般成本／僅同區段） =====")
        for period in ("早期60%","中期20%","後期20%"):
            for h in ("1","3","5","10"):
                arr = [(dt,r,v) for p,hh,dt,r,v in parsed if p == period and hh == h and dt is not None]
                counts = Counter(dt.isoformat() for dt,_,_ in arr)
                if not arr:
                    continue
                top_days = counts.most_common(5)
                log(f"{period} H{h}: rows={len(arr)}, unique_signal_dates={len(counts)}, "
                    f"max_rows_same_date={max(counts.values())}, top_dates={top_days}")

        # Inspect target late H3 and H10: small sample/concentration and extremes.
        for h in ("3","10"):
            arr = [(dt,r,v) for period,hh,dt,r,v in parsed if period=="後期20%" and hh==h and v is not None]
            arr.sort(key=lambda x:x[2], reverse=True)
            log(f"\n後期 H{h} 個別報酬前 5 名／後 5 名（百分點）")
            for dt,r,v in arr[:5]:
                log(f"TOP {dt} stock={r.get(scol,'NA') if scol else 'NA'} return={v*scale:.2f}%")
            for dt,r,v in arr[-5:]:
                log(f"LOW {dt} stock={r.get(scol,'NA') if scol else 'NA'} return={v*scale:.2f}%")
log("\n讀取完成：僅由 GitHub ZIP 讀取與分析，未修改 main。")

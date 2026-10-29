#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Read-only schema inspection of the frozen v2.50 ZIP from a temporary branch."""
import csv, io, json, urllib.request, zipfile
from urllib.parse import quote
REPO="CHLINX/sso"
PATH="SSO_v2.50_日成交量特徵與500日檢查點結果.zip"
SIZE=21654521
URL="https://raw.githubusercontent.com/"+REPO+"/main/"+quote(PATH,safe="")
def log(x=""): print(x, flush=True)
req=urllib.request.Request(URL,headers={"User-Agent":"sso-v250-schema-reader/1.0"})
with urllib.request.urlopen(req,timeout=180) as r: blob=r.read()
log("v2.50 baseline ZIP schema inspection (read-only)")
log(f"Expected bytes={SIZE}; downloaded bytes={len(blob)}")
if len(blob)!=SIZE: raise RuntimeError("ZIP size mismatch")
if not zipfile.is_zipfile(io.BytesIO(blob)): raise RuntimeError("Invalid ZIP")
z=zipfile.ZipFile(io.BytesIO(blob))
files=[i for i in z.infolist() if not i.is_dir()]
log(f"member_count={len(files)}")
for i in files: log(f"MEMBER {i.filename} | {i.file_size}")
for i in files:
    if not i.filename.lower().endswith(".csv"): continue
    raw=z.read(i)
    for enc in ("utf-8-sig","utf-8","cp950","big5"):
        try: txt=raw.decode(enc); break
        except UnicodeDecodeError: continue
    else: txt=raw.decode("utf-8",errors="replace")
    reader=csv.reader(io.StringIO(txt))
    header=next(reader,[])
    joined=" | ".join(header)
    log(f"CSV_HEADER {i.filename} | rows_approx={max(0, sum(1 for _ in io.StringIO(txt))-1)}")
    log(joined[:6000])
    interesting=[h for h in header if any(k in h for k in ("上漲潛力","預測淨報酬","股票代號","訊號日期","評估日期","預測報酬","代號","排名","成本","區段","資料版本"))]
    if interesting: log("KEY_FIELDS="+ " | ".join(interesting))
log("Done; no repository main files changed.")

#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
GitHub ZIP 讀取標準流程（供後續分析程式與 ChatGPT 自我提醒）

標準程序：
1. 先確認 Repository、分支、完整檔名與 GitHub 顯示的檔案大小。
2. 公開 ZIP 若無法透過一般 GitHub connector 直接讀取二進位，不得因第一次失敗就要求使用者重傳。
3. 從已核對的 main 提交建立獨立暫存分支，只在暫存分支新增 GitHub Actions workflow；絕不可修改 main。
4. 由 Actions runner 使用 Python 下載公開 ZIP，先核對下載大小，再以 zipfile 解壓，讀取 TXT／CSV。
5. 將摘要與必要 CSV 明細寫到 job log，透過 GitHub Actions 執行紀錄／job log 取回結果。
6. 如 log 截斷，縮小輸出範圍（只輸出指定摘要、欄位、分組或前後幾列）後再執行，不要重傳 ZIP。
7. 只有在完成讀取並檢查內容後，才分析與回答問題。

本工具採唯讀方式下載和解析來源 ZIP，不上傳、不修改 main，也不修改來源資料。
可在 GitHub Actions runner 中執行；亦可在一般 Python 3.10+ 環境執行。
"""
from __future__ import annotations

import argparse
import csv
import io
import sys
import urllib.error
import urllib.request
import zipfile
from pathlib import PurePosixPath
from urllib.parse import quote


def log(message: str) -> None:
    print(message, flush=True)


def download_zip(repo: str, ref: str, path: str, expected_size: int | None) -> bytes:
    encoded_path = quote(path, safe="/")
    url = f"https://raw.githubusercontent.com/{repo}/{quote(ref, safe='')}/{encoded_path}"
    request = urllib.request.Request(
        url,
        headers={"User-Agent": "sso-github-zip-reader/1.0", "Accept": "application/octet-stream"},
    )
    log(f"下載來源：{repo} @ {ref} / {path}")
    log(f"下載網址：{url}")
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            status = getattr(response, "status", 200)
            data = response.read()
    except urllib.error.HTTPError as exc:
        raise RuntimeError(f"GitHub 原始檔下載失敗：HTTP {exc.code}；請先核對分支與完整檔名。") from exc
    except Exception as exc:
        raise RuntimeError(f"GitHub ZIP 下載失敗：{type(exc).__name__}: {exc}") from exc

    log(f"HTTP 狀態：{status}")
    log(f"實際下載大小：{len(data):,} bytes")
    if expected_size is not None and len(data) != expected_size:
        raise RuntimeError(
            f"檔案大小不符：預期 {expected_size:,} bytes，實際 {len(data):,} bytes。"
        )
    if not zipfile.is_zipfile(io.BytesIO(data)):
        raise RuntimeError("下載內容不是有效 ZIP；停止解析，避免輸出誤導結果。")
    return data


def decode_text(data: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp950", "big5"):
        try:
            return data.decode(encoding)
        except UnicodeDecodeError:
            continue
    return data.decode("utf-8", errors="replace")


def csv_preview(name: str, data: bytes, limit_rows: int = 5) -> None:
    text = decode_text(data)
    reader = csv.reader(io.StringIO(text))
    rows = list(reader)
    if not rows:
        log(f"  CSV 為空：{name}")
        return
    log(f"  CSV：{name}；資料列數（不含標題）={max(0, len(rows)-1):,}；欄位數={len(rows[0])}")
    key_summary = any(key in PurePosixPath(name).stem.lower() for key in ("彙總", "summary", "統計"))
    show_n = min(len(rows) - 1, 80 if key_summary else limit_rows)
    log("  欄位：" + " | ".join(rows[0]))
    if show_n:
        log(f"  以下顯示 {show_n} 列" + ("（摘要／彙總檔）：" if key_summary else "："))
        for row in rows[1:1 + show_n]:
            log("  " + " | ".join(row))
    if len(rows) - 1 > show_n:
        log(f"  其餘 {len(rows)-1-show_n:,} 列略過，以避免 Actions log 過長。")


def inspect_zip(data: bytes) -> None:
    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        infos = [i for i in zf.infolist() if not i.is_dir()]
        log("")
        log(f"ZIP 檔案數：{len(infos)}")
        log("ZIP 內容清單：")
        for info in infos:
            log(f"  {info.filename}\t{info.file_size:,} bytes")

        txt_infos = [i for i in infos if i.filename.lower().endswith((".txt", ".md"))]
        csv_infos = [i for i in infos if i.filename.lower().endswith(".csv")]

        for info in txt_infos:
            text = decode_text(zf.read(info))
            log(f"\n===== TXT／報告：{info.filename} =====")
            if len(text) <= 20000:
                log(text)
            else:
                log(text[:14000])
                log("\n……報告中段省略，以控制 job log 長度……\n")
                log(text[-3000:])

        # 先完整輸出彙總／統計 CSV（最多 80 列），其他 CSV 僅輸出標題與少量例列。
        csv_infos.sort(key=lambda i: (
            0 if any(k in PurePosixPath(i.filename).stem.lower() for k in ("彙總", "summary", "統計")) else 1,
            i.filename,
        ))
        for info in csv_infos:
            log(f"\n===== CSV：{info.filename} =====")
            csv_preview(info.filename, zf.read(info), limit_rows=5)

        if not txt_infos and not csv_infos:
            log("ZIP 未找到 TXT／CSV；請檢查 ZIP 內其他格式再決定後續解析方式。")


def main() -> int:
    parser = argparse.ArgumentParser(description="下載並安全摘要公開 GitHub ZIP；不修改 repository。")
    parser.add_argument("--repo", default="CHLINX/sso", help="owner/repository")
    parser.add_argument("--ref", default="main", help="分支、標籤或提交 SHA")
    parser.add_argument("--path", required=True, help="ZIP 在 repository 內的完整路徑")
    parser.add_argument("--expected-size", type=int, default=None, help="先前由 GitHub 核對的檔案大小（bytes）")
    args = parser.parse_args()
    try:
        data = download_zip(args.repo, args.ref, args.path, args.expected_size)
        inspect_zip(data)
        log("\nGitHub ZIP 讀取完成；本程式只讀，不修改 main。")
        return 0
    except Exception as exc:
        log(f"錯誤：{exc}")
        return 1


if __name__ == "__main__":
    # 以一般返回碼結束；勿使用 sys.exit()，避免在 Notebook 出現 SystemExit traceback。
    result = main()
    if result != 0:
        print(f"程式回傳非零狀態：{result}", flush=True)

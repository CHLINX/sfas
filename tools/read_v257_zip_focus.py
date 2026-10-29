#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
v2.57 focused ZIP reader — GitHub Actions only, read-only.

固定提醒：依「GitHub ZIP 讀取標準流程」辦理。
- 先確認 Repository／分支／完整檔名／大小。
- 公開 ZIP 二進位讀取失敗時，不要求使用者重傳。
- 只在獨立暫存分支新增／調整 workflow，絕不修改 main。
- Python 下載並核對大小，解壓後讀取 TXT／CSV；用 job log 取回結果。
- log 截斷時縮小輸出範圍後再執行。
"""
from __future__ import annotations

import csv
import io
import urllib.request
import zipfile
from urllib.parse import quote

REPO = "CHLINX/sso"
REF = "main"
PATH = "SSO_v2.57_條件式交易模式回溯核驗結果_20261029_062605.zip"
EXPECTED_SIZE = 12_721_426


def say(text: str = "") -> None:
    print(text, flush=True)


def read_csv(zf: zipfile.ZipFile, name: str) -> list[dict[str, str]]:
    raw = zf.read(name)
    text = raw.decode("utf-8-sig", errors="replace")
    return list(csv.DictReader(io.StringIO(text)))


def truth(value: str | None) -> bool:
    return str(value or "").strip().lower() in {"true", "1", "yes", "t"}


def num(value: str | None) -> float | None:
    try:
        v = str(value or "").strip()
        if not v or v.lower() in {"nan", "none"}:
            return None
        return float(v)
    except (TypeError, ValueError):
        return None


def fmt(value: str | None) -> str:
    v = str(value or "").strip()
    return v if v else "NA"


def main() -> None:
    # 避免大 ZIP 在一般 connector 中被當作 UTF-8 文字讀取；由 runner 下載原始位元組。
    url = f"https://raw.githubusercontent.com/{REPO}/{quote(REF, safe='')}/{quote(PATH, safe='/')}"
    say("GitHub ZIP 讀取標準流程｜v2.57 定點核驗")
    say(f"Repository：{REPO}")
    say(f"Branch：{REF}")
    say(f"檔名：{PATH}")
    say(f"預期大小：{EXPECTED_SIZE:,} bytes")
    req = urllib.request.Request(url, headers={"User-Agent": "sso-v257-focused-reader/1.0"})
    with urllib.request.urlopen(req, timeout=120) as response:
        data = response.read()
        say(f"HTTP：{getattr(response, 'status', 200)}；實際大小：{len(data):,} bytes")
    if len(data) != EXPECTED_SIZE:
        raise RuntimeError(f"大小不符：expected={EXPECTED_SIZE}, actual={len(data)}")
    if not zipfile.is_zipfile(io.BytesIO(data)):
        raise RuntimeError("GitHub 回傳內容不是有效 ZIP")

    with zipfile.ZipFile(io.BytesIO(data)) as zf:
        files = [i for i in zf.infolist() if not i.is_dir()]
        say(f"ZIP 內檔案數：{len(files)}")
        for info in files:
            say(f"  {info.filename}\t{info.file_size:,} bytes")

        by_suffix = {name.rsplit("/", 1)[-1]: name for name in zf.namelist() if not name.endswith("/")}
        report_names = [n for n in by_suffix if n.lower().endswith((".txt", ".md")) and "v2.57" in n.lower()]
        for name in report_names:
            report = zf.read(by_suffix[name]).decode("utf-8-sig", errors="replace")
            say(f"\n===== 報告：{name} =====")
            say(report[:15000] if len(report) > 15000 else report)

        summary_name = next((n for n in by_suffix if n == "v2.57_條件式回溯績效彙總.csv"), None)
        consistency_name = next((n for n in by_suffix if n == "v2.57_條件旗標一致性.csv"), None)
        detail_name = next((n for n in by_suffix if n == "v2.57_條件式逐筆重建結果.csv"), None)
        mismatch_name = next((n for n in by_suffix if n == "v2.57_條件旗標不一致逐筆清單.csv"), None)

        if summary_name:
            rows = read_csv(zf, by_suffix[summary_name])
            say(f"\n===== 條件式回溯績效彙總：{len(rows)} rows（完整 32 組） =====")
            cols = [
                "持有期間H", "成本情境", "交易模式", "區段口徑",
                "模式原始資料列數", "條件旗標選中筆數",
                "成功配對且有實際淨報酬筆數", "平均淨報酬", "淨勝率",
                "前10名平均淨報酬", "前10名淨勝率",
            ]
            say(" | ".join(cols))
            for row in rows:
                say(" | ".join(fmt(row.get(c)) for c in cols))

        if consistency_name:
            rows = read_csv(zf, by_suffix[consistency_name])
            say(f"\n===== 條件旗標一致性：{len(rows)} rows =====")
            cols = [
                "持有期間H", "成本情境", "交易模式", "區段口徑",
                "參照條件定義", "比較列數", "不一致筆數",
                "模式旗標真但條件假", "條件真但模式旗標假",
            ]
            say(" | ".join(cols))
            for row in rows:
                say(" | ".join(fmt(row.get(c)) for c in cols))

        if detail_name:
            rows = read_csv(zf, by_suffix[detail_name])
            say(f"\n===== 逐筆重建資料旗標聚合：{len(rows):,} rows =====")
            modes: dict[str, dict[str, int]] = {}
            for row in rows:
                mode = fmt(row.get("交易模式"))
                agg = modes.setdefault(mode, {
                    "rows": 0, "mode_flag_true": 0, "profit_flag_true": 0,
                    "potential_high": 0, "predicted_net_positive": 0,
                    "selected_flag_true": 0, "usable_net_return": 0,
                })
                agg["rows"] += 1
                agg["mode_flag_true"] += int(truth(row.get("達成交易模式條件")))
                agg["profit_flag_true"] += int(truth(row.get("符合獲利候選條件")))
                agg["potential_high"] += int(fmt(row.get("上漲潛力")) == "高")
                pred = num(row.get("預測淨報酬"))
                agg["predicted_net_positive"] += int(pred is not None and pred > 0)
                agg["selected_flag_true"] += int(truth(row.get("條件旗標達成")))
                agg["usable_net_return"] += int(num(row.get("重建可用淨報酬")) is not None)
            say("交易模式 | 列數 | 達成交易模式條件=True | 符合獲利候選條件=True | 上漲潛力=高 | 預測淨報酬>0 | 條件旗標達成=True | 重建淨報酬可用")
            for mode, a in modes.items():
                say(f"{mode} | " + " | ".join(str(a[k]) for k in (
                    "rows", "mode_flag_true", "profit_flag_true", "potential_high",
                    "predicted_net_positive", "selected_flag_true", "usable_net_return"
                )))

        if mismatch_name:
            rows = read_csv(zf, by_suffix[mismatch_name])
            say(f"\n===== 旗標不一致逐筆清單聚合：{len(rows):,} rows =====")
            groups: dict[tuple[str, str, str, str, str], int] = {}
            for row in rows:
                key = (
                    fmt(row.get("交易模式")),
                    fmt(row.get("上漲潛力")),
                    fmt(row.get("符合獲利候選條件")),
                    fmt(row.get("達成交易模式條件")),
                    fmt(row.get("候選狀態")),
                )
                groups[key] = groups.get(key, 0) + 1
            say("交易模式 | 上漲潛力 | 符合獲利候選條件 | 達成交易模式條件 | 候選狀態 | 不一致列數")
            for key, count in sorted(groups.items(), key=lambda kv: (-kv[1], kv[0]))[:20]:
                say(" | ".join(key) + f" | {count}")

    say("\n完成：以 Python 在 GitHub Actions 讀取公開 ZIP；未修改 main，也未要求重新上傳。")


if __name__ == "__main__":
    main()

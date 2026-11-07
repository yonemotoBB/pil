#!/usr/bin/env python3
"""空港一覧と、AIP Japan の空港チャートから選んだ図を、ニーボードに挟む A5 の 1 冊にする。

  python3 印刷用/build_charts.py            # 落としてあればそれを使う
  python3 印刷用/build_charts.py --fetch    # AIP の写しから落とし直す（AIRAC が変わったとき）

出力: 印刷用/空港チャート.pdf（A5 148×210mm 縦。ニーボードと同じ大きさ）
  1 ページ目 空港一覧（印刷用/空港一覧.html。2026-11-07 にニーボードから移した）
  2 ページ目から 空港ごとのチャート（A4 の AIP のページをベクターのまま縮める）
落としたチャート: 印刷用/aip/<ICAO>_chart.pdf（PDF なので git には入らない）

チャートは nagodede.github.io/aip/japan の写し（AIS Japan の eAIP を機械で落としたもの）から取る。
写しの版は documents/info.json の EffectiveDate。使う前に最新の AIRAC と見比べる。
"""
import json
import pathlib
import sys
import tempfile
import urllib.request

import fitz  # PyMuPDF

from build_kneeboard import render

ROOT = pathlib.Path(__file__).resolve().parent
AIP = ROOT / "aip"
OUT = ROOT / "空港チャート.pdf"
BASE = "https://nagodede.github.io/aip/japan/documents/"

# 空港ごとに、チャートの PDF の何ページ目（1 から）を入れるか。
# 岡南以外に VFR の経路図は無いので、V-REP と LDG チャート（周りの地形・障害物）を入れる。
PICK = {
    "RJBK": [(1, "AD チャート"), (2, "Visual REP"), (3, "標準場周経路・到着出発経路")],
    "RJOB": [(1, "AD チャート"), (25, "Visual REP"), (26, "LDG チャート")],
    "RJOA": [(1, "AD チャート"), (30, "Visual REP"), (31, "LDG チャート")],
    "RJOT": [(1, "AD チャート"), (21, "Visual REP"), (22, "LDG チャート")],
}

A5 = (148 / 25.4 * 72, 210 / 25.4 * 72)  # A5 縦（pt）。ニーボード（build_kneeboard.py）と同じ


def fetch(name: str) -> pathlib.Path:
    AIP.mkdir(exist_ok=True)
    dst = AIP / name
    with urllib.request.urlopen(BASE + name, timeout=180) as r:
        dst.write_bytes(r.read())
    return dst


def main(out: pathlib.Path = OUT) -> None:
    """out はテストが一時ディレクトリのパスを渡すため。"""
    refetch = "--fetch" in sys.argv[1:]
    if refetch or not (AIP / "info.json").exists():
        fetch("info.json")
    eff = json.loads((AIP / "info.json").read_text())["EffectiveDate"][:10]

    doc = fitz.open()
    with tempfile.TemporaryDirectory() as tmp:
        part = pathlib.Path(tmp) / "空港一覧.pdf"
        render(ROOT / "空港一覧.html", part)
        doc.insert_pdf(fitz.open(part))
    print("空港一覧")
    for icao, pages in PICK.items():
        src_path = AIP / f"{icao}_chart.pdf"
        if refetch or not src_path.exists():
            src_path = fetch(src_path.name)
        src = fitz.open(src_path)
        for n, title in pages:
            sp = src[n - 1]
            page = doc.new_page(width=A5[0], height=A5[1])
            # 縦横比を保って A5 いっぱいに縮める（show_pdf_page が中央に寄せる）
            page.show_pdf_page(page.rect, src, n - 1, keep_proportion=True)
            print(f"{icao} p{n:2} {title}（元 {sp.rect.width:.0f}×{sp.rect.height:.0f}pt）")
    doc.set_metadata({"title": f"空港チャート（AIP Japan {eff} 発効の版）"})
    doc.save(out, garbage=3, deflate=True)
    print(f"{out}（{len(doc)} ページ、AIP {eff} 発効の版）")


if __name__ == "__main__":
    main()

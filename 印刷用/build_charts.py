#!/usr/bin/env python3
"""空港一覧と、AIP Japan の空港チャートから選んだ図を、ニーボードに挟む A5 の 1 冊にする。

  python3 印刷用/build_charts.py            # 落としてあればそれを使う
  python3 印刷用/build_charts.py --fetch    # AIP の写しから落とし直す（AIRAC が変わったとき）

出力（どれも A5 148×210mm 縦。ニーボードと同じ大きさ。A4 の AIP のページはベクターのまま縮める）:
  印刷用/空港チャート.pdf  1 ページ目が空港一覧（印刷用/空港一覧.html。2026-11-07 にニーボードから移した）、
                           そのあと空港ごとの AD チャートと経路／LDG チャート（白黒で刷る）
  印刷用/V-REP.pdf         空港ごとの Visual REP（カラーで刷るので分けた。2026-11-07、ユーザーの指定）
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
OUT_VREP = ROOT / "V-REP.pdf"
BASE = "https://nagodede.github.io/aip/japan/documents/"

# 空港ごとに、チャートの PDF の何ページ目（1 から）を入れるか。
# 岡南以外に VFR の経路図は無いので、LDG チャート（周りの地形・障害物）を入れる。
PICK = {
    "RJBK": [(1, "AD チャート"), (3, "標準場周経路・到着出発経路")],
    "RJOB": [(1, "AD チャート"), (26, "LDG チャート")],
    "RJOA": [(1, "AD チャート"), (31, "LDG チャート")],
    "RJOT": [(1, "AD チャート"), (22, "LDG チャート")],
}
# Visual REP のページ（V-REP.pdf に入れる）
VREP = {"RJBK": 2, "RJOB": 25, "RJOA": 30, "RJOT": 21}

A5 = (148 / 25.4 * 72, 210 / 25.4 * 72)  # A5 縦（pt）。ニーボード（build_kneeboard.py）と同じ


def fetch(name: str) -> pathlib.Path:
    AIP.mkdir(exist_ok=True)
    dst = AIP / name
    with urllib.request.urlopen(BASE + name, timeout=180) as r:
        dst.write_bytes(r.read())
    return dst


def add_page(doc, src, n: int) -> None:
    page = doc.new_page(width=A5[0], height=A5[1])
    # 縦横比を保って A5 いっぱいに縮める（show_pdf_page が中央に寄せる）
    page.show_pdf_page(page.rect, src, n - 1, keep_proportion=True)


def main(out: pathlib.Path = OUT, out_vrep: pathlib.Path = OUT_VREP) -> None:
    """out・out_vrep はテストが一時ディレクトリのパスを渡すため。"""
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
    vrep = fitz.open()
    for icao, pages in PICK.items():
        src_path = AIP / f"{icao}_chart.pdf"
        if refetch or not src_path.exists():
            src_path = fetch(src_path.name)
        src = fitz.open(src_path)
        for n, title in pages:
            add_page(doc, src, n)
            print(f"{icao} p{n:2} {title}")
        add_page(vrep, src, VREP[icao])
        print(f"{icao} p{VREP[icao]:2} Visual REP → V-REP.pdf")
    for d, path, name in [(doc, out, "空港チャート"), (vrep, out_vrep, "V-REP")]:
        d.set_metadata({"title": f"{name}（AIP Japan {eff} 発効の版）"})
        d.save(path, garbage=3, deflate=True)
        print(f"{path}（{len(d)} ページ、AIP {eff} 発効の版）")

if __name__ == "__main__":
    main()

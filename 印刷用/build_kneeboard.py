#!/usr/bin/env python3
"""ニーボードに挟む早見表を A5 の PDF にする。

  python3 印刷用/build_kneeboard.py

出力: 印刷用/ニーボード.pdf（A5（148×210mm）縦 2 ページ。両面で 1 枚）。中身は HTML を直す:
  1 ページ目 印刷用/ニーボード.html      ①非常時
  2 ページ目 印刷用/ニーボード_手順.html R44 の手順（始動前〜停止。2026-11-04 に足した）
2026-11-07、ユーザーの指定で、②空港は 空港一覧.html に分けて空港チャート（build_charts.py）の頭へ移し、
別の PDF だった手順をこちらにまとめた。

Playwright が落としてある Chromium をヘッドレスで使う。印刷の大きさは
HTML の @page で決めているので、印刷するときは「実際のサイズ」（拡大縮小なし）にする。
"""
import glob
import pathlib
import subprocess
import sys
import tempfile

import fitz  # PyMuPDF

ROOT = pathlib.Path(__file__).resolve().parent
PAGES = ["ニーボード", "ニーボード_手順"]  # この順で 1 冊にする
OUT_NAME = "ニーボード.pdf"

CANDIDATES = [
    "~/.cache/ms-playwright/chromium_headless_shell-*/chrome-headless-shell-linux64/chrome-headless-shell",
    "~/.cache/ms-playwright/chromium-*/chrome-linux64/chrome",
    "/opt/pw-browsers/chromium-*/chrome-linux/chrome",
]


def find_chrome() -> str:
    for pat in CANDIDATES:
        hits = sorted(glob.glob(str(pathlib.Path(pat).expanduser())))
        if hits:
            return hits[-1]
    sys.exit("Chromium が見つからない（~/.cache/ms-playwright を確認）")


def render(src: pathlib.Path, out: pathlib.Path) -> None:
    """HTML を PDF にする（紙の大きさは HTML の @page）。build_charts.py も使う。"""
    subprocess.run(
        [
            find_chrome(),
            "--headless",
            "--no-sandbox",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--print-to-pdf={out}",
            src.as_uri(),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def main(out_dir: pathlib.Path = ROOT) -> None:
    """out_dir はテストが一時ディレクトリを渡すため。"""
    out = out_dir / OUT_NAME
    doc = fitz.open()
    with tempfile.TemporaryDirectory() as tmp:
        for name in PAGES:
            part = pathlib.Path(tmp) / f"{name}.pdf"
            render(ROOT / f"{name}.html", part)
            doc.insert_pdf(fitz.open(part))
    doc.save(out, garbage=3, deflate=True)
    print(f"{out}（{len(doc)} ページ）")


if __name__ == "__main__":
    main()

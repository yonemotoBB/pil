#!/usr/bin/env python3
"""ニーボードに挟む早見表を A5 の PDF にする。

  python3 印刷用/build_kneeboard.py

入力 → 出力（中身は HTML を直す。どれも A5（148×210mm）縦・2 ページ。両面で 1 枚）:
  印刷用/ニーボード.html      → ニーボード.pdf      ①非常時・②空港
  印刷用/ニーボード_手順.html → ニーボード_手順.pdf ③始動前・エンジン始動・④離陸・停止（R44。2026-11-04 に足した）

Playwright が落としてある Chromium をヘッドレスで使う。印刷の大きさは
HTML の @page で決めているので、印刷するときは「実際のサイズ」（拡大縮小なし）にする。
"""
import glob
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent
PAGES = ["ニーボード", "ニーボード_手順"]

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


def main() -> None:
    chrome = find_chrome()
    for name in PAGES:
        src, out = ROOT / f"{name}.html", ROOT / f"{name}.pdf"
        subprocess.run(
            [
                chrome,
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
        print(out)


if __name__ == "__main__":
    main()

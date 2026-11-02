#!/usr/bin/env python3
"""ニーボードに挟む早見表（非常時・空港）を JIS B5 の PDF にする。

  python3 印刷用/build_kneeboard.py

入力: 印刷用/ニーボード.html（中身はこちらを直す）
出力: 印刷用/ニーボード.pdf（182×257mm 縦・2 ページ。両面で 1 枚）

Playwright が落としてある Chromium をヘッドレスで使う。印刷の大きさは
HTML の @page で決めているので、印刷するときは「実際のサイズ」（拡大縮小なし）にする。
"""
import glob
import pathlib
import subprocess
import sys

ROOT = pathlib.Path(__file__).resolve().parent
SRC = ROOT / "ニーボード.html"
OUT = ROOT / "ニーボード.pdf"

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
    subprocess.run(
        [
            find_chrome(),
            "--headless",
            "--no-sandbox",
            "--disable-gpu",
            "--no-pdf-header-footer",
            f"--print-to-pdf={OUT}",
            SRC.as_uri(),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    print(OUT)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""chapters/*.md から HackMD で印刷するための一条一ページ版を生成する。

  python3 印刷用/build_print.py

出力: 印刷用/法規_印刷用.md
  - 一条文＋その施行規則で 1 ページ（ページ末に page-break）
  - ページ下半分に罫線のメモ欄（表の枠線なので背景印刷オフでも出る）
  - <details> の原文は印刷で見えないため展開する
"""
import math
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent
SRC = [
    ROOT / "chapters" / "01_第一章.md",
    ROOT / "chapters" / "04_第四章.md",
    ROOT / "chapters" / "06_第六章.md",
]
OUT = ROOT / "印刷用" / "法規_印刷用.md"

# A4 縦・HackMD の既定スタイルで 1 ページに収まるおおよその行数
PAGE_LINES = 44
# 日本語で 1 行に入るおおよその文字数
CHARS_PER_LINE = 42
# メモ欄 1 行あたりの高さ（本文何行分か）
MEMO_ROW_LINES = 2

PAGE_BREAK = '<div style="page-break-after: always;"><span style="display: none;">&nbsp;</span></div>'

SKIP = re.compile(r"^(\[← 戻る\]|\[toc\]|\[TOC\]|\[前へ:|\[次へ:|---\s*$)", re.I)


def width(s: str) -> float:
    """全角を 1、半角を 0.5 として表示幅を返す。"""
    return sum(1.0 if ord(c) > 0x2E80 else 0.5 for c in s)


def est_lines(lines) -> int:
    """描画後のおおよその行数。"""
    n = 0
    in_mermaid = False
    for l in lines:
        s = l.strip()
        if s.startswith("```"):
            in_mermaid = not in_mermaid
            n += 1 if not in_mermaid else 0
            continue
        if in_mermaid:
            continue  # 図の高さは下でまとめて加算
        if not s:
            n += 0.4
            continue
        # 条文中の生 HTML 表はタグだけの行が多い。中身のある行だけ数える
        if re.match(r"^>?\s*</?(table|tbody|tr|section)", s):
            continue
        s = re.sub(r"^>\s*", "", s)
        s = re.sub(r"<[^>]+>", "", s)
        n += max(1, math.ceil(width(s) / CHARS_PER_LINE))
    # mermaid 1 図あたり 12 行分とみなす
    n += 12 * sum(1 for l in lines if l.strip() == "```mermaid")
    return int(round(n))


def memo_block(content_lines) -> list:
    """残りの高さに合わせた罫線メモ欄。最低 3 行は確保する。"""
    used = est_lines(content_lines) + 4  # 見出しとメモ欄のヘッダ分
    rows = int((PAGE_LINES - used) // MEMO_ROW_LINES)
    rows = max(3, min(rows, 14))
    out = ["", "| メモ |", "| :--- |"]
    out += ["| &nbsp;<br>&nbsp; |"] * rows
    return out


def expand_details(lines) -> list:
    """印刷すると畳まれたままの <details> を展開する。"""
    out = []
    for l in lines:
        s = l.strip()
        if s in ("<details>", "</details>"):
            continue
        m = re.match(r"^<summary>(.*)</summary>$", s)
        if m:
            if m.group(1).strip() != "原文":
                out.append(f"**{m.group(1)}**")
                out.append("")
            continue
        out.append(l)
    return out


def fold_raw_tables(body) -> list:
    """条文に埋まった生 HTML の別表を、同じページの要約表への参照に置き換える。

    別表をそのまま載せると 1 条で数ページになるため。要約表が同じページに
    ないときは畳まず原文のまま残す。
    """
    if not any(re.match(r"^\|", l) for l in body):
        return body
    out, buf, in_tbl = [], [], False
    for l in body:
        s = l.strip()
        if re.match(r"^>?\s*<table", s):
            in_tbl, buf = True, [l]
            continue
        if in_tbl:
            buf.append(l)
            if re.search(r"</table>", s):
                in_tbl = False
                if len(buf) > 15:
                    out.append("> ※ 別表は原文が長いため省略。**本条の要約表**を参照"
                               "（原文は `chapters/` の該当条）。")
                else:
                    out += buf
                buf = []
            continue
        out.append(l)
    return out + buf


def trim(lines) -> list:
    while lines and not lines[0].strip():
        lines.pop(0)
    while lines and not lines[-1].strip():
        lines.pop()
    return lines


def parse(path: pathlib.Path):
    """(章名, [(ページ見出し, 本文行)]) を返す。"""
    chapter = ""
    section = ""
    pages = []          # [(見出し, [行])]
    cur_title = None
    cur_body = []

    def flush():
        nonlocal cur_title, cur_body
        body = trim(fold_raw_tables(expand_details(cur_body)))
        if cur_title and body:
            pages.append((cur_title, body))
        cur_title, cur_body = None, []

    for raw in path.read_text(encoding="utf-8").split("\n"):
        line = raw.rstrip()
        if SKIP.match(line.strip()):
            continue
        if line.startswith("## ") and not line.startswith("###"):
            chapter = line[3:].strip()
            continue
        if line.startswith("### "):
            flush()
            section = line[4:].strip()
            # 第一章の「第二条 定義」のように ### 自体が条のもの
            if re.match(r"^第[〇一二三四五六七八九十百]+条", section):
                cur_title = section
                cur_body = []
            continue
        m = re.match(r"^#### ==(.+?)==\s*$", line)
        if m:
            flush()
            art = m.group(1).strip()
            cur_title = f"{art}　{section}" if section else art
            cur_body = []
            continue
        if cur_title is None:
            # 条の外（第一章の定義見出しなど）は直前のページに積む
            if pages and line.strip():
                pages[-1][1].append(line)
            elif line.strip():
                cur_title, cur_body = section or chapter, [line]
            continue
        cur_body.append(line)
    flush()
    return chapter, pages


def split_oversized(title, body):
    """1 ページに収まらない条は、規則や定義の見出しで区切って続きのページにする。"""
    if est_lines(body) <= PAGE_LINES:
        return [(title, body)]
    heads = [i for i, l in enumerate(body) if l.startswith(("#### ", "##### "))]
    if not heads:
        return [(title, body)]  # 区切りどころがない条はそのまま流す

    target = int(PAGE_LINES * 0.45)  # 本文は上半分まで、下半分をメモ欄に残す
    chunks, cur = [], []
    for i, l in enumerate(body):
        if i in heads and cur and est_lines(cur) >= target:
            chunks.append(cur)
            cur = []
        cur.append(l)
    if cur:
        chunks.append(cur)
    if len(chunks) == 1:
        return [(title, chunks[0])]
    return [(f"{title}（{i}/{len(chunks)}）", c) for i, c in enumerate(chunks, 1)]


def main():
    out = [
        "---",
        "title: 法規 印刷用（一条一ページ・メモ欄つき）",
        "---",
        "# 法規　印刷用",
        "",
        "`chapters/*.md` から生成。**一条文＋その施行規則で1ページ**、ページ下部が手書き用のメモ欄。",
        "A4縦・余白は既定のままブラウザから印刷する（メモ欄は表の枠線なので「背景のグラフィック」はオフでよい）。",
        "編集は `chapters/*.md` 側で行い、`python3 印刷用/build_print.py` で作り直す。",
        "",
        "[TOC]",
        "",
        PAGE_BREAK,
        "",
    ]
    stats = []
    for path in SRC:
        chapter, pages = parse(path)
        expanded = []
        for title, body in pages:
            expanded += split_oversized(title, body)
        out += [f"# {chapter}", "", PAGE_BREAK, ""]
        for title, body in expanded:
            out.append(f"## {title}")
            out.append("")
            out += body
            out += memo_block(body)
            out += ["", PAGE_BREAK, ""]
        over = [t for t, b in expanded if est_lines(b) > PAGE_LINES]
        stats.append((chapter, len(expanded), over))

    OUT.write_text("\n".join(out) + "\n", encoding="utf-8")

    total = sum(n for _, n, _ in stats)
    print(f"{OUT.relative_to(ROOT)}: {total + 1 + len(stats)} ページ")
    for chapter, n, over in stats:
        print(f"  {chapter}: {n} ページ")
        for t in over:
            print(f"    ※1ページに収まらない見込み: {t}")


if __name__ == "__main__":
    main()

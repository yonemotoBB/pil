from pathlib import Path

path = Path(r"D:\doc\heli\PIL法規.md")
text = path.read_text(encoding="utf-8")
needle = "## 第一章"
if needle in text:
    before = text[: text.index(needle)]
    new_section = "## 章ごとの本文\n\n各章の本文は個別のMarkdownファイルに分けました。以下のリンクから参照できます。\n\n- [第一章](chapters/01_第一章.md)\n- [第四章](chapters/04_第四章.md)\n- [第六章](chapters/06_第六章.md)\n\nこのページは目次・リンク集として整理しています。\n"
    path.write_text(before + new_section, encoding="utf-8")
    print("updated")
else:
    print("needle not found")

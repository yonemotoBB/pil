from pathlib import Path
import re

root = Path(r"D:\doc\heli")
src = root / "PIL法規.md"
text = src.read_text(encoding="utf-8")

pattern = re.compile(r"^## (第一章|第四章|第六章)", re.M)
matches = list(pattern.finditer(text))
if len(matches) < 3:
    raise SystemExit("Expected chapter headings not found")

prefix = text[:matches[0].start()].rstrip() + "\n"
chapters = [
    ("01_第一章.md", text[matches[0].start():matches[1].start()].lstrip("\n")),
    ("04_第四章.md", text[matches[1].start():matches[2].start()].lstrip("\n")),
    ("06_第六章.md", text[matches[2].start():].lstrip("\n")),
]

chap_dir = root / "chapters"
chap_dir.mkdir(exist_ok=True)

for filename, content in chapters:
    chapter_path = chap_dir / filename
    chapter_text = f"[← 戻る](../PIL法規.md)\n\n{content}"
    chapter_path.write_text(chapter_text, encoding="utf-8")

index_text = f"""{prefix}

## 章ごとの分割

各章の本文は個別のMarkdownファイルに分けました。以下のリンクから各章を開けます。

- [第一章](chapters/01_第一章.md)
- [第四章](chapters/04_第四章.md)
- [第六章](chapters/06_第六章.md)
"""

src.write_text(index_text, encoding="utf-8")
print("Split complete")

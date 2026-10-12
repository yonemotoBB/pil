#!/usr/bin/env python3
"""chapters/*.md から、ミュージックプレイヤーで聞く読み上げ音声（一条＝1トラックの mp3）を作る。

  読み上げ/.venv/bin/python 読み上げ/build_audio.py --dump            # 読み上げ原稿だけ 読み上げ/out/原稿/ に出す（音声は作らない）
  読み上げ/.venv/bin/python 読み上げ/build_audio.py                   # 全トラックを作る
  読み上げ/.venv/bin/python 読み上げ/build_audio.py --only 第七十条   # 見出しに一致するトラックだけ

出力: 読み上げ/out/法規/NNN_条_見出し.mp3（生成物なのでコミットしない）
  - 条の切り方は 印刷用/build_print.py と同じ（一条文＋その施行規則で 1 トラック）
  - mermaid の図とその見出しは読まない。要約表は「項目。見出し、値。」の形で読む
  - 長い別表（生 HTML）は、同じ条に要約表があれば読まない
  - 旧仮名の「あつて」「行つて」は「あって」「行って」に直してから読ませる

読み上げは手元の VOICEVOX エンジン（CPU 版、http://127.0.0.1:50021）。ネット不要・GPU 不要。
  docker run -d --name voicevox -p 127.0.0.1:50021:50021 voicevox/voicevox_engine:cpu-latest
mp3 化に ffmpeg、タグ付けに mutagen を使う（python3 -m venv 読み上げ/.venv して pip install mutagen）。
誤読は READINGS（VOICEVOX のユーザー辞書に登録）と clean() の置き換えで直している。
edge-tts（Microsoft の読み上げ）は 2026-10-12 に 403 で断られたので使っていない。
"""
import argparse
import html
import io
import json
import pathlib
import re
import subprocess
import sys
import urllib.parse
import urllib.request
import wave

ROOT = pathlib.Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "印刷用"))
import build_print  # noqa: E402  条の切り方を印刷用と揃える

OUT = ROOT / "読み上げ" / "out"
ALBUM = "PIL 法規"
ARTIST = "PIL 読み上げ"

# VOICEVOX が読み違える用語。起動のたびにユーザー辞書へ登録する（読み, アクセント核）。
# 2026-10-12 に原稿の漢字語 1433 語の読みを一覧して拾った。新しく誤読を見つけたらここに足す
READINGS = {
    "回転翼": ("カイテンヨク", 3), "補助翼": ("ホジョヨク", 2), "翼端": ("ヨクタン", 0),
    "滑油": ("カツユ", 0), "発動機": ("ハツドウキ", 3), "火工品": ("カコウヒン", 0),
    "型式": ("カタシキ", 0), "耐空": ("タイクウ", 0), "灯火": ("トウカ", 1),
    "正切": ("セイセツ", 0), "鉛直": ("エンチョク", 0), "蒸気圧": ("ジョウキアツ", 3),
    "安定板": ("アンテイバン", 0), "物標": ("ブッピョウ", 0), "緊急時": ("キンキュウジ", 3),
    "上方": ("ジョウホウ", 0), "直前方": ("チョクゼンポウ", 3), "最外側面": ("サイガイソクメン", 5),
    "上面": ("ジョウメン", 0), "下面": ("カメン", 0), "上欄": ("ジョウラン", 0), "下欄": ("カラン", 0),
    "前号": ("ゼンゴウ", 0), "水上": ("スイジョウ", 0), "標点": ("ヒョウテン", 0),
    "巡航高度": ("ジュンコウコウド", 5), "何人も": ("ナンピトモ", 1),
}

UNITS = [("km", "キロメートル"), ("kg", "キログラム"), ("cm", "センチメートル"),
         ("ft", "フィート"), ("kt", "ノット"), ("m", "メートル")]


def clean(s: str) -> str:
    """1 行ぶんの記法を落として、読ませる文字だけにする。"""
    s = re.sub(r"<ruby>.*?<rt>(.*?)</rt></ruby>", r"\1", s)  # ルビは読みのほうを使う
    s = re.sub(r"<br\s*/?>", "。", s)
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)
    s = re.sub(r"!\[[^\]]*\]\([^)]*\)", "", s)
    s = re.sub(r"\[([^\]]*)\]\([^)]*\)", r"\1", s)
    s = re.sub(r"==|\*\*|`", "", s)
    # 旧仮名の促音（あつて・行つて・知つた）
    s = re.sub(r"(?<=[一-鿿ぁ-ん])つ(?=[てた])", "っ", s)
    s = s.replace("フラツプ", "フラップ")
    # e-Gov のルビが地の文に混ざったもの
    s = s.replace("擾じよう乱", "じょうらん").replace("牽けん引", "牽引").replace("曳えい航", "えい航")
    s = re.sub(r"追越し?", "追い越し", s)
    s = re.sub(r"(?<=[〇一二三四五六七八九十百千0-9０-９])分の(?=[〇一二三四五六七八九十百千0-9０-９])", "ぶんの", s)
    s = re.sub(r"(?<=[0-9０-９])[〜～](?=[0-9０-９])", "から", s)
    for u, yomi in UNITS:
        s = re.sub(rf"(?<=[0-9０-９〇一二三四五六七八九十百千万])\s*{u}(?![A-Za-z])", yomi, s)
    s = s.replace("／", "、").replace("＋", "と").replace("→", "、").replace("＝", "、")
    s = re.sub(r"[　 \t]+", "、", s.strip())  # 「一　飛行機」の空白は間にする
    s = re.sub(r"、*。[、。]*", "。", s)
    s = re.sub(r"、{2,}", "、", s)
    return s.strip("、")


def sentence(s: str) -> str:
    s = clean(s)
    if s and s[-1] not in "。？！":
        s += "。"
    return s


def md_table(rows) -> list:
    """要約表を「1列目。見出し、値。…」の文にする。"""
    cells = [[c.strip() for c in r.strip().strip("|").split("|")] for r in rows]
    cells = [r for r in cells if not all(re.fullmatch(r":?-+:?", c or "-") for c in r)]
    if not cells:
        return []
    head, out = cells[0], []
    for r in cells[1:]:
        parts = [r[0]] if r and r[0] else []
        for i, c in enumerate(r[1:], 1):
            if not c or c in "―－-—":
                continue
            h = head[i] if i < len(head) else ""
            # 2 列の表は見出しを繰り返さない
            parts.append(f"{h}、{c}" if h and len(head) > 2 else c)
        line = sentence("。".join(parts))
        if line:
            out.append(line)
    return out


def to_speech(title: str, body: list) -> list:
    """1 条ぶんの本文行を、読み上げる段落のリストにする。"""
    body = build_print.expand_details(body)
    has_summary = any(l.startswith("|") for l in body)
    out = [sentence(title)]
    last_plain = False   # 直前が地の文（図や表の見出し）か
    i = 0
    while i < len(body):
        s = re.sub(r"^>\s*", "", body[i].strip())
        if s.startswith("```"):
            # 図は読まない。直前の見出しも図が無いと意味が通らないので落とす
            if last_plain:
                out.pop()
            i += 1
            while i < len(body) and not body[i].strip().startswith("```"):
                i += 1
            i += 1
            last_plain = False
            continue
        if s.startswith("<table"):
            j = i
            while j < len(body) and "</table>" not in body[j]:
                j += 1
            raw = [re.sub(r"^>\s?", "", l.strip()) for l in body[i:j + 1]]
            if has_summary and len(raw) > 15:
                out.append("別表は省略。")
            else:
                for row in re.findall(r"<tr>(.*?)</tr>", "".join(raw), re.S):
                    tds = [clean(c) for c in re.findall(r"<td[^>]*>(.*?)</td>", row, re.S)]
                    line = sentence("。".join(c for c in tds if c))
                    if line:
                        out.append(line)
            i = j + 1
            last_plain = False
            continue
        if s.startswith("|"):
            j = i
            while j < len(body) and body[j].strip().startswith("|"):
                j += 1
            if last_plain:
                out[-1] = "まとめ。" + out[-1]
            out += md_table(body[i:j])
            i = j
            last_plain = False
            continue
        i += 1
        if not s or build_print.SKIP.match(s):
            continue
        if s.startswith("※ 別表は原文が長いため省略"):
            # build_print.parse が長い別表を畳んだ跡
            out.append("別表は省略。")
            last_plain = False
            continue
        m = re.match(r"^#{3,6}\s+(.*)$", s)
        if m:
            out.append(sentence(re.sub(r"(施行規則)(第)", r"\1、\2", m.group(1))))
            last_plain = False
            continue
        plain = not body[i - 1].lstrip().startswith((">", "*", "-"))
        s = re.sub(r"^[*-]\s+", "", s)
        line = sentence(s)
        if line:
            out.append(line)
            last_plain = plain
    return out


def tracks() -> list:
    """[(通し番号, 章名, 見出し, 段落リスト)]"""
    res = []
    for path in build_print.SRC:
        chapter, pages = build_print.parse(path)
        for title, body in pages:
            res.append((len(res) + 1, chapter, title, to_speech(title, body)))
    return res


def filename(no: int, title: str) -> str:
    return f"{no:03d}_" + re.sub(r"[\s　/\\:*?\"<>|]+", "_", title)


# ---- エンジン ----

def _post(url: str, data: bytes = b"") -> bytes:
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=600) as r:
        return r.read()


def ensure_dict(host: str):
    """READINGS のうち、まだ無い語だけユーザー辞書に登録する。"""
    have = {w["surface"] for w in json.loads(urllib.request.urlopen(f"{host}/user_dict").read()).values()}
    zen = str.maketrans({chr(c): chr(c + 0xFEE0) for c in range(0x21, 0x7F)})
    for surface, (yomi, accent) in READINGS.items():
        if surface.translate(zen) in have or surface in have:
            continue
        q = urllib.parse.urlencode({"surface": surface, "pronunciation": yomi, "accent_type": accent,
                                    "word_type": "COMMON_NOUN", "priority": 9})
        _post(f"{host}/user_dict_word?{q}")


def synth(paras, dst: pathlib.Path, speaker: str, rate: float, host: str):
    frames, params = [], None
    for p in paras:
        # 長い段落は句点で切って渡す（1 回が長いと合成が極端に遅くなる）
        for sent in re.findall(r"[^。]+。?", p):
            q = json.loads(_post(f"{host}/audio_query?speaker={speaker}&text={urllib.parse.quote(sent)}"))
            q["speedScale"] = rate
            q["postPhonemeLength"] = 0.35
            wav = _post(f"{host}/synthesis?speaker={speaker}", json.dumps(q).encode())
            with wave.open(io.BytesIO(wav)) as w:
                params = params or w.getparams()
                frames.append(w.readframes(w.getnframes()))
        frames.append(b"\0" * int(params.framerate * params.sampwidth * params.nchannels * 0.4))
    buf = io.BytesIO()
    with wave.open(buf, "wb") as w:
        w.setparams(params)
        w.writeframes(b"".join(frames))
    subprocess.run(["ffmpeg", "-loglevel", "error", "-y", "-i", "pipe:0",
                    "-codec:a", "libmp3lame", "-b:a", "64k", str(dst)],
                   input=buf.getvalue(), check=True)


def tag(dst: pathlib.Path, no: int, total: int, chapter: str, title: str):
    from mutagen.id3 import ID3, TALB, TIT2, TPE1, TRCK, TCON, ID3NoHeaderError
    try:
        t = ID3(dst)
    except ID3NoHeaderError:
        t = ID3()
    t.setall("TIT2", [TIT2(encoding=3, text=f"{title}（{chapter}）")])
    t.setall("TALB", [TALB(encoding=3, text=ALBUM)])
    t.setall("TPE1", [TPE1(encoding=3, text=ARTIST)])
    t.setall("TRCK", [TRCK(encoding=3, text=f"{no}/{total}")])
    t.setall("TCON", [TCON(encoding=3, text="Speech")])
    t.save(dst, v2_version=3)


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--speaker", default="13", help="VOICEVOX の話者 ID（既定 13＝青山龍星）")
    ap.add_argument("--host", default="http://127.0.0.1:50021")
    ap.add_argument("--rate", type=float, default=1.0, help="話す速さの倍率")
    ap.add_argument("--only", default="", help="見出しにこの文字を含むトラックだけ")
    ap.add_argument("--dump", action="store_true", help="原稿だけ出して音声は作らない")
    ap.add_argument("--force", action="store_true", help="すでにある mp3 も作り直す")
    ap.add_argument("--out", default=str(OUT / "法規"))
    a = ap.parse_args()

    all_tracks = tracks()
    total = len(all_tracks)
    sel = [t for t in all_tracks if a.only in t[2]]
    chars = sum(len("".join(p)) for *_, p in sel)
    print(f"{len(sel)}/{total} トラック、{chars} 文字")

    if a.dump:
        d = OUT / "原稿"
        d.mkdir(parents=True, exist_ok=True)
        for no, chapter, title, paras in sel:
            (d / f"{filename(no, title)}.txt").write_text("\n".join(paras) + "\n", encoding="utf-8")
        print(f"原稿: {d.relative_to(ROOT)}")
        return

    ensure_dict(a.host)
    out = pathlib.Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    for no, chapter, title, paras in sel:
        dst = out / f"{filename(no, title)}.mp3"
        if dst.exists() and not a.force:
            continue
        tmp = dst.with_suffix(".part.mp3")
        synth(paras, tmp, a.speaker, a.rate, a.host)
        tag(tmp, no, total, chapter, title)
        tmp.replace(dst)
        print(f"  {dst.name}  ({len(''.join(paras))} 文字)", flush=True)


if __name__ == "__main__":
    main()

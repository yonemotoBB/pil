# -*- coding: utf-8 -*-
"""2026-06.md を他の過去問ファイルと同じ形式に正規化しつつ、各問の「正答」折り
畳みに解説を注入する。

出力する形式（他ファイルと共通）:
  - 科目見出しは `### <科目>`（旧: `## <科目>（P..）`）
  - 設問マーカーは `**問N**`（旧: `**例題N**`、全角番号は半角化）
  - 目次は `[TOC]`（旧: `[toc]`）
  - 正答スポイラー内の解説は**コードブロックを使わず**プレーンに記載
    （用語は `**用語**` 見出し＋箇条書き、各選択肢は末尾に改行用スペース）
  - 正答番号は半角

解説データは 解説/2026-06_<code>.json（キー=問番号の文字列, 値=解説テキスト）。
旧形式・新形式のどちらを入力しても同じ新形式を出力する（冪等）。
"""
import json, os, re, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, '2026-06.md')
DATADIR = os.path.join(HERE, '解説')

NAME2CODE = {
    '航空工学': 'eng', '空中航法': 'nav', '航空気象': 'met',
    '航空通信': 'com', '航空法規': 'law',
}
WRAPPER = '## ２０２６年６月 例題集（回転翼）'


def nfkc(s):
    return unicodedata.normalize('NFKC', s)


def clean_yougo(line):
    """用語行から「～を問う問題」等のメタ説明文を除去する。"""
    segs = line.split('。')
    kept = [s for s in segs if s.strip() and not (
        s.rstrip().endswith('問う問題') or s.rstrip().endswith('を問う'))]
    if not kept:
        return None
    return '。'.join(kept) + '。'


def format_expl(expl):
    """JSON の解説テキストを、他ファイルと同じプレーン形式の行リストに整形する。
    - 「正答: <番号>」行は削除（番号はスポイラー先頭に既出）
    - 「用語:」行は `**用語**` 見出し＋箇条書きに変換
    - それ以外の行は末尾に改行用スペース2つを付ける
    """
    out = []
    for ln in expl.rstrip('\n').split('\n'):
        s = ln.strip()
        if not s:
            continue
        if re.match(r'^正答[:：]', s):
            continue
        m = re.match(r'^用語[:：]\s*(.*)$', s)
        if m:
            cleaned = clean_yougo('用語: ' + m.group(1))
            if cleaned is None:
                continue
            body = re.sub(r'^用語[:：]\s*', '', cleaned)
            out.append('**用語**  ')
            out.append('・' + body + '  ')
            continue
        out.append(s + '  ')
    return out


def load_data():
    data = {}
    for code in NAME2CODE.values():
        p = os.path.join(DATADIR, f'2026-06_{code}.json')
        if os.path.exists(p):
            with open(p, encoding='utf-8') as f:
                data[code] = json.load(f)
        else:
            data[code] = {}
    return data


def main():
    data = load_data()
    with open(TARGET, encoding='utf-8') as f:
        lines = f.read().split('\n')

    out = []
    cur_code = None
    cur_q = None
    injected = 0
    missing = []
    wrapper_done = False
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]

        # 目次
        if line.strip().lower() == '[toc]':
            out.append('[TOC]')
            i += 1
            continue

        # 既存のラッパー見出し（再実行時）
        if line.strip() == WRAPPER:
            wrapper_done = True
            out.append(line); i += 1; continue

        # 科目見出し（旧 `## 科目（P..）` / 新 `### 科目`）
        m = re.match(r'^#{2,3}\s*(.+?)(?:（|\(|\s|$)', line)
        if m and m.group(1).strip() in NAME2CODE:
            name = m.group(1).strip()
            if not wrapper_done:
                out.append(WRAPPER)
                out.append('')
                wrapper_done = True
            cur_code = NAME2CODE[name]
            cur_q = None
            out.append(f'### {name}')
            out.append('')
            i += 1
            while i < n and lines[i].strip() == '':
                i += 1
            continue

        # 設問マーカー（旧 `**例題N**` / 新 `**問N**`）
        m = re.match(r'^\*\*(?:例題|問)\s*([0-9０-９]+)\s*\*\*', line)
        if m:
            cur_q = str(int(nfkc(m.group(1))))
            out.append(f'**問{cur_q}**')
            out.append('')
            i += 1
            while i < n and lines[i].strip() == '':
                i += 1
            continue

        # 正答スポイラー
        if line.strip() == ':::spoiler 正答':
            j = i + 1
            body = []
            while j < n and lines[j].strip() != ':::':
                body.append(lines[j])
                j += 1
            # body の先頭にある正答番号（最初の非空行）だけ残す
            ans = None
            for b in body:
                if b.strip():
                    ans = nfkc(b.strip())
                    break
            out.append(line)  # :::spoiler 正答
            if ans is not None:
                out.append(ans)
            expl = None
            if cur_code and cur_q:
                expl = data.get(cur_code, {}).get(cur_q)
            if expl:
                out.append('')
                out.extend(format_expl(expl))
                injected += 1
            else:
                missing.append((cur_code, cur_q))
            out.append(':::')
            i = j + 1
            continue

        out.append(line)
        i += 1

    with open(TARGET, 'w', encoding='utf-8') as f:
        f.write('\n'.join(out))
    print(f'注入: {injected}件')
    if missing:
        print(f'解説なし: {len(missing)}件 -> {missing[:20]}')


if __name__ == '__main__':
    main()

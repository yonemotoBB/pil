# -*- coding: utf-8 -*-
"""2026-06.md の各例題の「正答」折り畳みに、解説コードブロックを注入する。

解説データは 解説/2026-06_<code>.json（キー=例題番号の文字列, 値=解説テキスト）。
再実行しても二重注入しないよう、既存のコードブロックは置換する（冪等）。
"""
import json, os, re, unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
TARGET = os.path.join(HERE, '2026-06.md')
DATADIR = os.path.join(HERE, '解説')

NAME2CODE = {
    '航空工学': 'eng', '空中航法': 'nav', '航空気象': 'met',
    '航空通信': 'com', '航空法規': 'law',
}

def nfkc(s):
    return unicodedata.normalize('NFKC', s)

def clean_yougo(line):
    """用語行から「～を問う問題」等のメタ説明文（何を問う問題か）を除去する。"""
    segs = line.split('。')
    kept = [s for s in segs if s.strip() and not (
        s.rstrip().endswith('問う問題') or s.rstrip().endswith('を問う'))]
    if not kept:
        return None  # 用語行が丸ごとメタ説明だった場合は行ごと削除
    return '。'.join(kept) + '。'

def trim_expl(expl):
    """コードブロックに入れる解説を整形する。
    - 「正答: <番号>」行は削除（番号は折り畳み内・コードブロック外に既出のため）
    - 「用語:」行の「～を問う問題」等のメタ説明を除去
    """
    out = []
    for ln in expl.rstrip('\n').split('\n'):
        s = ln.strip()
        if re.match(r'^正答[:：]', s):
            continue
        if re.match(r'^用語[:：]', s):
            cleaned = clean_yougo(ln)
            if cleaned is None:
                continue
            out.append(cleaned)
            continue
        out.append(ln)
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
    i = 0
    n = len(lines)
    while i < n:
        line = lines[i]
        # 科目見出し
        m = re.match(r'^##\s*(.+?)(?:（|\(|$)', line)
        if m and m.group(1).strip() in NAME2CODE:
            cur_code = NAME2CODE[m.group(1).strip()]
            cur_q = None
            out.append(line); i += 1; continue
        # 例題マーカー
        m = re.match(r'^\*\*例題\s*([0-9０-９]+)\s*\*\*', line)
        if m:
            cur_q = str(int(nfkc(m.group(1))))
            out.append(line); i += 1; continue
        # 正答スポイラー
        if line.strip() == ':::spoiler 正答':
            # ブロック終端 ::: まで収集
            j = i + 1
            body = []
            while j < n and lines[j].strip() != ':::':
                body.append(lines[j])
                j += 1
            # body から既存コードブロックを除去し、正答行だけ残す
            ans_lines = []
            k = 0
            while k < len(body):
                if body[k].strip().startswith('```'):
                    k += 1
                    while k < len(body) and not body[k].strip().startswith('```'):
                        k += 1
                    k += 1  # 閉じフェンス
                    continue
                if body[k].strip():
                    ans_lines.append(body[k])
                k += 1
            out.append(line)  # :::spoiler 正答
            out.extend(ans_lines)
            expl = None
            if cur_code and cur_q:
                expl = data.get(cur_code, {}).get(cur_q)
            if expl:
                out.append('')
                out.append('```')
                out.extend(trim_expl(expl))
                out.append('```')
                injected += 1
            else:
                missing.append((cur_code, cur_q))
            out.append(':::')  # 閉じ
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

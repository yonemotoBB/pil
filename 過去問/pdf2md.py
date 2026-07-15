import fitz, re, os, unicodedata

SRC = '/tmp/kakomon.pdf'
OUTDIR = '/home/fogbi/pil/過去問'
IMGDIR = os.path.join(OUTDIR, 'images')
os.makedirs(IMGDIR, exist_ok=True)

doc = fitz.open(SRC)

FIGURE_PAGES = {5, 7, 9, 11, 12, 24, 25}
FIG_KW = re.compile(r'下図|右図|左図|上図|次の図|図中|下表|下記の図|図面|の図')

Q_RE  = re.compile(r'^問\s*([０-９0-9]+)\s*(.*)$')
CH_RE = re.compile(r'^（\s*([１-４1-4])\s*）\s*(.*)$')

def is_cover(text):
    if not text.strip():
        return False
    head = re.sub(r'\s', '', text.splitlines()[0])
    return '航空従事者学科試験問題' in head

def parse_cover(text):
    subj = res = None
    for line in text.splitlines():
        l = unicodedata.normalize('NFKC', line).replace(' ', '')
        m = re.search(r'科目(.+?)(?:記号|$)', l)
        if m and subj is None:
            subj = m.group(1).strip('　 :：')
        m = re.search(r'資格(.+?)(?:題数|$)', l)
        if m and res is None:
            res = m.group(1).strip('　 :：')
    return subj, res

sections = []
cur = None

for i in range(doc.page_count):
    pno = i + 1
    text = doc[i].get_text(sort=True)
    if is_cover(text):
        subj, res = parse_cover(text)
        cur = {'subject': subj or f'科目{pno}', 'resource': res or '',
               'questions': [], 'notes': []}
        sections.append(cur)
        continue
    if cur is None:
        continue

    q = None
    ctx = None  # 'choice' | 'stem' | 'preamble'
    preamble = []  # このページで最初の設問より前のテキスト
    page_questions = []

    for raw in text.splitlines():
        line = raw.strip()
        if not line:
            continue
        if re.match(r'^自操|^共通', unicodedata.normalize('NFKC', line).replace(' ', '')):
            continue
        mq = Q_RE.match(line)
        mc = CH_RE.match(line)
        # 「問１から問６について解答せよ」等は設問見出しではなく前文
        false_q = mq and re.match(r'^から', mq.group(2))
        if mq and not false_q:
            num = int(unicodedata.normalize('NFKC', mq.group(1)))
            q = {'num': num, 'stem': mq.group(2).strip(), 'choices': [], 'figs': []}
            cur['questions'].append(q)
            page_questions.append(q)
            ctx = 'stem'
        elif mc and q is not None:
            q['choices'].append(mc.group(2).strip())
            ctx = 'choice'
        elif q is None:
            preamble.append(line)  # 設問前の共通説明（航法ログ等）
        else:
            if ctx == 'choice' and q['choices']:
                q['choices'][-1] += line
            else:
                q['stem'] += line

    # 図の割り当て
    if pno in FIGURE_PAGES:
        img = f'page{pno:02d}.png'
        targeted = [qq for qq in page_questions if FIG_KW.search(qq['stem'])]
        if preamble and FIG_KW.search(''.join(preamble)):
            # 共通の表（航法ログ）はページ先頭設問群に紐付け
            targeted = targeted or []
            if page_questions:
                page_questions[0].setdefault('figs', [])
                if img not in page_questions[0]['figs']:
                    page_questions[0]['figs'].insert(0, img)
        for qq in targeted:
            if img not in qq['figs']:
                qq['figs'].append(img)
        if not targeted and not preamble and page_questions:
            page_questions[0]['figs'].append(img)

    # 前文（共通説明）を保持。ただし表データ行（崩れるため）は除外し説明文のみ。
    if preamble:
        prose = [l for l in preamble
                 if l.endswith('。') or 'について解答' in l]
        if prose:
            cur['notes'].append((page_questions[0]['num'] if page_questions else None,
                                 ' '.join(prose) + '（表は下図参照）'))

# 図ページを画像化
for pno in sorted(FIGURE_PAGES):
    doc[pno-1].get_pixmap(dpi=150).save(os.path.join(IMGDIR, f'page{pno:02d}.png'))

# 工学(飛)/(回) の重複科目名を資格で区別
seen = {}
for sec in sections:
    key = sec['subject']
    seen[key] = seen.get(key, 0) + 1
name_count = {}
for sec in sections:
    name_count[sec['subject']] = name_count.get(sec['subject'], 0) + 1

CIRCLED = ['①','②','③','④']
out = []
out.append('# 航空従事者学科試験 過去問（自家用操縦士）\n')
out.append('> 出典: 国土交通省 航空局 <https://www.mlit.go.jp/koku/content/001619888.pdf>  ')
out.append('> 記号: Ａ４ＣＣ ／ PDF作成日: 2023-06-07 ／ 各科目 20題・40分・1問5点・70点以上で合格\n')
out.append('図表を含む設問は、原本の該当ページ画像を `images/` に添付しています。\n')

for sec in sections:
    heading = sec['subject']
    if name_count[sec['subject']] > 1 and sec['resource']:
        heading = f'{sec["subject"]}（{sec["resource"]}）'
    out.append(f'\n## {heading}\n')
    notes_by_q = {}
    for qnum, txt in sec['notes']:
        notes_by_q.setdefault(qnum, []).append(txt)
    for q in sec['questions']:
        for txt in notes_by_q.get(q['num'], []):
            out.append(f'> {txt.strip()}\n')
        out.append(f'### 問{q["num"]}\n')
        out.append(q['stem'] + '\n')
        for img in q['figs']:
            out.append(f'![問{q["num"]}の図](images/{img})\n')
        for idx, c in enumerate(q['choices']):
            mark = CIRCLED[idx] if idx < 4 else f'({idx+1})'
            out.append(f'- {mark} {c}')
        out.append('')

outpath = os.path.join(OUTDIR, '自家用操縦士_学科試験.md')
with open(outpath, 'w', encoding='utf-8') as f:
    f.write('\n'.join(out) + '\n')

# 旧ファイル削除
old = os.path.join(OUTDIR, '自家用操縦士_航空気象ほか.md')
if os.path.exists(old):
    os.remove(old)

print('written:', outpath)
for s in sections:
    print(' ', s['subject'], s['resource'], 'Q=', len(s['questions']),
          'figs=', sum(len(q['figs']) for q in s['questions']),
          'notes=', len(s['notes']))

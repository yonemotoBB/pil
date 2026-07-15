# -*- coding: utf-8 -*-
import fitz, re, os, unicodedata

PDFDIR = '/tmp/kakomon'
OUTDIR = '/home/fogbi/pil/過去問'
IMGDIR = os.path.join(OUTDIR, 'images')
os.makedirs(IMGDIR, exist_ok=True)
RAW = 'https://raw.githubusercontent.com/yonemotoBB/pil/main/'
import urllib.parse
def rawurl(fname):
    p = '過去問/images/' + fname
    return RAW + '/'.join(urllib.parse.quote(s) for s in p.split('/'))

# 期メタ: (pdf_id, ラベル, slug, 年度, ソートキー)
SESSIONS = [
    ('001619888','令和5年7月','r5-07','令和5年度',202307),
    ('001594861','令和5年3月','r5-03','令和4年度',202303),
    ('001572042','令和4年11月','r4-11','令和4年度',202211),
    ('001491296','令和4年7月','r4-07','令和4年度',202207),
    ('001470766','令和4年3月','r4-03','令和3年度',202203),
    ('001441775','令和3年11月','r3-11','令和3年度',202111),
    ('001415231','令和3年7月','r3-07','令和3年度',202107),
    ('001391736','令和3年3月','r3-03','令和2年度',202103),
    ('001372771','令和2年11月','r2-11','令和2年度',202011),
    ('001355204','令和2年7月','r2-07','令和2年度',202007),
    ('001341137','令和2年3月','r2-03','令和元年度',202003),
    ('001317398','令和元年11月','r1-11','令和元年度',201911),
    ('001302114','令和元年7月','r1-07','令和元年度',201907),
    ('001279241','平成31年3月','h31-03','平成30年度',201903),
    ('001262216','平成30年11月','h30-11','平成30年度',201811),
    ('001255552','平成30年9月臨時','h30-09r','平成30年度',201809),
    ('001246397','平成30年7月','h30-07','平成30年度',201807),
]
NENDO_ORDER = ['令和5年度','令和4年度','令和3年度','令和2年度','令和元年度','平成30年度']

FIG_KW = re.compile(r'下図|右図|左図|上図|次の図|前図|図中|下の図|下記の図|図面|下表|下記の表|次の表')
Q_RE  = re.compile(r'^問\s*([０-９0-9]+)\s*(.*)$')
CH_RE = re.compile(r'^（\s*([１-４1-4])\s*）\s*(.*)$')
CIRCLED = ['①','②','③','④']

def nfkc(s): return unicodedata.normalize('NFKC', s)

def is_cover(text):
    if not text.strip(): return False
    return '航空従事者学科試験問題' in re.sub(r'\s','',text.splitlines()[0])

def parse_cover(text):
    flat = nfkc(text).replace(' ','')
    subj = res = None
    m = re.search(r'科目(.+?)(?:記号|$)', flat)
    if m: subj = m.group(1).strip('　:：')
    m = re.search(r'資格(.+?)(?:題数|$)', flat)
    if m: res = m.group(1).strip('　:：')
    return subj, res

def subject_display(subj, res):
    """(表示名, コード) を返す"""
    if '気象' in subj: return '航空気象','met'
    if '工学' in subj:
        if '(回)' in res: return '航空工学（回転翼）','eng-r'
        if '(飛)' in res: return '航空工学（飛行機）','eng-a'
        return '航空工学','eng'
    if '通信' in subj: return '航空通信','com'
    if '法規' in subj: return '航空法規','law'
    if '航法' in subj: return '空中航法','nav'
    return subj,'x'

def parse_pdf(pid):
    """PDFを (subjects) に構造化。各subject: {name,code,questions}"""
    doc = fitz.open(os.path.join(PDFDIR, f'{pid}.pdf'))
    subjects = []
    cur = None
    for i in range(doc.page_count):
        pno = i+1
        text = doc[i].get_text(sort=True)
        if is_cover(text):
            subj,res = parse_cover(text)
            name,code = subject_display(subj or '', res or '')
            cur = {'name':name,'code':code,'questions':[],'notes':[]}
            subjects.append(cur)
            continue
        if cur is None: continue
        has_img = len(doc[i].get_images())>0
        q=None; ctx=None; preamble=[]; page_qs=[]
        for raw in text.splitlines():
            line=raw.strip()
            if not line: continue
            if re.match(r'^自操|^共通', nfkc(line).replace(' ','')): continue
            mq=Q_RE.match(line); mc=CH_RE.match(line)
            false_q = mq and re.match(r'^から', mq.group(2))
            if mq and not false_q:
                q={'num':int(nfkc(mq.group(1))),'stem':mq.group(2).strip(),'choices':[],'pages':set()}
                cur['questions'].append(q); page_qs.append(q); ctx='stem'
            elif mc and q is not None:
                q['choices'].append(mc.group(2).strip()); ctx='choice'
            elif q is None:
                preamble.append(line)
            else:
                if ctx=='choice' and q['choices']: q['choices'][-1]+=line
                else: q['stem']+=line
        # 図の割当
        kw_qs=[qq for qq in page_qs if FIG_KW.search(qq['stem'])]
        pre_has_fig = preamble and FIG_KW.search(''.join(preamble))
        for qq in kw_qs: qq['pages'].add(pno)
        if pre_has_fig and page_qs: page_qs[0]['pages'].add(pno)
        if has_img and not kw_qs and not pre_has_fig and page_qs:
            page_qs[-1]['pages'].add(pno)
        # 共通前文（説明文のみ）
        if preamble:
            prose=[l for l in preamble if l.endswith('。') or 'について解答' in l]
            if prose and page_qs:
                cur['notes'].append((page_qs[0]['num'], ' '.join(prose)))
    return doc, subjects

def render_pages(doc, pid, slug, pages):
    for pno in sorted(pages):
        fname=f'{slug}_p{pno:02d}.png'
        out=os.path.join(IMGDIR,fname)
        if not os.path.exists(out):
            doc[pno-1].get_pixmap(dpi=120).save(out)

def session_md(pid, label, slug):
    doc, subjects = parse_pdf(pid)
    total_q = sum(len(s['questions']) for s in subjects)
    # スキャンPDF（テキスト層なし）: 全ページを画像として埋め込む
    if total_q == 0:
        lines=[f'<a id="{slug}"></a>', f'## {label}期\n']
        lines.append('> ⚠ この期の原本はスキャン画像PDFのためテキスト化できません。原本ページ画像を掲載します（本文検索は不可）。\n')
        pages=list(range(1, doc.page_count+1))
        for pno in pages:
            fname=f'{slug}_p{pno:02d}.png'
            lines.append(f'![{label} p{pno}]({rawurl(fname)})\n')
        render_pages(doc, pid, slug, pages)
        return '\n'.join(lines)+'\n', [], {'subjects':0,'questions':0,'figs':len(pages),'scanned':True}
    all_pages=set()
    lines=[]
    lines.append(f'<a id="{slug}"></a>')
    lines.append(f'## {label}期\n')
    # 期内の学科目次
    subj_links=[]
    for s in subjects:
        aid=f'{slug}-{s["code"]}'
        subj_links.append(f'[{s["name"]}](#{aid})')
    lines.append('　'.join(subj_links)+'\n')
    for s in subjects:
        aid=f'{slug}-{s["code"]}'
        lines.append(f'<a id="{aid}"></a>')
        lines.append(f'### {s["name"]}\n')
        notes={}
        for qnum,txt in s['notes']: notes.setdefault(qnum,[]).append(txt)
        for q in s['questions']:
            for txt in notes.get(q['num'],[]):
                lines.append(f'> {txt.strip()}（表・図は下の画像参照）\n')
            lines.append(f'#### 問{q["num"]}\n')
            lines.append(q['stem']+'\n')
            for pno in sorted(q['pages']):
                fname=f'{slug}_p{pno:02d}.png'; all_pages.add(pno)
                lines.append(f'![問{q["num"]}の図]({rawurl(fname)})\n')
            for idx,c in enumerate(q['choices']):
                mark=CIRCLED[idx] if idx<4 else f'({idx+1})'
                lines.append(f'- {mark} {c}')
            lines.append('')
    render_pages(doc, pid, slug, all_pages)
    stats={'subjects':len(subjects),'questions':sum(len(s['questions']) for s in subjects),'figs':len(all_pages)}
    return '\n'.join(lines)+'\n', subjects, stats

# 全期処理
meta={}  # slug -> (label, subjects[name,code], nendo)
by_nendo={}
for pid,label,slug,nendo,sk in SESSIONS:
    md, subjects, stats = session_md(pid,label,slug)
    by_nendo.setdefault(nendo,[]).append((sk,slug,label,md,[(s['name'],s['code']) for s in subjects]))
    print(f'{label:14s} 科目{stats["subjects"]} 問{stats["questions"]:3d} 図{stats["figs"]}')

# 年度ファイル生成
nendo_files={}
for nendo in NENDO_ORDER:
    items=sorted(by_nendo[nendo], key=lambda x:x[0])  # 時系列昇順
    fname=f'自家用操縦士_{nendo}.md'
    nendo_files[nendo]=fname
    out=[f'# 自家用操縦士 学科試験 過去問（{nendo}）\n']
    out.append(f'> 出典: 国土交通省 航空局 [過去問一覧](https://www.mlit.go.jp/koku/koku_fr10_000025.html)  ')
    out.append(f'> 各科目20題・1問5点・70点以上で合格。図表は原本ページ画像を添付。\n')
    out.append('## 目次\n')
    for sk,slug,label,md,subs in items:
        out.append(f'- [{label}期](#{slug})')
        if subs:
            links=' ／ '.join(f'[{n}](#{slug}-{c})' for n,c in subs)
            out.append(f'  - {links}')
        else:
            out.append('  - （スキャン画像・テキスト無し）')
    out.append('\n---\n')
    for sk,slug,label,md,subs in items:
        out.append(md)
        out.append('\n---\n')
    with open(os.path.join(OUTDIR,fname),'w',encoding='utf-8') as f:
        f.write('\n'.join(out))
    print(f'書出: {fname} ({len(items)}期)')

# 索引ファイル
idx=['# 自家用操縦士（飛・回） 学科試験 過去問インデックス\n']
idx.append('国土交通省 航空局が公開する[学科試験 過去問](https://www.mlit.go.jp/koku/koku_fr10_000025.html)を年度ごとにMarkdown化したもの。\n')
idx.append('## 年度別\n')
for nendo in NENDO_ORDER:
    items=sorted(by_nendo[nendo], key=lambda x:x[0])
    labels='、'.join(l for _,_,l,_,_ in items)
    idx.append(f'- [{nendo}]({urllib.parse.quote(nendo_files[nendo])}) — {labels}')
with open(os.path.join(OUTDIR,'README.md'),'w',encoding='utf-8') as f:
    f.write('\n'.join(idx)+'\n')
print('書出: README.md')

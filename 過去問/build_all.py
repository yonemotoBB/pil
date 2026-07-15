# -*- coding: utf-8 -*-
import fitz, re, os, unicodedata, urllib.parse

PDFDIR='/tmp/kakomon'; OCRDIR='/tmp/ocr'; ANSDIR='/tmp/kaito'
OUTDIR='/home/fogbi/pil/過去問'
IMGDIR=os.path.join(OUTDIR,'images')
os.makedirs(IMGDIR,exist_ok=True)
RAW='https://raw.githubusercontent.com/yonemotoBB/pil/main/'
def rawurl(fname):
    p='過去問/images/'+fname
    return RAW+'/'.join(urllib.parse.quote(s) for s in p.split('/'))

# 期メタ: (pdf_id, ラベル, slug, 年度, ソートキー, パス)
KOKU={'001619888','001594861','001572042','001491296','001317398'}
def src_url(pid):
    return f'https://www.mlit.go.jp/{"koku/content" if pid in KOKU else "common"}/{pid}.pdf'
SESSIONS=[
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
NENDO_ORDER=['令和5年度','令和4年度','令和3年度','令和2年度','令和元年度','平成30年度']

FIG_KW=re.compile(r'下図|右図|左図|上図|次の図|前図|図中|下の図|下記の図|図面|下表|下記の表|次の表')
Q_RE=re.compile(r'^問\s*([０-９0-9]+)\s*(.*)$')
CH_RE=re.compile(r'^（\s*([１-４1-4])\s*）\s*(.*)$')
CIRCLED=['①','②','③','④']
def nfkc(s): return unicodedata.normalize('NFKC',s)

def answers(slug):
    """解答PDFから {P##: [20解答]} を座標グリッドで抽出"""
    apdf=os.path.join(ANSDIR,f'{slug}.pdf')
    if not os.path.exists(apdf): return {}
    d=fitz.open(apdf); result={}
    for pi in range(d.page_count):
        words=d[pi].get_text('words')
        digs=[(w[0],w[1],w[4]) for w in words if re.fullmatch(r'[1-5]',w[4])]
        heads=[(w[0],w[1],nfkc(w[4])) for w in words if re.fullmatch(r'P[0-9]{1,2}',nfkc(w[4]))]
        for hx,hy,lab in heads:
            col=sorted([(y,t) for x,y,t in digs if abs(x-hx)<9 and hy+2<y<hy+2+21*16],key=lambda z:z[0])
            seq=[t for _,t in col][:20]
            if len(seq)>=18 and lab not in result: result[lab]=seq
    return result

def cover_pcode(page):
    """問題用紙cover右上のP##科目記号"""
    w,h=page.rect.width,page.rect.height
    for b in page.get_text('words'):
        x0,y0,txt=b[0],b[1],nfkc(b[4])
        if x0>w*0.45 and y0<h*0.22:
            m=re.search(r'P[0-9]{1,2}',txt)
            if m: return m.group(0)
    return None

def is_cover(t):
    if not t.strip(): return False
    return '航空従事者学科試験問題' in re.sub(r'\s','',t.splitlines()[0])
def parse_cover(t):
    flat=nfkc(t).replace(' ','')
    subj=res=None
    m=re.search(r'科目(.+?)(?:記号|$)',flat);  subj=m.group(1).strip('　:：') if m else None
    m=re.search(r'資格(.+?)(?:題数|$)',flat);   res=m.group(1).strip('　:：') if m else None
    return subj,res
def subject_display(subj,res):
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
    doc=fitz.open(os.path.join(PDFDIR,f'{pid}.pdf'))
    subjects=[]; cur=None
    for i in range(doc.page_count):
        pno=i+1; text=doc[i].get_text(sort=True)
        if is_cover(text):
            subj,res=parse_cover(text); name,code=subject_display(subj or '',res or '')
            cur={'name':name,'code':code,'pcode':cover_pcode(doc[i]),'questions':[],'notes':[]}; subjects.append(cur); continue
        if cur is None: continue
        has_img=len(doc[i].get_images())>0
        q=None;ctx=None;preamble=[];page_qs=[]
        for raw in text.splitlines():
            line=raw.strip()
            if not line: continue
            if re.match(r'^自操|^共通',nfkc(line).replace(' ','')): continue
            mq=Q_RE.match(line); mc=CH_RE.match(line)
            false_q=mq and re.match(r'^から',mq.group(2))
            qnum=None
            if mq and not false_q:
                qnum=int(nfkc(mq.group(1)))
                if qnum>20:
                    # 「問 2020」のようにラベルが二重埋め込みされたPDF対策(h30-07気象問20)
                    s=str(qnum)
                    if len(s)%2==0 and s[:len(s)//2]==s[len(s)//2:]: qnum=int(s[:len(s)//2])
                    else: qnum=None
            if qnum is not None:
                q={'num':qnum,'stem':mq.group(2).strip(),'choices':[],'pages':set()}
                cur['questions'].append(q);page_qs.append(q);ctx='stem'
            elif mc and q is not None:
                q['choices'].append(mc.group(2).strip());ctx='choice'
            elif q is None: preamble.append(line)
            else:
                if ctx=='choice' and q['choices']: q['choices'][-1]+=line
                else: q['stem']+=line
        kw_qs=[qq for qq in page_qs if FIG_KW.search(qq['stem'])]
        pre_fig=preamble and FIG_KW.search(''.join(preamble))
        for qq in kw_qs: qq['pages'].add(pno)
        if pre_fig and page_qs: page_qs[0]['pages'].add(pno)
        if has_img and not kw_qs and not pre_fig and page_qs: page_qs[-1]['pages'].add(pno)
        if preamble:
            prose=[l for l in preamble if l.endswith('。') or 'について解答' in l]
            if prose and page_qs: cur['notes'].append((page_qs[0]['num'],' '.join(prose)))
    for s in subjects:
        for q in s['questions']: post_fix(q)
    return doc,subjects

def post_fix(q):
    """図が選択肢テキストに食い込む定型問を原本画像で確認済みの正しい内容に置換。
    (安定性・馬力・TEMは全期で同一の並びであることを各期のページ画像で確認済み)"""
    stem=q['stem']; n=len(q['choices'])
    if '右図の安定性に関する記述' in stem and n!=4:
        q['stem']='右図の安定性に関する記述で正しいものはどれか。'
        q['choices']=['静的には安定、動的には不安定','静的には不安定、動的にも不安定',
                      '静的には安定、動的にも安定','静的には不安定、動的には安定']
    elif '馬力と前進速度との関係' in stem and n!=4:
        q['stem']='下図は馬力と前進速度との関係を示した一例である。①～④のうち、全必要パワーを示しているものはどれか。'
        q['choices']=['①','②','③','④']
    elif 'スレット・アンド・エラー' in stem and n!=4:
        # 注意: この置換はr4-11/r5-03/r5-07の3期(選択肢が正誤表で乱れる)のみ対象。
        # 同じTEM題材でも(a)(b)本文・選択肢並びが異なる期がある(例:r1-11は①正正～④誤誤)ため
        # 正常にパースできた期には適用しない。
        q['stem']=('TEM（スレット・アンド・エラー・マネージメント）に関する次の文（ａ）、（ｂ）'
                   'について、その正誤の組み合わせとして正しいものはどれか。\n\n'
                   '（ａ）スレットは、乗員が関与するところで発生し、運航をさらに複雑にし、'
                   '安全マージンを維持するために、乗員に注意や対処を要求するものをいう。\n'
                   '（ｂ）エラーは、乗員自身、または組織の意図や期待から逸脱し、安全マージンを'
                   '減少させ、運航を悪化させる事態が発生する可能性を高めるものをいう。')
        q['choices']=['（ａ）誤　（ｂ）誤','（ａ）誤　（ｂ）正','（ａ）正　（ｂ）誤','（ａ）正　（ｂ）正']

# ---- OCRセッション（令和元年7月 スキャンPDF）----
# P##科目記号は全期共通: 通信P18 気象P21 工学飛P23 工学回P24 法規P27 航法P29
OCR_COVERS=[(1,'航空通信','com','P18',(2,4)),(5,'航空気象','met','P21',(6,8)),
            (9,'航空工学（飛行機）','eng-a','P23',(10,12)),(13,'航空工学（回転翼）','eng-r','P24',(14,17)),
            (18,'航空法規','law','P27',(19,21)),(22,'空中航法','nav','P29',(23,26))]
def ocr_choice(line,exp):
    c=CIRCLED[exp-1]
    for p in (rf'^\s*[（(]?\s*{c}\s*[）)]?\s*(.*)',rf'^\s*[（(]\s*{exp}\s*[）)]?\s*(.*)',rf'^\s*{exp}\s*[）)]\s*(.*)'):
        m=re.match(p,line)
        if m: return m.group(1)
    return None
def ocr_clean(s):
    return s.replace('どれかが','どれか').replace('はどれか。','はどれか。')

# OCRで拾えなかった4問(スキャン画像 p8/p14/p15/p24 から転記)
OCR_EXTRA={
 ('met',19):{'stem':'850hPa天気図の説明で誤りはどれか。','choices':[
   '対流圏の中間層にあたり、大気の流れを知るために最適である。',
   'この高さの湿った暖気移流は雨の予報に利用される。',
   '山岳地帯を除けば気象要素は下層大気の代表的な値を示す。',
   '前線系の解析に最適である。']},
 ('eng-r',4):{'stem':'ロータ・ハブ型式のうち、全関節型ハブが有するヒンジで誤りはどれか。','choices':[
   'フェザリング・ヒンジ','フラップ・ヒンジ','ドラッグ・ヒンジ','デルタスリー・ヒンジ']},
 ('eng-r',10):{'stem':'ダイナミック・ロール・オーバーに関する記述で誤りはどれか。','choices':[
   'ダイナミック・ロール・オーバーとは、片方の降着装置が接地したまま、機体がこの接地点周りに旋転する状態をいう。',
   'ダイナミック・ロール・オーバーの経過時間は極めて短時間であるため、これに関する知識がなければリカバリーは不可能といわれている。',
   '不整地や柔らかな地面での離着陸はダイナミック・ロール・オーバーによる転覆の可能性が高くなる。',
   '低い重心位置での離着陸はダイナミック・ロール・オーバーによる転覆の可能性が高くなる。']},
 ('nav',13):{'stem':'TH270度で飛行中、15 nm飛行して0.5 nm右側にオフコースした。このときのDAとして正しいものはどれか。ただし、WCAは0度とする。','choices':[
   '1度R','2度R','1度L','2度L']},
}
# 図を含む問 → スキャンページ番号
OCR_FIGS={('met',20):8,('eng-r',5):14,('eng-r',6):14,('nav',1):23,('nav',15):25}
def parse_ocr(subj_pages):
    lines=[]
    for p in range(subj_pages[0],subj_pages[1]+1):
        fp=os.path.join(OCRDIR,f'p{p:02d}.txt')
        if os.path.exists(fp): lines+=open(fp,encoding='utf-8').read().splitlines()
    qs=[];q=None;exp=1
    for raw in lines:
        line=raw.strip()
        if not line: continue
        if '航空従事者' in line or re.match(r'^自操|^共通',line): continue
        if re.search(r'[ー一\-]{8,}',line): continue  # スキャンノイズ行
        mq=re.match(r'^\s*[問間商固]\s*([0-9０-９OoＯｏ]{1,3})\s*(.*)$',line)
        n=None
        if mq:
            digs=re.sub(r'[OoＯｏ]','0',nfkc(mq.group(1)))
            if digs.isdigit(): n=int(digs)
        if mq and 1<=n<=20 and (q is None or len(q['choices'])>=2 or n==q['num']+1):
            q={'num':n,'stem':ocr_clean(mq.group(2).strip()),'choices':[],'pages':set()}
            qs.append(q);exp=1;continue
        if q is not None and exp<=4:
            rest=ocr_choice(line,exp)
            if rest is not None:
                rest=re.sub(r'^[①②③④]?\s*[)）]\s*','',rest.strip())  # 「③)」等の重複マーカー除去
                q['choices'].append(ocr_clean(rest));exp+=1;continue
        if q is not None:
            if q['choices']: q['choices'][-1]+=ocr_clean(line)
            else: q['stem']+=ocr_clean(line)
    return qs
def ocr_subjects():
    subs=[]
    for cover,name,code,pcode,pr in OCR_COVERS:
        qs=parse_ocr(pr)
        for q in qs:
            q.setdefault('pages',set())
        # 「問2O」→問2 誤認識の補正: 直前が問19なら問20
        for i in range(1,len(qs)):
            if qs[i-1]['num']==19 and qs[i]['num']<19: qs[i]['num']=20
        # 欠落問を挿入(スキャン画像から転記)
        for (c,n),data in OCR_EXTRA.items():
            if c==code and not any(q['num']==n for q in qs):
                qs.append({'num':n,'stem':data['stem'],'choices':list(data['choices']),'pages':set()})
        qs.sort(key=lambda q:q['num'])
        # 図付き問へページ画像を添付
        for (c,n),pno in OCR_FIGS.items():
            if c==code:
                for q in qs:
                    if q['num']==n: q['pages'].add(pno)
        notes=[(1,'下表はＡ空港から変針点Ｂ、Ｃを経由してＤ空港に至る未完成の航法ログである。問１から問６について解答せよ。')] if code=='nav' else []
        subs.append({'name':name,'code':code,'pcode':pcode,'questions':qs,'notes':notes})
    return subs

def render_pages(doc,slug,pages):
    for pno in sorted(pages):
        out=os.path.join(IMGDIR,f'{slug}_p{pno:02d}.png')
        if not os.path.exists(out): doc[pno-1].get_pixmap(dpi=120).save(out)

def emit_subject(lines,slug,s,ans):
    lines.append(f'### {s["name"]}\n')
    notes={}
    for qn,tx in s['notes']: notes.setdefault(qn,[]).append(tx)
    seq=ans.get(s.get('pcode')) if s.get('pcode') else None
    pages=set()
    for q in s['questions']:
        for tx in notes.get(q['num'],[]): lines.append(f'> {tx.strip()}（表・図は下の画像参照）\n')
        lines.append(f'**問{q["num"]}**\n')
        lines.append(q['stem']+'\n')
        for pno in sorted(q['pages']):
            fname=f'{slug}_p{pno:02d}.png'; pages.add(pno)
            lines.append(f'![問{q["num"]}の図]({rawurl(fname)})\n')
        for idx,c in enumerate(q['choices']):
            mark=CIRCLED[idx] if idx<4 else f'({idx+1})'
            lines.append(f'- [ ] {mark} {c}')
        lines.append('')
        if seq and 1<=q['num']<=len(seq):
            lines.append(':::spoiler 正答')
            lines.append(seq[q['num']-1])
            lines.append(':::\n')
    return pages

def session_md(pid,label,slug):
    url=src_url(pid); ans=answers(slug)
    if slug=='r1-07':
        subjects=ocr_subjects()
        lines=[f'## {label}期\n']
        lines.append(f'原本PDF: <{url}>（解答: <https://www.mlit.go.jp/common/001301067.pdf>）\n')
        lines.append('> ⚠ この期の原本はスキャン画像PDFのため、**OCR（自動文字認識）で作成**しています。誤字・脱字が含まれる可能性があります。正確な内容は原本PDFをご確認ください。\n')
        allpg=set()
        for s in subjects: allpg|=emit_subject(lines,slug,s,ans)
        doc=fitz.open(os.path.join(PDFDIR,'001302114.pdf'))
        render_pages(doc,slug,allpg)
        return '\n'.join(lines)+'\n', [(s['name'],s['code']) for s in subjects], \
               {'q':sum(len(s['questions']) for s in subjects)}
    doc,subjects=parse_pdf(pid)
    lines=[f'## {label}期\n', f'原本PDF: <{url}>\n']
    allpg=set()
    for s in subjects: allpg|=emit_subject(lines,slug,s,ans)
    render_pages(doc,slug,allpg)
    return '\n'.join(lines)+'\n', [(s['name'],s['code']) for s in subjects], \
           {'q':sum(len(s['questions']) for s in subjects)}

by_nendo={}
for pid,label,slug,nendo,sk in SESSIONS:
    md,subs,st=session_md(pid,label,slug)
    by_nendo.setdefault(nendo,[]).append((sk,slug,label,md,subs))
    print(f'{label:14s} 科目{len(subs)} 問{st["q"]:3d}')

nendo_files={}
for nendo in NENDO_ORDER:
    items=sorted(by_nendo[nendo],key=lambda x:x[0])
    fname=f'自家用操縦士_{nendo}.md'; nendo_files[nendo]=fname
    out=[f'# 自家用操縦士 学科試験 過去問（{nendo}）\n']
    out.append('出典: 国土交通省 航空局 [過去問一覧](https://www.mlit.go.jp/koku/koku_fr10_000025.html)　各科目20題・1問5点・70点以上で合格。\n')
    out.append('各設問の選択肢はチェックボックス、**正答は「正答」の折りたたみ**（HackMDでクリックで開く）です。\n')
    out.append('[TOC]\n')
    out.append('---\n')
    for sk,slug,label,md,subs in items:
        out.append(md); out.append('---\n')
    open(os.path.join(OUTDIR,fname),'w',encoding='utf-8').write('\n'.join(out))
    print(f'書出: {fname} ({len(items)}期)')

idx=['# 自家用操縦士（飛・回） 学科試験 過去問インデックス\n']
idx.append('国土交通省 航空局が公開する[学科試験 過去問](https://www.mlit.go.jp/koku/koku_fr10_000025.html)を年度ごとにMarkdown化したもの。各ファイル冒頭の `[TOC]` から各期・各学科へ移動できます（HackMD）。\n')
idx.append('## 年度別\n')
for nendo in NENDO_ORDER:
    items=sorted(by_nendo[nendo],key=lambda x:x[0])
    labels='、'.join(l for _,_,l,_,_ in items)
    idx.append(f'- [{nendo}]({urllib.parse.quote(nendo_files[nendo])}) — {labels}')
open(os.path.join(OUTDIR,'README.md'),'w',encoding='utf-8').write('\n'.join(idx)+'\n')
print('書出: README.md')

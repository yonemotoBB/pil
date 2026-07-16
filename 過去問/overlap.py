# -*- coding: utf-8 -*-
"""過去問の期間重複分析: 独自問題率と過去問学習の期待得点"""
import re, glob, unicodedata
from difflib import SequenceMatcher

def nfkc(s): return unicodedata.normalize('NFKC', s)
def norm(s):
    s = nfkc(s)
    s = re.sub(r'[\s、。，．・「」『』（）()～〜]', '', s)
    return s

ORDER = {'平成30年7月期':1,'平成30年9月臨時期':2,'平成30年11月期':3,'平成31年3月期':4,
'令和元年7月期':5,'令和元年11月期':6,'令和2年3月期':7,'令和2年7月期':8,'令和2年11月期':9,
'令和3年3月期':10,'令和3年7月期':11,'令和3年11月期':12,'令和4年3月期':13,'令和4年7月期':14,
'令和4年11月期':15,'令和5年3月期':16,'令和5年7月期':17}

Q = []  # (order, label, subj, num, stem_n, all_n)
for md in glob.glob('/home/fogbi/pil/過去問/自家用操縦士_*.md'):
    s = open(md, encoding='utf-8').read()
    for p in re.split(r'^## ', s, flags=re.M)[1:]:
        label = p.splitlines()[0].strip()
        if label not in ORDER: continue
        for sp in re.split(r'^### ', p, flags=re.M)[1:]:
            name = sp.splitlines()[0].strip()
            qparts = re.split(r'^\*\*問(\d+)\*\*', sp, flags=re.M)
            for i in range(1, len(qparts), 2):
                num = int(qparts[i]); body = qparts[i+1]
                body = re.sub(r':::spoiler 正答.*?:::', '', body, flags=re.S)
                body = re.sub(r'^!\[.*$', '', body, flags=re.M)
                chs = re.findall(r'^- \[ \] [①②③④]?\s*(.*)$', body, flags=re.M)
                stem = body.strip().split('\n- [ ]')[0]
                stem = re.sub(r'^>.*$', '', stem, flags=re.M).strip()
                Q.append((ORDER[label], label, name, num, norm(stem), norm(stem+'|'+'|'.join(sorted(chs)))))

print(f'総問題数: {len(Q)}')

# 科目ごとにペア類似度 → union-find クラスタリング
from collections import defaultdict
by_subj = defaultdict(list)
for idx, q in enumerate(Q): by_subj[q[2]].append(idx)

parent = list(range(len(Q)))
def find(a):
    while parent[a]!=a: parent[a]=parent[parent[a]]; a=parent[a]
    return a
def union(a,b):
    ra,rb=find(a),find(b)
    if ra!=rb: parent[rb]=ra

STEM_TH = 0.85   # 題意が同じ(類題含む)
FULL_TH = 0.92   # 選択肢までほぼ同一(丸暗記で正解可)

exact_pairs = set()
for subj, idxs in by_subj.items():
    for a in range(len(idxs)):
        ia = idxs[a]; sa = Q[ia][4]
        for b in range(a+1, len(idxs)):
            ib = idxs[b]; sb = Q[ib][4]
            if Q[ia][0]==Q[ib][0]: continue  # 同一期内は除外
            if abs(len(sa)-len(sb)) > max(len(sa),len(sb))*0.3: continue
            m = SequenceMatcher(None, sa, sb)
            if m.quick_ratio() < STEM_TH: continue
            r = m.ratio()
            if r >= STEM_TH:
                union(ia, ib)
                fa, fb = Q[ia][5], Q[ib][5]
                mf = SequenceMatcher(None, fa, fb)
                if mf.quick_ratio()>=FULL_TH and mf.ratio()>=FULL_TH:
                    exact_pairs.add((ia,ib)); exact_pairs.add((ib,ia))

clusters = defaultdict(list)
for i in range(len(Q)): clusters[find(i)].append(i)
multi = [c for c in clusters.values() if len({Q[i][0] for i in c})>1]
solo  = [c for c in clusters.values() if len({Q[i][0] for i in c})==1]
print(f'問題クラスタ数(実質的な問題の種類): {len(clusters)}')
print(f'  複数期に出題: {len(multi)}クラスタ ({sum(len(c) for c in multi)}問)')
print(f'  1期のみ(独自): {len(solo)}クラスタ ({sum(len(c) for c in solo)}問)')

# 期ごと: 「過去の期に出題あり」率(=過去問全部学習後の既視率)
print('\n===== 期ごとの既視率(それ以前の全期を学習済みと仮定) =====')
print('期            既視(類題含む)  うち選択肢まで同一')
recent_loose=[]; recent_strict=[]
for label, o in sorted(ORDER.items(), key=lambda kv: kv[1]):
    idxs=[i for i,q in enumerate(Q) if q[0]==o]
    if not idxs: continue
    loose=strict=0
    for i in idxs:
        prior=[j for j in clusters[find(i)] if Q[j][0]<o]
        if prior:
            loose+=1
            if any((i,j) in exact_pairs for j in prior): strict+=1
    n=len(idxs)
    print(f'{label:12s} {loose:3d}/{n} ({100*loose/n:4.0f}%)   {strict:3d}/{n} ({100*strict/n:4.0f}%)')
    if o>=13: recent_loose.append(loose/n); recent_strict.append(strict/n)  # 令和4年3月以降

print(f'\n直近5期平均: 類題含む既視率 {100*sum(recent_loose)/len(recent_loose):.0f}% / 選択肢まで同一 {100*sum(recent_strict)/len(recent_strict):.0f}%')

# 科目別(直近5期)
print('\n===== 科目別・直近5期(令和4年3月～令和5年7月)の既視率 =====')
for subj in ['航空気象','航空工学（飛行機）','航空工学（回転翼）','航空通信','航空法規','空中航法']:
    tl=ts=tn=0
    for label,o in ORDER.items():
        if o<13: continue
        idxs=[i for i,q in enumerate(Q) if q[0]==o and q[2]==subj]
        for i in idxs:
            prior=[j for j in clusters[find(i)] if Q[j][0]<o]
            if prior:
                tl+=1
                if any((i,j) in exact_pairs for j in prior): ts+=1
        tn+=len(idxs)
    print(f'{subj:12s} 類題含む {tl:3d}/{tn} ({100*tl/tn:3.0f}%)  選択肢同一 {ts:3d}/{tn} ({100*ts/tn:3.0f}%)')

# サンプル出力(妥当性確認用)
print('\n===== 使い回しクラスタの例(頻出上位5) =====')
for c in sorted(multi, key=len, reverse=True)[:5]:
    labels=sorted({Q[i][1] for i in c}, key=lambda l:ORDER[l])
    stem=Q[c[0]][4][:45]
    print(f'{len(labels)}期: {stem}...')
    print(f'   → {"、".join(labels[:8])}{"…" if len(labels)>8 else ""}')

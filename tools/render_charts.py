#!/usr/bin/env python3
"""Render all benchmark figures from the published numeric evidence."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np

ROOT = Path(__file__).resolve().parents[1]
D = json.loads((ROOT / 'data/metrics.json').read_text())
BG, INK, MUTED, GRID = '#f8fafc', '#14243b', '#607086', '#e1e8f0'
BLUE, TEAL, PURPLE, GOLD, GREY = '#2563eb', '#008779', '#8063c7', '#c78617', '#9cabbc'
plt.rcParams.update({'font.family': 'DejaVu Sans', 'font.size': 11,
    'text.color': INK, 'axes.labelcolor': MUTED, 'xtick.color': MUTED,
    'ytick.color': INK, 'svg.hashsalt': 'gemma4-strix-halo', 'axes.spines.top': False, 'axes.spines.right': False,
    'axes.spines.left': False, 'axes.spines.bottom': False, 'svg.fonttype': 'none'})


def figure(title, subtitle, note, height=5.6):
    fig = plt.figure(figsize=(12, height), facecolor=BG)
    fig.text(.065, .93, title, fontsize=24, fontweight='bold')
    fig.text(.065, .865, subtitle, fontsize=11, color=MUTED)
    fig.text(.065, .04, note, fontsize=9, color=MUTED)
    return fig


def axis(fig, rect, title='', unit=''):
    ax = fig.add_axes(rect, facecolor=BG)
    ax.set_title(title, loc='left', fontsize=13, fontweight='bold', pad=16)
    ax.set_axisbelow(True)
    ax.grid(axis='x', color=GRID, linewidth=.8)
    ax.tick_params(length=0, pad=9)
    if unit: ax.set_xlabel(unit, labelpad=10)
    return ax


def bars(ax, labels, values, colors, xmax=None, suffix='', decimals=2):
    ys = np.arange(len(values))
    ax.barh(ys, values, color=colors, height=.55, zorder=3)
    ax.set_yticks(ys, labels)
    ax.invert_yaxis()
    ax.set_xlim(0, xmax or max(values) * 1.27)
    for y, value in zip(ys, values):
        ax.text(value + ax.get_xlim()[1] * .02, y, f'{value:.{decimals}f}{suffix}',
                va='center', fontweight='bold', fontsize=11)


def save(fig, name):
    for ext in ('png', 'svg'):
        path = ROOT / 'assets' / f'{name}.{ext}'
        fig.savefig(path, dpi=180, facecolor=BG, metadata={'Date': None} if ext == 'svg' else None)
        if ext == 'svg':
            path.write_text('\n'.join(line.rstrip() for line in path.read_text().splitlines()) + '\n')
    plt.close(fig)


initial = D['initial']; deployed = initial['deployed']; plain = initial['plain-vulkan']
fig = figure('Gemma 4 31B',
    'ROG Flow Z13 (2025)',
    'Vulkan · Q4_K_M · 128 tokens · n=9', 6.2)
for x, value, label, color in [(.065, f"{deployed['median_decode_tps']:.2f}", 'MEDIAN TOK/S', BLUE),
        (.385, f"{deployed['median_decode_tps']/plain['median_decode_tps']:.2f}×", 'VS PLAIN VULKAN', TEAL),
        (.715, f"{deployed['ttft_p50_s']:.3f} s", 'MEDIAN TTFT', PURPLE)]:
    fig.text(x, .735, value, fontsize=31, fontweight='bold', color=color)
    fig.text(x, .685, label, fontsize=9, color=MUTED)
ax=axis(fig,[.18,.18,.68,.36], 'Generation', 'Median · tok/s')
bars(ax,['MTP-4','Plain'],[deployed['median_decode_tps'],plain['median_decode_tps']],[BLUE,GREY],35)
save(fig,'overview')

fig=figure('MTP depth',
    'Vulkan · Q4_K_M · Q8 assistant',
    'Screening · n=9')
ax=axis(fig,[.09,.19,.81,.54],unit='Draft tokens')
ax.grid(axis='y',color=GRID); ax.xaxis.grid(False)
rows=sorted(D['depth'],key=lambda r:int(r['case'].removeprefix('mtp')))
x=[int(r['case'].removeprefix('mtp')) for r in rows]; y=[r['median_tps'] for r in rows]
ax.plot(x,y,color=BLUE,lw=2.5,marker='o',markersize=7)
ax.fill_between(x,y,0,color=BLUE,alpha=.06)
ax.set_ylim(0,30);ax.set_xticks(x);ax.set_ylabel('Median · tok/s')
for a,b in zip(x,y):ax.annotate(f'{b:.2f}',(a,b),xytext=(0,12),textcoords='offset points',ha='center',fontsize=10)
ax.scatter([4],[y[3]],s=140,color=TEAL,zorder=5)
save(fig,'speculation')

q=D['target-quants-results']; labels=['Q4_K_M','IQ4_XS','Q4_0']; names=['baseline-before','iq4_xs','q4_0']
fig=figure('Quantization',
    'Vulkan · MTP-4',
    'Screening · quality pending')
ax=axis(fig,[.17,.20,.30,.51],'Aggregate decode','tok/s')
bars(ax,labels,[q[n]['aggregate_decode_tps'] for n in names],[GREY,PURPLE,TEAL],34)
ax=axis(fig,[.66,.20,.26,.51],'First token · p95','seconds')
bars(ax,labels,[q[n]['ttft_p95_s'] for n in names],[GREY,PURPLE,TEAL],.82,decimals=3)
save(fig,'quantization')

fig=figure('Context latency',
    'Vulkan · cold prefix · 128 tokens',
    'Screening · n=3 · context = 2× input')
for rect,key,title in [([.09,.21,.36,.51],'ttft_p50_s','First token · median'),([.59,.21,.34,.51],'completion_p50_s','Completion · median')]:
    ax=axis(fig,rect,title,'Input tokens'); ax.xaxis.grid(False);ax.grid(axis='y',color=GRID)
    for kv,label,color in [('f16','F16',GREY),('q8_0','Q8',TEAL),('q4_0','Q4',PURPLE)]:
        vals=[]
        for ctx in [8192,16384,32768]:
            ws=D['long-context-results'][f'context{ctx}-{kv}']['workloads']
            vals.append(next(r[key] for r in ws if not r['workload'].get('reuse')))
        ax.plot([0,1,2],vals,color=color,label=label,lw=2.4,marker='o',markersize=6)
        if kv in ['f16','q8_0']:
            for i,v in enumerate(vals):ax.annotate(f'{v:.1f}',(i,v),xytext=(0,9 if kv=='f16' else -16),textcoords='offset points',ha='center',fontsize=9,color=color)
    ax.set_xticks([0,1,2],['4K','8K','16K']);ax.set_ylim(0,110);ax.set_ylabel('seconds')
    ax.legend(frameon=False,ncol=3,loc='upper left')
save(fig,'long-context')

c=D['concurrency-results']
fig=figure('Concurrency',
    'Vulkan · 8K context/request · 128 tokens',
    'Screening · 3 batches · p95 completion')
for rect,title,keys,labels in [([.22,.20,.23,.51],'2 requests', ['queued2-mtp4','clients2-mtp2','clients2-mtp4'],['1 slot · MTP-4','2 slots · MTP-2','2 slots · MTP-4']),
    ([.72,.20,.21,.51],'4 requests',['queued4-mtp4','clients4-mtp0','clients4-mtp4'],['1 slot · MTP-4','4 slots · no MTP','4 slots · MTP-4'])]:
    ax=axis(fig,rect,title,'Aggregate · tok/s')
    bars(ax,labels,[c[k]['aggregate_wall_tps'] for k in keys],[GREY,TEAL,PURPLE],48)
    for i,k in enumerate(keys):
        ax.text(1,i+.28,f"p95 {c[k]['completion_p95_s']:.2f} s",color=MUTED,fontsize=9,va='top')
save(fig,'concurrency')

fig=figure('Kernel dispatch',
    'Q4_K matrix · 21,504 × 5,376',
    'Diagnostic trace · separate screening batches')
ax=axis(fig,[.23,.20,.23,.51],'Operation duration','microseconds / call')
bars(ax,['5 columns · MMV','9 columns · MM'],D['kernel']['duration_us'],[TEAL,GOLD],1250,decimals=0)
ax=axis(fig,[.76,.20,.17,.51],'Median generation','tok/s')
rates=[next(r['median_tps'] for r in D['depth'] if r['case']=='mtp8'),D['runtime-results']['threshold16-mtp8']['median_decode_tps'],D['initial']['deployed']['median_decode_tps']]
bars(ax,['Original MTP-8','Patched MTP-8','Deployed MTP-4'],rates,[GREY,PURPLE,BLUE],33)
save(fig,'kernel-boundary')
print('Rendered 6 figures as PNG and editable SVG.')

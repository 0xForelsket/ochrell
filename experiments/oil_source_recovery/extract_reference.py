"""Digitize Figure 6 vector geometry from the original author-hosted PDF."""
import hashlib,json
from pathlib import Path
import pdfplumber
HERE=Path(__file__).parent;SOURCE=HERE.resolve().parents[1]/'target/measured-oils/public-audit/grillini-paper.pdf'
EXPECTED='cb49f755727a8b437f54dc55042b81b4b311b0e24848eacd3faf56cb34080a4e'
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==EXPECTED
with pdfplumber.open(SOURCE) as doc:
    p=doc.pages[8]
    ticks=sorted([q for q in p.lines if 175<q['x0']<355 and 635<q['top']<636 and abs(q['x0']-q['x1'])<1e-8],key=lambda q:q['x0'])
    assert len(ticks)==5
    origin=ticks[0]['x0'];scale=(ticks[-1]['x0']-origin)/.04
    bars=sorted([q for q in p.rects if q.get('fill') and abs(q['x0']-origin)<.001 and 12<q['height']<12.3 and 521<q['top']<626],key=lambda q:q['top'])
    means={f'M{i+1}':(q['x1']-origin)/scale for i,q in enumerate(bars)}
    assert len(means)==7
    intervals={}
    for i,bar in enumerate(bars):
        center=(bar['top']+bar['bottom'])/2
        lines=[q for q in p.lines if q['linewidth']>.5 and 200<q['x0']<340 and abs(q['top']-center)<.002 and abs(q['bottom']-q['top'])<1e-8]
        assert len(lines)==2
        intervals[f'M{i+1}']=(max(q['x1'] for q in lines)-min(q['x0'] for q in lines))/(2*scale)
    plot=next(q for q in p.rects if q['fill'] and 384<q['x0']<386 and 170<q['width']<172 and 134<q['height']<136)
    count_scale=plot['height']/200
    counts={}
    for label,color in [('best',(0.0,.501953,.599609)),('worst',(.122070,.800781,.800781))]:
        boxes=sorted([q for q in p.rects if not q['fill'] and q['non_stroking_color']==color and 8<q['width']<8.5 and abs(q['bottom']-plot['bottom'])<1e-4],key=lambda q:q['x0'])
        assert len(boxes)==7
        counts[label]=[round(q['height']/count_scale) for q in boxes]
        assert sum(counts[label])==175
    report={'method':'Vector axis tick marks, bar endpoints, confidence interval lines, and count-bar heights; approximate plot digitization.',
            'pdf_sha256':EXPECTED,'MSE':means,'CI_halfwidth':intervals,'counts':counts,
            'ticks':[q['x0'] for q in ticks],'bars':[{k:q[k] for k in ['x0','x1','width']} for q in bars]}
(HERE/'figure6-vector-ticks.json').write_bytes((json.dumps(report,indent=2)+'\n').encode())
print(json.dumps(report,indent=2))

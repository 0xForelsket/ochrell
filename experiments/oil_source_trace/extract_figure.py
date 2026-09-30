"""Read Figure 6 vector bar widths; values are approximate plot digitization."""
import hashlib
import json
from pathlib import Path
import pdfplumber

HERE=Path(__file__).resolve().parent
ROOT=HERE.parents[1]
SOURCE=ROOT/'target/measured-oils/public-audit/grillini-paper.pdf'
EXPECTED='cb49f755727a8b437f54dc55042b81b4b311b0e24848eacd3faf56cb34080a4e'
assert hashlib.sha256(SOURCE.read_bytes()).hexdigest()==EXPECTED
with pdfplumber.open(SOURCE) as pdf:
    page=pdf.pages[8]
    bars=sorted([r for r in page.rects if r.get('fill') and abs(r['x0']-180.660229)<.001
                 and 12<r['height']<12.3 and 521<r['top']<626],key=lambda r:r['top'])
    ticks=[w for w in page.extract_words() if w['text'] in ['0','0.01','0.02','0.03','0.04']
           and 177<w['x0']<355 and 639<w['top']<642]
    centers=[(float(w['text']),(w['x0']+w['x1'])/2) for w in ticks]
    zero=next(x for v,x in centers if v==0)
    end=next(x for v,x in centers if v==.04)
    scale=(end-zero)/.04
    values={f'M{i+1}':(b['x1']-b['x0'])/scale for i,b in enumerate(bars)}
    assert len(values)==7 and len(centers)==5
    report={'method':'Vector bar widths from author-hosted PDF Figure 6a, calibrated by numeric tick text centers. Approximate graph-derived values, not original numerical results.',
            'pdf_sha256':EXPECTED,'page_one_based':9,'figure':'6a',
            'tick_centers':centers,'bar_width_derived_mse':values}
(HERE/'figure6-values.json').write_bytes((json.dumps(report,indent=2)+'\n').encode())
print(json.dumps(values,indent=2))

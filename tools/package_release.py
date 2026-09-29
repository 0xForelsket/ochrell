"""Create an inspectable source/results ZIP, excluding build and review debris."""
from pathlib import Path
import zipfile,hashlib,json
ROOT=Path(__file__).resolve().parents[1]
required=['Cargo.toml','README.md','LICENSE','src/lib.rs','tests/numerics.rs','docs/research.md','docs/math.md','docs/architecture.md','docs/benchmarks.md','paper/paper.md','paper/paper.tex','paper/paper.pdf','paper/references.bib','results/summary.json','results/environment.json','data/default.lut','src/optical.rs','src/optical_generated.rs','data/optical_basis.csv','results/revision/summary.json','results/revision/environment.json','tools/reproduce.py','docs/coefficients.md']
for name in required:
 if not (ROOT/name).is_file():raise FileNotFoundError(name)
files=[]
for p in sorted(ROOT.rglob('*')):
 if not p.is_file():continue
 r=p.relative_to(ROOT)
 if any(x in {'target','__pycache__','.git','tmp','.venv'} for x in r.parts):continue
 if p.suffix in {'.aux','.log','.out','.toc','.pyc'} or p.name=='build-error.txt':continue
 if r.as_posix()=='MANIFEST.sha256':continue
 files.append((r,p))
manifest=''.join(hashlib.sha256(p.read_bytes()).hexdigest()+'  '+r.as_posix()+'\n' for r,p in files)
(ROOT/'MANIFEST.sha256').write_text(manifest)
files.append((Path('MANIFEST.sha256'),ROOT/'MANIFEST.sha256'))
out=ROOT.parent/'ochrell.zip'
with zipfile.ZipFile(out,'w',zipfile.ZIP_DEFLATED,compresslevel=6) as z:
 for r,p in files:z.write(p,'ochrell/'+r.as_posix())
with zipfile.ZipFile(out) as z:
 if z.testzip() is not None:raise RuntimeError('ZIP integrity failure')
 # Validate every archived file against the manifest, not merely a count.
 for r,p in files:
  if z.read('ochrell/'+r.as_posix())!=p.read_bytes():raise RuntimeError(str(r))
print(json.dumps({'path':str(out),'bytes':out.stat().st_size,'files':len(files),'sha256':hashlib.sha256(out.read_bytes()).hexdigest()}))

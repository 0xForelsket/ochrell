"""Package source, captures and outputs; exclude installed third-party code."""
from pathlib import Path
import argparse,hashlib,json,zipfile
root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('output',type=Path);args=p.parse_args()
files=[x for x in sorted(root.rglob('*')) if x.is_file() and not any(d in {'node_modules','__pycache__','.git'} for d in x.relative_to(root).parts) and x.suffix not in {'.log','.zip','.pyc'} and x.name not in {'probe','MANIFEST.sha256'}]
(root/'MANIFEST.sha256').write_text(''.join(hashlib.sha256(x.read_bytes()).hexdigest()+'  '+str(x.relative_to(root))+'\n' for x in files))
files.append(root/'MANIFEST.sha256')
with zipfile.ZipFile(args.output,'w',zipfile.ZIP_DEFLATED) as z:
 for x in files:z.write(x,'mixbox-comparison/'+str(x.relative_to(root)))
with zipfile.ZipFile(args.output) as z:
 assert z.testzip() is None
 for x in files:assert z.read('mixbox-comparison/'+str(x.relative_to(root)))==x.read_bytes()
print(json.dumps({'path':str(args.output.resolve()),'files':len(files),'bytes':args.output.stat().st_size,'sha256':hashlib.sha256(args.output.read_bytes()).hexdigest()}))

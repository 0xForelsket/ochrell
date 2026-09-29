"""Run the pinned evaluation-only npm dependency with settings from TOML."""
from pathlib import Path
import subprocess,tomllib,json,csv,hashlib
root=Path(__file__).resolve().parents[1]
settings=tomllib.loads((root/'config.toml').read_text())['spectral']
cases=json.loads((root/'captures/manifest.json').read_text())['cases']
result=json.loads(subprocess.check_output(['node',str(root/'tools/run_spectral.cjs')],input=json.dumps({'settings':settings,'cases':cases}).encode(),cwd=root))
rows=result.pop('rows')
with (root/'results/spectral.csv').open('w',newline='') as f:
 w=csv.DictWriter(f,fieldnames=['pair','t','r','g','b']);w.writeheader();w.writerows(rows)
result['package_lock_sha256']=hashlib.sha256((root/'package-lock.json').read_bytes()).hexdigest()
result['package_entry_sha256']=hashlib.sha256((root/'node_modules/spectral.js/spectral.js').read_bytes()).hexdigest()
result['source']='https://registry.npmjs.org/spectral.js/-/spectral.js-3.0.0.tgz'
result['api']='spectral.mix([a,1-t],[b,t]).toGamut({method:"map"}).sRGB; native RGB8 output'
errors=[]
for c in result['checks']:
 expected=[int(c['input'][j:j+2],16) for j in [1,3,5]]
 errors.append(max(abs(a-b) for a,b in zip(expected,c['output'])))
result['max_endpoint_rgb8_error']=max(errors)
(root/'results/spectral_environment.json').write_text(json.dumps(result,indent=2)+'\n')
print(f'Recorded {len(rows)} Spectral.js outputs. Maximum endpoint RGB8 discrepancy: {max(errors)}.')

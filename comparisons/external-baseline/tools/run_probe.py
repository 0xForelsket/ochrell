"""Run against an extracted pigment-mix release. No Mixbox SDK is required."""
import argparse,json,os,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
p=argparse.ArgumentParser();p.add_argument('pigment_mix',type=Path);args=p.parse_args()
source=args.pigment_mix.resolve();cargo=os.environ.get('CARGO','cargo');rustc=os.environ.get('RUSTC','rustc')
subprocess.run([cargo,'build','--release','--offline','--lib','--manifest-path',str(source/'Cargo.toml')],check=True)
meta=json.loads(subprocess.check_output([cargo,'metadata','--offline','--no-deps','--format-version','1','--manifest-path',str(source/'Cargo.toml')]))
target=Path(meta['target_directory'])/'release'
out=root/'results/probe'
subprocess.run([rustc,'--edition=2021','-O',str(root/'tools/probe.rs'),'--extern',f'pigment_mix={target / "libpigment_mix.rlib"}','-L',str(target/'deps'),'-o',str(out)],check=True)
with (root/'inputs.txt').open('rb') as src,(root/'results/ours.csv').open('wb') as dst:
 subprocess.run([str(out)],stdin=src,stdout=dst,check=True)
print('Recorded 13 matched pairs at 401 ratios each.')

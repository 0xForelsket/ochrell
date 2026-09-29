#!/usr/bin/env python3
"""Reproduce v0.2 results and manuscript; use reproduce_legacy.py for v0.1."""
import os,sys,subprocess,json,platform,hashlib,shutil,tomllib,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];os.chdir(ROOT);C=tomllib.loads(Path('config.toml').read_text());E=C['revision'];O=C['optical']
for k in ['random_colors','random_pairs','trajectory_steps','random_trajectories','benchmark_iterations','benchmark_repeats']:
 if not isinstance(E[k],int) or E[k]<2:raise ValueError(f'revision.{k} must be integer >=2')
if E['trajectory_steps']%2!=1:raise ValueError('trajectory_steps must be odd to include the midpoint')
if not isinstance(E['seed'],int) or not 0<E['seed']<2**64:raise ValueError('seed must be a positive u64')
if O['beta']!=.5 or O['reference_step_nm']!=5 or O['fast_step_nm']!=10:raise ValueError('Published v0.2 suite requires beta=.5, reference 5nm, fast 10nm; use Python model for resolution/normalization ablations')
if O['white_strength']<1 or O['logit_smoothing']<=0 or O['initial_smoothing']<=0:raise ValueError('Invalid optical strength/smoothing')
# Declared historical ablations are intentionally fixed protocols, independently
# recorded from the configurable default model and validation workloads.
cargo=os.environ.get('CARGO','cargo');env=dict(os.environ,OPENBLAS_NUM_THREADS='1')
def run(*args,**kwargs):return subprocess.run(args,check=True,env=env,**kwargs)
for script in ['tools/revision/explore.py','tools/revision/sweep_optics.py','tools/revision/sweep_basis.py','tools/revision/assess_candidates.py','tools/optical_model.py']:
 run(sys.executable,script,stdout=subprocess.DEVNULL)
run(cargo,'test','--release','--offline');run(cargo,'build','--release','--offline','--example','sample_pairs')
run(cargo,'run','--release','--offline','--bin','revision-experiments','--',*[str(E[k]) for k in ['random_colors','random_pairs','trajectory_steps','random_trajectories','benchmark_iterations','benchmark_repeats','seed']])
run(sys.executable,'tools/revision/holdout.py')
for script in ['tools/revision/analyze.py','tools/revision/external.py']:run(sys.executable,script,stdout=subprocess.DEVNULL)
cpu=subprocess.check_output(['lscpu'],text=True) if shutil.which('lscpu') else platform.processor()
compiler=run(cargo,'rustc','--release','--offline','--lib','--','--version',capture_output=True,text=True).stdout.strip()
meta={'platform':platform.platform(),'python':sys.version,'rustc':compiler,'cargo':subprocess.check_output([cargo,'--version'],text=True).strip(),'cpu':cpu,'cpu_model':next((l.split(':',1)[1].strip() for l in cpu.splitlines() if l.startswith('Model name:')),platform.processor()),'config_sha256':hashlib.sha256(Path('config.toml').read_bytes()).hexdigest(),'threading':'single-thread Rust; OPENBLAS_NUM_THREADS=1','release_profile':'LTO disabled; codegen-units=1; no target-cpu=native','wall_clock_unix':time.time()}
Path('results/revision/environment.json').write_text(json.dumps(meta,indent=2)+'\n')
run(sys.executable,'tools/revision/figures.py');run(sys.executable,'tools/revision/render_paper.py')
Path('examples/comparisons').mkdir(parents=True,exist_ok=True);shutil.copyfile('paper/figures/comparisons.png','examples/comparisons/comparisons.png')
print('Reproduced v0.2: tests, fit, experiments, ablations, comparisons, figures and paper.')

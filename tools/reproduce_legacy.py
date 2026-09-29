#!/usr/bin/env python3
"""Single-command reproduction. Config is read, validated and never rewritten."""
import os,sys,tomllib,subprocess,json,platform,hashlib,shutil,time
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];os.chdir(ROOT)
C=tomllib.loads((ROOT/'config.toml').read_text());E=C['experiments'];P=C['paths'];M=C['model']
for key in ['random_colors','random_pairs','trajectory_steps','benchmark_iterations','benchmark_repeats']:
 if not isinstance(E[key],int) or E[key]<2:raise ValueError(f'config.toml: experiments.{key} must be an integer >= 2')
if E['lut_resolutions']!=[17,33,65]:raise ValueError('config.toml: experiments.lut_resolutions must be [17,33,65] for the published experiment suite')
if not 0<M['reflectance_floor']<M['reflectance_ceiling']<1:raise ValueError('config.toml: model reflectance bounds must satisfy 0 < floor < ceiling < 1')
for k in ['transition_nm','white_scattering','black_scattering','chromatic_scattering','regularization']:
 if M[k]<=0:raise ValueError(f'config.toml: model.{k} must be positive')
if not isinstance(M['solver_iterations'],int) or M['solver_iterations']<1:raise ValueError('config.toml: model.solver_iterations must be positive integer')
for k,v in P.items():
 if Path(v).is_absolute() or '..' in Path(v).parts:raise ValueError(f'config.toml: paths.{k} must be relative within the repository')
if not isinstance(E['seed'],int) or not 0<E['seed']<2**64:raise ValueError('config.toml: experiments.seed must be a positive u64')
# CARGO allows a local toolchain wrapper; otherwise use the user's standard cargo.
cargo=os.environ.get('CARGO','cargo');env=dict(os.environ,OPENBLAS_NUM_THREADS='1')
def run(*args):subprocess.run(args,check=True,env=env)
run(sys.executable,'tools/explore_all.py');run(sys.executable,'tools/generate_model.py');run(cargo,'build','--release','--offline')
output=ROOT/P['results'];(output/'performance').mkdir(parents=True,exist_ok=True)
gen=[]
for n in E['lut_resolutions']:
 start=time.perf_counter();run('target/release/generate-lut',str(n),f'data/lut-{n}.bin');gen.append({'resolution':n,'seconds':time.perf_counter()-start,'bytes':(ROOT/f'data/lut-{n}.bin').stat().st_size})
shutil.copyfile('data/lut-33.bin','data/default.lut');run(cargo,'test','--release','--offline');run(cargo,'build','--release','--offline')
run('target/release/experiments',*[str(E[k]) for k in ['random_colors','random_pairs','trajectory_steps','benchmark_iterations','benchmark_repeats','seed']],P['results'])
for example,filename in [('precision','reconstruction/precision.csv'),('random_smoothness','mixing/random_smoothness.csv')]:
 run(cargo,'build','--release','--offline','--example',example)
 with open(output/filename,'w') as f:subprocess.run(['target/release/examples/'+example]+([str(output/'reconstruction/samples.csv')] if example=='precision' else []),stdout=f,check=True,env=env)
(output/'performance/generation.json').write_text(json.dumps(gen,indent=2)+'\n')
environment={'platform':platform.platform(),'python':sys.version,'cargo':subprocess.check_output([cargo,'--version'],text=True).strip(),'cpu':subprocess.check_output(['lscpu'],text=True) if shutil.which('lscpu') else platform.processor(),'config_sha256':hashlib.sha256((ROOT/'config.toml').read_bytes()).hexdigest(),'threading':'single-thread Rust; OPENBLAS_NUM_THREADS=1 for Python','release_profile':'LTO disabled, codegen-units=1; no target-cpu=native','wall_clock_unix':time.time()}
(output/'environment.json').write_text(json.dumps(environment,indent=2)+'\n')
run(sys.executable,'tools/analyze.py');run(sys.executable,'tools/generate_figures.py')
if (ROOT/'tools/render_paper_legacy.py').exists():run(sys.executable,'tools/render_paper_legacy.py')
print('Reproduced experiment CSV, metrics, figures and generated paper tables.')

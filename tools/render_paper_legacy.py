"""Generate manuscript values and readable two-column TeX/PDF from recorded data."""
import json,re,subprocess,shutil,tomllib,os
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1];C=tomllib.loads((ROOT/'config.toml').read_text());S=json.loads((ROOT/C['paths']['results']/'summary.json').read_text());E=C['experiments'];ENV=json.loads((ROOT/C['paths']['results']/'environment.json').read_text());P=S['performance'];R=S['reconstruction'];L=S['lut'];S20=next(x for x in S['spectral_resolution'] if x['step_nm']==20)
def f(x):return f'{x:.3g}'
def table(headers,rows):return '\n'.join(['| '+' | '.join(headers)+' |','| '+' | '.join(['---']*len(headers))+' |']+['| '+' | '.join(map(str,row))+' |' for row in rows])
keys=['mean','median','p95','p99','max']
values={'N':E['random_colors'],'NP':E['random_pairs'],'SEED':E['seed'],'STEPS':E['trajectory_steps'],'BN':E['benchmark_iterations'],'REFBN':min(1000,E['benchmark_iterations']),
'RECON_MEAN':f(R['fast_hybrid']['deltaE00']['mean']),'RECON_MAX':f(R['fast_hybrid']['deltaE00']['max']),'RAW_MEAN':f(R['reference_no_residual']['deltaE00']['mean']),
'LUT_MEAN':f(L['n33_']['deltaE00']['mean']),'LUT_P95':f(L['n33_']['deltaE00']['p95']),'LUT_MAX':f(L['n33_']['deltaE00']['max']),
'FAST_MPS':f(P['fast RGB']['million_per_second']),'CACHED_MPS':f(P['fast cached latent']['million_per_second']),'FAST_NS':f(P['fast RGB']['median']),'CACHED_NS':f(P['fast cached latent']['median']),'STARTUP_MS':f(P['LUT parsing']['median']/1e6),
'CROSS_ERROR':f(S['cross_language_max_linear_error']),'PRECISION_ERROR':f(S['precision_max_linear_error']),
'GAMUT_PERCENT':f(S['random_mix_gamut_fraction']*100),'RAW_RANGE':str([round(x,3) for x in S['random_mix_raw_range']]),'SPEC_MEAN':f(S20['mean']),'SPEC_P95':f(S20['p95']),
'MAXSTEP':f(max(x['max_step_deltaEOK100'] for x in S['smoothness'] if x['mode']==3)),'RANDOMSTEP':f(S['random_smoothness_max_step']),
'CPU':next((line.split(':',1)[1].strip() for line in ENV['cpu'].splitlines() if line.startswith('Model name:')),'see environment.json')}
labels={'reference_hybrid':'Reference + residual','fast_hybrid':'Fast + residual','reference_no_residual':'Reference palette only','fast_no_residual':'Fast palette only'}
values['RECON_TABLE']=table(['Model','Mean','Median','P95','P99','Max'],[[labels[k]]+[f(v['deltaE00'][s]) for s in keys] for k,v in R.items()])
values['MIDPOINT_TABLE']=table(['Pair','Fast midpoint (sRGB8)'],[[x['pair'].replace('_',' + '),str(tuple(x['srgb8']))] for x in S['midpoints']])
values['LUT_TABLE']=table(['Encoder','Mean','Median','P95','P99','Max'],[[k.replace('_','')]+[f(v['deltaE00'][s]) for s in keys] for k,v in L.items()])
values['PERF_TABLE']=table(['Operation','Median ns','Million/s'],[[k,f(v['median']),f(v['million_per_second'])] for k,v in P.items() if k!='LUT parsing'])
values['ABLATION_TABLE']=table(['Basis / S variant','Mean','Median','P95','Max'],[[x['label'].replace('_',' ')]+[f(x[s]) for s in ['mean','median','p95','max']] for x in S['basis_ablation']])
s=(ROOT/'tools/paper.template.md').read_text()
for k,v in values.items():s=s.replace('@'+k+'@',str(v))
if re.search(r'@[A-Z_]+@',s):raise ValueError('Unsubstituted manuscript token')
s=s.replace('](figures/',']('+os.path.relpath(ROOT/'paper/legacy/figures',ROOT/'paper/legacy')+'/')
(ROOT/'paper/legacy/paper.md').write_text(s)
bench='# Benchmarks and numerical results\n\nAll numbers are generated from recorded CSV files; no comparison against real paint is implied.\n\n'+values['PERF_TABLE']+'\n\nCPU: '+values['CPU']+'. Rust 1.75.0, release, LTO disabled, codegen-units=1; single thread. Seven repetitions. Full RGB timings include encoding and final display conversion; cached latent timings include one decode. Lookup alone is not a complete mix. Startup table parsing median: '+values['STARTUP_MS']+' ms.\n\n## Reconstruction (CIEDE2000)\n\n'+values['RECON_TABLE']+'\n\n## LUT mixture error against direct reference (CIEDE2000)\n\n'+values['LUT_TABLE']+'\n\nThe 33³ maximum discrepancy is '+values['LUT_MAX']+' ΔE00: large outliers remain despite a low median. The raw palette mean error is '+values['RAW_MEAN']+' ΔE00. '+values['GAMUT_PERCENT']+'% of random mixtures require gamut mapping. The largest random-trajectory adjacent step is '+values['RANDOMSTEP']+' ΔEOK100 at Δt=0.001. Numerical continuity does not imply gentle visual transitions.\n\n## Reference checks\n\nCross-language f64 maximum linear-channel difference: '+values['CROSS_ERROR']+'. f32-vs-f64 at 20 nm, including weight quantization: '+values['PRECISION_ERROR']+'. The 20 nm vs 5 nm fixed-recipe mean and P95 ΔE00 are '+values['SPEC_MEAN']+' and '+values['SPEC_P95']+'.\n\n## Regeneration\n\n`python3 tools/reproduce.py` runs the declared experiment suite; `cargo bench --bench mixing` runs a smaller standalone microbenchmark. Raw repetitions, generation cost, environment and worst examples are retained under `results/`. Compiler, system load, cache state and frequency affect timing; no cross-platform performance guarantee is made.\n'
(ROOT/'docs/legacy/benchmarks.md').write_text(bench)
(ROOT/'paper/legacy/tables/values.json').write_text(json.dumps(values,indent=2)+'\n')
if not shutil.which('pandoc'):print('Pandoc unavailable; Markdown paper generated.');raise SystemExit(0)
os.chdir(ROOT/'paper/legacy')
subprocess.run(['pandoc','paper.md','--standalone','--citeproc','--resource-path=.', '-V','documentclass=article','-V','classoption=twocolumn','-V','fontsize=10pt','-V','geometry:margin=0.7in','-V','colorlinks=true','--bibliography=references.bib','-o','paper.tex'],check=True)
tex=Path('paper.tex').read_text()
# Standard Pandoc longtables do not fit two-column output. Convert them to
# full-width float tables, preserving their generated contents and alignment.
table_titles=iter(["Source reconstruction (CIEDE2000).", "Canonical fast-model midpoint colors.", "Mixture error relative to direct reference (CIEDE2000).", "Single-thread native timing; lookup is not a full mix.", "Palette and scattering ablations, without residual (CIEDE2000)."])
def convert_table(m):
 block=m.group(1);block=re.sub(r'\\endfirsthead.*?\\endhead','',block,flags=re.S);block=block.replace('\\endhead','').replace('\\endlastfoot','').replace('\\endfoot','');return '\\begin{table*}[t]\n\\caption{'+next(table_titles)+'}\n\\centering\\small\n\\begin{tabular}'+block+'\\end{tabular}\n\\end{table*}'
tex=re.sub(r'\\begin\{longtable\}\[\](.*?)\\end\{longtable\}',convert_table,tex,flags=re.S)
# Full-width figures keep axis labels legible in the two-column paper.
tex=tex.replace('\\begin{figure}', '\\begin{figure*}[t]').replace('\\end{figure}','\\end{figure*}')
tex=re.sub(r'\\includegraphics(?:\[[^\]]*\])?\{(figures/[^}]+)\}',r'\\includegraphics[width=0.94\\textwidth,height=0.76\\textheight,keepaspectratio]{\1}',tex)
# Let TeX break URLs and difficult code identifiers rather than overprinting columns.
tex=tex.replace('Δ',r'\ensuremath{\Delta}')
tex=tex.replace('\\begin{document}','\\setlength{\\emergencystretch}{2em}\n\\sloppy\n\\begin{document}')
Path('paper.tex').write_text(tex)
if shutil.which('pdflatex'):
 for _ in range(2):
  run=subprocess.run(['pdflatex','-interaction=nonstopmode','-halt-on-error','paper.tex'],stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
  if run.returncode:Path('build-error.txt').write_text(run.stdout);raise RuntimeError(run.stdout[-2500:])
 print('Generated Markdown, TeX and PDF paper.')
else:print('pdflatex unavailable; Markdown and TeX generated.')

"""Plot the frozen parallel results; no fitting or measurement reconstruction."""
import json
from pathlib import Path
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
v3 = json.loads((ROOT / 'results/measured-oils-v3/summary.json').read_text())
physical = json.loads((HERE / 'physical/summary.json').read_text())
objective = json.loads((HERE / 'objective/summary.json').read_text())
interaction = json.loads((HERE / 'interaction/summary.json').read_text())
models = [
    ('V1 reference (21 fit)', v3['primary_multicolor16']['v1'], '#8c939a'),
    ('V3 reference (29 fit)', v3['primary_multicolor16']['v3'], '#abb1b7'),
    ('Finite layer', physical['multicolor16']['finite'], '#b86745'),
    ('Color-aware objective', objective['primary_multicolor16']['hybrid'], '#547ea1'),
    ('Empirical interaction', interaction['primary16']['interaction'], '#278371'),
]
fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), layout='constrained', gridspec_kw={'width_ratios': [1.5, 1]})
for i, (label, data, color) in enumerate(models):
    de = data['delta_e_2000']; rmse = data['spectral_rmse']
    axes[0].barh(i, de['mean'], color=color)
    axes[0].plot(de['p95'], i, 'o', color=color, markersize=6)
    axes[0].plot(de['max'], i, 'x', color=color, markersize=7)
    axes[1].barh(i, rmse['mean'], color=color)
axes[0].set_yticks(range(len(models)), [m[0] for m in models])
axes[1].set_yticks(range(len(models)), [])
for ax in axes:
    ax.invert_yaxis(); ax.grid(axis='x', alpha=.2); ax.set_axisbelow(True)
axes[0].axvline(3, color='#555', linestyle='--', linewidth=1)
axes[1].axvline(.02, color='#555', linestyle='--', linewidth=1)
axes[0].set_xlabel('DE00: bar = mean, dot = p95, cross = maximum')
axes[1].set_xlabel('Mean spectral RMSE (reflectance)')
axes[0].set_title('Color accuracy, truncated D65 / 2-degree')
axes[1].set_title('Spectral accuracy, 400–700 nm')
fig.suptitle('Parallel experiments: same 16 multicolor samples\nExploratory results; dashed lines are original mean-error screens', fontsize=13)
fig.savefig(HERE / 'comparison.png', dpi=180)

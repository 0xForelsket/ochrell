"""Audit public recipe coverage and duplicate-source evidence, without fitting."""
import csv
import hashlib
import io
import itertools
import json
import sys
import tarfile
import zipfile
from collections import Counter
from pathlib import Path

import numpy as np
from scipy.io import loadmat
from scipy.spatial.distance import cdist

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
CACHE = ROOT/'target/measured-oils/ternary-source-audit'
sys.path.insert(0, str(ROOT/'experiments/oil_public_data'))
import audit as grillini

NAMES = ['Lemon Yellow', 'Cadmium Yellow', 'Scarlet Lake', 'Alizarine Lake',
         'Cobalt Blue', 'Ultramarine Blue', 'Viridian Green', 'Mixed White']
OLD = ROOT/'target/measured-oils/source/spectralDatasets.zip'
OLD_SHA = 'cda35e5ab968bb18a05127c1b9fb0b2bd3c4a4bb88d4bf4ae1e4b2bb5de07538'


def sha(path): return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value): path.write_bytes((json.dumps(value, indent=2, allow_nan=False)+'\n').encode())


def csv_write(path, rows):
    with path.open('w', encoding='utf-8', newline='') as file:
        writer = csv.DictWriter(file, fieldnames=list(rows[0]), lineterminator='\n')
        writer.writeheader(); writer.writerows(rows)


def main():
    assert sha(OLD) == OLD_SHA
    with zipfile.ZipFile(OLD) as source:
        amounts_raw = source.read('oilmixtureportions.txt'); spectra_raw = source.read('oilspectra.txt')
        assert hashlib.sha256(amounts_raw).hexdigest() == 'e968f8384f2ee03dcc16d34f87f895bf61cd63a67a4af99550d6144d0b1995ce'
        assert hashlib.sha256(spectra_raw).hexdigest() == '11436afe638351193eef2dbc87167ab0981464e170f4fd7e6106668adf85fc5b'
        amounts = np.loadtxt(io.BytesIO(amounts_raw)); spectra = np.loadtxt(io.BytesIO(spectra_raw))
    assert amounts.shape == (286,8) and spectra.shape == (286,31)
    assert np.isfinite(amounts).all() and (amounts >= 0).all() and (amounts.sum(1) > 0).all()
    assert np.isfinite(spectra).all() and (spectra > 0).all() and (spectra < 1).all()
    c = amounts/amounts.sum(1, keepdims=True); count = (c > 0).sum(1)
    assert len(np.unique(c.round(12), axis=0)) == len(c)
    no_white = (count == 3) & (c[:,7] == 0)
    previous = (c[:,[1,3,5,6]] == 0).all(1)
    known = no_white & previous; new = no_white & ~previous
    assert (np.flatnonzero(known)+1).tolist() == [172,174,176]
    assert no_white.sum() == 38 and new.sum() == 35
    families, samples, palettes = [], [], []
    for triple in itertools.combinations(range(7),3):
        columns = [*triple,7]
        subset = (c[:,[j for j in range(8) if j not in columns]] == 0).all(1)
        test = subset & no_white
        if not test.any(): continue
        train = subset & (count <= 2)
        pure = train & (count == 1)
        white_tints = train & (count == 2) & (c[:,7] > 0)
        chromatic_pairs = train & (count == 2) & (c[:,7] == 0)
        pair_counts = {f'{a+1}+{b+1}': int((train & (c[:,a] > 0) & (c[:,b] > 0)).sum()) for a,b in itertools.combinations(columns,2)}
        assert pure.sum() == 4 and min(pair_counts.values()) >= 1 and not (train & test).any()
        assert not (count[train] >= 3).any()
        gate = 27*np.prod(c[test][:,triple],axis=1)
        family = '+'.join(str(x+1) for x in triple)
        is_prior = triple == (0,2,4)
        families.append({'family_columns_one_based': family, 'paint_names': '; '.join(NAMES[x] for x in triple),
            'assessment_rows': ','.join(str(i+1) for i in np.flatnonzero(test)), 'assessment_count': int(test.sum()),
            'prior_four_paint_family': is_prior, 'gate_min': float(gate.min()), 'gate_max': float(gate.max()),
            'calibration_count': int(train.sum()), 'pure_count': int(pure.sum()), 'white_tint_count': int(white_tints.sum()),
            'chromatic_pair_count': int(chromatic_pairs.sum()), 'binary_support': json.dumps(pair_counts, sort_keys=True),
            'related_white_multicolor_rows': ','.join(str(i+1) for i in np.flatnonzero(subset & (count >= 3) & (c[:,7] > 0)))})
        for i in np.flatnonzero(test):
            samples.append({'source_row_one_based': int(i+1), 'family_columns_one_based': family,
                'fractions_in_family_order': ','.join(f'{x:.12g}' for x in c[i,list(triple)]),
                'gate_27_product': float(27*np.prod(c[i,list(triple)])), 'prior_four_paint_family': is_prior})
        if not is_prior:
            palettes.append({'id': 'old-holland-'+family.replace('+','-'), 'columns_one_based': [x+1 for x in columns],
                'paint_names': [NAMES[x] for x in columns], 'calibration_rows_one_based': (np.flatnonzero(train)+1).tolist(),
                'assessment_rows_one_based': (np.flatnonzero(test)+1).tolist(), 'pair_calibration_counts': pair_counts})
    assert len(families) == 26 and len(palettes) == 25
    combined = [i for p in palettes for i in p['assessment_rows_one_based']]
    assert sorted(combined) == (np.flatnonzero(new)+1).tolist() and len(set(combined)) == 35
    csv_write(HERE/'old-holland-families.csv', families); csv_write(HERE/'old-holland-ternaries.csv', samples)
    cohort = {'status': 'Unscored cohort selected by recipe coverage, not model errors.', 'source_sha256': OLD_SHA,
        'source_row_indexing': 'one-based numeric rows, no header', 'wavelengths_nm': list(range(400,701,10)),
        'concentrations': 'recorded tube-paint mass, normalized per recipe', 'assessment_rows': 35,
        'palettes': palettes, 'previously_assessed_control_rows_one_based': [172,174,176],
        'fitting_policy': 'For a future comparison: pure and binary calibration only; all multi-material rows excluded from calibration.',
        'caveat': 'Same-source extension outside the previous four-paint palette, not a new independent dataset.'}
    write(HERE/'next-cohort.json', cohort)

    labels, order, weights, nominal, nm, reflectance, _ = grillini.load()
    k = (weights > 0).sum(1); w = order.index('W'); mask = (k == 3) & (weights[:,w] == 0)
    ambiguity_path = ROOT/'experiments/oil_source_recovery/pair-ambiguity-audit.json'
    ambiguity = json.loads(ambiguity_path.read_text(encoding='utf-8'))
    affected = {str(case['tolerance']): {label for p in case['ambiguous_pairs'] for label in p['labels']} for case in ambiguity['cases']}
    grillini_families = []
    for triple in itertools.combinations([j for j in range(7) if j != w],3):
        selected = mask & (weights[:,[j for j in range(7) if j not in triple]] == 0).all(1)
        names = np.array(labels)[selected].tolist()
        assert len(names) == 3
        grillini_families.append({'paints': ''.join(order[j] for j in triple), 'labels': ','.join(names),
            'count': len(names), 'gate': float((27*np.prod(weights[selected][:,triple],axis=1))[0]),
            'ambiguous_targets_at_5e_6': ','.join(n for n in names if n in affected['5e-06']),
            'ambiguous_targets_at_1e_5': ','.join(n for n in names if n in affected['1e-05'])})
    assert len(grillini_families) == 20 and all(r['gate'] == 27/32 for r in grillini_families)
    csv_write(HERE/'grillini-families.csv', grillini_families)

    mat_path = CACHE/'mixed-ink-oil.mat'
    assert sha(mat_path) == '52f0ccf0e9b6fc945cfd241d72f41c9e8f7018e3763ff976758573c00201a117'
    duplicate = loadmat(mat_path)['spec']; assert duplicate.shape == (289,31)
    distance = cdist(spectra, duplicate, metric='chebyshev')
    nearest = distance.argmin(1)
    assert len(set(nearest.tolist())) == 286 and distance.min(1).max() < 1e-12
    matching = [{'asadi_row_one_based': i+1, 'mixed_ink_row_one_based': int(j+1), 'max_absolute_difference': float(distance[i,j])} for i,j in enumerate(nearest)]
    csv_write(HERE/'duplicate-source-matches.csv', matching)

    bath_path = CACHE/'bath-reflectance.tar.gz'
    assert sha(bath_path) == '018dfa9d5452cf3a24e017b5e1a4d145ac0005cde13092c8ae591515fc40fb62'
    with tarfile.open(bath_path) as archive:
        groups = sorted({Path(m.name).parts[1] for m in archive.getmembers() if m.isfile()})
        kinds = Counter('pure' if g.endswith('_Pure') else 'layered' if g.endswith('_Glaze') else 'binary' for g in groups)
        assert all(len(g.split('_')[0].split('-')) <= 2 for g in groups)

    downloads_path = HERE/'downloads.json' if (HERE/'downloads.json').exists() else CACHE/'downloads.json'
    downloads = json.loads(downloads_path.read_text(encoding='utf-8'))
    for f in downloads:
        if 'sha256' in f and (CACHE/f['file']).exists(): assert sha(CACHE/f['file']) == f['sha256']
    write(HERE/'downloads.json', downloads)
    novel_gates = [r['gate_27_product'] for r in samples if not r['prior_four_paint_family']]
    result = {'date': '2026-10-01', 'status': 'Coverage and provenance only; no new model fit or model-error score.',
        'hashes': {str(p.relative_to(ROOT)).replace('\\','/'):sha(p) for p in [OLD,grillini.SOURCE,Path(__file__),HERE/'PLAN.md',ambiguity_path,mat_path,bath_path]},
        'old_holland': {'rows':len(c),'bands':31,'range_nm':[400,700], 'ingredient_count_histogram':dict(sorted(Counter(count.tolist()).items())),
            'no_white_ternaries':int(no_white.sum()),'no_white_families':len(families),'previous_control_rows':[172,174,176],
            'additional_ternaries':len(combined),'additional_families':len(palettes),'additional_gate_range':[min(novel_gates),max(novel_gates)],
            'additional_distinct_gate_values':len(set(round(x,12) for x in novel_gates)),
            'additional_calibration_row_range':[min(len(p['calibration_rows_one_based']) for p in palettes),max(len(p['calibration_rows_one_based']) for p in palettes)],
            'no_duplicate_normalized_recipes':True,'all_25_palettes_have_four_pures_and_all_six_binary_pairs':True},
        'grillini':{'rows':len(weights),'ingredient_count_histogram':dict(sorted(Counter(k.tolist()).items())),
            'no_white_ternaries':int(mask.sum()),'no_white_families':len(grillini_families),'additional_to_YCB':int(mask.sum())-3,
            'gate_range':[.84375,.84375],'targets_ambiguous_at_1e_5':sum(n in affected['1e-05'] for n in np.array(labels)[mask]),
            'qualification':'All identities remain inferred. The seven earlier Y/C/B/W projections do not exhaust ambiguity for other palettes.'},
        'mixed_ink_repository':{'array_shape':list(duplicate.shape),'matched_asadi_rows':286,'unique_matches':len(set(nearest.tolist())),
            'maximum_nearest_spectrum_difference':float(distance.min(1).max()),
            'additional_spectrum_rows_one_based':(np.flatnonzero(distance.min(0)>1e-12)+1).tolist(),
            'qualification':'The inspected repository contains no oil recipe table for the three additional spectra; not an independent 289-sample test.'},
        'bath':{'groups':groups,'group_type_counts':dict(kinds),'no_ternary_group_in_archive':True}}
    write(HERE/'summary.json', result)
    print(json.dumps({k:v for k,v in result.items() if k not in ['hashes','bath']}, indent=2))
    print('Bath group types',dict(kinds))


if __name__ == '__main__': main()

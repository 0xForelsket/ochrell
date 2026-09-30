"""Read and audit the public Grillini supplementary tables without fitting a model."""
import hashlib
import io
import json
import re
import sys
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import numpy as np

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
SOURCE = ROOT / 'target/measured-oils/public-audit/grillini-data.zip'
EXPECTED_SHA = '6d8cec6fb4fff5d4c24d18d1783422da8ef955d3e7ba7263179a84ed6c9b683e'
NS = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
PAINTS = {'W': ('Kremer White', '46360'), 'B': ('Ultramarine Blue', '45030'),
          'Y': ('Naples Yellow', '43125'), 'C': ('Carmine', '23403'),
          'V': ('Vermilion', '42000'), 'G': ('Viridian Green', '44250'),
          'O': ('Gold Ochre DD', '40214')}


def read_table(raw):
    """Decode the supplied single-sheet, cached-value XLSX files without Excel."""
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        workbook = ET.fromstring(z.read('xl/workbook.xml'))
        assert len(workbook.findall('s:sheets/s:sheet', NS)) == 1
        strings = [''.join(e.itertext()) for e in ET.fromstring(z.read('xl/sharedStrings.xml'))]
        root = ET.fromstring(z.read('xl/worksheets/sheet1.xml'))
        cells = {}
        for row in root.findall('s:sheetData/s:row', NS):
            for cell in row:
                assert cell.find('s:f', NS) is None, 'Formula needs explicit handling'
                value = cell.find('s:v', NS)
                if value is None:
                    continue
                letters, number = re.fullmatch(r'([A-Z]+)([0-9]+)', cell.attrib['r']).groups()
                column = 0
                for letter in letters:
                    column = column * 26 + ord(letter) - ord('A') + 1
                content = strings[int(value.text)] if cell.get('t') == 's' else float(value.text)
                cells[int(number)-1, column-1] = content
        height = max(r for r, _ in cells) + 1
        width = max(c for _, c in cells) + 1
        assert len(cells) == height * width, 'Unexpected blank table cells'
        return [[cells[r, c] for c in range(width)] for r in range(height)]


def nominal_recipe(label, order):
    assert all(ch.upper() in PAINTS for ch in label) and len(set(label.upper())) == len(label)
    weights = np.zeros(len(order))
    for ch in label:
        weights[order.index(ch.upper())] = 2 if ch.isupper() and any(x.islower() for x in label) else 1
    return weights / weights.sum()


def load():
    raw = SOURCE.read_bytes()
    assert hashlib.sha256(raw).hexdigest() == EXPECTED_SHA
    with zipfile.ZipFile(io.BytesIO(raw)) as z:
        files = {n: z.read('supplementary_material/' + n) for n in
                 ['mockups_concentration.xlsx', 'mockups_reflectance.xlsx', 'readme.txt']}
    concentrations = read_table(files['mockups_concentration.xlsx'])
    spectra = read_table(files['mockups_reflectance.xlsx'])
    labels = concentrations[0]
    assert spectra[0][0] == 'Wavelengths' and spectra[0][1:] == labels
    assert len(labels) == len(set(labels)) == 175
    amounts = np.array(concentrations[1:], dtype=float).T
    values = np.array(spectra[1:], dtype=float)
    nm, reflectance = values[:, 0], values[:, 1:].T
    order = [None] * 7
    for label in PAINTS:
        c = amounts[labels.index(label)]
        assert np.count_nonzero(c) == 1 and c.max() == 1
        index = int(np.argmax(c))
        assert order[index] is None
        order[index] = label
    assert all(order)
    nominal = np.array([nominal_recipe(label, order) for label in labels])
    assert np.isfinite(amounts).all() and (amounts >= 0).all()
    np.testing.assert_allclose(amounts.sum(1), 1, atol=1e-12, rtol=0)
    assert abs(amounts-nominal).max() <= .003334
    assert np.isfinite(reflectance).all() and (reflectance > 0).all() and (reflectance < 1).all()
    assert np.isfinite(nm).all() and (np.diff(nm) > 0).all()
    return labels, order, amounts, nominal, nm, reflectance, files


def main():
    labels, order, amounts, nominal, nm, reflectance, files = load()
    chosen = ['Y', 'C', 'B', 'W']
    keep = (amounts[:, [i for i, label in enumerate(order) if label not in chosen]] == 0).all(1)
    c = amounts[keep][:, [order.index(label) for label in chosen]]
    selected = [label for label, retained in zip(labels, keep) if retained]
    n = (c > 0).sum(1)
    anchors = (n == 1) | ((n == 2) & (c[:, 3] > 0))
    pairs = (n == 2) & (c[:, 3] == 0)
    # The paper removes ten bands at each edge. The supplied table has all 186.
    trimmed = nm[10:-10]
    grid = np.arange(440, 741, 10)
    assert grid.min() >= trimmed.min() and grid.max() <= trimmed.max()
    report = {'source_archive_sha256': EXPECTED_SHA,
              'files': {name: {'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)} for name, raw in files.items()},
              'samples': len(labels), 'native_bands': len(nm), 'native_range_nm': [float(nm.min()), float(nm.max())],
              'after_ten_edge_bands_each_side': {'bands': len(trimmed), 'range_nm': [float(trimmed.min()), float(trimmed.max())]},
              'reflectance_range': [float(reflectance.min()), float(reflectance.max())],
              'concentration_row_order': order, 'labels_align_between_tables': True,
              'max_stored_vs_nominal_mass_fraction_difference': float(abs(amounts-nominal).max()),
              'duplicate_normalized_recipes': int(len(amounts)-len(np.unique(amounts.round(12), axis=0))),
              'four_material_subset': {'order': chosen, 'paint_names_and_codes': {k: PAINTS[k] for k in chosen},
                                      'samples': int(keep.sum()), 'pure': int((n==1).sum()),
                                      'white_tint_anchors_including_pure': int(anchors.sum()),
                                      'chromatic_pairs': int(pairs.sum()), 'multicolor': int((n==3).sum()),
                                      'labels': selected},
              'possible_31_band_common_grid_nm': grid.tolist(),
              'qualification': 'A different pigment-mass-based palette and 45/0 imaging setup; not validation of Old Holland coefficients. No fits or model-error scoring performed.'}
    (HERE/'audit.json').write_bytes((json.dumps(report, indent=2)+'\n').encode())
    print(json.dumps(report, indent=2))


if __name__ == '__main__':
    main()

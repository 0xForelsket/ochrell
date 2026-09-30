"""Check actual Rust palette outputs against direct Python equations; render swatches.

Does not import the generator or generated optical arrays. Uses only standard
Python, the declarative synthetic definition, and the attributed CIE CSV.
Outputs default to ignored target/palette-reference, leaving frozen studies alone.
"""
import argparse
import csv
import hashlib
import json
import math
import os
from pathlib import Path
import platform
import subprocess

ROOT = Path(__file__).resolve().parents[1]


def reference_inputs():
    definition = json.loads((ROOT / "data/palettes/synthetic-four-v1.json").read_text())
    with (ROOT / "data/cie_380_780_1nm.csv").open(newline="") as stream:
        cie = {int(row["nm"]): row for row in csv.DictReader(stream)}
    optics, xyz = [], []
    for wavelength in range(380, 781, 5):
        band = []
        for paint in definition["paints"]:
            r = paint["floor"]
            for kind in ("rising", "falling"):
                for lower, upper, gain in paint[kind]:
                    x = max(0., min(1., (wavelength-lower)/(upper-lower)))
                    # Expanded polynomial, independent of the generator's expression.
                    h = 3*x*x - 2*x*x*x
                    r += gain * (h if kind == "rising" else 1-h)
            q = (1-r)*(1-r)/(2*r)
            s = paint["strength"] * math.sqrt(2*r/(1+r*r))
            band.append((q*s, s))
        optics.append(band)
        row = cie[wavelength]
        weight = .5 if wavelength in (380, 780) else 1.
        xyz.append([weight*float(row["D65"])*float(row[c]) for c in ("xbar", "ybar", "zbar")])
    norm = sum(x[1] for x in xyz)
    return definition, optics, [[x/norm for x in row] for row in xyz]


def xyz_to_rgb(x):
    # Project XYZ after integration rather than integrating RGB weights as Rust does.
    return [
        3.2409699419045226*x[0]-1.537383177570094*x[1]-.4986107602930034*x[2],
        -.9692436362808796*x[0]+1.8759675015077202*x[1]+.04155505740717559*x[2],
        .05563007969699366*x[0]-.20397695888897652*x[1]+1.0569715142428786*x[2],
    ]


def reference(recipe, optics, xyz):
    reflectance = []
    for band in optics:
        k = sum(w * ks[0] for w, ks in zip(recipe, band))
        s = sum(w * ks[1] for w, ks in zip(recipe, band))
        q = k/s
        # Direct subtractive KM form is safe for this bounded synthetic domain.
        reflectance.append(1+q-math.sqrt(q*q+2*q))
    raw = xyz_to_rgb([sum(r*row[c] for r, row in zip(reflectance, xyz)) for c in range(3)])
    neutral = xyz_to_rgb([sum(row[c] for row in xyz) for c in range(3)])
    raw = [v/w for v, w in zip(raw, neutral)]
    y = min(1., max(0., sum(v*w for v, w in zip(raw, (.2126,.7152,.0722)))))
    scale = 1.
    for v in raw:
        if v > y:
            scale = min(scale, (1-y)/(v-y))
        elif v < y:
            scale = min(scale, -y/(v-y))
    mapped = [min(1., max(0., y+scale*(v-y))) for v in raw]
    display = [12.92*v if v <= .0031308 else 1.055*v**(1/2.4)-.055 for v in mapped]
    return reflectance, raw, display


def swatches(rows, palette_id):
    # Colors come from the actual Rust output, not the Python reference.
    def color(row):
        return '#'+''.join(f'{int(v*255+.5):02x}' for v in row[-3:])
    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="960" height="690" viewBox="0 0 960 690">',
           '<rect width="960" height="690" fill="#faf9f6"/>',
           '<g font-family="sans-serif" fill="#222">',
           f'<text x="28" y="36" font-size="22">{palette_id}</text>',
           '<text x="28" y="62" font-size="14">Synthetic reference only; no measured-paint claim. Actual Rust display output.</text>']
    for i, name in enumerate(('Yellow', 'Red', 'Blue', 'White')):
        x = 28 + i*233
        out.append(f'<rect x="{x}" y="86" width="205" height="72" fill="{color(rows[i])}" stroke="#ccc"/>')
        out.append(f'<text x="{x}" y="180" font-size="15">{name} {color(rows[i])}</text>')
    labels = ('Yellow / red', 'Yellow / blue', 'Yellow / white', 'Red / blue', 'Red / white', 'Blue / white')
    for pair, label in enumerate(labels):
        y = 216 + pair*68
        out.append(f'<text x="28" y="{y+27}" font-size="14">{label}</text>')
        for j, row in enumerate(rows[4+65*pair:4+65*(pair+1)]):
            out.append(f'<rect x="{185+11*j}" y="{y}" width="11.2" height="44" fill="{color(row)}"/>')
    out.append('<text x="28" y="660" font-size="13">Reference ingredients and amounts are preserved; display gamut mapping does not alter recipes.</text>')
    out.append('</g></svg>')
    return '\n'.join(out)+'\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--out', type=Path, default=ROOT/'target/palette-reference')
    args = parser.parse_args()
    cargo = os.environ.get('CARGO', 'cargo')
    command = [cargo, 'run', '--release', '--offline', '--quiet', '--example', 'palette_probe']
    try:
        run = subprocess.run(command, cwd=ROOT, check=True, capture_output=True, text=True)
    except subprocess.CalledProcessError as error:
        raise SystemExit(error.stderr or str(error)) from error
    rows = [[float(v) for v in line.split(',')] for line in run.stdout.splitlines()]
    if len(rows) != 1418 or any(len(row) != 91 for row in rows):
        raise ValueError('Unexpected Rust probe corpus')
    definition, optics, xyz = reference_inputs()
    maxima = [0., 0., 0.]
    gamut_count = 0
    for row in rows:
        if not all(math.isfinite(v) for v in row):
            raise ValueError('Nonfinite Rust output')
        expected = reference(row[:4], optics, xyz)
        if not all(math.isfinite(v) for group in expected for v in group):
            raise ValueError('Nonfinite independent reference output')
        actual = (row[4:85], row[85:88], row[88:91])
        for i in range(3):
            maxima[i] = max(maxima[i], max(abs(a-b) for a, b in zip(expected[i], actual[i])))
        gamut_count += any(v < 0 or v > 1 for v in actual[1])
    limits = (2e-12, 2e-12, 2e-7)
    if any(error > limit for error, limit in zip(maxima, limits)):
        raise AssertionError(f'Independent reference mismatch: {maxima}')
    sources = ['src/palette.rs', 'src/palette_generated.rs', 'src/kubelka_munk.rs',
               'src/conversion.rs', 'src/color.rs', 'examples/palette_probe.rs',
               'tools/check_palette.py', 'tools/generate_palette.py',
               'data/palettes/synthetic-four-v1.json', 'data/cie_380_780_1nm.csv']
    summary = {
        'palette_id': definition['id'], 'samples': len(rows),
        'corpus': '4 pure paints, 6 pair ramps with 65 steps, 1024 seeded random recipes; seed 1907',
        'max_abs_error': dict(zip(('reflectance', 'linear_rgb', 'display_srgb'), maxima)),
        'limits': dict(zip(('reflectance', 'linear_rgb', 'display_srgb'), limits)),
        'out_of_gamut_raw_recipes': gamut_count,
        'interpretation': 'Implementation agreement with independent equations, not physical validation or speed measurement',
        'platform': platform.platform(), 'python': platform.python_version(),
        'rustc': subprocess.check_output(['rustc', '-Vv'], text=True).strip(),
        'source_sha256': {name: hashlib.sha256((ROOT/name).read_bytes()).hexdigest() for name in sources},
        'probe_csv_sha256': hashlib.sha256(run.stdout.encode()).hexdigest(),
    }
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out/'summary.json').write_bytes((json.dumps(summary, indent=2)+'\n').encode('utf-8'))
    (args.out/'swatches.svg').write_bytes(swatches(rows, definition['id']).encode('utf-8'))
    print(json.dumps({'output': str(args.out), 'samples': len(rows), 'max_abs_error': summary['max_abs_error'], 'out_of_gamut_raw_recipes': gamut_count}, indent=2))


if __name__ == '__main__':
    main()

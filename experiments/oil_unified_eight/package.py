"""Export frozen eight-paint fits and verify the Rust runtime's binary probes."""
import argparse
import json
import struct
from pathlib import Path
import numpy as np
import run as study
from generate_window_projection import projection


def export_package(model, corrected, provenance):
    kind='empirical' if corrected else 'km'
    out=bytearray(b'OPP3')
    out.extend(struct.pack('<6I',8,31,400,10,1,int(corrected)))
    for value in [f'ochrell-old-holland-eight-{kind}-v1',provenance,*study.NAMES]:
        raw=value.encode('utf-8'); out.extend(struct.pack('<I',len(raw)));out.extend(raw)
    for matrix in [np.array(model['base']['K']).T,np.array(model['base']['S']).T,projection()]:
        for row in matrix:
            for value in row: out.extend(struct.pack('<d',float(value)))
    controls=np.array(model['theta']).reshape(28,4) if corrected else np.empty((0,4))
    out.extend(struct.pack('<I',len(controls)))
    for value in controls.ravel(): out.extend(struct.pack('<d',float(value)))
    out.extend(bytes.fromhex(study.old.sha(out)))
    return bytes(out)


def main():
    parser=argparse.ArgumentParser();parser.add_argument('phase',choices=['export','verify'])
    parser.add_argument('--out',type=Path,default=study.DEFAULT);args=parser.parse_args()
    out=study.old.research_directory(args.out)
    c,r,train,manifest=study.inputs(); raw=(out/'frozen-model.json').read_bytes(); artifact=json.loads(raw)
    assert artifact['manifest']==manifest
    verified=json.loads((out/'verification.json').read_text(encoding='utf-8'))
    assert verified['bundle_sha256']==study.old.sha(raw)
    model=artifact['model']; weights=np.array(projection())
    recipes=np.vstack([c,np.random.default_rng(81019).dirichlet(np.ones(8),1024),np.eye(8)])
    if args.phase=='export':
        provenance=json.dumps({'source':'Asadi Shahmirzadi et al. 2020 Old Holland oil dataset',
            'source_sha256':study.old.HASHES['archive'],'fit_sha256':study.old.sha(raw),
            'calibration_samples':103,'assessment_samples':183,'amounts':'normalized tube-paint mass portions',
            'status':'Experimental fitted model; not independently validated; local research package',
            'display':'400-700 nm windowed D65 preview; no extrapolated spectral tails'},separators=(',',':'))
        info={}
        for name,corrected in [('km',False),('empirical',True)]:
            path=out/f'old-holland-eight-{name}.opp'; data=export_package(model,corrected,provenance);path.write_bytes(data)
            info[name]={'file':path.name,'bytes':len(data),'sha256':study.old.sha(data),'identity':data[-32:].hex()}
        (out/'recipes.f64').write_bytes(recipes.astype('<f8').tobytes())
        study.old.write_json(out/'packages.json',{'frozen_fit_sha256':study.old.sha(raw),'packages':info,'recipe_count':len(recipes),
            'recipes_sha256':study.old.sha((out/'recipes.f64').read_bytes())})
        print(json.dumps(info,indent=2));return
    packages=json.loads((out/'packages.json').read_text(encoding='utf-8'));assert packages['frozen_fit_sha256']==study.old.sha(raw)
    assert (out/'recipes.f64').read_bytes()==recipes.astype('<f8').tobytes()
    checks={}
    for name,corrected in [('km',False),('empirical',True)]:
        assert study.old.sha((out/packages['packages'][name]['file']).read_bytes())==packages['packages'][name]['sha256']
        actual=np.frombuffer((out/f'{name}-predictions.f64').read_bytes(),dtype='<f8').reshape(len(recipes),34)
        expected=study.predict(recipes,model,corrected)
        checks[name]={'spectral_max_abs':float(abs(actual[:,:31]-expected).max()),
            'linear_rgb_max_abs':float(abs(actual[:,31:]-expected@weights).max())}
        assert checks[name]['spectral_max_abs']<1e-12 and checks[name]['linear_rgb_max_abs']<1e-12
    files=[Path(__file__),study.ROOT/'tools/generate_window_projection.py',study.ROOT/'src/palette_window.rs',
        study.ROOT/'src/palette.rs',study.ROOT/'src/palette_package.rs',study.ROOT/'examples/measured_palette_probe.rs']
    result={'packages':packages,'checks':checks,'runtime_hashes':{p.relative_to(study.ROOT).as_posix():study.old.sha(p.read_bytes()) for p in files}}
    for dest in [out,study.HERE]:study.old.write_json(dest/'package-verification.json',result)
    print(json.dumps(checks,indent=2))


if __name__=='__main__':main()

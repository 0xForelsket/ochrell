//! Validate and benchmark the opt-in compact implementation against both cores.
use ochrell::{
    compact::CompactLatent, conversion::delta_e_ok100, Color, FastPigmentMixer, Latent,
    ReferenceLatent, ReferenceSpectralMixer,
};
use std::{
    fs::{self, File},
    hint::black_box as bb,
    io::{BufWriter, Write},
    path::Path,
    time::Instant,
};

fn corpus(dir: &Path) -> (Vec<Latent>, Vec<ReferenceLatent>) {
    let f = fs::read(dir.join("fast.f32")).unwrap();
    let f: Vec<f32> = f
        .chunks_exact(4)
        .map(|a| f32::from_le_bytes(a.try_into().unwrap()))
        .collect();
    let z = f
        .chunks_exact(85)
        .map(|a| {
            Latent::try_from_parts(
                a[..41].try_into().unwrap(),
                a[41..82].try_into().unwrap(),
                a[82..].try_into().unwrap(),
            )
            .unwrap()
        })
        .collect();
    let r = fs::read(dir.join("reference.f64")).unwrap();
    let r: Vec<f64> = r
        .chunks_exact(8)
        .map(|a| f64::from_le_bytes(a.try_into().unwrap()))
        .collect();
    let r = r
        .chunks_exact(165)
        .map(|a| {
            ReferenceLatent::try_from_parts(
                a[..81].try_into().unwrap(),
                a[81..162].try_into().unwrap(),
                a[162..].try_into().unwrap(),
            )
            .unwrap()
        })
        .collect();
    (z, r)
}
fn record(
    w: &mut impl Write,
    case: &str,
    id: usize,
    c: CompactLatent,
    full: Color,
    reference: Color,
) {
    let rgb = c.decode();
    let [fr, fg, fb] = full.channels();
    let [rr, rg, rb] = reference.channels();
    writeln!(
        w,
        "{case},{id},{:.12e},{:.12e},{:.9},{:.9},{:.9},{fr:.9},{fg:.9},{fb:.9},{rr:.9},{rg:.9},{rb:.9}",
        delta_e_ok100(rgb.linear(), full.linear()),
        delta_e_ok100(rgb.linear(), reference.linear()),
        rgb.channels()[0],
        rgb.channels()[1],
        rgb.channels()[2]
    )
    .unwrap();
}
fn quality(dir: &Path, out: &Path) {
    let (z, r) = corpus(dir);
    let n = z.len();
    let m = FastPigmentMixer;
    let rm = ReferenceSpectralMixer;
    let c: Vec<_> = z
        .iter()
        .map(|z| CompactLatent::try_from_full(*z).unwrap())
        .collect();
    let (white, black, rw, rb, cw, cb) = (
        z[n - 1],
        z[n - 256],
        r[n - 1],
        r[n - 256],
        c[n - 1],
        c[n - 256],
    );
    let mut w = BufWriter::new(File::create(out).unwrap());
    writeln!(
        w,
        "case,sample,delta_ok100_full,delta_ok100_reference,r,g,b,full_r,full_g,full_b,reference_r,reference_g,reference_b"
    )
    .unwrap();
    for i in 0..n {
        let j = (i * 73 + 19) % n;
        let k = (i * 101 + 11) % n;
        let t = (i % 997 + 1) as f32 / 999.;
        record(
            &mut w,
            "reconstruction",
            i,
            c[i],
            m.decode(z[i]),
            rm.decode(r[i]),
        );
        let pair = c[i].interpolate(c[j], t);
        let zp = z[i].interpolate(z[j], t);
        let rp = r[i].interpolate(r[j], t as f64);
        record(&mut w, "mixture", i, pair, m.decode(zp), rm.decode(rp));
        record(
            &mut w,
            "white",
            i,
            pair.interpolate(cw, 0.7),
            m.decode(zp.interpolate(white, 0.7)),
            rm.decode(rp.interpolate(rw, 0.7)),
        );
        record(
            &mut w,
            "black",
            i,
            pair.interpolate(cb, 0.1),
            m.decode(zp.interpolate(black, 0.1)),
            rm.decode(rp.interpolate(rb, 0.1)),
        );
        let direct = CompactLatent::weighted(&[(c[i], 2.), (c[j], 3.), (c[k], 5.)]).unwrap();
        let ab = CompactLatent::weighted(&[(c[i], 2.), (c[j], 3.)]).unwrap();
        let grouped = CompactLatent::weighted(&[(ab, 5.), (c[k], 5.)]).unwrap();
        let full = Latent::weighted(&[(z[i], 2.), (z[j], 3.), (z[k], 5.)]).unwrap();
        let rf = ReferenceLatent::weighted(&[(r[i], 2.), (r[j], 3.), (r[k], 5.)]).unwrap();
        record(
            &mut w,
            "weighted",
            i,
            grouped,
            m.decode(full),
            rm.decode(rf),
        );
        record(
            &mut w,
            "grouping_self",
            i,
            grouped,
            direct.decode(),
            rm.decode(rf),
        );
    }
    for (pair, (a, b)) in [(3, 4), (1, 4), (2, 1), (4, 7), (1, 7), (0, 7), (5, 6)]
        .into_iter()
        .enumerate()
    {
        let a = n - 264 + a;
        let b = n - 264 + b;
        for i in 0..=1000 {
            let t = i as f32 / 1000.;
            record(
                &mut w,
                "canonical_trajectories",
                pair * 1001 + i,
                c[a].interpolate(c[b], t),
                m.decode(z[a].interpolate(z[b], t)),
                rm.decode(r[a].interpolate(r[b], t as f64)),
            );
        }
    }
    let ids: Vec<_> = (0..128)
        .chain(n - 264..n - 256)
        .chain((n - 256..n).step_by(32))
        .collect();
    for i in ids {
        let j = (i * 73 + 19) % n;
        for (steps, t, label) in [(256, 0.03, "repeated256"), (4096, 0.0001, "tiny4096")] {
            let (mut a, mut b, mut f, mut rf) = (c[i], c[i], z[i], r[i]);
            for _ in 0..steps {
                a = a.interpolate(c[j], t);
                b = CompactLatent::try_from_full(b.interpolate(c[j], t).to_full()).unwrap();
                b = CompactLatent::try_from_le_bytes(b.to_le_bytes()).unwrap();
                f = f.interpolate(z[j], t);
                rf = rf.interpolate(r[j], t as f64);
            }
            record(&mut w, label, i, a, m.decode(f), rm.decode(rf));
            record(
                &mut w,
                &format!("{label}_repack"),
                i,
                b,
                m.decode(f),
                rm.decode(rf),
            );
            record(
                &mut w,
                &format!("{label}_then_white"),
                i,
                a.interpolate(cw, 0.5),
                m.decode(f.interpolate(white, 0.5)),
                rm.decode(rf.interpolate(rw, 0.5)),
            );
        }
        let mut a = c[i];
        for _ in 0..512 {
            a = CompactLatent::try_from_full(a.to_full()).unwrap();
        }
        record(&mut w, "reload512", i, a, m.decode(z[i]), rm.decode(r[i]));
    }
    w.flush().unwrap();
}
fn bench(dir: &Path, out: &Path, iterations: usize, repeats: usize) {
    let (z, _) = corpus(dir);
    let m = FastPigmentMixer;
    let colors: Vec<_> = fs::read(dir.join("colors.f32"))
        .unwrap()
        .chunks_exact(12)
        .map(|row| {
            let channel = |i: usize| f32::from_le_bytes(row[i * 4..i * 4 + 4].try_into().unwrap());
            Color::srgb(channel(0), channel(1), channel(2)).unwrap()
        })
        .collect();
    assert_eq!(colors.len(), z.len());
    assert_eq!(std::mem::size_of::<Latent>(), 340);
    assert_eq!(std::mem::size_of::<CompactLatent>(), 204);
    let c: Vec<_> = z
        .iter()
        .map(|z| CompactLatent::try_from_full(*z).unwrap())
        .collect();
    let stream_n = 262144;
    let mut full: Vec<_> = (0..stream_n).map(|i| z[i % z.len()]).collect();
    let mut small: Vec<_> = (0..stream_n).map(|i| c[i % c.len()]).collect();
    let ops = [
        "full_encode",
        "compact_encode",
        "full_mix",
        "compact_mix",
        "full_decode",
        "compact_decode",
        "full_mix_decode",
        "compact_mix_decode",
        "pack",
        "unpack",
        "full_stream_update",
        "compact_stream_update",
        "full_stream_read",
        "compact_stream_read",
    ];
    let mut w = BufWriter::new(File::create(out).unwrap());
    writeln!(w, "operation,repeat,iterations,ns_per_operation").unwrap();
    for rep in 0..=repeats {
        for offset in 0..ops.len() {
            let op = ops[(rep + offset) % ops.len()];
            let start = Instant::now();
            for i in 0..iterations {
                let j = i % z.len();
                let k = (i * 73 + 19) % z.len();
                match op {
                    "full_encode" => {
                        bb(m.encode(bb(colors[j])));
                    }
                    "compact_encode" => {
                        bb(CompactLatent::encode(bb(colors[j])));
                    }
                    "full_mix" => {
                        bb(bb(z[j]).interpolate(bb(z[k]), bb(0.37)));
                    }
                    "compact_mix" => {
                        bb(bb(c[j]).interpolate(bb(c[k]), bb(0.37)));
                    }
                    "full_decode" => {
                        bb(m.decode(bb(z[j])));
                    }
                    "compact_decode" => {
                        bb(bb(c[j]).decode());
                    }
                    "full_mix_decode" => {
                        bb(m.decode(bb(z[j]).interpolate(bb(z[k]), bb(0.37))));
                    }
                    "compact_mix_decode" => {
                        bb(bb(c[j]).interpolate(bb(c[k]), bb(0.37)).decode());
                    }
                    "pack" => {
                        bb(CompactLatent::try_from_full(bb(z[j])).unwrap());
                    }
                    "unpack" => {
                        bb(bb(c[j]).to_full());
                    }
                    "full_stream_update" => {
                        let k = i % stream_n;
                        full[k] = bb(full[k]).interpolate(bb(z[j]), bb(0.37));
                        bb(&full[k]);
                    }
                    "compact_stream_update" => {
                        let k = i % stream_n;
                        small[k] = bb(small[k]).interpolate(bb(c[j]), bb(0.37));
                        bb(&small[k]);
                    }
                    "full_stream_read" => {
                        bb(full[i % stream_n]);
                    }
                    _ => {
                        bb(small[i % stream_n]);
                    }
                }
            }
            if rep > 0 {
                writeln!(
                    w,
                    "{op},{},{iterations},{:.6}",
                    rep - 1,
                    start.elapsed().as_nanos() as f64 / iterations as f64
                )
                .unwrap();
            }
        }
    }
    w.flush().unwrap();
}
fn main() {
    let args: Vec<_> = std::env::args().collect();
    let mode = args
        .get(1)
        .expect("quality|bench CORPUS OUTPUT [ITERATIONS] [REPEATS]");
    if mode == "quality" {
        quality(Path::new(&args[2]), Path::new(&args[3]));
    } else if mode == "bench" {
        bench(
            Path::new(&args[2]),
            Path::new(&args[3]),
            args.get(4).map(|x| x.parse().unwrap()).unwrap_or(200000),
            args.get(5).map(|x| x.parse().unwrap()).unwrap_or(7),
        );
    } else {
        panic!("unknown operation");
    }
}

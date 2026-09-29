use ochrell::legacy::{FastPigmentMixer, PigmentMixer, ReferenceSpectralMixer};
use ochrell::{conversion::*, spectrum, *};
use std::{
    fs::{create_dir_all, File},
    hint::black_box,
    io::{BufWriter, Write},
    time::Instant,
};
struct Rng(u64);
impl Rng {
    fn next(&mut self) -> f32 {
        self.0 ^= self.0 << 13;
        self.0 ^= self.0 >> 7;
        self.0 ^= self.0 << 17;
        ((self.0 >> 40) as u32) as f32 / 16777216.
    }
    fn color(&mut self) -> Color {
        Color::srgb(self.next(), self.next(), self.next()).unwrap()
    }
}
fn row(w: &mut impl Write, s: &str, values: &[f64]) {
    write!(w, "{s}").unwrap();
    for x in values {
        write!(w, ",{x:.12e}").unwrap()
    }
    writeln!(w).unwrap()
}
fn append(v: &mut Vec<f64>, x: Color) {
    v.extend(x.channels().map(|v| v as f64))
}
fn baseline(a: Color, b: Color, t: f32, mode: usize) -> Color {
    if mode == 0 {
        return Color::srgb(
            a.channels()[0] * (1. - t) + b.channels()[0] * t,
            a.channels()[1] * (1. - t) + b.channels()[1] * t,
            a.channels()[2] * (1. - t) + b.channels()[2] * t,
        )
        .unwrap();
    }
    let a = a.linear();
    let b = b.linear();
    let t = t as f64;
    let lerp = |a: [f64; 3], b: [f64; 3]| std::array::from_fn(|i| a[i] * (1. - t) + b[i] * t);
    Color::from_linear_gamut_mapped(if mode == 1 {
        lerp(a, b)
    } else {
        oklab_to_linear(lerp(oklab(a), oklab(b)))
    })
}
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<_> = std::env::args().collect();
    let n: usize = args.get(1).map(|x| x.parse()).transpose()?.unwrap_or(10000);
    let np: usize = args.get(2).map(|x| x.parse()).transpose()?.unwrap_or(10000);
    let steps: usize = args.get(3).map(|x| x.parse()).transpose()?.unwrap_or(1001);
    let bn: usize = args
        .get(4)
        .map(|x| x.parse())
        .transpose()?
        .unwrap_or(100000);
    let repeats: usize = args.get(5).map(|x| x.parse()).transpose()?.unwrap_or(7);
    let seed: u64 = args
        .get(6)
        .map(|x| x.parse())
        .transpose()?
        .unwrap_or(20260929);
    let root = args.get(7).map(String::as_str).unwrap_or("results");
    for d in ["reconstruction", "mixing", "performance", "ablations"] {
        create_dir_all(format!("{root}/{d}"))?
    }
    let m = PigmentMixer::default();
    let reference = ReferenceSpectralMixer;
    let mut recon = BufWriter::new(File::create(format!("{root}/reconstruction/samples.csv"))?);
    writeln!(recon,"id,r,g,b,w0,w1,w2,w3,w4,w5,w6,w7,raw_r,raw_g,raw_b,ref_r,ref_g,ref_b,fast_r,fast_g,fast_b,fast_raw_r,fast_raw_g,fast_raw_b")?;
    let mut rng = Rng(seed);
    for id in 0..n {
        let c = rng.color();
        let z = reference.encode(c);
        let fast = m.encode(c);
        let mut v = Vec::new();
        append(&mut v, c);
        v.extend(z.concentrations());
        v.extend(spectrum::forward(&z.concentrations()));
        append(&mut v, reference.decode(z));
        append(&mut v, m.decode(fast));
        v.extend(spectrum::forward_fast(&fast.concentrations()).map(|x| x as f64));
        row(&mut recon, &id.to_string(), &v)
    }
    let luts: Vec<_> = [17, 33, 65]
        .iter()
        .map(|n| LutLoad::load(*n))
        .collect::<Result<_, _>>()?;
    let mut pairs = BufWriter::new(File::create(format!("{root}/mixing/random_pairs.csv"))?);
    writeln!(pairs,"id,ar,ag,ab,br,bg,bb,t,ref_r,ref_g,ref_b,n17_r,n17_g,n17_b,n33_r,n33_g,n33_b,n65_r,n65_g,n65_b,tri33_r,tri33_g,tri33_b,raw_r,raw_g,raw_b")?;
    for id in 0..np {
        let a = rng.color();
        let b = rng.color();
        let t = rng.next();
        let mut v = Vec::new();
        append(&mut v, a);
        append(&mut v, b);
        v.push(t as f64);
        append(&mut v, reference.mix(a, b, t));
        for l in &luts {
            append(&mut v, l.mix(a, b, t))
        }
        append(
            &mut v,
            luts[1].decode(
                luts[1]
                    .encode_trilinear(a)
                    .interpolate(luts[1].encode_trilinear(b), t),
            ),
        );
        v.extend(m.decode_linear(m.encode(a).interpolate(m.encode(b), t)));
        row(&mut pairs, &id.to_string(), &v)
    }
    let canonical = [
        ("yellow_blue", [255, 220, 0], [20, 70, 255]),
        ("red_blue", [230, 30, 40], [20, 70, 255]),
        ("red_yellow", [230, 30, 40], [255, 220, 0]),
        ("cyan_magenta", [0, 190, 210], [220, 0, 160]),
        ("magenta_yellow", [220, 0, 160], [255, 220, 0]),
        ("black_white", [0, 0, 0], [255, 255, 255]),
        ("red_green", [230, 30, 40], [30, 170, 55]),
        ("blue_orange", [20, 70, 255], [255, 130, 0]),
        ("yellow_purple", [255, 220, 0], [140, 30, 180]),
        ("blue_white", [20, 70, 255], [255, 255, 255]),
        ("red_white", [230, 30, 40], [255, 255, 255]),
        ("extreme_yellow_blue", [255, 255, 0], [0, 0, 255]),
    ];
    let mut gradients = BufWriter::new(File::create(format!("{root}/mixing/gradients.csv"))?);
    writeln!(
        gradients,
        "pair,mode,t,r,g,b,raw_r,raw_g,raw_b,w0,w1,w2,w3,w4,w5,w6,w7"
    )?;
    for (name, a, b) in canonical {
        let a = Color::srgb8(a[0], a[1], a[2]);
        let b = Color::srgb8(b[0], b[1], b[2]);
        let za = m.encode(a);
        let zb = m.encode(b);
        let ra = reference.encode(a);
        let rb = reference.encode(b);
        for mode in 0..6 {
            for i in 0..steps {
                let t = i as f32 / (steps - 1) as f32;
                let z = za.interpolate(zb, t);
                let raw = if mode == 3 {
                    m.decode_linear(z)
                } else if mode == 4 {
                    reference.decode_linear(ra.interpolate(rb, t as f64))
                } else if mode == 5 {
                    spectrum::forward_fast(&z.concentrations()).map(|x| x as f64)
                } else {
                    baseline(a, b, t, mode).linear()
                };
                let c = Color::from_linear_gamut_mapped(raw);
                let mut v = vec![t as f64];
                append(&mut v, c);
                v.extend(raw);
                v.extend(z.concentrations().map(|x| x as f64));
                row(&mut gradients, &format!("{name},{mode}"), &v)
            }
        }
    }
    // One seeded dataset, same varying pairs and t; encoder and decoded-only workloads separated.
    let workload: Vec<_> = (0..1024)
        .map(|_| (rng.color(), rng.color(), rng.next()))
        .collect();
    let encoded: Vec<_> = workload
        .iter()
        .map(|(a, b, t)| (m.encode(*a), m.encode(*b), *t))
        .collect();
    let refencoded: Vec<_> = workload
        .iter()
        .map(|(a, b, t)| (reference.encode(*a), reference.encode(*b), *t))
        .collect();
    let mut bench = BufWriter::new(File::create(format!("{root}/performance/raw.csv"))?);
    writeln!(bench, "mode,repeat,iterations,elapsed_ns,ns_per_operation")?;
    for mode in 0..9 {
        let iterations = if mode == 3 { bn.min(1000) } else { bn };
        for rep in 0..repeats {
            let now = Instant::now();
            for i in 0..iterations {
                let (a, b, t) = black_box(workload[i % workload.len()]);
                match mode {
                    0..=2 => {
                        black_box(baseline(a, b, t, mode));
                    }
                    3 => {
                        black_box(reference.mix(a, b, t));
                    }
                    4 => {
                        black_box(m.mix(a, b, t));
                    }
                    5 => {
                        let (a, b, t) = black_box(encoded[i % encoded.len()]);
                        black_box(m.decode(a.interpolate(b, t)));
                    }
                    6 => {
                        black_box(m.lut().lookup(a));
                    }
                    7 => {
                        let (a, b, t) = black_box(refencoded[i % refencoded.len()]);
                        black_box(reference.decode(a.interpolate(b, t as f64)));
                    }
                    _ => {
                        black_box(m.lut().lookup_trilinear(a));
                    }
                }
            }
            let ns = now.elapsed().as_nanos();
            writeln!(
                bench,
                "{mode},{rep},{iterations},{ns},{}",
                ns as f64 / iterations as f64
            )?;
        }
    }
    let bytes = m.lut().to_bytes();
    for rep in 0..repeats {
        let now = Instant::now();
        black_box(ochrell::lut::Lut::from_bytes(black_box(&bytes))?);
        let ns = now.elapsed().as_nanos();
        writeln!(bench, "9,{rep},1,{ns},{ns}")?;
    }
    println!(
        "Recorded {n} reconstructions, {np} random mixtures, {} trajectories.",
        canonical.len()
    );
    Ok(())
}
struct LutLoad;
impl LutLoad {
    fn load(n: usize) -> Result<FastPigmentMixer, Box<dyn std::error::Error>> {
        Ok(FastPigmentMixer::with_lut(
            ochrell::lut::Lut::from_bytes(&std::fs::read(format!("data/lut-{n}.bin"))?)?,
        ))
    }
}

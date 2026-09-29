//! Export this crate's own states for a compact-state authoring experiment.
//! Binary arrays are little-endian, not Rust struct layout; see manifest.json.
#[allow(dead_code)]
#[path = "../src/optical_generated.rs"]
mod generated;
use ochrell::{Color, FastPigmentMixer, ReferenceSpectralMixer};
use std::{
    fs::{self, File},
    io::{BufWriter, Write},
    path::Path,
};

fn rand(s: &mut u32) -> f32 {
    *s ^= *s << 13;
    *s ^= *s >> 17;
    *s ^= *s << 5;
    (*s >> 8) as f32 / 16777216.
}
fn main() {
    let args: Vec<_> = std::env::args().collect();
    let dir = Path::new(args.get(1).expect("OUTPUT_DIR [SEED] [COUNT]"));
    let seed: u32 = args.get(2).map(|s| s.parse().unwrap()).unwrap_or(20260930);
    let n: usize = args.get(3).map(|s| s.parse().unwrap()).unwrap_or(8192);
    fs::create_dir_all(dir).unwrap();
    let mut state = seed;
    let mut colors: Vec<Color> = (0..n)
        .map(|i| {
            let mut c = std::array::from_fn::<_, 3, _>(|_| rand(&mut state));
            match i % 4 {
                1 => c = c.map(|v| v.powi(4)),
                2 => c = c.map(|v| 1. - 0.02 * v),
                3 => c[(i / 4) % 3] = if i % 8 == 3 { 0. } else { 1. },
                _ => {}
            }
            Color::srgb(c[0], c[1], c[2]).unwrap()
        })
        .collect();
    for i in 0..8 {
        colors.push(
            Color::srgb((i & 1) as f32, ((i >> 1) & 1) as f32, ((i >> 2) & 1) as f32).unwrap(),
        );
    }
    for i in 0..=255 {
        colors.push(Color::srgb8(i, i, i));
    }
    let mut rgb = BufWriter::new(File::create(dir.join("colors.f32")).unwrap());
    let mut fast = BufWriter::new(File::create(dir.join("fast.f32")).unwrap());
    let mut reference = BufWriter::new(File::create(dir.join("reference.f64")).unwrap());
    for c in &colors {
        for v in c.channels() {
            rgb.write_all(&v.to_le_bytes()).unwrap();
        }
        let z = FastPigmentMixer.encode(*c);
        for v in z
            .absorption()
            .iter()
            .chain(z.scattering())
            .chain(z.residual().iter())
        {
            fast.write_all(&v.to_le_bytes()).unwrap();
        }
        let z = ReferenceSpectralMixer.encode(*c);
        for v in z
            .absorption()
            .iter()
            .chain(z.scattering())
            .chain(z.residual().iter())
        {
            reference.write_all(&v.to_le_bytes()).unwrap();
        }
    }
    rgb.flush().unwrap();
    fast.flush().unwrap();
    reference.flush().unwrap();
    let mut f = File::create(dir.join("fast_rgb.f32")).unwrap();
    for v in generated::FAST_RGB.iter().flatten() {
        f.write_all(&v.to_le_bytes()).unwrap();
    }
    let mut f = File::create(dir.join("reference_rgb.f64")).unwrap();
    for v in generated::REF_RGB.iter().flatten() {
        f.write_all(&v.to_le_bytes()).unwrap();
    }
    fs::write(dir.join("manifest.json"),format!(
        "{{\n  \"seed\": {seed},\n  \"random_samples\": {n},\n  \"samples\": {},\n  \"state_layout\": \"K, S, linear RGB residual\",\n  \"fast_components\": 85,\n  \"reference_components\": 165,\n  \"byte_order\": \"little endian\"\n}}\n",colors.len())).unwrap();
    println!(
        "{}: {} source colors and encoded states",
        dir.display(),
        colors.len()
    );
}

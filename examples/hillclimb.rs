//! Core-only optimization probe: deterministic quality records and CPU timings.
//! No renderer, comparator, third-party crate, or generated model changes.
use ochrell::{conversion::delta_e_ok100, Color, FastPigmentMixer, Latent, ReferenceSpectralMixer};
use std::{
    fs::File,
    hint::black_box as bb,
    io::{BufWriter, Write},
    time::Instant,
};

fn random(s: &mut u32) -> f32 {
    *s ^= *s << 13;
    *s ^= *s >> 17;
    *s ^= *s << 5;
    (*s >> 8) as f32 / 16777216.
}
fn colors(seed: u32, n: usize) -> Vec<Color> {
    let mut s = seed;
    (0..n)
        .map(|_| Color::srgb(random(&mut s), random(&mut s), random(&mut s)).unwrap())
        .collect()
}
fn fingerprint(z: Latent) -> u64 {
    z.absorption()
        .iter()
        .chain(z.scattering())
        .chain(z.residual().iter())
        .fold(0xcbf29ce484222325_u64, |h, v| {
            (h ^ v.to_bits() as u64).wrapping_mul(0x100000001b3)
        })
}
fn record(w: &mut impl Write, kind: &str, i: usize, z: Latent, reference: Color) {
    let rgb = FastPigmentMixer.decode(z);
    let [r, g, b] = rgb.channels().map(f32::to_bits);
    writeln!(
        w,
        "{kind},{i},{r:08x},{g:08x},{b:08x},{:016x},{:.12e}",
        fingerprint(z),
        delta_e_ok100(rgb.linear(), reference.linear())
    )
    .unwrap();
}
fn quality(path: &str, seed: u32) {
    let m = FastPigmentMixer;
    let rm = ReferenceSpectralMixer;
    let mut w = BufWriter::new(File::create(path).unwrap());
    writeln!(
        w,
        "case,sample,r_bits,g_bits,b_bits,state_hash,delta_e_ok100_reference"
    )
    .unwrap();
    let mut c = colors(seed, 4096);
    c.extend((0..4096u32).map(|i| {
        Color::srgb8(
            (i % 16 * 17) as u8,
            (i / 16 % 16 * 17) as u8,
            (i / 256 * 17) as u8,
        )
    }));
    let white = Color::srgb8(255, 255, 255);
    let black = Color::srgb8(0, 0, 0);
    for (i, a) in c.iter().enumerate() {
        let b = c[(i * 73 + 19) % c.len()];
        let d = c[(i * 101 + 11) % c.len()];
        let t = (i % 997 + 1) as f32 / 999.;
        let (za, zb, zd) = (m.encode(*a), m.encode(b), m.encode(d));
        let (ra, rb, rd) = (rm.encode(*a), rm.encode(b), rm.encode(d));
        record(&mut w, "reconstruction", i, za, *a);
        let z = za.interpolate(zb, t);
        let r = ra.interpolate(rb, t as f64);
        record(&mut w, "mixture", i, z, rm.decode(r));
        record(
            &mut w,
            "white",
            i,
            z.interpolate(m.encode(white), 0.7),
            rm.decode(r.interpolate(rm.encode(white), 0.7)),
        );
        record(
            &mut w,
            "black",
            i,
            z.interpolate(m.encode(black), 0.1),
            rm.decode(r.interpolate(rm.encode(black), 0.1)),
        );
        let all = Latent::weighted(&[(za, 2.), (zb, 3.), (zd, 5.)]).unwrap();
        let reference = rm.mix_weighted(&[(*a, 2.), (b, 3.), (d, 5.)]).unwrap();
        record(&mut w, "weighted", i, all, reference);
        let ab = Latent::weighted(&[(za, 2.), (zb, 3.)]).unwrap();
        record(
            &mut w,
            "grouped",
            i,
            Latent::weighted(&[(ab, 5.), (zd, 5.)]).unwrap(),
            reference,
        );
        // Exercise the full RGB API too, including its endpoint shortcuts.
        let full = m.mix(*a, b, t);
        record(&mut w, "full_rgb", i, m.encode(full), rm.mix(*a, b, t));
        let _ = rd;
        if i < 128 {
            let mut repeated = za;
            let mut rr = ra;
            for step in 0..256 {
                let add = if step % 3 == 0 { zd } else { zb };
                let ar = if step % 3 == 0 { rm.encode(d) } else { rb };
                repeated = repeated.interpolate(add, 0.03);
                rr = rr.interpolate(ar, 0.03);
            }
            record(&mut w, "repeated256", i, repeated, rm.decode(rr));
            let mut tiny = za;
            let mut tr = ra;
            for _ in 0..4096 {
                tiny = tiny.interpolate(zb, 0.0001);
                tr = tr.interpolate(rb, 0.0001);
            }
            record(&mut w, "tiny4096", i, tiny, rm.decode(tr));
        }
    }
    // try_from_parts admits arbitrary finite positive coefficients, including
    // scales far outside the model's own encodes. Preserve this existing domain.
    for (i, (k, s)) in [
        (1., 1.),
        (1e-30, 1e-30),
        (1e30, 1e30),
        (0., f32::MIN_POSITIVE),
        (1., f32::MAX),
        (f32::MAX, f32::MAX),
        (f32::MIN_POSITIVE, 1.),
        (1., f32::MIN_POSITIVE),
    ]
    .into_iter()
    .enumerate()
    {
        let z = Latent::try_from_parts([k; 41], [s; 41], [0.; 3]).unwrap();
        let r = ochrell::ReferenceLatent::try_from_parts([k as f64; 81], [s as f64; 81], [0.; 3])
            .unwrap();
        record(&mut w, "imported_extreme", i, z, rm.decode(r));
    }
    for (i, (a, b)) in [
        (Color::srgb8(255, 220, 0), Color::srgb8(20, 70, 255)),
        (Color::srgb8(230, 30, 40), white),
        (black, white),
    ]
    .into_iter()
    .enumerate()
    {
        record(
            &mut w,
            "canonical",
            i,
            m.encode(a).interpolate(m.encode(b), 0.5),
            rm.mix(a, b, 0.5),
        );
    }
}

fn bench(path: &str, seed: u32, iterations: usize, repeats: usize) {
    let m = FastPigmentMixer;
    let c = colors(seed, 4096);
    let z: Vec<_> = c.iter().map(|c| m.encode(*c)).collect();
    let mut stream: Vec<_> = (0..262144).map(|i| z[i % z.len()]).collect();
    let ops = [
        "encode",
        "interpolate",
        "decode_linear",
        "decode",
        "cached_mix_decode",
        "full_rgb",
        "update_stream",
    ];
    let mut w = BufWriter::new(File::create(path).unwrap());
    writeln!(w, "operation,repeat,iterations,ns_per_operation").unwrap();
    // Rotate operation order each round; round zero is discarded warmup.
    for rep in 0..=repeats {
        for offset in 0..ops.len() {
            let op = ops[(offset + rep) % ops.len()];
            let start = Instant::now();
            for i in 0..iterations {
                let j = i % z.len();
                let k = (i * 73 + 19) % z.len();
                match op {
                    "encode" => {
                        bb(m.encode(bb(c[j])));
                    }
                    "interpolate" => {
                        bb(bb(z[j]).interpolate(bb(z[k]), bb(0.37)));
                    }
                    "decode_linear" => {
                        bb(m.decode_linear(bb(z[j])));
                    }
                    "decode" => {
                        bb(m.decode(bb(z[j])));
                    }
                    "cached_mix_decode" => {
                        bb(m.decode(bb(z[j]).interpolate(bb(z[k]), bb(0.37))));
                    }
                    "full_rgb" => {
                        bb(m.mix(bb(c[j]), bb(c[k]), bb(0.37)));
                    }
                    _ => {
                        let idx = i % stream.len();
                        stream[idx] = bb(stream[idx]).interpolate(bb(z[k]), bb(0.37));
                        bb(m.decode(bb(stream[idx])));
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
}
fn main() {
    let args: Vec<_> = std::env::args().collect();
    let seed = args.get(3).map(|v| v.parse().unwrap()).unwrap_or(20260930);
    match args.get(1).map(String::as_str) {
        Some("quality") => quality(&args[2], seed),
        Some("bench") => bench(
            &args[2],
            seed,
            args.get(4).map(|v| v.parse().unwrap()).unwrap_or(200000),
            args.get(5).map(|v| v.parse().unwrap()).unwrap_or(7),
        ),
        _ => panic!("usage: hillclimb quality|bench OUTPUT [SEED] [ITERATIONS] [REPEATS]"),
    }
}

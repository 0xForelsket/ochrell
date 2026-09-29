use ochrell::{conversion::*, *};
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
fn open(name: &str, header: &str) -> BufWriter<File> {
    let mut w = BufWriter::new(File::create(format!("results/revision/{name}.csv")).unwrap());
    writeln!(w, "{header}").unwrap();
    w
}
fn row(w: &mut impl Write, key: &str, v: &[f64]) {
    write!(w, "{key}").unwrap();
    for x in v {
        write!(w, ",{x:.12e}").unwrap()
    }
    writeln!(w).unwrap()
}
fn append(v: &mut Vec<f64>, c: Color) {
    v.extend(c.channels().map(|v| v as f64))
}
fn base(a: Color, b: Color, t: f32, mode: usize) -> Color {
    let t = t as f64;
    let lerp = |a: [f64; 3], b: [f64; 3]| std::array::from_fn(|i| a[i] * (1. - t) + b[i] * t);
    if mode == 0 {
        let x = lerp(
            a.channels().map(|v| v as f64),
            b.channels().map(|v| v as f64),
        );
        return Color::srgb(x[0] as f32, x[1] as f32, x[2] as f32).unwrap();
    }
    Color::from_linear_gamut_mapped(if mode == 1 {
        lerp(a.linear(), b.linear())
    } else {
        oklab_to_linear(lerp(oklab(a.linear()), oklab(b.linear())))
    })
}
fn main() {
    let args: Vec<_> = std::env::args().collect();
    let arg = |i: usize, d: usize| args.get(i).map(|x| x.parse().unwrap()).unwrap_or(d);
    let n = arg(1, 10000);
    let np = arg(2, 10000);
    let steps = arg(3, 1001);
    let nt = arg(4, 200);
    let bn = arg(5, 100000);
    let reps = arg(6, 7);
    let seed = arg(7, 20260930);
    create_dir_all("results/revision").unwrap();
    let m = PigmentMixer::default();
    let r = ReferenceSpectralMixer;
    let old = legacy::PigmentMixer::default();
    let mut rng = Rng(seed as u64);
    let mut rec=open("reconstruction","id,r,g,b,new_r,new_g,new_b,ref_r,ref_g,ref_b,new_raw_r,new_raw_g,new_raw_b,old_raw_r,old_raw_g,old_raw_b");
    for i in 0..n {
        let c = rng.color();
        let z = m.encode(c);
        let z0 = old.encode(c);
        let mut v = vec![];
        append(&mut v, c);
        append(&mut v, m.decode(z));
        append(&mut v, r.decode(r.encode(c)));
        v.extend(m.decode_linear(z.without_residual()));
        v.extend(spectrum::forward_fast(&z0.concentrations()).map(|v| v as f64));
        row(&mut rec, &i.to_string(), &v)
    }
    let mut grid = open(
        "reconstruction_grid",
        "id,r,g,b,new_r,new_g,new_b,ref_r,ref_g,ref_b",
    );
    for i in 0..4096u32 {
        let c = Color::srgb8(
            ((i % 16) * 17) as u8,
            ((i / 16 % 16) * 17) as u8,
            ((i / 256) * 17) as u8,
        );
        let mut v = vec![];
        append(&mut v, c);
        append(&mut v, m.decode(m.encode(c)));
        append(&mut v, r.decode(r.encode(c)));
        row(&mut grid, &i.to_string(), &v);
    }
    grid.flush().unwrap();
    grid.get_ref().sync_all().unwrap();
    let mut mix=open("mixtures","id,ar,ag,ab,br,bg,bb,t,new_r,new_g,new_b,ref_r,ref_g,ref_b,old_r,old_g,old_b,raw_r,raw_g,raw_b,precision_error");
    for i in 0..np {
        let a = rng.color();
        let b = rng.color();
        let t = rng.next();
        let z = m.encode(a).interpolate(m.encode(b), t);
        let raw = m.decode_linear(z);
        let pr = optical::decode_fast_f64(z);
        let err = raw
            .iter()
            .zip(pr)
            .map(|(a, b)| (*a - b).abs())
            .fold(0., f64::max);
        let mut v = vec![];
        append(&mut v, a);
        append(&mut v, b);
        v.push(t as f64);
        append(&mut v, m.decode(z));
        append(&mut v, r.mix(a, b, t));
        append(&mut v, old.mix(a, b, t));
        v.extend(raw);
        v.push(err);
        row(&mut mix, &i.to_string(), &v)
    }
    let pairs = [
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
        ("official_default", [0, 33, 133], [252, 210, 0]),
    ];
    let mut can=open("canonical","pair,t,srgb_r,srgb_g,srgb_b,linear_r,linear_g,linear_b,oklab_r,oklab_g,oklab_b,old_r,old_g,old_b,new_r,new_g,new_b,ref_r,ref_g,ref_b,nores_r,nores_g,nores_b");
    for (name, a, b) in pairs {
        let a = Color::srgb8(a[0], a[1], a[2]);
        let b = Color::srgb8(b[0], b[1], b[2]);
        for j in 0..steps {
            let t = j as f32 / (steps - 1) as f32;
            let mut v = vec![t as f64];
            for mode in 0..3 {
                append(&mut v, base(a, b, t, mode))
            }
            append(&mut v, old.mix(a, b, t));
            append(&mut v, m.mix(a, b, t));
            append(&mut v, r.mix(a, b, t));
            append(
                &mut v,
                m.decode(m.encode(a).interpolate(m.encode(b), t).without_residual()),
            );
            row(&mut can, name, &v)
        }
    }
    let mut sm = open(
        "smoothness",
        "id,ar,ag,ab,br,bg,bb,new_max_step,old_max_step,new_second,old_second,new_endpoint_step",
    );
    for i in 0..nt {
        let a = rng.color();
        let b = rng.color();
        let mut v = vec![];
        append(&mut v, a);
        append(&mut v, b);
        let mut max = [0_f64; 2];
        let mut second = [0_f64; 2];
        let mut prev = [oklab(a.linear()); 2];
        let mut delta = [[0.; 3]; 2];
        let mut end = 0_f64;
        for j in 1..steps {
            let t = j as f32 / (steps - 1) as f32;
            for mode in 0..2 {
                let c = if mode == 0 {
                    m.mix(a, b, t)
                } else {
                    old.mix(a, b, t)
                };
                let x = oklab(c.linear());
                let d: [f64; 3] = std::array::from_fn(|ch| x[ch] - prev[mode][ch]);
                let norm = |d: [f64; 3]| 100. * d.iter().map(|v| v * v).sum::<f64>().sqrt();
                max[mode] = max[mode].max(norm(d));
                if j > 1 {
                    second[mode] =
                        second[mode].max(norm(std::array::from_fn(|ch| d[ch] - delta[mode][ch])))
                }
                if mode == 0 && (j == 1 || j == steps - 1) {
                    end = end.max(norm(d))
                }
                prev[mode] = x;
                delta[mode] = d;
            }
        }
        v.extend(max);
        v.extend(second);
        v.push(end);
        row(&mut sm, &i.to_string(), &v)
    }
    let mut pert = open("perturbations", "id,new_delta,old_delta");
    for i in 0..5000 {
        let a = rng.color();
        let b = rng.color();
        let mut x = a.channels();
        x[i % 3] = (x[i % 3] + 1e-5).min(1.);
        let c = Color::srgb(x[0], x[1], x[2]).unwrap();
        row(
            &mut pert,
            &i.to_string(),
            &[
                delta_e_ok100(m.mix(a, b, 0.5).linear(), m.mix(c, b, 0.5).linear()),
                delta_e_ok100(old.mix(a, b, 0.5).linear(), old.mix(c, b, 0.5).linear()),
            ],
        )
    }
    let mut tint = open(
        "tints",
        "id,r,g,b,new_r,new_g,new_b,old_r,old_g,old_b,new_min_dy,old_min_dy,new_max_step",
    );
    let white = Color::srgb8(255, 255, 255);
    for i in 0..1024 {
        let a = if i == 0 {
            Color::srgb8(0, 0, 0)
        } else {
            rng.color()
        };
        let mut v = vec![];
        append(&mut v, a);
        append(&mut v, m.mix(a, white, 0.5));
        append(&mut v, old.mix(a, white, 0.5));
        let y = |c: Color| {
            c.linear()
                .iter()
                .zip([0.2126, 0.7152, 0.0722])
                .map(|(v, w)| v * w)
                .sum::<f64>()
        };
        let mut prev = [a; 2];
        let mut dy = [1_f64; 2];
        let mut step = 0_f64;
        for j in 1..steps {
            let t = j as f32 / (steps - 1) as f32;
            let colors = [m.mix(a, white, t), old.mix(a, white, t)];
            for mode in 0..2 {
                dy[mode] = dy[mode].min(y(colors[mode]) - y(prev[mode]));
                if mode == 0 {
                    step = step.max(delta_e_ok100(prev[mode].linear(), colors[mode].linear()))
                }
                prev[mode] = colors[mode]
            }
        }
        v.extend(dy);
        v.push(step);
        row(&mut tint, &i.to_string(), &v)
    }
    let colors: Vec<_> = (0..256).map(|_| rng.color()).collect();
    let states: Vec<_> = colors.iter().map(|c| m.encode(*c)).collect();
    let oldstates: Vec<_> = colors.iter().map(|c| old.encode(*c)).collect();
    let mut perf = open("performance", "method,repeat,iterations,ns_per_mix");
    for mode in 0..8 {
        let name = [
            "sRGB",
            "linear RGB",
            "OKLab",
            "v0.1 RGB",
            "v0.2 RGB",
            "v0.2 cached",
            "v0.2 reference",
            "v0.1 cached",
        ][mode];
        for rep in 0..reps {
            let start = Instant::now();
            for i in 0..bn {
                let ai = i % 256;
                let bi = (i * 73 + 31) % 256;
                let a = black_box(colors[ai]);
                let b = black_box(colors[bi]);
                let t = black_box((i % 997) as f32 / 997.);
                match mode {
                    0..=2 => {
                        black_box(base(a, b, t, mode));
                    }
                    3 => {
                        black_box(old.mix(a, b, t));
                    }
                    4 => {
                        black_box(m.mix(a, b, t));
                    }
                    5 => {
                        black_box(
                            m.decode(black_box(states[ai]).interpolate(black_box(states[bi]), t)),
                        );
                    }
                    6 => {
                        black_box(r.mix(a, b, t));
                    }
                    _ => {
                        black_box(old.decode(
                            black_box(oldstates[ai]).interpolate(black_box(oldstates[bi]), t),
                        ));
                    }
                }
            }
            row(
                &mut perf,
                name,
                &[
                    rep as f64,
                    bn as f64,
                    start.elapsed().as_nanos() as f64 / bn as f64,
                ],
            )
        }
    }
    let mut memory = open("memory", "model,latent_bytes,mixer_bytes");
    row(
        &mut memory,
        "v0.1",
        &[
            std::mem::size_of::<legacy::Latent>() as f64,
            std::mem::size_of::<legacy::PigmentMixer>() as f64,
        ],
    );
    row(
        &mut memory,
        "v0.2",
        &[
            std::mem::size_of::<Latent>() as f64,
            std::mem::size_of::<PigmentMixer>() as f64,
        ],
    );
    for writer in [
        &mut rec,
        &mut mix,
        &mut can,
        &mut sm,
        &mut pert,
        &mut tint,
        &mut perf,
        &mut memory,
    ] {
        writer.flush().unwrap();
        writer.get_ref().sync_all().unwrap();
    }
}

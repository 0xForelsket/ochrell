//! Reproducible quality and alternating native timing probe for forward LUTs.
use ochrell::{
    conversion::delta_e_ok100,
    palette::{synthetic_four, Recipe},
    palette_lut::{LutMapping, PaletteLut},
};
use std::{hint::black_box, time::Instant};

struct Rng(u64);
impl Rng {
    fn unit(&mut self) -> f64 {
        self.0 ^= self.0 << 13;
        self.0 ^= self.0 >> 7;
        self.0 ^= self.0 << 17;
        (self.0 >> 11) as f64 / (1_u64 << 53) as f64
    }
    fn amounts(&mut self) -> [f64; 4] {
        std::array::from_fn(|_| self.unit())
    }
}

fn quality(resolution: usize, seed: u64, mapping: LutMapping) {
    let p = synthetic_four();
    let lut = PaletteLut::build_with_mapping(p, resolution, mapping).unwrap();
    let mut index = 0;
    println!("family,index,de_ok100,raw_error,luminance_drop");
    let mut emit = |family: &str, recipe: Recipe<'_>, previous: Option<f64>| {
        let before = recipe.to_le_bytes();
        let raw = lut.decode_linear(&recipe).unwrap();
        let expected = recipe.decode_linear();
        let de = delta_e_ok100(
            lut.decode(&recipe).unwrap().linear(),
            recipe.decode().linear(),
        );
        let error = raw
            .into_iter()
            .zip(expected)
            .map(|(a, b)| (a - b).abs())
            .fold(0., f64::max);
        let luminance = raw[0] * 0.2126 + raw[1] * 0.7152 + raw[2] * 0.0722;
        let drop = previous.map(|v| (v - luminance).max(0.)).unwrap_or(0.);
        assert_eq!(before, recipe.to_le_bytes());
        println!("{family},{index},{de:.17e},{error:.17e},{drop:.17e}");
        index += 1;
        luminance
    };
    let paints = ["yellow", "red", "blue", "white"].map(|n| p.paint(n).unwrap());
    for paint in paints {
        emit("pure", paint, None);
    }
    for a in 0..4 {
        for b in a + 1..4 {
            for step in 0..=512 {
                emit(
                    "pairs",
                    paints[a]
                        .interpolate(paints[b], step as f64 / 512.)
                        .unwrap(),
                    None,
                );
            }
        }
    }
    let mut rng = Rng(seed);
    for _ in 0..4096 {
        emit("interior", p.recipe(rng.amounts()).unwrap(), None);
    }
    for face in 0..4 {
        for _ in 0..1024 {
            let mut amounts = rng.amounts();
            amounts[face] = 0.;
            emit("faces", p.recipe(amounts).unwrap(), None);
        }
    }
    for i in 0..2048 {
        let mut amounts = [0.; 4];
        amounts[i % 4] = 1.;
        amounts[(i + 1) % 4] = 10_f64.powf(-1. - 10. * rng.unit());
        amounts[(i + 2) % 4] = 10_f64.powf(-1. - 10. * rng.unit());
        emit("edge_bias", p.recipe(amounts).unwrap(), None);
    }
    for _ in 0..16 {
        let base = p.recipe(rng.amounts()).unwrap();
        let mut previous = None;
        for step in 0..=256 {
            previous = Some(emit(
                "white_tints",
                base.interpolate(paints[3], step as f64 / 256.).unwrap(),
                previous,
            ));
        }
    }
    for _ in 0..16 {
        let mut recipe = p.recipe(rng.amounts()).unwrap();
        for step in 0..256 {
            recipe = recipe.interpolate(paints[step % 4], 0.03).unwrap();
            emit("chains", recipe, None);
        }
    }
    for start in 0..4 {
        let mut recipe = paints[start];
        for _ in 0..4096 {
            recipe = recipe.interpolate(paints[(start + 1) % 4], 0.0001).unwrap();
            recipe = p.recipe_from_bytes(&recipe.to_le_bytes()).unwrap();
            emit("tiny_updates", recipe, None);
        }
    }
}

fn measure(iterations: usize, mut f: impl FnMut(usize)) -> f64 {
    let start = Instant::now();
    for i in 0..iterations {
        f(i);
    }
    start.elapsed().as_secs_f64() * 1e9 / iterations as f64
}

fn bench(resolution: usize, iterations: usize, repeats: usize, mapping: LutMapping) {
    let p = synthetic_four();
    let start = Instant::now();
    let lut = PaletteLut::build_with_mapping(p, resolution, mapping).unwrap();
    let build_ns = start.elapsed().as_secs_f64() * 1e9;
    let bytes = lut.to_bytes();
    let start = Instant::now();
    let loaded = PaletteLut::from_bytes(p, &bytes).unwrap();
    let load_ns = start.elapsed().as_secs_f64() * 1e9;
    assert_eq!(bytes, loaded.to_bytes());
    println!("operation,repeat,ns");
    println!("build,0,{build_ns}");
    println!("load,0,{load_ns}");
    println!("payload_bytes,0,{}", lut.payload_bytes());
    for repeat in 1..repeats {
        let start = Instant::now();
        let built = black_box(PaletteLut::build_with_mapping(p, resolution, mapping).unwrap());
        let build_ns = start.elapsed().as_secs_f64() * 1e9;
        let start = Instant::now();
        let loaded = black_box(PaletteLut::from_bytes(p, &bytes).unwrap());
        let load_ns = start.elapsed().as_secs_f64() * 1e9;
        println!("build,{repeat},{build_ns}");
        println!("load,{repeat},{load_ns}");
        drop(built);
        drop(loaded);
    }
    let mut rng = Rng(1907);
    let recipes: Vec<_> = (0..4096)
        .map(|_| p.recipe(rng.amounts()).unwrap())
        .collect();
    for round in 0..=repeats {
        let count = if round == 0 {
            iterations.min(100_000)
        } else {
            iterations
        };
        for offset in 0..6 {
            let op = (offset + round) % 6;
            let (name, ns) = match op {
                0 => (
                    "reference_linear",
                    measure(count, |i| {
                        black_box(black_box(&recipes[i & 4095]).decode_linear());
                    }),
                ),
                1 => (
                    "lut_linear",
                    measure(count, |i| {
                        black_box(lut.decode_linear(black_box(&recipes[i & 4095])).unwrap());
                    }),
                ),
                2 => (
                    "reference_display",
                    measure(count, |i| {
                        black_box(black_box(&recipes[i & 4095]).decode());
                    }),
                ),
                3 => (
                    "lut_display",
                    measure(count, |i| {
                        black_box(lut.decode(black_box(&recipes[i & 4095])).unwrap());
                    }),
                ),
                4 => (
                    "reference_mix_display",
                    measure(count, |i| {
                        let a = black_box(recipes[i & 4095]);
                        let b = black_box(recipes[(i + 997) & 4095]);
                        black_box(a.interpolate(b, (i % 997) as f64 / 996.).unwrap().decode());
                    }),
                ),
                _ => (
                    "lut_mix_display",
                    measure(count, |i| {
                        let a = black_box(recipes[i & 4095]);
                        let b = black_box(recipes[(i + 997) & 4095]);
                        black_box(
                            lut.decode(&a.interpolate(b, (i % 997) as f64 / 996.).unwrap())
                                .unwrap(),
                        );
                    }),
                ),
            };
            if round > 0 {
                println!("{name},{},{ns:.6}", round - 1);
            }
        }
    }
}

fn main() {
    let args: Vec<_> = std::env::args().collect();
    match args.get(1).map(String::as_str) {
        Some("quality") => quality(
            args[2].parse().unwrap(),
            args[3].parse().unwrap(),
            mapping(args.get(4)),
        ),
        Some("bench") => bench(
            args[2].parse().unwrap(),
            args[3].parse().unwrap(),
            args[4].parse().unwrap(),
            mapping(args.get(5)),
        ),
        _ => panic!("usage: palette_lut_eval quality RES SEED | bench RES ITERATIONS REPEATS"),
    }
}

fn mapping(value: Option<&String>) -> LutMapping {
    match value.map(String::as_str) {
        None | Some("uniform") => LutMapping::Uniform,
        Some("edge") => LutMapping::EdgeFocused,
        Some("recipe-sqrt") => LutMapping::RecipeSqrt,
        _ => panic!("mapping must be uniform, edge or recipe-sqrt"),
    }
}

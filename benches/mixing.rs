//! Standalone benchmark; full paper workloads are in `experiments`.
use ochrell::*;
use std::{hint::black_box, time::Instant};
fn main() {
    let m = PigmentMixer::default();
    let r = ReferenceSpectralMixer;
    let colors: Vec<_> = (0u16..256)
        .map(|j| {
            let i = j as u8;
            Color::srgb8(i, 255 - i, i.wrapping_mul(37))
        })
        .collect();
    println!("method,repeat,iterations,ns_per_mix");
    for mode in 0..4 {
        for rep in 0..7 {
            let n = if mode == 3 { 1000 } else { 100000 };
            let start = Instant::now();
            for i in 0..n {
                let a = black_box(colors[i % 256]);
                let b = black_box(colors[(i * 73 + 31) % 256]);
                let t = black_box((i % 101) as f32 / 100.);
                match mode {
                    0 => {
                        black_box(std::array::from_fn::<_, 3, _>(|ch| {
                            a.channels()[ch] * (1. - t) + t * b.channels()[ch]
                        }));
                    }
                    1 => {
                        black_box(m.mix(a, b, t));
                    }
                    2 => {
                        black_box(m.encode(a));
                    }
                    _ => {
                        black_box(r.mix(a, b, t));
                    }
                }
            }
            println!(
                "{mode},{rep},{n},{}",
                start.elapsed().as_nanos() as f64 / n as f64
            )
        }
    }
}

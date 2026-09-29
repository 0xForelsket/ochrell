//! Isolated CPU timings: no FFI, rasterization, allocation or lighting in loops.
//! CSV on stdout; seed=20260930, seven repetitions, warmup before measurement.
use ochrell::{Color, FastPigmentMixer, Latent};
use std::{hint::black_box as bb, time::Instant};

fn main() {
    let m = FastPigmentMixer;
    let colors: Vec<_> = (0..4096u32)
        .map(|i| {
            let x = i
                .wrapping_add(20260930)
                .wrapping_mul(1664525)
                .wrapping_add(1013904223);
            Color::srgb8((x >> 24) as u8, (x >> 16) as u8, (x >> 8) as u8)
        })
        .collect();
    let hot: Vec<_> = colors.iter().map(|c| m.encode(*c)).collect();
    let count = 262144; // 85 MiB exceeds typical last-level cache on this host.
    let mut states: Vec<_> = (0..count).map(|i| hot[i % hot.len()]).collect();
    let mut copy = states.clone();
    let n = 200000;
    eprintln!(
        "Latent={} bytes; streaming buffer={} bytes; seed=20260930; iterations={n}",
        std::mem::size_of::<Latent>(),
        count * std::mem::size_of::<Latent>()
    );
    println!("operation,repeat,iterations,ns_per_op,logical_bytes_per_op");
    for name in [
        "encode",
        "mix_hot",
        "decode_hot",
        "mix_decode_hot",
        "rgb_roundtrip",
        "read_sequential",
        "read_scattered",
        "update_sequential",
        "update_scattered",
        "copy_stream",
    ] {
        for rep in 0..8 {
            let start = Instant::now();
            let iterations = if name == "copy_stream" { 12 } else { n };
            for i in 0..iterations {
                let j = i % hot.len();
                match name {
                    "encode" => {
                        bb(m.encode(bb(colors[j])));
                    }
                    "mix_hot" => {
                        bb(bb(hot[j]).interpolate(bb(hot[(j + 137) % hot.len()]), bb(0.13)));
                    }
                    "decode_hot" => {
                        bb(m.decode(bb(hot[j])));
                    }
                    "mix_decode_hot" => {
                        bb(m.decode(
                            bb(hot[j]).interpolate(bb(hot[(j + 137) % hot.len()]), bb(0.13)),
                        ));
                    }
                    "rgb_roundtrip" => {
                        let z = bb(hot[j]).interpolate(bb(hot[(j + 137) % hot.len()]), bb(0.13));
                        bb(m.encode(m.decode(z)));
                    }
                    "read_sequential" => {
                        bb(states[i % count]);
                    }
                    "read_scattered" => {
                        bb(states[(i.wrapping_mul(104729) + 1907) % count]);
                    }
                    "update_sequential" | "update_scattered" => {
                        let idx = if name == "update_sequential" {
                            i % count
                        } else {
                            (i.wrapping_mul(104729) + 1907) % count
                        };
                        states[idx] = bb(states[idx]).interpolate(bb(hot[j]), bb(0.13));
                        bb(&states[idx]);
                    }
                    _ => {
                        copy.copy_from_slice(bb(&states));
                        bb(&copy);
                    }
                }
            }
            let elapsed = start.elapsed().as_nanos() as f64;
            let ops = if name == "copy_stream" {
                iterations * count
            } else {
                iterations
            };
            let bytes = match name {
                "read_sequential" | "read_scattered" => 340,
                "update_sequential" | "update_scattered" | "copy_stream" => 680,
                _ => 0,
            };
            if rep > 0 {
                println!(
                    "{name},{},{ops},{:.4},{bytes}",
                    rep - 1,
                    elapsed / ops as f64
                );
            }
        }
    }
}

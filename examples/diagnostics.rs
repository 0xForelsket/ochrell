use ochrell::legacy::{PigmentMixer, ReferenceSpectralMixer};
use ochrell::*;
fn main() {
    for c in [
        Color::srgb8(255, 220, 0),
        Color::srgb8(20, 70, 255),
        Color::srgb8(230, 30, 40),
    ] {
        let z = ReferenceSpectralMixer.encode(c);
        println!("{:?} {:?} {:?}", c, z.concentrations(), z.residual());
    }
    let a = Color::srgb8(255, 220, 0);
    let b = Color::srgb8(20, 70, 255);
    println!("ref {:?}", ReferenceSpectralMixer.mix(a, b, 0.5));

    let m = PigmentMixer::default();
    let mut prev = a;
    let mut mx = 0f32;
    for i in 1..=2000 {
        let c = m.mix(a, b, i as f32 / 2000.);
        let d = c
            .channels()
            .iter()
            .zip(prev.channels())
            .map(|(x, y)| (x - y).abs())
            .fold(0., f32::max);
        if d > mx {
            mx = d;
            if d > 0.01 {
                println!("jump {i} {d} {:?} {:?}", prev, c)
            }
        }
        prev = c;
    }
}

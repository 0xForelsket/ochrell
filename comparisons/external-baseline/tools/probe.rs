//! Compare the frozen pigment-mix release without modifying its implementation.
use pigment_mix::{Color, FastPigmentMixer, ReferenceSpectralMixer};
use std::io::{self, Read};
fn main() {
    let mut inputs = String::new();
    io::stdin().read_to_string(&mut inputs).unwrap();
    let fast = FastPigmentMixer::default();
    let reference = ReferenceSpectralMixer;
    println!("pair,t,fast_r,fast_g,fast_b,ref_r,ref_g,ref_b");
    for line in inputs.lines() {
        let mut parts = line.split_whitespace();
        let name = parts.next().unwrap();
        let v: Vec<u8> = parts.map(|s| s.parse().unwrap()).collect();
        assert_eq!(v.len(), 6);
        let a = Color::srgb8(v[0],v[1],v[2]);
        let b = Color::srgb8(v[3],v[4],v[5]);
        let za=fast.encode(a); let zb=fast.encode(b);
        let ra=reference.encode(a); let rb=reference.encode(b);
        for i in 0..=400 {
            let t=i as f32/400.;
            let x=fast.decode(za.interpolate(zb,t)).channels();
            let y=reference.decode(ra.interpolate(rb,t as f64)).channels();
            println!("{name},{t:.9},{:.9},{:.9},{:.9},{:.9},{:.9},{:.9}",x[0],x[1],x[2],y[0],y[1],y[2]);
        }
    }
}

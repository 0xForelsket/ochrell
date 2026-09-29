//! CSV stdin: ar,ag,ab,br,bg,bb,t (unit encoded sRGB, no header).
//! CSV stdout: new RGB, old RGB. Used by independently generated holdout probes.
use ochrell::*;
use std::io::{self, BufRead};
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let m = PigmentMixer::default();
    let old = legacy::PigmentMixer::default();
    println!("new_r,new_g,new_b,old_r,old_g,old_b");
    for line in io::stdin().lock().lines() {
        let v: Vec<f32> = line?.split(',').map(str::parse).collect::<Result<_, _>>()?;
        if v.len() != 7 {
            return Err("expected seven CSV fields".into());
        }
        let a = Color::srgb(v[0], v[1], v[2])?;
        let b = Color::srgb(v[3], v[4], v[5])?;
        let x = m.try_mix(a, b, v[6])?.channels();
        let y = old.try_mix(a, b, v[6])?.channels();
        println!(
            "{:.12e},{:.12e},{:.12e},{:.12e},{:.12e},{:.12e}",
            x[0], x[1], x[2], y[0], y[1], y[2]
        );
    }
    Ok(())
}

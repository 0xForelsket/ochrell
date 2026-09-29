use ochrell::legacy::PigmentMixer;
use ochrell::*;
use std::io::Write;
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let m = PigmentMixer::default();
    let mut state = 20260929u64;
    let mut next = || {
        state ^= state << 13;
        state ^= state >> 7;
        state ^= state << 17;
        ((state >> 40) as u32) as f32 / 16777216.
    };
    let mut out = std::io::BufWriter::new(std::io::stdout());
    writeln!(
        out,
        "id,max_step_deltaEOK100,min_y,max_y,mapped_count,finite"
    )?;
    for id in 0..200 {
        let a = Color::srgb(next(), next(), next())?;
        let b = Color::srgb(next(), next(), next())?;
        let za = m.encode(a);
        let zb = m.encode(b);
        let mut prev = a.linear();
        let mut maxstep: f64 = 0.;
        let mut ymin: f64 = 1.;
        let mut ymax: f64 = 0.;
        let mut mapped = 0;
        let mut finite = true;
        for j in 0..1001 {
            let z = za.interpolate(zb, j as f32 / 1000.);
            let raw = m.decode_linear(z);
            mapped += usize::from(raw.iter().any(|v| !(0. ..=1.).contains(v)));
            let x = m.decode(z).linear();
            finite &= x.iter().all(|v| v.is_finite());
            let y = 0.2126 * x[0] + 0.7152 * x[1] + 0.0722 * x[2];
            ymin = ymin.min(y);
            ymax = ymax.max(y);
            maxstep = maxstep.max(conversion::delta_e_ok100(prev, x));
            prev = x;
        }
        writeln!(out, "{id},{maxstep},{ymin},{ymax},{mapped},{finite}")?;
    }
    Ok(())
}

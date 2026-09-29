//! Compare f32 forward values with a separately evaluated f64 20 nm model.
use std::io::{BufRead, Write};
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let path = std::env::args()
        .nth(1)
        .unwrap_or_else(|| "results/reconstruction/samples.csv".into());
    let f = std::io::BufReader::new(std::fs::File::open(path)?);
    let mut out = std::io::BufWriter::new(std::io::stdout());
    writeln!(out, "id,r,g,b")?;
    for line in f.lines().skip(1) {
        let line = line?;
        let p: Vec<_> = line.split(',').collect();
        let mut w = [0.; 8];
        for i in 0..8 {
            w[i] = p[i + 4].parse::<f32>()?
        }
        let c = ochrell::spectrum::forward_fast(&w);
        writeln!(out, "{},{:.12e},{:.12e},{:.12e}", p[0], c[0], c[1], c[2])?;
    }
    Ok(())
}

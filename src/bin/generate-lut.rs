use ochrell::lut::Lut;
fn main() -> Result<(), Box<dyn std::error::Error>> {
    let args: Vec<_> = std::env::args().collect();
    let n = args.get(1).map(|x| x.parse()).transpose()?.unwrap_or(33);
    let path = args
        .get(2)
        .cloned()
        .unwrap_or_else(|| "data/default.lut".into());
    let start = std::time::Instant::now();
    let lut = Lut::generate(n)?;
    std::fs::write(&path, lut.to_bytes())?;
    println!(
        "resolution={n} bytes={} seconds={:.6} path={path}",
        lut.memory_bytes() + 8,
        start.elapsed().as_secs_f64()
    );
    Ok(())
}

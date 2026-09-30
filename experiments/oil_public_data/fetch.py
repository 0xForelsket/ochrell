"""Retrieve the public, checksum-selected supplement into ignored research output."""
import hashlib
import io
import urllib.request
import zipfile
from pathlib import Path

ROOT=Path(__file__).resolve().parents[2]
DEST=ROOT/'target/measured-oils/public-audit/grillini-data.zip'
EXPECTED='6d8cec6fb4fff5d4c24d18d1783422da8ef955d3e7ba7263179a84ed6c9b683e'
URL='https://www.ebi.ac.uk/europepmc/webservices/rest/PMC8038140/supplementaryFiles'

if DEST.exists():
    assert hashlib.sha256(DEST.read_bytes()).hexdigest()==EXPECTED
    print('Existing selected supplement verified:',DEST)
else:
    with urllib.request.urlopen(URL,timeout=30) as response:
        outer=response.read(20_000_001)
    if len(outer)>20_000_000:raise ValueError('Unexpected download size')
    with zipfile.ZipFile(io.BytesIO(outer)) as archive:
        raw=archive.read('sensors-21-02471-s001.zip')
    assert hashlib.sha256(raw).hexdigest()==EXPECTED,'Public artifact changed; inspect before reuse'
    DEST.parent.mkdir(parents=True,exist_ok=True)
    DEST.write_bytes(raw)
    print('Saved selected public supplement:',DEST)

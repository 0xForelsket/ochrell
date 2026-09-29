"""Regenerate initial, failed edge-sweep, and selected exploratory trials."""
import copy,runpy,shutil
from model import ROOT,CFG
saved=copy.deepcopy(CFG['model'])
CFG['model'].update(blue_edge_nm=500.,yellow_edge_nm=490.)
runpy.run_path(str(ROOT/'tools/explore.py'))
for a,b in [('midpoints.csv','initial_midpoints.csv'),('reconstruction.json','initial_reconstruction.json')]:shutil.copyfile(ROOT/CFG['paths']['results']/'exploration'/a,ROOT/CFG['paths']['results']/'exploration'/b)
CFG['model'].update(saved)
CFG['model'].update(blue_edge_nm=530.,yellow_edge_nm=530.)
runpy.run_path(str(ROOT/'tools/explore.py'))
for a,b in [('midpoints.csv','failed_530_530_midpoints.csv'),('reconstruction.json','failed_530_530_reconstruction.json')]:shutil.copyfile(ROOT/CFG['paths']['results']/'exploration'/a,ROOT/CFG['paths']['results']/'exploration'/b)
CFG['model'].update(saved)
runpy.run_path(str(ROOT/'tools/explore.py'))
runpy.run_path(str(ROOT/'tools/sweep.py'))
CFG['model'].update(saved)

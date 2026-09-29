// Evaluate only the documented Spectral.js API; no implementation is copied.
const fs = require('node:fs');
const spectral = require('spectral.js');
const version = require('spectral.js/package.json').version;
const input = JSON.parse(fs.readFileSync(0,'utf8'));
if(version !== input.settings.version) throw Error('Unexpected Spectral.js version');
const rows=[];const checks=[];
for(const c of input.cases){
 const a=new spectral.Color(c.a),b=new spectral.Color(c.b);
 a.tintingStrength=input.settings.tinting_strength;
 b.tintingStrength=input.settings.tinting_strength;
 for(let i=0;i<=400;i++){
  const t=i/400;
  const mixed=spectral.mix([a,1-t],[b,t]);
  const rgb=mixed.toGamut({method:input.settings.gamut_mapping}).sRGB;
  if(rgb.length!==3||rgb.some(x=>!Number.isFinite(x)||x<0||x>255))throw Error('Invalid RGB '+c.pair+' '+t);
  rows.push({pair:c.pair,t,r:rgb[0],g:rgb[1],b:rgb[2]});
  if(i===0||i===400)checks.push({pair:c.pair,t,input:i===0?c.a:c.b,output:rgb});
 }
}
console.log(JSON.stringify({version,node:process.version,settings:input.settings,rows,checks}));

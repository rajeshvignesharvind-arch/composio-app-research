"""Human spot-check page: one card per gold app. Vignesh agrees/corrects, copies the JSON result back. python -m agent.build_checklist"""
import json
from .util import ROOT
gold = json.load(open(ROOT/"data"/"gold.json"))
page = '''<!doctype html><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>Gold set check</title>
<style>body{font:15px/1.5 system-ui;max-width:860px;margin:0 auto;padding:16px;background:#fbfaf8;color:#1b1b1f}.c{background:#fff;border:1px solid #ddd;border-radius:12px;padding:14px;margin:12px 0}.c.flag{border-color:#f08c00}
table{border-collapse:collapse;width:100%;font-size:13px}td,th{border-bottom:1px solid #eee;padding:4px 6px;text-align:left}button{padding:6px 12px;border-radius:8px;border:1px solid #bbb;background:#fff;cursor:pointer}.on{background:#2f9e44;color:#fff}.off{background:#e03131;color:#fff}textarea{width:100%}pre{background:#eee;padding:8px;overflow:auto}</style>
<h1>Gold set: 20 apps, ~2 min each</h1><p>For each app: open the evidence link, check my answers against the docs, press <b>Agree</b> or <b>Disagree</b> (then say what is true). Orange cards are the ones I am least sure of: do those first. When done, press <b>Copy result</b> and paste it back to me in the thread.</p>
<div id=list></div><button onclick=out()>Copy result</button><pre id=o></pre>
<script>const G=__G__;const S={};
G.forEach(g=>{const d=document.createElement('div');d.className='c'+(g.needs_human_confirm?' flag':'');
const rows=['auth_methods','primary_auth','credential_access','api_type','api_breadth','existing_mcp'].map(k=>'<tr><th>'+k+'</th><td>'+JSON.stringify(g[k])+'</td></tr>').join('');
d.innerHTML='<b>#'+g.id+' '+g.app+'</b> '+(g.needs_human_confirm?'(please check carefully)':'')+'<br><small>'+g.note+'</small><table>'+rows+'</table><p>'+g.evidence.map(u=>'<a target=_blank href="'+u+'">'+u+'</a>').join('<br>')+'</p><button id=a'+g.id+'>Agree</button> <button id=d'+g.id+'>Disagree</button><br><textarea id=t'+g.id+' rows=2 placeholder="what is actually true (field: value)"></textarea>';
document.getElementById('list').appendChild(d);
d.querySelector('#a'+g.id).onclick=e=>{S[g.id]={app:g.app,verdict:'agree'};e.target.className='on';d.querySelector('#d'+g.id).className=''};
d.querySelector('#d'+g.id).onclick=e=>{S[g.id]={app:g.app,verdict:'disagree'};e.target.className='off';d.querySelector('#a'+g.id).className=''}});
function out(){G.forEach(g=>{if(S[g.id]&&S[g.id].verdict=='disagree')S[g.id].correction=document.getElementById('t'+g.id).value});const s=JSON.stringify(S);document.getElementById('o').textContent=s;navigator.clipboard&&navigator.clipboard.writeText(s)}</script>'''.replace('__G__', json.dumps(gold))
(ROOT/"site"/"checklist.html").write_text(page); print("ok")

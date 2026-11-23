"""Render site/ from data/final.jsonl + analysis + verification. No runtime deps in the page. python -m agent.build_site"""
import json, html, csv, datetime
from .util import ROOT
from .analyze import analyze, load, v
from .schema import SCORED

E = html.escape
OUT = ROOT / "site"; OUT.mkdir(exist_ok=True)
rows = load(ROOT / "data" / "final.jsonl")
comp = json.load(open(ROOT / "data" / "composio.json")) if (ROOT / "data" / "composio.json").exists() else {}
for r in rows: r["composio_toolkit"] = "yes" if comp.get(str(r["id"])) else "no"
A = analyze(rows); (ROOT / "data" / "analysis.json").write_text(json.dumps(A, indent=1))
VER = json.load(open(ROOT / "data" / "verification.json")) if (ROOT / "data" / "verification.json").exists() else None
n = len(rows); ok = A["n_ok"]
pct = lambda a, b: round(100 * a / b) if b else 0
LBL = {"self_serve_free": "self-serve free", "self_serve_trial": "self-serve trial", "paid_plan": "paid plan", "admin_approval": "admin approval", "partner_gated": "partner gated",
       "sales_contact": "sales contact", "no_public_api": "no public API", "unknown": "unknown"}
ACC_ORDER = ["self_serve_free", "self_serve_trial", "paid_plan", "admin_approval", "partner_gated", "sales_contact", "no_public_api"]

def top(lst, i=0): return lst[i] if len(lst) > i else ("n/a", 0)
pa_top = top(A["primary_auth"]); bl = [b for b in A["blockers"] if b[0] != "none"]; bl_top = bl[0] if bl else ("none", 0, [])
acc_n = sum(c for _, c in A["access"])
oauth_n = dict(A["primary_auth"]).get("oauth2", 0); key_n = dict(A["primary_auth"]).get("api_key", 0) + dict(A["primary_auth"]).get("bearer_token", 0)
mcp = dict(A["mcp"]); ready = len(A["build_now"]); blocked = len(A["outreach"])
final_acc = f'{VER["passes"][-1]["overall"]["pct"]}%' if VER else "pending"

# ---- pattern sentences, computed from the tables, never free-written
pats = []
pats.append(f"<b>{A['self_serve_pct']}% of apps are self-serve</b> (a developer can get working credentials free or on a trial); {pct(sum(c for k,c in A['access'] if k in ('partner_gated','sales_contact','admin_approval','no_public_api')), acc_n)}% need an admin, a sales call or a partner gate.")
pats.append(f"<b>OAuth2 is the primary auth for {oauth_n} apps; static API keys / bearer tokens for {key_n}.</b> {A['multi_auth']} apps offer more than one method.")
if bl: pats.append(f"<b>Most common blocker: {E(bl_top[0].replace('_',' '))} ({bl_top[1]} apps).</b> " + ", ".join(E(x) for x in bl_top[2][:6]) + ("…" if len(bl_top[2]) > 6 else ""))
pats.append(f"<b>{ready} apps are ready to build today</b> (self-serve credentials + moderate/broad documented API); <b>{blocked} are blocked</b> by access, and need outreach or a different path.")
pats.append(f"<b>{mcp.get('official',0)} apps already have an official MCP server</b>, {mcp.get('community',0)} only a community one, {mcp.get('none_found',0)} none found: a quick win is wrapping what exists.")
cats = A["categories"]
def selfserve_share(c):
    m = A["matrix"].get(c, {}); t = sum(m.values()); return (sum(m.get(k, 0) for k in ("self_serve_free", "self_serve_trial")) / t) if t else None
sh = [(c, selfserve_share(c)) for c in cats if selfserve_share(c) is not None]
if sh:
    hi = max(sh, key=lambda x: x[1]); lo = min(sh, key=lambda x: x[1])
    pats.append(f"<b>Most self-serve category: {E(hi[0])} ({round(100*hi[1])}%). Most gated: {E(lo[0])} ({round(100*lo[1])}% self-serve).</b>")

def heat():
    h = "<table class=heat><tr><th></th>" + "".join(f"<th>{LBL[k]}</th>" for k in ACC_ORDER) + "<th>unknown</th></tr>"
    for c in cats:
        m = A["matrix"].get(c, {}); tot = sum(m.values()) or 1
        h += f"<tr><th>{E(c)}</th>" + "".join(f'<td style="--p:{m.get(k,0)/tot:.2f}" class="{"g" if k.startswith("self") else "r"}">{m.get(k,0) or ""}</td>' for k in ACC_ORDER)
        unk = len([r for r in rows if r["category"] == c]) - sum(m.values()); h += f"<td class=u>{unk or ''}</td></tr>"
    return h + "</table>"
def bars(pairs, cls=""):
    mx = max([c for _, c in pairs] + [1])
    return "".join(f'<div class="bar {cls}"><span>{E(str(k).replace("_"," "))}</span><i style="width:{100*c/mx:.0f}%"></i><b>{c}</b></div>' for k, c in pairs)
def quad():
    q = A["quadrants"]; cell = lambda key, title, cls: f'<div class="q {cls}"><h4>{title} <small>{len(q.get(key,[]))}</small></h4><p>{", ".join(E(a) for a in q.get(key,[])) or "none"}</p></div>'
    return '<div class=quads>' + cell("gated / broad-moderate", "Gated · broad API: needs outreach", "o") + cell("self-serve / broad-moderate", "Self-serve · broad API: build now", "b") + cell("gated / narrow", "Gated · narrow: skip", "s") + cell("self-serve / narrow", "Self-serve · narrow: low value", "m") + "</div>"
def chip(val, kind=""):
    if isinstance(val, list): return " ".join(chip(x, kind) for x in val)
    return f'<span class="chip c-{E(str(val))}">{E(str(val).replace("_"," "))}</span>'

TABLE = []
for r in rows:
    TABLE.append({"id": r["id"], "app": r["app"], "category": r["category"], "one_liner": r.get("one_liner", ""), "auth": v(r, "auth_methods") or "unknown", "primary_auth": v(r, "primary_auth") or "unknown",
                  "access": v(r, "credential_access") or "unknown", "api_type": v(r, "api_type") or "unknown", "breadth": v(r, "api_breadth") or "unknown", "mcp": v(r, "existing_mcp") or "unknown",
                  "build": v(r, "buildability") or "unknown", "blocker": v(r, "main_blocker") or "unknown", "composio": r["composio_toolkit"], "gating": r.get("gating_notes", ""), "docs": r.get("docs_url") or (r.get("sources") or [""])[0],
                  "needs_human": r.get("needs_human", []), "hist": [h for h in r.get("pass_history", []) if h.get("field")],
                  "ev": {k: {"url": (r.get(k) or {}).get("evidence_url"), "quote": (r.get(k) or {}).get("quote"), "grounded": (r.get(k) or {}).get("grounded")} for k in SCORED[:6] if isinstance(r.get(k), dict)}})
ds = {"@context": "https://schema.org", "@type": "Dataset", "name": "100-app agent-toolkit buildability research", "description": "Auth, access, API surface, MCP and buildability verdict for 100 apps, with evidence quotes.",
      "dateCreated": datetime.date.today().isoformat(), "variableMeasured": SCORED, "distribution": [{"@type": "DataDownload", "contentUrl": "results.json"}, {"@type": "DataDownload", "contentUrl": "results.csv"}]}
(OUT / "results.json").write_text(json.dumps(rows, indent=1))
with open(OUT / "results.csv", "w", newline="") as f:
    w = csv.writer(f); w.writerow(["id", "app", "category", "primary_auth", "auth_methods", "credential_access", "api_type", "api_breadth", "existing_mcp", "buildability", "main_blocker", "composio_toolkit", "docs_url"])
    for t in TABLE: w.writerow([t["id"], t["app"], t["category"], t["primary_auth"], "|".join(t["auth"]) if isinstance(t["auth"], list) else t["auth"], t["access"], "|".join(t["api_type"]) if isinstance(t["api_type"], list) else t["api_type"], t["breadth"], t["mcp"], t["build"], t["blocker"], t["composio"], t["docs"]])
from .schema import ENUMS
(OUT / "schema.json").write_text(json.dumps({"fields": {k: ENUMS[k] for k in ENUMS}, "record": "each scored field = {value, evidence_url, quote, grounded}"}, indent=1))
(OUT / "llms.txt").write_text(f"# 100-app agent-toolkit research\n\nMachine-readable: results.json (full records with evidence), results.csv, schema.json.\nEach scored field has value + evidence_url + verbatim quote. 'unknown' means not confirmed from sources.\nSummary: {A['self_serve_pct']}% self-serve; primary auth {pa_top[0]} ({pa_top[1]} apps); {ready} ready now; {blocked} blocked.\nVerification accuracy (gold set): {final_acc}.\n")

def ver_html():
    if not VER: return "<p class=note>Verification results are being finalised.</p>"
    ps = VER["passes"]; fields = SCORED
    t = "<table class=ver><tr><th>field</th>" + "".join(f"<th>{E(p['name'])}</th>" for p in ps) + "</tr>"
    for k in fields: t += f"<tr><th>{k}</th>" + "".join(f"<td>{p['per_field'][k]['correct']}/{p['per_field'][k]['n']}</td>" for p in ps) + "</tr>"
    t += "<tr class=tot><th>overall</th>" + "".join(f"<td>{p['overall']['correct']}/{p['overall']['n']} = <b>{p['overall']['pct']}%</b></td>" for p in ps) + "</tr></table>"
    steps = "".join(f'<div class=step><b>{p["overall"]["pct"]}%</b><span>{E(p["name"])}</span><small>{E(p.get("what",""))}</small></div>' for p in ps)
    ms = "".join(f"<tr><td>{E(m['app'])}</td><td>{m['field']}</td><td>{E(json.dumps(m['agent']))}</td><td>{E(json.dumps(m['truth']))}</td><td>{E(m.get('caught_by','not caught'))}</td></tr>" for m in VER.get("misses", []))
    fx = "".join(f"<li>{E(x)}</li>" for x in VER.get("fixes", []))
    return f'<div class=steps>{steps}</div>{t}<h3>Every remaining miss (final pass)</h3><table class=ver><tr><th>app</th><th>field</th><th>agent said</th><th>truth</th><th>caught by</th></tr>{ms or "<tr><td colspan=5>none</td></tr>"}</table><h3>Concrete fixes the loops made</h3><ul>{fx}</ul><p class=note>{E(VER.get("caveat",""))}</p>'

doc = f'''<!doctype html><html lang=en><head><meta charset=utf-8><meta name=viewport content="width=device-width,initial-scale=1"><title>100-App Toolkit Research</title>
<meta name=description content="An agent researched 100 apps for agent-toolkit buildability. Patterns, evidence, and measured accuracy.">
<script type="application/ld+json">{json.dumps(ds)}</script>
<style>
:root{{--bg:#fbfaf8;--fg:#1b1b1f;--mut:#6b6b73;--card:#fff;--line:#e4e2dc;--acc:#3b5bdb;--g:#2f9e44;--r:#e03131;--y:#f08c00}}
@media(prefers-color-scheme:dark){{:root:not([data-theme=light]){{--bg:#121214;--fg:#ececf0;--mut:#9a9aa5;--card:#1b1b1f;--line:#2e2e35;--acc:#7c93ff;--g:#51cf66;--r:#ff6b6b;--y:#fcc419}}}}
:root[data-theme=dark]{{--bg:#121214;--fg:#ececf0;--mut:#9a9aa5;--card:#1b1b1f;--line:#2e2e35;--acc:#7c93ff;--g:#51cf66;--r:#ff6b6b;--y:#fcc419}}
*{{box-sizing:border-box}}body{{margin:0;background:var(--bg);color:var(--fg);font:16px/1.55 system-ui,-apple-system,Segoe UI,sans-serif}}
nav{{position:sticky;top:0;background:var(--bg);border-bottom:1px solid var(--line);padding:8px 16px;display:flex;gap:14px;overflow-x:auto;white-space:nowrap;z-index:5;font-size:14px}}nav a{{color:var(--mut);text-decoration:none}}nav a:hover{{color:var(--fg)}}
main{{max-width:1100px;margin:0 auto;padding:0 16px 80px}}section{{padding-top:36px}}h1{{font-size:clamp(26px,5vw,40px);line-height:1.15;margin:28px 0 8px}}h2{{font-size:24px;margin:0 0 4px}}h2+p.lead{{margin:0 0 16px;color:var(--mut)}}h3{{margin:24px 0 8px}}
.tiles{{display:grid;grid-template-columns:repeat(auto-fit,minmax(200px,1fr));gap:12px;margin:20px 0}}.tile{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:14px}}.tile b{{display:block;font-size:30px}}.tile span{{color:var(--mut);font-size:13px}}
.pats li{{margin:8px 0}}.pats{{padding-left:20px}}.card{{background:var(--card);border:1px solid var(--line);border-radius:12px;padding:16px;margin:12px 0}}
table{{border-collapse:collapse;width:100%;font-size:13px}}th,td{{border-bottom:1px solid var(--line);padding:6px 8px;text-align:left;vertical-align:top}}.scroll{{overflow-x:auto}}
.heat td{{text-align:center;min-width:60px}}.heat td.g{{background:color-mix(in srgb,var(--g) calc(var(--p)*80%),transparent)}}.heat td.r{{background:color-mix(in srgb,var(--r) calc(var(--p)*80%),transparent)}}
.bar{{display:grid;grid-template-columns:150px 1fr 36px;gap:8px;align-items:center;margin:4px 0;font-size:13px}}.bar i{{display:block;height:12px;background:var(--acc);border-radius:6px}}.bar b{{text-align:right}}
.quads{{display:grid;grid-template-columns:1fr 1fr;gap:10px}}.q{{border:1px solid var(--line);border-radius:10px;padding:10px;font-size:13px}}.q.b{{border-color:var(--g)}}.q.o{{border-color:var(--y)}}.q h4{{margin:0 0 4px}}
.chip{{display:inline-block;padding:1px 8px;border-radius:99px;font-size:12px;background:color-mix(in srgb,var(--acc) 14%,transparent);margin:1px}}
.c-ready_now,.c-self_serve_free,.c-official{{background:color-mix(in srgb,var(--g) 25%,transparent)}}.c-blocked,.c-sales_contact,.c-partner_gated,.c-no_public_api,.c-unknown{{background:color-mix(in srgb,var(--r) 22%,transparent)}}.c-buildable_with_effort,.c-paid_plan,.c-admin_approval,.c-self_serve_trial,.c-community{{background:color-mix(in srgb,var(--y) 28%,transparent)}}
.filters{{display:flex;gap:8px;flex-wrap:wrap;margin:10px 0}}input,select{{padding:6px 8px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--fg);font:inherit;font-size:14px}}
tr.row{{cursor:pointer}}tr.row:hover{{background:color-mix(in srgb,var(--acc) 8%,transparent)}}.detail td{{background:color-mix(in srgb,var(--acc) 5%,transparent);font-size:12.5px}}blockquote{{margin:4px 0;padding-left:10px;border-left:3px solid var(--line);color:var(--mut)}}
.flow{{display:flex;flex-wrap:wrap;gap:8px;align-items:center}}.flow div{{border:1px solid var(--line);background:var(--card);border-radius:10px;padding:8px 10px;font-size:13px;max-width:200px}}.flow .h{{border-color:var(--y)}}.flow em{{color:var(--mut);font-style:normal}}
.steps{{display:flex;gap:10px;flex-wrap:wrap;margin:10px 0}}.step{{flex:1;min-width:160px;border:1px solid var(--line);border-radius:12px;padding:12px;background:var(--card)}}.step b{{font-size:30px;display:block}}.step small{{display:block;color:var(--mut)}}
.note{{color:var(--mut);font-size:14px}}code,pre{{background:color-mix(in srgb,var(--fg) 8%,transparent);border-radius:6px;padding:1px 5px}}pre{{padding:10px;overflow-x:auto}}
@media(max-width:640px){{.quads{{grid-template-columns:1fr}}.bar{{grid-template-columns:100px 1fr 30px}}}}
</style></head><body>
<nav><a href=#top>Headline</a><a href=#patterns>Patterns</a><a href=#build>Build vs outreach</a><a href=#table>All 100</a><a href=#agent>The agent</a><a href=#verify>Verification</a><a href=#defeated>What defeated it</a><a href=#run>Run it</a><a href="results.json">results.json</a><a href="llms.txt">llms.txt</a></nav>
<main id=top>
<h1>We researched 100 apps for agent-toolkit buildability. Here is what the pattern says.</h1>
<p><b>{A['self_serve_pct']}% are self-serve, {ready} can be built today, {blocked} need outreach or a different route.</b> An agent did the research with evidence quotes for every answer; a different model re-checked it, and a hand-checked 20-app gold set scored it: <b>{final_acc} accurate</b> on the eight fields a reviewer acts on.</p>
<div class=tiles><div class=tile><b>{A['self_serve_pct']}%</b><span>self-serve credentials (free or trial)</span></div><div class=tile><b>{E(pa_top[0].replace('_',' '))}</b><span>dominant primary auth ({pa_top[1]} apps)</span></div><div class=tile><b>{E(bl_top[0].replace('_',' '))}</b><span>most common blocker ({bl_top[1]} apps)</span></div><div class=tile><b>{final_acc}</b><span>gold-set accuracy (pass 1 → final)</span></div></div>
<section id=patterns><h2>Patterns</h2><p class=lead>Computed by code over the final records; nothing below is a model's impression.</p><ul class=pats>{"".join(f"<li>{p}</li>" for p in pats)}</ul>
<div class=card><h3>Category × credential access</h3><p class=note>Cell = number of apps. Green = self-serve, red = gated.</p><div class=scroll>{heat()}</div></div>
<div class=card><h3>Primary auth</h3>{bars([(k,c) for k,c in A['primary_auth']])}</div>
<div class=card><h3>Main blocker (apps that are not ready)</h3>{bars([(k,c) for k,c,_ in bl])}</div>
<div class=card><h3>Official MCP servers</h3>{bars(A['mcp'])}<p class=note>Official = published by the vendor. {mcp.get('official',0)} apps can be wrapped instead of built from scratch.</p></div>
<div class=card><h3>Access × API breadth</h3>{quad()}</div></section>
<section id=build><h2>Build now vs needs outreach</h2><p class=lead>The easy wins and the people-to-call list.</p>
<div class=card><h3>Build this week ({ready})</h3><p>{", ".join(E(a) for a in A['build_now'])}</p></div>
<div class=card><h3>Needs outreach / blocked ({blocked})</h3><div class=scroll><table><tr><th>app</th><th>gate</th><th>note</th></tr>{"".join(f"<tr><td>{E(o['app'])}</td><td>{chip(o['why'])}</td><td>{E(o.get('note') or '')}</td></tr>" for o in A['outreach'])}</table></div></div>
<div class=card><h3>Buildable with effort ({len(A['effort'])})</h3><p>{", ".join(E(a) for a in A['effort'])}</p></div></section>
<section id=table><h2>All {n} apps</h2><p class=lead>Click a row for evidence quotes, links and what the verification loops changed.</p>
<div class=filters><input id=q placeholder="search app…"><select id=fc><option value="">all categories</option></select><select id=fa><option value="">all access</option></select><select id=fb><option value="">all verdicts</option></select><select id=fau><option value="">all primary auth</option></select></div>
<div class=scroll><table id=tbl><thead><tr><th>#</th><th>App</th><th>Auth</th><th>Access</th><th>API</th><th>MCP</th><th>Verdict</th><th>Blocker</th><th>In Composio</th></tr></thead><tbody></tbody></table></div></section>
<section id=agent><h2>The agent</h2><p class=lead>A Python pipeline, free-tier only. Every field must carry a source and a verbatim quote, or it is marked unknown.</p>
<div class=flow><div><b>1 Seed</b><br><em>apps.yaml, hint URL pins identity</em></div>→<div><b>2 Discover</b><br><em>Tavily: 3 vendor-domain searches + 1 open MCP search</em></div>→<div><b>3 Fetch</b><br><em>Firecrawl, Jina Reader fallback, cached</em></div>→<div><b>4 Extract</b><br><em>Groq LLM, strict JSON + quotes</em></div>→<div><b>5 Ground</b><br><em>code checks each quote is on the page, else unknown</em></div>→<div><b>6 Derive</b><br><em>buildability + blocker from a written rule</em></div>→<div><b>7 Critic</b><br><em>other Groq model: live re-fetch, judge, adversarial search</em></div>→<div><b>8 Re-research</b><br><em>flagged fields redo, max 2 rounds</em></div>→<div class=h><b>9 Human</b><br><em>gold-set check + needs_human fields</em></div></div>
<h3>Why two Groq models</h3><p>Both models run on Groq's free tier, because that was the budget. To keep the check independent, each app is extracted by one model (<code>gpt-oss</code> or <code>qwen</code>, alternating) and re-checked by the <em>other</em>. This is weaker independence than a different vendor would give; the gold set is what measures actual accuracy.</p>
<h3>Where a human was needed</h3><ul><li>Naming the 20-app gold set and confirming/correcting each gold answer from primary docs (the verification loop).</li><li>Ambiguous or obscure identities: fanbasis, iPayX, Paygent Connect, Waterfall.io, Sherlock, higgsfield.</li><li>Docs behind a login or sales gate (DealCloud, Gladly, PitchBook, fanbasis docs), where the gate itself is the finding.</li><li>Fields still flagged after 2 critic rounds are listed in <a href=#defeated>what defeated it</a>.</li></ul>
<h3>Run stats</h3><p class=note>{ok}/{n} apps completed; {sum(len(r.get("sources",[])) for r in rows)} pages fetched; total cost $0 (free tiers). Groq's 8k tokens/min and 200k tokens/day caps set the speed, not the code.</p></section>
<section id=verify><h2>Verification</h2><p class=lead>A 20-app gold set (2 per category: one well-known, one obscure/gated) was drafted from live docs and confirmed by a human, frozen before pass 2, and used to score every pass on the same apps.</p>{ver_html()}</section>
<section id=defeated><h2>What defeated the agent</h2><p class=lead>Honest list: apps where the answer is unknown or a human decided it.</p>
<div class=card>{"".join(f"<p><b>{E(d['app'])}</b>: {E(d['why'])}</p>" for d in A['defeated']) or "<p>None.</p>"}</div>
<p class=note>Fields unknown across all {ok} apps: {", ".join(f"{k} {c}" for k,c in A['unknown_rate'].items())}.</p></section>
<section id=run><h2>Run it yourself</h2><pre>git clone https://github.com/rajeshvignesharvind-arch/composio-app-research
cd composio-app-research &amp;&amp; pip install -r requirements.txt &amp;&amp; cp .env.example .env   # add GROQ / TAVILY / FIRECRAWL keys
python -m agent.run --app "Pumble"      # one app end to end, about a minute
python -m agent.run --all               # all 100, resumable
python -m agent.build_site              # rebuild this page</pre>
<p>Data for agents: <a href=results.json>results.json</a> · <a href=results.csv>results.csv</a> · <a href=schema.json>schema.json</a> · <a href=llms.txt>llms.txt</a>. The dataset is also embedded in this page as JSON-LD.</p></section>
</main>
<script>
const D={json.dumps(TABLE)};const $=s=>document.querySelector(s);
const uniq=k=>[...new Set(D.map(r=>r[k]))].sort();
for(const[id,k]of[['fc','category'],['fa','access'],['fb','build'],['fau','primary_auth']])uniq(k).forEach(x=>$('#'+id).insertAdjacentHTML('beforeend','<option>'+x+'</option>'));
const chip=v=>(Array.isArray(v)?v:[v]).map(x=>'<span class="chip c-'+x+'">'+String(x).replace(/_/g,' ')+'</span>').join('');
const esc=s=>String(s??'').replace(/[&<>]/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;'}}[c]));
function draw(){{const q=$('#q').value.toLowerCase(),f={{category:$('#fc').value,access:$('#fa').value,build:$('#fb').value,primary_auth:$('#fau').value}};const tb=$('#tbl tbody');tb.innerHTML='';
D.filter(r=>(!q||r.app.toLowerCase().includes(q))&&Object.entries(f).every(([k,v])=>!v||r[k]===v)).forEach(r=>{{const tr=document.createElement('tr');tr.className='row';
tr.innerHTML='<td>'+r.id+'</td><td><b>'+esc(r.app)+'</b><br><small>'+esc(r.one_liner)+'</small></td><td>'+chip(r.auth)+'</td><td>'+chip(r.access)+'</td><td>'+chip(r.api_type)+' '+chip(r.breadth)+'</td><td>'+chip(r.mcp)+'</td><td>'+chip(r.build)+'</td><td>'+chip(r.blocker)+'</td><td>'+r.composio+'</td>';
tr.onclick=()=>{{const n=tr.nextSibling;if(n&&n.className==='detail'){{n.remove();return}}const d=document.createElement('tr');d.className='detail';
let h='<td colspan=9><b>Gating:</b> '+esc(r.gating)+'<br><b>Docs:</b> <a href="'+esc(r.docs)+'">'+esc(r.docs)+'</a>';
for(const[k,e]of Object.entries(r.ev))h+='<blockquote><b>'+k+'</b>'+(e.grounded?' <small>(quote '+e.grounded+')</small>':'')+': '+(e.quote?'“'+esc(e.quote)+'” ':'<i>no grounded quote</i> ')+(e.url?'<a href="'+esc(e.url)+'">source</a>':'')+'</blockquote>';
if(r.hist.length)h+='<b>Verification loop changes:</b><ul>'+r.hist.map(x=>'<li>'+esc(x.field)+': '+esc(JSON.stringify(x.from))+' → '+esc(JSON.stringify(x.to))+' ('+esc(x.why||'')+')</li>').join('')+'</ul>';
if(r.needs_human.length)h+='<b>Needs human:</b> '+r.needs_human.join(', ');d.innerHTML=h+'</td>';tr.after(d)}};tb.appendChild(tr)}})}}
['q','fc','fa','fb','fau'].forEach(i=>$('#'+i).addEventListener('input',draw));draw();
</script></body></html>'''
(OUT / "index.html").write_text(doc)
print("built site/index.html", len(doc) // 1024, "KB")

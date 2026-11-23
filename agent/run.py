"""CLI: python -m agent.run --app Pumble | --all [--pass2]"""
import argparse, json, yaml, time, concurrent.futures as cf
from .util import ROOT
from .fetch import gather, scrape
from .extract import extract
from .critic import critique

def load_apps(): return yaml.safe_load((ROOT/"data"/"apps.yaml").read_text())

def pass1(a):
    f = ROOT/"data"/"pass1"/f"{a['id']}.json"; f.parent.mkdir(exist_ok=True)
    if f.exists(): return json.loads(f.read_text())
    r = _pass1(a)
    if r.get("status") == "ok": f.write_text(json.dumps(r))
    return r

def _pass1(a):
    t = time.time()
    try:
        pages, _ = gather(a["app"], a["hint"])
        rec = extract(a["app"], a["category"], pages, app_id=a["id"])
        rec["status"] = "ok"
    except Exception as e:
        rec = {"status": "error", "error": str(e)[:300]}
    return {**a, **rec, "pass_history": [{"pass": 1, "secs": round(time.time()-t, 1)}]}

def pass2(r):
    """critic flags -> targeted re-extraction of ONLY the flagged fields (1 round, then needs_human)."""
    from .schema import derive, consistency_flags
    from .extract import extractor_for, gemini, snippet, quote_ok, ground
    if r.get("status") != "ok": return r
    flags = critique(r["app"], r, r["id"]); r["critic_flags"] = flags
    fix = {}
    for f in flags:
        if f["kind"] in ("unknown", "refetch", "judge", "adversarial") and f["field"] in ("auth_methods","primary_auth","credential_access","api_type","api_breadth","existing_mcp"):
            fix.setdefault(f["field"], []).append(f)
    if fix:
        urls = list(dict.fromkeys(r["sources"][:3] + [u for fl in sum(fix.values(), []) for u in fl.get("extra_urls", [])]))[:5]
        pages = [p for p in (scrape(u) for u in urls) if p["text"]]
        note = "; ".join(f"{k}: {x['note']}" + (f" (critic suggests {x['suggest']})" if x.get("suggest") else "") for k, xs in fix.items() for x in xs[:1])
        src = "\n\n".join(f"[SOURCE {i}] {p['url']}\n{snippet(p['text'], 900)}" for i, p in enumerate(pages))
        from .extract import prompt as _p
        q = (f'Re-check ONLY these fields for app "{r["app"]}": {list(fix)}. A reviewer flagged: {note}.\n'
             'Return JSON {"<field>": {"value":..., "source": <SOURCE number>, "quote": "<verbatim from that source>", "confidence":"high|medium|low"}} for just those fields. Use "unknown" if the sources do not show it. Allowed values: auth from '
             'oauth2,api_key,bearer_token,basic,jwt_service_account,hmac_signature,session_cookie,none,other; credential_access from self_serve_free,self_serve_trial,paid_plan,admin_approval,partner_gated,sales_contact,no_public_api; '
             'api_type list from rest,graphql,grpc,websocket,sdk_only,cli_only,none; api_breadth broad|moderate|narrow; existing_mcp official(vendor-published)|community|none_found.\n\nSOURCES:\n' + src)
        new = gemini(q, extractor_for(r["id"]))
        new = ground({k: (x if isinstance(x, dict) else {"value": x}) for k, x in new.items() if k in fix}, pages)
        for k, x in new.items():
            old = (r.get(k) or {}).get("value")
            if x.get("value") not in (None, "unknown") and x.get("grounded") and x["value"] != old:
                r["pass_history"].append({"pass": 2, "field": k, "from": old, "to": x["value"], "why": fix[k][0]["note"], "kind": fix[k][0]["kind"]})
                r[k] = x
    from .schema import ENUMS
    for k, xs in fix.items():   # fallback: critic's search-backed suggestion, tagged as lower-trust
        adv = [x for x in xs if x["kind"] == "adversarial" and x.get("suggest") in ENUMS.get(k, [])]
        if adv and not any(h.get("field") == k for h in r["pass_history"]):
            old = (r.get(k) or {}).get("value")
            if adv[0]["suggest"] != old:
                r["pass_history"].append({"pass": 2, "field": k, "from": old, "to": adv[0]["suggest"], "why": adv[0]["note"], "kind": "adversarial-search"})
                r[k] = {"value": adv[0]["suggest"], "source": None, "quote": None, "evidence_url": (adv[0].get("extra_urls") or [None])[0], "grounded": "critic_search", "confidence": "low", "note": adv[0]["note"]}
    b, bl = derive(r); r["buildability"] = {"value": b, "rule": "derive()"}; r["main_blocker"] = {"value": bl, "rule": "derive()"}
    r["flags"] = consistency_flags(r)
    r["needs_human"] = sorted({f["field"] for f in flags if f["kind"] in ("unknown", "judge", "adversarial", "refetch") and (r.get(f["field"]) or {}).get("value") in ("unknown", None) or f["kind"] == "adversarial" and not any(h.get("field") == f["field"] for h in r["pass_history"])})
    return r

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--app"); ap.add_argument("--all", action="store_true")
    ap.add_argument("--pass2", action="store_true"); ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int)
    a = ap.parse_args(); apps = load_apps()
    if a.app: apps = [x for x in apps if x["app"].lower() == a.app.lower()]
    if a.limit: apps = apps[:a.limit]
    out = ROOT/"data"/("pass2.jsonl" if a.pass2 else "pass1.jsonl")
    with cf.ThreadPoolExecutor(a.workers) as ex:
        if a.pass2:
            (ROOT/"data"/"pass2").mkdir(exist_ok=True)
            def one(x):
                f = ROOT/"data"/"pass2"/f"{x['id']}.json"; src = ROOT/"data"/"pass1"/f"{x['id']}.json"
                if f.exists(): return json.loads(f.read_text())
                if not src.exists(): return {**x, "status": "not_run"}
                try: r = pass2(json.loads(src.read_text()))
                except Exception as e: return {**json.loads(src.read_text()), "pass2_error": str(e)[:200]}
                f.write_text(json.dumps(r)); return r
            res = list(ex.map(one, apps))
        else:
            res = list(ex.map(pass1, apps))
    print("ok:", sum(r.get("status")=="ok" for r in res), "/", len(res))
    out.write_text("\n".join(json.dumps(r) for r in res)+"\n")
    for r in res: print(r["id"], r["app"], r.get("status"), (r.get("credential_access") or {}).get("value"), (r.get("buildability") or {}).get("value"))

if __name__ == "__main__": main()

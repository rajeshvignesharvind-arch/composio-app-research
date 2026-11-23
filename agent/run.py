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

def pass2(r, max_rounds=2):
    if r.get("status") != "ok": return r
    for rnd in range(max_rounds):
        flags = [f for f in critique(r["app"], r, r["id"]) if f["kind"] != "rule" or rnd == 0]
        r.setdefault("critic_flags", []).append(flags)
        fixable = [f for f in flags if f["kind"] in ("unknown", "refetch", "judge", "adversarial")]
        if not fixable: break
        pages = [scrape(u) for u in r["sources"]]
        for f in fixable:
            for u in f.get("extra_urls", [])[:2]:
                if u not in r["sources"]: r["sources"].append(u); pages.append(scrape(u))
        pages = [p for p in pages if p["text"]]
        new = extract(r["app"], r["category"], pages, app_id=r["id"], note="; ".join(f"{f['field']}: {f['note']}" for f in fixable))
        for f in fixable:
            k = f["field"]
            if k in new and new[k] != r.get(k):
                r["pass_history"].append({"pass": 2, "round": rnd+1, "field": k, "from": (r.get(k) or {}).get("value"),
                                          "to": new[k].get("value") if isinstance(new[k], dict) else new[k], "why": f["note"], "kind": f["kind"]})
                r[k] = new[k]
        r["sources"] = new["sources"]
        from .schema import derive, consistency_flags
        b, bl = derive(r); r["buildability"] = {"value": b, "rule": "derive()"}; r["main_blocker"] = {"value": bl, "rule": "derive()"}
        r["flags"] = consistency_flags(r)
    left = [f for f in (r.get("critic_flags") or [[]])[-1] if f["kind"] != "rule"]
    r["needs_human"] = [f["field"] for f in left]
    return r

def main():
    ap = argparse.ArgumentParser(); ap.add_argument("--app"); ap.add_argument("--all", action="store_true")
    ap.add_argument("--pass2", action="store_true"); ap.add_argument("--workers", type=int, default=6)
    ap.add_argument("--limit", type=int)
    a = ap.parse_args(); apps = load_apps()
    if a.app: apps = [x for x in apps if x["app"].lower() == a.app.lower()]
    if a.limit: apps = apps[:a.limit]
    out = ROOT/"data"/("pass2.jsonl" if a.pass2 else "pass1.jsonl")
    src = ROOT/"data"/"pass1.jsonl"
    with cf.ThreadPoolExecutor(a.workers) as ex:
        if a.pass2:
            rows = {json.loads(l)["id"]: json.loads(l) for l in src.read_text().splitlines()}
            todo = [rows[x["id"]] for x in apps if x["id"] in rows]
            res = list(ex.map(pass2, todo))
        else:
            res = list(ex.map(pass1, apps))
    if not a.pass2: print("ok:", sum(r.get("status")=="ok" for r in res), "/", len(res))
    out.write_text("\n".join(json.dumps(r) for r in res)+"\n")
    for r in res: print(r["id"], r["app"], r.get("status"), (r.get("credential_access") or {}).get("value"), (r.get("buildability") or {}).get("value"))

if __name__ == "__main__": main()

"""Score a pass against the frozen gold set, per field, with every miss listed. python -m agent.score data/pass1.jsonl"""
import json, sys
from .util import ROOT
from .schema import SCORED
vv = lambda r, k: (r.get(k) or {}).get("value") if isinstance(r.get(k), dict) else r.get(k)
def eq(a, b):
    if isinstance(a, list) or isinstance(b, list):
        return sorted(a if isinstance(a, list) else [a]) == sorted(b if isinstance(b, list) else [b])
    return a == b
def score(rows, gold):
    by = {r["id"]: r for r in rows}
    per = {k: [0, 0] for k in SCORED}; misses = []
    for g in gold:
        r = by.get(g["id"], {})
        # buildability / blocker gold = the deterministic rule applied to gold fields
        from .schema import derive
        gd = {k: {"value": g[k]} for k in ["credential_access", "api_type", "api_breadth"]}; gb, gbl = derive(gd)
        gv = {**{k: g[k] for k in SCORED[:6]}, "buildability": gb, "main_blocker": gbl}
        for k in SCORED:
            per[k][1] += 1; a = vv(r, k)
            if eq(a, gv[k]): per[k][0] += 1
            else: misses.append({"id": g["id"], "app": g["app"], "field": k, "agent": a, "truth": gv[k], "evidence": g["evidence"][:1]})
    tot = sum(v[0] for v in per.values()), sum(v[1] for v in per.values())
    return {"per_field": {k: {"correct": v[0], "n": v[1]} for k, v in per.items()}, "overall": {"correct": tot[0], "n": tot[1], "pct": round(100 * tot[0] / tot[1], 1)}, "misses": misses}
if __name__ == "__main__":
    rows = [json.loads(l) for l in open(sys.argv[1])]; gold = json.load(open(ROOT/"data"/"gold.json"))
    s = score(rows, gold); print(json.dumps({k: v for k, v in s.items() if k != "misses"}, indent=1)); print(len(s["misses"]), "misses")

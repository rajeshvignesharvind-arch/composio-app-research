"""Build per-stage record sets + scores. stage1=extractor; stage2=+critic/re-research; stage3=+deterministic checkers (enum normalisation, MCP detector)."""
import json, glob, re, copy
from .util import ROOT
from .schema import derive, consistency_flags, ENUMS
from .score import score
vv = lambda r, k: (r.get(k) or {}).get("value") if isinstance(r.get(k), dict) else r.get(k)

def load_dir(d):
    return {json.load(open(f))["id"]: json.load(open(f)) for f in glob.glob(str(ROOT/"data"/d/"*.json"))}

def normalise(r):
    r = copy.deepcopy(r)
    for k, allowed in ENUMS.items():
        f = r.get(k)
        if not isinstance(f, dict): continue
        v = f.get("value")
        def fix(x):
            if isinstance(x, str):
                x = re.sub(r"\(.*?\)", "", x).strip().lower().replace(" ", "_")
            return x
        if isinstance(v, str) and "," in v: v = [fix(t) for t in v.split(",")]
        elif isinstance(v, list): v = [fix(t) for t in v]
        else: v = fix(v)
        if k in ("auth_methods", "api_type") and isinstance(v, str) and v != "unknown": v = [v]
        f["value"] = v
    b, bl = derive(r); r["buildability"] = {"value": b, "rule": "derive()"}; r["main_blocker"] = {"value": bl, "rule": "derive()"}
    return r

def stage3(r):
    r = normalise(r); d = json.load(open(ROOT/"data"/"mcp_detect.json")).get(str(r["id"]))
    if d and d[0] in ("official", "community", "none_found"):
        old = vv(r, "existing_mcp")
        if old != d[0]:
            r.setdefault("pass_history", []).append({"pass": 3, "field": "existing_mcp", "from": old, "to": d[0], "why": "deterministic MCP detector (who published the search hit)", "kind": "detector"})
            r["existing_mcp"] = {"value": d[0], "evidence_url": d[1], "quote": None, "grounded": "detector", "confidence": "medium"}
    return r

def build():
    p1 = load_dir("pass1"); p2 = {**p1, **load_dir("pass2")}
    S = {"stage1": [p1[i] for i in sorted(p1)], "stage2": [normalise(p2[i]) for i in sorted(p2)], "stage3": [stage3(p2[i]) for i in sorted(p2)]}
    gold = json.load(open(ROOT/"data"/"gold.json"))
    res = {k: score(v, gold) for k, v in S.items()}
    g1 = json.load(open(ROOT/"data"/"gold_v1_frozen.json"))
    for k, v in S.items(): res[k]["v1"] = score(v, g1)
    json.dump(S["stage3"], open(ROOT/"data"/"stage3.json", "w"))
    (ROOT/"data"/"final.jsonl").write_text("\n".join(json.dumps(r) for r in S["stage3"]) + "\n")
    return res
if __name__ == "__main__":
    for k, s in build().items(): print(k, s["overall"], {f: f'{v["correct"]}/{v["n"]}' for f, v in s["per_field"].items()})

"""Pattern analysis: pure code over the final JSONL. Every number on the page comes from here."""
import json, collections, sys
from .util import ROOT
C = collections.Counter
v = lambda r, k: ((r.get(k) or {}).get("value") if isinstance(r.get(k), dict) else r.get(k))

def load(path):
    return [json.loads(l) for l in open(path) if l.strip()]

def analyze(rows):
    ok = [r for r in rows if r.get("status") == "ok"]
    cats = sorted({r["category"] for r in rows}, key=lambda c: min(r["id"] for r in rows if r["category"] == c))
    known = lambda k: [r for r in ok if v(r, k) not in (None, "unknown", [])]
    out = {"n": len(rows), "n_ok": len(ok), "categories": cats}
    pa = C(v(r, "primary_auth") for r in known("primary_auth")); out["primary_auth"] = pa.most_common()
    am = C(m for r in known("auth_methods") for m in (v(r, "auth_methods") if isinstance(v(r, "auth_methods"), list) else [v(r, "auth_methods")]))
    out["auth_methods_any"] = am.most_common()
    out["multi_auth"] = sum(1 for r in known("auth_methods") if isinstance(v(r, "auth_methods"), list) and len(v(r, "auth_methods")) > 1)
    acc = C(v(r, "credential_access") for r in known("credential_access")); out["access"] = acc.most_common()
    selfserve = {"self_serve_free", "self_serve_trial"}
    out["self_serve_pct"] = round(100 * sum(acc[k] for k in selfserve) / max(1, sum(acc.values())))
    out["matrix"] = {c: dict(C(v(r, "credential_access") for r in known("credential_access") if r["category"] == c)) for c in cats}
    out["blockers"] = [(b, n, [r["app"] for r in ok if v(r, "main_blocker") == b]) for b, n in C(v(r, "main_blocker") for r in ok).most_common()]
    out["buildability"] = C(v(r, "buildability") for r in ok).most_common()
    out["mcp"] = C(v(r, "existing_mcp") for r in ok).most_common()
    out["breadth"] = C(v(r, "api_breadth") for r in ok).most_common()
    out["api_type"] = C(t for r in known("api_type") for t in (v(r, "api_type") if isinstance(v(r, "api_type"), list) else [v(r, "api_type")])).most_common()
    out["build_now"] = [r["app"] for r in ok if v(r, "buildability") == "ready_now"]
    out["outreach"] = [{"app": r["app"], "why": v(r, "credential_access"), "note": r.get("gating_notes")} for r in ok if v(r, "buildability") == "blocked"]
    out["effort"] = [r["app"] for r in ok if v(r, "buildability") == "buildable_with_effort"]
    out["composio_have"] = [r["app"] for r in rows if r.get("composio_toolkit") == "yes"]
    out["unknown_rate"] = {k: sum(1 for r in ok if v(r, k) in (None, "unknown")) for k in ["auth_methods", "primary_auth", "credential_access", "api_type", "api_breadth", "existing_mcp"]}
    out["defeated"] = [{"app": r["app"], "id": r["id"], "why": r.get("error") or ("unknown: " + ", ".join(k for k in out["unknown_rate"] if v(r, k) in (None, "unknown")))}
                       for r in rows if r.get("status") != "ok" or sum(v(r, k) in (None, "unknown") for k in out["unknown_rate"]) >= 3]
    # 2x2: access (self-serve vs gated) x breadth
    quad = collections.defaultdict(list)
    for r in ok:
        ss = v(r, "credential_access") in selfserve; br = v(r, "api_breadth") in ("broad", "moderate")
        if v(r, "credential_access") in (None, "unknown") or v(r, "api_breadth") in (None, "unknown"): continue
        quad[("self-serve" if ss else "gated") + " / " + ("broad-moderate" if br else "narrow")].append(r["app"])
    out["quadrants"] = dict(quad)
    return out

if __name__ == "__main__":
    p = sys.argv[1] if len(sys.argv) > 1 else str(ROOT / "data" / "pass1.jsonl")
    a = analyze(load(p)); (ROOT / "data" / "analysis.json").write_text(json.dumps(a, indent=1)); print(json.dumps(a, indent=1)[:3000])

"""One Gemini call per app -> strict JSON with verbatim quotes; then deterministic grounding."""
import json, os
from .util import key, post, norm
from .schema import ENUMS, SCORED, derive, consistency_flags

FIELD_DEFS = """
auth_methods: list from %(auth)s - every method the public API accepts (personal access token = bearer_token)
primary_auth: one of %(auth)s - what a multi-tenant agent toolkit would use; prefer oauth2 if offered
credential_access: one of %(acc)s - the CHEAPEST path for a developer to get working credentials (free sandbox/trial counts as self-serve; nuance goes to gating_notes)
api_type: list from %(api)s
api_breadth: broad(>50 endpoints) | moderate(10-50) | narrow(<10)
existing_mcp: official (published by the vendor) | community | none_found
""" 

KW = ["oauth","api key","api-key","token","bearer","basic auth","authenticat","authoriz","scope","free","trial","sandbox","pricing","plan","paid","enterprise","partner","approval","review","contact","sales","request access","mcp","rest","graphql","endpoint","openapi","webhook","developer","credential","secret","client_id","app"]
def snippet(text, budget=1300):
    """Keyword-dense lines of a page, in original order, verbatim (so quotes still ground)."""
    lines = [l.strip() for l in text.split("\n") if len(l.strip()) > 25]
    sc = sorted(range(len(lines)), key=lambda i: -sum(k in lines[i].lower() for k in KW))
    keep, used = set(), 0
    for i in sc:
        if used + min(len(lines[i]), 300) > budget: continue
        keep.add(i); used += min(len(lines[i]), 300)
    return "\n".join(lines[i][:300] for i in sorted(keep))

def prompt(app, category, pages, note=""):
    from .schema import AUTH, ACCESS, APITYPE
    d = FIELD_DEFS % {"auth": AUTH, "acc": ACCESS, "api": APITYPE}
    src = "\n\n".join(f"[SOURCE {i}] {p['url']}\n{snippet(p['text'])}" for i, p in enumerate(pages))
    return f"""You research whether an AI-agent toolkit can be built for the app "{app}" ({category}).
Use ONLY the sources below. For each field return {{"value":..., "source": <SOURCE number>, "quote": <VERBATIM text copied from that source, <=200 chars>, "confidence":"high|medium|low"}}.
If the sources do not show it, value="unknown", source=null, quote=null. Never guess.
Fields:{d}
Also return: one_liner (<=20 words, plain string), subcategory (string), gating_notes (string), oauth_details (string), docs_url (string|null), openapi_spec (url|null), mcp_url (url|null).
{('CRITIC NOTE to address: '+note) if note else ''}
Return a single JSON object with keys: one_liner, subcategory, gating_notes, oauth_details, docs_url, openapi_spec, mcp_url, {", ".join(ENUMS if False else ['auth_methods','primary_auth','credential_access','api_type','api_breadth','existing_mcp'])}.

EXAMPLE of the required shape for each of the six scored fields (do NOT return bare values):
"auth_methods": {{"value": ["oauth2","api_key"], "source": 2, "quote": "exact sentence copied from SOURCE 2", "confidence": "high"}}

SOURCES:
{src}"""

MODELS = ["openai/gpt-oss-20b", "qwen/qwen3.8-27b"]  # gpt-oss-120b used for early apps until its 200k tokens/day cap
def extractor_for(app_id): return MODELS[app_id % 2]      # two Groq models, separate rate-limit buckets
def critic_for(app_id): return MODELS[(app_id + 1) % 2]    # critic is always the OTHER model than the extractor

def groq_extract(p, model):
    from .critic import groq_raw
    return groq_raw(model, "Reply with one JSON object only.", p)

def gemini(p, model=None):
    if os.environ.get("EXTRACT_PROVIDER","gemini") == "groq": return groq_extract(p, model)
    m = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    r = post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={key('GEMINI_API_KEY')}", {},
             {"contents": [{"parts": [{"text": p}]}], "generationConfig": {"responseMimeType": "application/json", "temperature": 0}}, timeout=180)
    return json.loads(r["candidates"][0]["content"]["parts"][0]["text"])

def quote_ok(q, text):
    """exact (normalised) substring, else >=70% of the quote's word 4-grams occur in the page ('fuzzy', logged)."""
    nq, nt = norm(q), norm(text)
    if nq in nt: return "exact"
    w = nq.split()
    if len(w) < 6: return None
    g = {" ".join(w[i:i+4]) for i in range(len(w)-3)}
    tw = nt.split(); tg = {" ".join(tw[i:i+4]) for i in range(len(tw)-3)}
    return "fuzzy" if len(g & tg) / len(g) >= 0.7 else None

def ground(rec, pages):
    """Quote must appear in cited page (whitespace-normalised) else field -> unknown."""
    for k in SCORED[:3] + ["api_type", "api_breadth", "existing_mcp"]:
        f = rec.get(k)
        if not isinstance(f, dict) or f.get("value") in (None, "unknown"): continue
        s, q = f.get("source"), f.get("quote")
        ok = isinstance(s, int) and 0 <= s < len(pages) and q and quote_ok(q, pages[s]["text"])
        if ok: f["evidence_url"] = pages[s]["url"]; f["grounded"] = ok
        else:
            f["ungrounded_value"] = f["value"]; f["value"] = "unknown"; f["confidence"] = "low"; f["grounded"] = False
    return rec

def extract(app, category, pages, note="", app_id=0):
    rec = gemini(prompt(app, category, pages, note), extractor_for(app_id))
    rec["extractor_model"] = extractor_for(app_id)
    for k in ["auth_methods","primary_auth","credential_access","api_type","api_breadth","existing_mcp"]:
        f = rec.get(k)
        if not isinstance(f, dict): rec[k] = {"value": f if f is not None else "unknown", "source": None, "quote": None, "confidence": "low"}
        elif "value" not in f: f["value"] = "unknown"
    rec = ground(rec, pages)
    b, bl = derive(rec)
    rec["buildability"] = {"value": b, "rule": "derive()"}; rec["main_blocker"] = {"value": bl, "rule": "derive()"}
    rec["flags"] = consistency_flags(rec)
    rec["sources"] = [p["url"] for p in pages]
    return rec

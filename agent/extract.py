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

def prompt(app, category, pages, note=""):
    from .schema import AUTH, ACCESS, APITYPE
    d = FIELD_DEFS % {"auth": AUTH, "acc": ACCESS, "api": APITYPE}
    src = "\n\n".join(f"[SOURCE {i}] {p['url']}\n{p['text'][:2500]}" for i, p in enumerate(pages))
    return f"""You research whether an AI-agent toolkit can be built for the app "{app}" ({category}).
Use ONLY the sources below. For each field return {{"value":..., "source": <SOURCE number>, "quote": <VERBATIM text copied from that source, <=200 chars>, "confidence":"high|medium|low"}}.
If the sources do not show it, value="unknown", source=null, quote=null. Never guess.
Fields:{d}
Also return: one_liner (<=20 words, plain string), subcategory (string), gating_notes (string), oauth_details (string), docs_url (string|null), openapi_spec (url|null), mcp_url (url|null).
{('CRITIC NOTE to address: '+note) if note else ''}
Return a single JSON object with keys: one_liner, subcategory, gating_notes, oauth_details, docs_url, openapi_spec, mcp_url, {", ".join(ENUMS if False else ['auth_methods','primary_auth','credential_access','api_type','api_breadth','existing_mcp'])}.

SOURCES:
{src}"""

def groq_extract(p):
    from .critic import groq_raw
    return groq_raw(os.environ.get("EXTRACT_MODEL","openai/gpt-oss-120b"), "Reply with one JSON object only.", p)

def gemini(p):
    if os.environ.get("EXTRACT_PROVIDER","gemini") == "groq": return groq_extract(p)
    m = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")
    r = post(f"https://generativelanguage.googleapis.com/v1beta/models/{m}:generateContent?key={key('GEMINI_API_KEY')}", {},
             {"contents": [{"parts": [{"text": p}]}], "generationConfig": {"responseMimeType": "application/json", "temperature": 0}}, timeout=180)
    return json.loads(r["candidates"][0]["content"]["parts"][0]["text"])

def ground(rec, pages):
    """Quote must appear in cited page (whitespace-normalised) else field -> unknown."""
    for k in SCORED[:3] + ["api_type", "api_breadth", "existing_mcp"]:
        f = rec.get(k)
        if not isinstance(f, dict) or f.get("value") in (None, "unknown"): continue
        s, q = f.get("source"), f.get("quote")
        ok = isinstance(s, int) and 0 <= s < len(pages) and q and norm(q) in norm(pages[s]["text"])
        if ok: f["evidence_url"] = pages[s]["url"]
        else:
            f["ungrounded_value"] = f["value"]; f["value"] = "unknown"; f["confidence"] = "low"; f["grounded"] = False
    return rec

def extract(app, category, pages, note=""):
    rec = gemini(prompt(app, category, pages, note))
    rec = ground(rec, pages)
    b, bl = derive(rec)
    rec["buildability"] = {"value": b, "rule": "derive()"}; rec["main_blocker"] = {"value": bl, "rule": "derive()"}
    rec["flags"] = consistency_flags(rec)
    rec["sources"] = [p["url"] for p in pages]
    return rec

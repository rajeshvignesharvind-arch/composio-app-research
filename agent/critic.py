"""Pass 2. A different model than the extractor checks the extractor's claims (cheap, batched), with free code checks first."""
import json, os
from .util import key, post, norm
from .fetch import scrape, search
from .extract import critic_for, quote_ok

import itertools, threading
_KEYS = [os.environ[k] for k in ("GROQ_API_KEY", "GROQ_API_KEY_2") if os.environ.get(k)]
_rr = itertools.cycle(range(max(1, len(_KEYS)))); _lock = threading.Lock()
def _next_key():
    with _lock: return _KEYS[next(_rr)] if _KEYS else key("GROQ_API_KEY")   # round-robin: keys used for quota only

def groq_raw(model, sys, user):
    r = post("https://api.groq.com/openai/v1/chat/completions", {"Authorization": f"Bearer {_next_key()}"},
             {"model": model, "temperature": 0, **({"reasoning_effort": "low"} if "gpt-oss" in model else {}),
              "response_format": {"type": "json_object"}, "messages": [{"role": "system", "content": sys}, {"role": "user", "content": user}]})
    return json.loads(r["choices"][0]["message"]["content"])

FIELDS = ["auth_methods", "primary_auth", "credential_access", "api_type", "api_breadth", "existing_mcp"]
DEFS = ("credential_access = cheapest path for a developer to get WORKING credentials (free sandbox/trial/free tier = self_serve; credentials only via sales, a paying customer's admin, or a partner programme = gated). "
        "existing_mcp = official only if published by the vendor itself.")

def critique(app, rec, app_id=0):
    cm = critic_for(app_id); flags = []
    # 1. free checks: unknown/ungrounded, live re-fetch of the cited page, consistency rules
    for k in FIELDS:
        f = rec.get(k) or {}
        if f.get("value") in ("unknown", None):
            flags.append({"field": k, "note": f"agent could not ground a value (it proposed {f.get('ungrounded_value')!r})" if f.get("ungrounded_value") else "no value found", "kind": "unknown"}); continue
        url = f.get("evidence_url")
        if url and f.get("quote"):
            live = scrape(url)["text"]
            if live and not quote_ok(f["quote"], live): flags.append({"field": k, "note": "quote not found on live re-fetch", "kind": "refetch"})
    for fl in rec.get("flags", []): flags.append({"field": fl, "note": "consistency rule", "kind": "rule"})
    # 2. one batched judge call (other model): does each quote support its value?
    claims = {k: {"value": rec[k]["value"], "quote": (rec[k].get("quote") or "")[:220]} for k in FIELDS if isinstance(rec.get(k), dict) and rec[k].get("value") not in ("unknown", None)}
    if claims:
        v = groq_raw(cm, 'You are a strict fact-checker. Reply JSON {"<field>": {"verdict":"supported|unsupported|contradicted","reason":"<=20 words"}} for every field given. ' + DEFS,
                     f"App: {app}\nClaims with the quote each rests on:\n{json.dumps(claims)}")
        for k, x in (v or {}).items():
            if isinstance(x, dict) and x.get("verdict") in ("unsupported", "contradicted") and k in claims:
                flags.append({"field": k, "note": x.get("reason", ""), "kind": "judge"})
    # 3. adversarial: independent search for the two fields extractors get wrong most
    hits = search(f"{app} developer API free sandbox OR trial OR partner program OR sales access", 3) + search(f"{app} official MCP server", 3)
    ctx = "\n".join(f"{h['url']}: {h['snippet'][:260]}" for h in hits)
    cur = {k: rec.get(k, {}).get("value") for k in ("credential_access", "existing_mcp")}
    v = groq_raw(cm, 'Be sceptical. Reply JSON {"credential_access":{"change":true|false,"to":"<enum or null>","reason":"..."},"existing_mcp":{"change":true|false,"to":"official|community|none_found|null","reason":"..."}}. Only say change=true if the search results clearly show it. ' + DEFS,
                 f"App {app}. Current: {json.dumps(cur)}\nSearch results:\n{ctx}")
    for k, x in (v or {}).items():
        if isinstance(x, dict) and x.get("change") and k in cur:
            flags.append({"field": k, "note": x.get("reason", ""), "kind": "adversarial", "suggest": x.get("to"), "extra_urls": [h["url"] for h in hits[:4]]})
    return flags

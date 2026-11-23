"""Pass 2: a different model family (Groq) judges each field against its quote + a live re-fetch, plus adversarial questions."""
import json, os
from .util import key, post, norm
from .fetch import scrape, search

def groq(sys, user): return groq_raw(os.environ.get("GROQ_MODEL", "qwen/qwen3.8-27b"), sys, user)

def groq_raw(model, sys, user):
    r = post("https://api.groq.com/openai/v1/chat/completions", {"Authorization": f"Bearer {key('GROQ_API_KEY')}"},
             {"model": model, "temperature": 0, "response_format": {"type": "json_object"},
              "messages": [{"role": "system", "content": sys}, {"role": "user", "content": user}]})
    return json.loads(r["choices"][0]["message"]["content"])

SYS = "You are a strict fact-checker. Reply JSON: {\"verdict\":\"supported|unsupported|contradicted\",\"reason\":\"...\"}."

def judge_field(app, name, f, page_text):
    return groq(SYS, f"App: {app}\nField: {name}\nClaimed value: {f['value']}\nQuote: {f.get('quote')}\nPage excerpt:\n{page_text[:6000]}\nDoes the page support the claimed value for this field?")

ADV = {
 "credential_access": "Is there a free developer sandbox/trial or self-serve signup that the claim missed, or is access actually limited to approved partners / paid tiers?",
 "existing_mcp": "Is the MCP server published by the vendor itself (official) or by a third party (community)?",
 "auth_methods": "Does the public API really accept every listed method, and are any missing (e.g. OAuth2 for third parties)?",
}

def critique(app, rec):
    """Return list of flagged fields with notes (re-fetch + judge + adversarial search)."""
    flags = []
    for k in ["auth_methods", "primary_auth", "credential_access", "api_type", "api_breadth", "existing_mcp"]:
        f = rec.get(k) or {}
        if f.get("value") == "unknown":
            flags.append({"field": k, "note": "value unknown/ungrounded; look harder", "kind": "unknown"}); continue
        url = f.get("evidence_url")
        live = scrape(url)["text"] if url else ""
        if f.get("quote") and norm(f["quote"]) not in norm(live):
            flags.append({"field": k, "note": "quote not found on live re-fetch", "kind": "refetch"}); continue
        v = judge_field(app, k, f, live)
        if v.get("verdict") != "supported": flags.append({"field": k, "note": v.get("reason", ""), "kind": "judge"})
    for k, q in ADV.items():
        hits = search(f"{app} {q}", 3)
        ctx = "\n".join(f"{h['url']}: {h['snippet']}" for h in hits)
        v = groq("Reply JSON {\"change_needed\":true|false,\"reason\":\"...\"}.",
                 f"App {app}. Current {k}={rec.get(k,{}).get('value')}. Question: {q}\nSearch results:\n{ctx}")
        if v.get("change_needed"): flags.append({"field": k, "note": v.get("reason", ""), "kind": "adversarial", "extra_urls": [h['url'] for h in hits]})
    for fl in rec.get("flags", []): flags.append({"field": fl, "note": "consistency rule", "kind": "rule"})
    return flags

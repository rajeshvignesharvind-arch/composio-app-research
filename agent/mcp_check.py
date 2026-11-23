"""Deterministic MCP detector (verification loop 3): classify existing_mcp from search results by WHO published the hit. No LLM."""
import re, json, yaml
from urllib.parse import urlparse
from .fetch import search, root_domain
from .util import ROOT
HOSTS_3P = ("glama.ai", "smithery.ai", "pulsemcp.com", "mcp.so", "lobehub.com", "playbooks.com", "mcpservers.org", "scalekit.com", "composio.dev", "npmjs.com", "pypi.org", "medium.com", "reddit.com", "youtube.com")
def tokens(app): return {t for t in re.sub(r"[^a-z0-9 ]", " ", app.lower()).split() if len(t) > 2} | {re.sub(r"[^a-z0-9]", "", app.lower())}
def classify(app, hint):
    dom = root_domain(hint); toks = tokens(app); off = []; com = []
    for q in (f"{app} MCP server", f"{app} official MCP server"):
        for h in search(q, 4) + search(q, 3):
            u = h["url"]; txt = (h["title"] + " " + h["snippet"] + " " + u).lower()
            if "mcp" not in txt: continue
            p = urlparse(u); host = p.netloc.lower().replace("www.", ""); parts = [x for x in p.path.split("/") if x]
            if host.endswith(dom) and host != "github.com": off.append(u)
            elif host == "github.com" and parts and (parts[0].lower() in toks or parts[0].lower() == dom.split(".")[0]): off.append(u)
            elif any(host.endswith(x) for x in HOSTS_3P) or host == "github.com": com.append(u)
            elif any(t in host for t in toks): off.append(u)
    return ("official", off[0]) if off else (("community", com[0]) if com else ("none_found", None))
if __name__ == "__main__":
    apps = yaml.safe_load((ROOT/"data"/"apps.yaml").read_text()); out = {}
    for a in apps:
        try: out[a["id"]] = classify(a["app"], a["hint"])
        except Exception as e: out[a["id"]] = ("error", str(e)[:80])
    (ROOT/"data"/"mcp_detect.json").write_text(json.dumps(out, indent=1))
    from collections import Counter; print(Counter(v[0] for v in out.values()))

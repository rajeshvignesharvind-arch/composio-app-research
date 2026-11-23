"""Search (Tavily) + scrape (Firecrawl, Jina Reader fallback). Everything cached to disk."""
import httpx
from urllib.parse import urlparse
from .util import key, cached, post
import os

def search(q, n=5, domain=None):
    def go():
        body = {"query": q, "max_results": n, "search_depth": "basic"}
        if domain: body["include_domains"] = [domain]
        r = post("https://api.tavily.com/search", {"Authorization": f"Bearer {key('TAVILY_API_KEY')}"}, body)
        return [{"url": x["url"], "title": x.get("title",""), "snippet": x.get("content","")[:300]} for x in r.get("results",[])]
    return cached("s:"+q+"|"+str(domain), go)

def scrape(url, max_chars=4500):
    def go():
        try:
            r = post("https://api.firecrawl.dev/v1/scrape", {"Authorization": f"Bearer {key('FIRECRAWL_API_KEY')}"},
                     {"url": url, "formats": ["markdown"], "onlyMainContent": True}, retries=2, timeout=60)
            md = (r.get("data") or {}).get("markdown") or ""
            if len(md) > 300: return {"url": url, "text": md[:max_chars], "via": "firecrawl"}
        except Exception: pass
        try:
            h = {"Accept": "text/plain"}
            if os.environ.get("JINA_API_KEY"): h["Authorization"] = "Bearer "+os.environ["JINA_API_KEY"]
            t = httpx.get("https://r.jina.ai/"+url, headers=h, timeout=60, follow_redirects=True).text
            return {"url": url, "text": t[:max_chars], "via": "jina", "thin": len(t) < 300}
        except Exception as e:
            return {"url": url, "text": "", "via": "failed", "error": str(e)[:100]}
    return cached("p:"+url, go)

def vendor_boost(results, hint):
    host = urlparse(hint if "://" in hint else "https://"+hint).netloc.split(":")[0]
    root = ".".join(host.split(".")[-2:]) if host else ""
    return sorted(results, key=lambda r: 0 if root and root in r["url"] else 1)

def root_domain(hint):
    host = urlparse(hint if "://" in hint else "https://"+hint.split(" ")[0]).netloc.split(":")[0]
    p = host.split(".")
    return ".".join(p[-2:]) if len(p) >= 2 else host

def gather(app, hint):
    """Discover + fetch up to 6 pages. Identity is pinned to the hint domain: vendor-restricted searches first, one open search for MCP/pricing context."""
    dom = root_domain(hint)
    qs = [f"{app} API authentication", f"{app} API reference documentation", f"{app} developer account pricing partner program access"]
    urls = [hint if hint.startswith("http") else "https://"+hint.split(" ")[0]]
    hits = []
    for q in qs:
        try: hits += search(q, 3, dom)[:2]
        except Exception: pass
    hits += search(f"{app} MCP server", 4)[:3]   # open web: MCP often lives on GitHub/registries
    for h in hits:
        if h["url"] not in urls: urls.append(h["url"])
    urls = urls[:6]
    pages = [scrape(u) for u in urls]
    return [p for p in pages if p["text"]], hits

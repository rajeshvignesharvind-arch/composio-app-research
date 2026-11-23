import os, json, hashlib, pathlib, re, time
import httpx
ROOT = pathlib.Path(__file__).resolve().parent.parent
CACHE = ROOT/"data"/"cache"; CACHE.mkdir(parents=True, exist_ok=True)

def load_env():
    p = ROOT/".env"
    if p.exists():
        for l in p.read_text().splitlines():
            if "=" in l and not l.startswith("#"):
                k, v = l.split("=",1); os.environ.setdefault(k.strip(), v.split("#")[0].strip())
load_env()
def key(n): 
    v = os.environ.get(n); 
    if not v: raise SystemExit(f"missing env {n} (see .env.example)")
    return v

def cached(name, fn):
    p = CACHE/(hashlib.sha1(name.encode()).hexdigest()+".json")
    if p.exists(): return json.loads(p.read_text())
    out = fn(); p.write_text(json.dumps(out)); return out

def norm(s):
    s = (s or "").translate({0x2011:"-",0x2010:"-",0x2013:"-",0x2014:"-",0x2019:"'",0x2018:"'",0x201c:'"',0x201d:'"',0xa0:" "})
    s = re.sub(r"[*_`#>\[\]\\]", "", s)
    return re.sub(r"\s+"," ",s).strip().lower()

def post(url, headers, body, retries=6, timeout=90):
    for i in range(retries):
        try:
            r = httpx.post(url, headers=headers, json=body, timeout=timeout)
            if r.status_code in (429,500,502,503):
                w = float(r.headers.get('retry-after') or 2**i*3); print('retry', r.status_code, w, flush=True); time.sleep(min(w, 60)); continue
            r.raise_for_status(); return r.json()
        except httpx.HTTPError as e:
            if i == retries-1: raise
            time.sleep(2**i*2)

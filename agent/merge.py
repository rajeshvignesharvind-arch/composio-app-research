"""Assemble data/pass1.jsonl from per-app results; final.jsonl = pass2 if present else pass1."""
import json, glob, yaml, pathlib
from .util import ROOT
rows = {}
for f in glob.glob(str(ROOT/"data"/"pass1"/"*.json")):
    r = json.load(open(f)); rows[r["id"]] = r
apps = yaml.safe_load((ROOT/"data"/"apps.yaml").read_text())
for a in apps: rows.setdefault(a["id"], {**a, "status": "not_run"})
p1 = [rows[a["id"]] for a in apps]
(ROOT/"data"/"pass1.jsonl").write_text("\n".join(json.dumps(r) for r in p1)+"\n")
p2f = ROOT/"data"/"pass2"
if p2f.exists() and list(p2f.glob("*.json")):
    for f in p2f.glob("*.json"):
        r = json.load(open(f)); rows[r["id"]] = r
(ROOT/"data"/"final.jsonl").write_text("\n".join(json.dumps(rows[a["id"]]) for a in apps)+"\n")
print(sum(1 for r in rows.values() if r.get("status")=="ok"), "ok of", len(rows))

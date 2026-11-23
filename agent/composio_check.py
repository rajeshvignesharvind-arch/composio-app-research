"""Does Composio already list this app? Checks the public toolkit docs page (200 vs 404); no key needed."""
import re, json, httpx, concurrent.futures as cf, yaml
from .util import ROOT
MANUAL = {"Lark (Larksuite)": ["lark", "larksuite"], "Magento (Adobe Commerce)": ["magento", "adobe_commerce"], "WhatsApp Business": ["whatsapp"],
          "Meta Ads": ["metaads", "facebook"], "Google Ads": ["googleads"], "Threads (Meta)": ["threads"], "Amazon Selling Partner": ["amazon"],
          "Salesforce Commerce Cloud": ["salesforce_commerce_cloud"], "NotebookLM": ["notebooklm"], "Otter AI": ["otter", "otterai"], "Monday.com": ["monday"],
          "MongoDB Atlas": ["mongodb", "mongodbatlas"], "YouTube Transcript": ["youtube_transcript"], "Mermaid CLI": ["mermaid"], "GoHighLevel": ["highlevel", "gohighlevel"], "Zoho Cliq": ["zoho_cliq", "zohocliq"], "Zoho CRM": ["zoho_crm", "zoho"]}
def slugs(app):
    b = re.sub(r"[^a-z0-9 ]", " ", app.lower()).split()
    return MANUAL.get(app, []) + ["".join(b), "_".join(b), "-".join(b), b[0]]
def check(a):
    for s in dict.fromkeys(slugs(a["app"])):
        try:
            if httpx.get(f"https://docs.composio.dev/toolkits/{s}", timeout=20, follow_redirects=True).status_code == 200:
                return a["id"], s
        except Exception: pass
    return a["id"], None
if __name__ == "__main__":
    apps = yaml.safe_load((ROOT/"data"/"apps.yaml").read_text())
    with cf.ThreadPoolExecutor(8) as ex: res = dict(ex.map(check, apps))
    (ROOT/"data"/"composio.json").write_text(json.dumps(res, indent=1))
    print(sum(1 for v in res.values() if v), "of", len(res), "have a Composio toolkit page")
    print([a["app"] for a in apps if not res[a["id"]]])

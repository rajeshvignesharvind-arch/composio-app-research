"""Closed-enum record schema. Every researched field = {value, source, quote, confidence}."""
from typing import Literal, Optional
from pydantic import BaseModel

AUTH = ["oauth2","api_key","bearer_token","basic","jwt_service_account","hmac_signature","session_cookie","none","other"]
ACCESS = ["self_serve_free","self_serve_trial","paid_plan","admin_approval","partner_gated","sales_contact","no_public_api"]
APITYPE = ["rest","graphql","grpc","websocket","sdk_only","cli_only","none"]
BREADTH = ["broad","moderate","narrow"]
MCP = ["official","community","none_found"]
BUILD = ["ready_now","buildable_with_effort","blocked"]
BLOCKER = ["none","partner_approval","paid_plan","app_review","no_public_api","narrow_api","docs_gated","per_tenant_setup","other"]
SCORED = ["auth_methods","primary_auth","credential_access","api_type","api_breadth","existing_mcp","buildability","main_blocker"]

class Field(BaseModel):
    value: object = "unknown"
    source: Optional[int] = None      # index into the numbered sources given to the model
    quote: Optional[str] = None       # verbatim quote from that source
    confidence: Literal["high","medium","low"] = "low"

ENUMS = {"auth_methods":AUTH,"primary_auth":AUTH,"credential_access":ACCESS,"api_type":APITYPE,
         "api_breadth":BREADTH,"existing_mcp":MCP,"buildability":BUILD,"main_blocker":BLOCKER}

def derive(r: dict) -> tuple[str, str]:
    """Deterministic buildability/blocker rule over the other fields (the model may not override silently)."""
    g = lambda k: (r.get(k) or {}).get("value")
    acc, br, typ = g("credential_access"), g("api_breadth"), g("api_type") or []
    if acc == "no_public_api" or typ in ([], ["none"], ["cli_only"], ["sdk_only"]): return "blocked","no_public_api"
    if acc in ("partner_gated","sales_contact"): return "blocked","partner_approval"
    if acc == "paid_plan": return "buildable_with_effort","paid_plan"
    if acc == "admin_approval": return "buildable_with_effort","app_review"
    if br == "narrow": return "buildable_with_effort","narrow_api"
    if acc in ("self_serve_free","self_serve_trial") and br in ("broad","moderate"): return "ready_now","none"
    return "buildable_with_effort","other"

def consistency_flags(r: dict) -> list[str]:
    g = lambda k: (r.get(k) or {}).get("value")
    f = []
    if g("credential_access") in ("partner_gated","sales_contact") and g("buildability") == "ready_now": f.append("gated_but_ready")
    if "oauth2" in (g("auth_methods") or []) and not (r.get("auth_methods") or {}).get("quote"): f.append("oauth_without_evidence")
    if not r.get("docs_url") and g("api_breadth") == "broad": f.append("broad_without_docs")
    for k, allowed in ENUMS.items():
        v = g(k); vs = v if isinstance(v, list) else [v]
        if any(x not in allowed + ["unknown"] for x in vs): f.append(f"bad_enum:{k}")
    return f

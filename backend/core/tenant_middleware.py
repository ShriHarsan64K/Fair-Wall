"""
backend/core/tenant_middleware.py
FastAPI middleware — validates X-API-Key header and injects tenant_id into
request.state for all downstream modules.
Segment 1 — Foundation.
"""

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from .tenant_registry import resolve_tenant


class TenantMiddleware(BaseHTTPMiddleware):
    """
    Reads X-API-Key from every request (except excluded paths).
    On valid key → injects tenant_id, tenant_name, allowed_domains into request.state.
    On invalid key → returns 401.
    On disallowed domain → returns 403.

    Domain check is skipped here to avoid reading the JSON body twice
    (which would break FastAPI's body parsing). Domain is validated inside
    each endpoint that needs it using request.state.allowed_domains.
    """

    EXCLUDED_PATHS: set[str] = {"/health", "/docs", "/openapi.json", "/redoc"}

    async def dispatch(self, request: Request, call_next):
        # Skip auth for public endpoints
        if request.url.path in self.EXCLUDED_PATHS:
            return await call_next(request)

        api_key = request.headers.get("X-API-Key", "").strip()
        tenant = resolve_tenant(api_key)

        if not tenant:
            return JSONResponse(
                {"error": "Invalid or missing API key", "code": "INVALID_KEY"},
                status_code=401,
            )

        # Inject into request state — available in all downstream handlers
        request.state.tenant_id = tenant["tenant_id"]
        request.state.tenant_name = tenant["name"]
        request.state.allowed_domains = tenant["domains"]
        request.state.api_key = api_key

        return await call_next(request)


def check_domain(request: Request, domain: str) -> JSONResponse | None:
    """
    Call this inside any endpoint that accepts a domain parameter.
    Returns a 403 JSONResponse if domain is not allowed, else None.

    Usage in endpoint:
        err = check_domain(request, payload.domain)
        if err:
            return err
    """
    if domain not in request.state.allowed_domains:
        return JSONResponse(
            {
                "error": f"Domain '{domain}' is not enabled for this tenant",
                "allowed": request.state.allowed_domains,
                "code": "DOMAIN_NOT_ALLOWED",
            },
            status_code=403,
        )
    return None


# ── test ──────────────────────────────────────────────────────────────────────
# Run backend then:
# curl http://localhost:8000/trust-score                         → 401
# curl http://localhost:8000/trust-score -H "X-API-Key: bad"    → 401
# curl http://localhost:8000/trust-score -H "X-API-Key: fw-demo-key-2026" → 200

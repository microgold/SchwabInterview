from __future__ import annotations

import hmac

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse

from app.config import load_settings
from app.models import AnalyticsResponse, ShortenRequest, ShortenResponse, UrlInfoResponse
from app.repository import UrlRepository
from app.security import InMemoryRateLimiter
from app.service import AliasAlreadyExistsError, UrlExpiredError, UrlNotFoundError, UrlService

settings = load_settings()
repository = UrlRepository(settings.database_path)
service = UrlService(repository=repository, default_ttl_days=settings.default_ttl_days)

app = FastAPI(title="Agentic URL Shortener", version="1.0.0")
api_limiter = InMemoryRateLimiter(max_requests=settings.api_rate_limit_per_minute, window_seconds=60)
redirect_limiter = InMemoryRateLimiter(max_requests=settings.redirect_rate_limit_per_minute, window_seconds=60)

UI_HTML = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8" />
  <meta name="viewport" content="width=device-width, initial-scale=1" />
  <title>URL Shortener - Interactive UI</title>
  <style>
    body { font-family: Arial, sans-serif; margin: 2rem auto; max-width: 900px; line-height: 1.4; }
    h1 { margin-bottom: 0.5rem; }
    .card { border: 1px solid #ddd; border-radius: 8px; padding: 1rem; margin: 1rem 0; }
    .grid { display: grid; grid-template-columns: 1fr 1fr; gap: 0.75rem; }
    label { font-weight: 600; }
    input { width: 100%; padding: 0.5rem; }
    button { padding: 0.55rem 0.9rem; cursor: pointer; }
    code, pre { background: #f4f4f4; border-radius: 6px; padding: 0.2rem 0.35rem; }
    pre { padding: 0.8rem; overflow-x: auto; }
    .error { color: #b00020; font-weight: 600; }
  </style>
</head>
<body>
  <h1>Agentic URL Shortener</h1>
  <p>Use this page to create short links and inspect analytics interactively.</p>

  <section class="card">
    <h2>Create short URL</h2>
    <div style="margin-bottom:0.75rem;">
      <label for="api_key">API key</label>
      <input id="api_key" type="text" value="dev-interview-key" />
    </div>
    <form id="create-form">
      <div class="grid">
        <div>
          <label for="url">Original URL</label>
          <input id="url" type="url" required placeholder="https://example.com/page" />
        </div>
        <div>
          <label for="custom_alias">Custom alias (optional)</label>
          <input id="custom_alias" type="text" placeholder="my-alias" />
        </div>
      </div>
      <div style="margin-top:0.75rem;">
        <label for="ttl_days">TTL days (optional)</label>
        <input id="ttl_days" type="number" min="1" max="3650" placeholder="30" />
      </div>
      <div style="margin-top:0.75rem;">
        <button type="submit">Shorten URL</button>
      </div>
    </form>
    <p id="create-error" class="error"></p>
    <pre id="create-result"></pre>
  </section>

  <section class="card">
    <h2>Inspect short code</h2>
    <div class="grid">
      <div>
        <label for="lookup_code">Short code</label>
        <input id="lookup_code" type="text" placeholder="abc1234" />
      </div>
      <div style="display:flex; align-items:end; gap:0.5rem;">
        <button id="lookup-btn" type="button">Get URL Info</button>
        <button id="analytics-btn" type="button">Get Analytics</button>
        <button id="open-btn" type="button">Open Redirect</button>
      </div>
    </div>
    <p id="lookup-error" class="error"></p>
    <pre id="lookup-result"></pre>
  </section>

  <script>
    const createForm = document.getElementById("create-form");
    const createError = document.getElementById("create-error");
    const createResult = document.getElementById("create-result");
    const lookupInput = document.getElementById("lookup_code");
    const lookupError = document.getElementById("lookup-error");
    const lookupResult = document.getElementById("lookup-result");

    function clearErrors() {
      createError.textContent = "";
      lookupError.textContent = "";
    }

    function showJson(target, data) {
      target.textContent = JSON.stringify(data, null, 2);
    }

    function buildAuthHeaders(includeJsonContentType = false) {
      const headers = {};
      const apiKey = document.getElementById("api_key").value.trim();
      if (apiKey) {
        headers["X-API-Key"] = apiKey;
      }
      if (includeJsonContentType) {
        headers["Content-Type"] = "application/json";
      }
      return headers;
    }

    createForm.addEventListener("submit", async (event) => {
      event.preventDefault();
      clearErrors();

      const payload = {
        url: document.getElementById("url").value.trim(),
      };
      const alias = document.getElementById("custom_alias").value.trim();
      const ttl = document.getElementById("ttl_days").value.trim();
      if (alias) payload.custom_alias = alias;
      if (ttl) payload.ttl_days = Number(ttl);

      const response = await fetch("/api/v1/shorten", {
        method: "POST",
        headers: buildAuthHeaders(true),
        body: JSON.stringify(payload),
      });
      const body = await response.json();
      if (!response.ok) {
        createError.textContent = body.detail || "Request failed";
        createResult.textContent = "";
        return;
      }
      showJson(createResult, body);
      lookupInput.value = body.short_code;
    });

    async function fetchAndRender(url) {
      clearErrors();
      const response = await fetch(url, { headers: buildAuthHeaders(false) });
      const body = await response.json();
      if (!response.ok) {
        lookupError.textContent = body.detail || "Request failed";
        lookupResult.textContent = "";
        return;
      }
      showJson(lookupResult, body);
    }

    document.getElementById("lookup-btn").addEventListener("click", async () => {
      const code = lookupInput.value.trim();
      if (!code) {
        lookupError.textContent = "Enter a short code first.";
        return;
      }
      await fetchAndRender(`/api/v1/urls/${code}`);
    });

    document.getElementById("analytics-btn").addEventListener("click", async () => {
      const code = lookupInput.value.trim();
      if (!code) {
        lookupError.textContent = "Enter a short code first.";
        return;
      }
      await fetchAndRender(`/api/v1/analytics/${code}`);
    });

    document.getElementById("open-btn").addEventListener("click", () => {
      const code = lookupInput.value.trim();
      if (!code) {
        lookupError.textContent = "Enter a short code first.";
        return;
      }
      window.open(`/${code}`, "_blank");
    });
  </script>
</body>
</html>
"""


def _client_identifier(request: Request) -> str:
    if request.client and request.client.host:
        return request.client.host
    return "unknown-client"


def _is_api_path(path: str) -> bool:
    return path.startswith("/api/")


def _is_exempt_path(path: str) -> bool:
    return path in {"/health", "/ui", "/"}


def _extract_api_key(x_api_key: str | None, authorization: str | None) -> str | None:
    if x_api_key:
        return x_api_key.strip()
    if authorization and authorization.startswith("Bearer "):
        return authorization.removeprefix("Bearer ").strip()
    return None


def enforce_auth(
    x_api_key: str | None = Header(default=None, alias="X-API-Key"),
    authorization: str | None = Header(default=None),
) -> None:
    received = _extract_api_key(x_api_key=x_api_key, authorization=authorization)
    if not received or not hmac.compare_digest(received, settings.api_key):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or missing API key.")


@app.middleware("http")
async def apply_rate_limit(request: Request, call_next):
    path = request.url.path
    if _is_exempt_path(path):
        return await call_next(request)

    identifier = _client_identifier(request)
    limiter = api_limiter if _is_api_path(path) else redirect_limiter
    limiter_key = f"{identifier}:{'api' if _is_api_path(path) else 'redirect'}"
    decision = limiter.check(limiter_key)
    if not decision.allowed:
        return Response(
            content='{"detail":"Rate limit exceeded. Please retry later."}',
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            media_type="application/json",
            headers={"Retry-After": str(decision.retry_after_seconds)},
        )

    response = await call_next(request)
    response.headers["X-RateLimit-Remaining"] = str(decision.remaining)
    return response


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/ui", response_class=HTMLResponse)
def interactive_ui() -> str:
    return UI_HTML


@app.post("/api/v1/shorten", response_model=ShortenResponse, status_code=status.HTTP_201_CREATED)
def shorten_url(payload: ShortenRequest, _: None = Depends(enforce_auth)) -> ShortenResponse:
    try:
        created = service.create_short_url(
            original_url=str(payload.url),
            custom_alias=payload.custom_alias,
            ttl_days=payload.ttl_days,
        )
    except AliasAlreadyExistsError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return ShortenResponse(
        short_code=created.short_code,
        short_url=f"{settings.base_url}/{created.short_code}",
        original_url=created.original_url,
        expires_at=created.expires_at,
    )


@app.get("/api/v1/urls/{short_code}", response_model=UrlInfoResponse)
def get_url(short_code: str, _: None = Depends(enforce_auth)) -> UrlInfoResponse:
    try:
        record = service.get_url_info(short_code)
    except UrlNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return UrlInfoResponse(
        short_code=record.short_code,
        original_url=record.original_url,
        created_at=record.created_at,
        expires_at=record.expires_at,
        is_active=record.is_active,
    )


@app.get("/api/v1/analytics/{short_code}", response_model=AnalyticsResponse)
def get_analytics(short_code: str, _: None = Depends(enforce_auth)) -> AnalyticsResponse:
    try:
        analytics = service.get_analytics(short_code)
    except UrlNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc

    return AnalyticsResponse(
        short_code=analytics.short_code,
        total_clicks=analytics.total_clicks,
        unique_visitors=analytics.unique_visitors,
        last_accessed_at=analytics.last_accessed_at,
    )


@app.get("/{short_code}")
def redirect(short_code: str, request: Request) -> RedirectResponse:
    try:
        resolved = service.resolve_short_code(
            short_code=short_code,
            user_agent=request.headers.get("user-agent"),
            referrer=request.headers.get("referer"),
            client_host=request.client.host if request.client else None,
        )
    except UrlNotFoundError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc)) from exc
    except UrlExpiredError as exc:
        raise HTTPException(status_code=status.HTTP_410_GONE, detail=str(exc)) from exc

    return RedirectResponse(url=resolved.original_url, status_code=status.HTTP_307_TEMPORARY_REDIRECT)

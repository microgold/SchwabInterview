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
    :root {
      color-scheme: light;
      --ink: #11253d;
      --muted: #64748b;
      --line: #dbe6f0;
      --panel: rgba(255, 255, 255, 0.94);
      --blue: #1468d4;
      --blue-dark: #0a438f;
      --blue-soft: #eaf3ff;
      --teal: #098b83;
      --danger: #c9364d;
      --shadow: 0 22px 55px rgba(25, 72, 117, 0.13);
    }
    * { box-sizing: border-box; }
    body {
      margin: 0;
      min-height: 100vh;
      color: var(--ink);
      font-family: Inter, ui-sans-serif, system-ui, -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      line-height: 1.5;
      background:
        radial-gradient(circle at 10% 0%, rgba(45, 134, 230, 0.18), transparent 31rem),
        radial-gradient(circle at 95% 20%, rgba(9, 139, 131, 0.12), transparent 26rem),
        #f5f9fd;
    }
    button, input { font: inherit; }
    .shell { width: min(1160px, calc(100% - 32px)); margin: 0 auto; padding: 28px 0 54px; }
    .topbar { display: flex; align-items: center; justify-content: space-between; gap: 20px; margin-bottom: 44px; }
    .brand { display: inline-flex; align-items: center; gap: 12px; font-weight: 800; letter-spacing: -0.02em; }
    .brand-mark {
      display: grid; place-items: center; width: 38px; height: 38px; border-radius: 12px;
      color: white; background: linear-gradient(145deg, var(--blue), var(--blue-dark));
      box-shadow: 0 10px 22px rgba(20, 104, 212, 0.25);
    }
    .health { display: flex; align-items: center; gap: 8px; color: var(--muted); font-size: 0.86rem; font-weight: 700; }
    .health-dot { width: 9px; height: 9px; border-radius: 50%; background: #94a3b8; box-shadow: 0 0 0 4px rgba(148, 163, 184, 0.14); }
    .health.online .health-dot { background: #16a085; box-shadow: 0 0 0 4px rgba(22, 160, 133, 0.13); }
    .hero { display: grid; grid-template-columns: 1.15fr 0.85fr; gap: 36px; align-items: end; margin-bottom: 30px; }
    .eyebrow { margin: 0 0 10px; color: var(--blue); font-size: 0.76rem; font-weight: 850; letter-spacing: 0.14em; text-transform: uppercase; }
    h1 { max-width: 720px; margin: 0; font-size: clamp(2.45rem, 6vw, 4.6rem); line-height: 0.98; letter-spacing: -0.055em; }
    .hero-copy { max-width: 610px; margin: 20px 0 0; color: var(--muted); font-size: 1.08rem; }
    .hero-note { padding: 18px 20px; border: 1px solid rgba(20, 104, 212, 0.14); border-radius: 18px; background: rgba(234, 243, 255, 0.72); }
    .hero-note strong { display: block; margin-bottom: 4px; color: var(--blue-dark); }
    .hero-note span { color: var(--muted); font-size: 0.92rem; }
    .workspace { display: grid; grid-template-columns: minmax(0, 1.05fr) minmax(340px, 0.95fr); gap: 22px; align-items: start; }
    .card { border: 1px solid rgba(185, 204, 222, 0.72); border-radius: 24px; padding: 28px; background: var(--panel); box-shadow: var(--shadow); backdrop-filter: blur(14px); }
    .card-header { display: flex; align-items: flex-start; justify-content: space-between; gap: 16px; margin-bottom: 24px; }
    .step { display: grid; place-items: center; flex: 0 0 auto; width: 32px; height: 32px; border-radius: 50%; color: var(--blue); background: var(--blue-soft); font-size: 0.85rem; font-weight: 850; }
    h2 { margin: 0 0 5px; font-size: 1.34rem; letter-spacing: -0.025em; }
    .subtitle { margin: 0; color: var(--muted); font-size: 0.91rem; }
    .field { margin-bottom: 17px; }
    .grid { display: grid; grid-template-columns: 1fr 0.72fr; gap: 14px; }
    label { display: block; margin-bottom: 7px; font-size: 0.83rem; font-weight: 760; }
    .optional { color: #8a9bad; font-weight: 550; }
    input {
      width: 100%; min-height: 46px; padding: 11px 13px; border: 1px solid #cddae7; border-radius: 12px;
      color: var(--ink); outline: none; background: #fbfdff; transition: border-color 140ms, box-shadow 140ms, background 140ms;
    }
    input::placeholder { color: #9aabba; }
    input:focus { border-color: var(--blue); background: #fff; box-shadow: 0 0 0 4px rgba(20, 104, 212, 0.11); }
    .auth-field { position: relative; margin-bottom: 20px; padding: 15px; border-radius: 15px; background: #f6f9fc; }
    .auth-field label { display: flex; align-items: center; justify-content: space-between; }
    .demo-pill { padding: 3px 8px; border-radius: 999px; color: #81600a; background: #fff1be; font-size: 0.67rem; letter-spacing: 0.06em; text-transform: uppercase; }
    .actions { display: flex; flex-wrap: wrap; gap: 10px; margin-top: 4px; }
    button {
      min-height: 44px; padding: 10px 16px; border: 1px solid transparent; border-radius: 12px;
      font-weight: 760; cursor: pointer; transition: transform 120ms, box-shadow 120ms, background 120ms, opacity 120ms;
    }
    button:hover { transform: translateY(-1px); }
    button:active { transform: translateY(0); }
    button:disabled { cursor: wait; opacity: 0.65; transform: none; }
    .primary { color: white; background: linear-gradient(135deg, var(--blue), var(--blue-dark)); box-shadow: 0 10px 20px rgba(20, 104, 212, 0.2); }
    .secondary { color: var(--blue-dark); border-color: #bfd2e5; background: white; }
    .ghost { color: var(--muted); background: #edf3f8; }
    pre {
      min-height: 82px; margin: 18px 0 0; padding: 16px; overflow-x: auto; border: 1px solid #dce7f0;
      border-radius: 14px; color: #d7ecff; background: #10273f; font: 0.82rem/1.6 ui-monospace, SFMono-Regular, Consolas, monospace;
      white-space: pre-wrap; word-break: break-word;
    }
    pre:empty { display: none; }
    .analytics-result { margin-top: 18px; overflow: hidden; border: 1px solid #dce7f0; border-radius: 14px; }
    .analytics-result[hidden] { display: none; }
    .analytics-table { width: 100%; border-collapse: collapse; background: white; }
    .analytics-table caption { padding: 13px 16px; color: white; background: #10273f; font-weight: 750; text-align: left; }
    .analytics-table th, .analytics-table td { padding: 11px 16px; border-bottom: 1px solid #e4edf4; text-align: left; }
    .analytics-table tr:last-child th, .analytics-table tr:last-child td { border-bottom: 0; }
    .analytics-table th { width: 44%; color: var(--muted); font-size: 0.78rem; letter-spacing: 0.03em; text-transform: uppercase; }
    .analytics-table td { color: var(--ink); font-weight: 700; word-break: break-word; }
    .error { min-height: 0; margin: 13px 0 0; color: var(--danger); font-size: 0.88rem; font-weight: 700; }
    .error:empty { display: none; }
    .link-strip { display: flex; align-items: center; justify-content: space-between; gap: 12px; margin-top: 14px; padding: 12px 14px; border-radius: 13px; background: #eaf8f6; }
    .link-strip[hidden] { display: none; }
    .link-strip a { min-width: 0; overflow: hidden; color: #08756e; font-weight: 750; text-overflow: ellipsis; white-space: nowrap; }
    .copy-button { min-height: 34px; padding: 6px 10px; color: #08756e; border-color: rgba(8, 117, 110, 0.2); background: white; font-size: 0.78rem; }
    .footer { display: flex; justify-content: space-between; gap: 20px; margin-top: 22px; color: var(--muted); font-size: 0.8rem; }
    .footer a { color: var(--blue); font-weight: 700; text-decoration: none; }
    @media (max-width: 820px) {
      .hero, .workspace { grid-template-columns: 1fr; }
      .hero { gap: 22px; }
      .hero-note { display: none; }
    }
    @media (max-width: 560px) {
      .shell { width: min(100% - 20px, 1160px); padding-top: 18px; }
      .topbar { margin-bottom: 30px; }
      .grid { grid-template-columns: 1fr; }
      .card { padding: 21px; border-radius: 19px; }
      .actions button { flex: 1 1 100%; }
      .footer { flex-direction: column; }
    }
  </style>
</head>
<body>
  <main class="shell">
    <nav class="topbar" aria-label="Application header">
      <div class="brand"><span class="brand-mark" aria-hidden="true">↗</span> LinkForge</div>
      <div id="health" class="health"><span class="health-dot"></span><span>Checking API</span></div>
    </nav>

    <header class="hero">
      <div>
        <p class="eyebrow">Agentic URL Shortener</p>
        <h1>Short links.<br />Clear signals.</h1>
        <p class="hero-copy">Create durable short URLs, verify their configuration, and inspect click analytics from one focused workspace.</p>
      </div>
      <aside class="hero-note">
        <strong>Built for reviewability</strong>
        <span>API-key protection, expiring links, rate limits, and observable redirect analytics are included.</span>
      </aside>
    </header>

    <div class="workspace">
      <section class="card">
        <div class="card-header">
          <div>
            <h2>Create a short link</h2>
            <p class="subtitle">Choose a destination and optional memorable alias.</p>
          </div>
          <span class="step">01</span>
        </div>

        <div class="auth-field">
          <label for="api_key">API key <span class="demo-pill">Local demo</span></label>
          <input id="api_key" type="text" value="dev-interview-key" autocomplete="off" />
        </div>

        <form id="create-form">
          <div class="field">
            <label for="url">Destination URL</label>
            <input id="url" type="url" required placeholder="https://example.com/remarkable-page" />
          </div>
          <div class="grid">
            <div class="field">
              <label for="custom_alias">Custom alias <span class="optional">optional</span></label>
              <input id="custom_alias" type="text" placeholder="launch-notes" />
            </div>
            <div class="field">
              <label for="ttl_days">Expires after <span class="optional">days</span></label>
              <input id="ttl_days" type="number" min="1" max="3650" placeholder="30" />
            </div>
          </div>
          <div class="actions">
            <button id="create-btn" class="primary" type="submit">Create short link&nbsp; →</button>
          </div>
        </form>
        <p id="create-error" class="error" role="alert"></p>
        <div id="link-strip" class="link-strip" hidden>
          <a id="created-link" href="#" target="_blank" rel="noopener"></a>
          <button id="copy-btn" class="copy-button" type="button">Copy</button>
        </div>
        <pre id="create-result" aria-live="polite"></pre>
      </section>

      <section class="card">
        <div class="card-header">
          <div>
            <h2>Inspect a link</h2>
            <p class="subtitle">Review metadata, engagement, or test the redirect.</p>
          </div>
          <span class="step">02</span>
        </div>
        <div class="field">
          <label for="lookup_code">Short code</label>
          <input id="lookup_code" type="text" placeholder="abc1234" />
        </div>
        <div class="actions">
          <button id="lookup-btn" class="secondary" type="button">URL details</button>
          <button id="analytics-btn" class="secondary" type="button">Analytics</button>
          <button id="open-btn" class="ghost" type="button">Open ↗</button>
        </div>
        <p id="lookup-error" class="error" role="alert"></p>
        <pre id="lookup-result" aria-live="polite"></pre>
        <div id="analytics-result" class="analytics-result" aria-live="polite" hidden>
          <table class="analytics-table">
            <caption>Link analytics</caption>
            <tbody>
              <tr><th scope="row">Short code</th><td id="analytics-short-code"></td></tr>
              <tr><th scope="row">Total clicks</th><td id="analytics-total-clicks"></td></tr>
              <tr><th scope="row">Unique visitors</th><td id="analytics-unique-visitors"></td></tr>
              <tr><th scope="row">Last accessed</th><td id="analytics-last-accessed-at"></td></tr>
            </tbody>
          </table>
        </div>
      </section>
    </div>

    <footer class="footer">
      <span>Local interview prototype · Redirects open in a new tab</span>
      <span><a href="/docs" target="_blank" rel="noopener">Explore Swagger API ↗</a></span>
    </footer>
  </main>

  <script>
    const createForm = document.getElementById("create-form");
    const createError = document.getElementById("create-error");
    const createResult = document.getElementById("create-result");
    const createButton = document.getElementById("create-btn");
    const linkStrip = document.getElementById("link-strip");
    const createdLink = document.getElementById("created-link");
    const copyButton = document.getElementById("copy-btn");
    const lookupInput = document.getElementById("lookup_code");
    const lookupError = document.getElementById("lookup-error");
    const lookupResult = document.getElementById("lookup-result");
    const analyticsResult = document.getElementById("analytics-result");
    const analyticsShortCode = document.getElementById("analytics-short-code");
    const analyticsTotalClicks = document.getElementById("analytics-total-clicks");
    const analyticsUniqueVisitors = document.getElementById("analytics-unique-visitors");
    const analyticsLastAccessedAt = document.getElementById("analytics-last-accessed-at");

    function clearErrors() {
      createError.textContent = "";
      lookupError.textContent = "";
    }

    function showJson(target, data) {
      target.textContent = JSON.stringify(data, null, 2);
    }

    function clearAnalyticsResult() {
      analyticsResult.hidden = true;
      analyticsShortCode.textContent = "";
      analyticsTotalClicks.textContent = "";
      analyticsUniqueVisitors.textContent = "";
      analyticsLastAccessedAt.textContent = "";
    }

    function clearLookupOutputs() {
      lookupResult.textContent = "";
      clearAnalyticsResult();
    }

    function showAnalytics(data) {
      analyticsShortCode.textContent = String(data.short_code);
      analyticsTotalClicks.textContent = String(data.total_clicks);
      analyticsUniqueVisitors.textContent = String(data.unique_visitors);
      analyticsLastAccessedAt.textContent = data.last_accessed_at === null ? "Never" : String(data.last_accessed_at);
      analyticsResult.hidden = false;
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
      linkStrip.hidden = true;
      createButton.disabled = true;
      createButton.textContent = "Creating…";

      const payload = {
        url: document.getElementById("url").value.trim(),
      };
      const alias = document.getElementById("custom_alias").value.trim();
      const ttl = document.getElementById("ttl_days").value.trim();
      if (alias) payload.custom_alias = alias;
      if (ttl) payload.ttl_days = Number(ttl);

      try {
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
        createdLink.href = body.short_url;
        createdLink.textContent = body.short_url;
        linkStrip.hidden = false;
      } catch (error) {
        createError.textContent = "Could not reach the API. Confirm the server is running.";
        createResult.textContent = "";
      } finally {
        createButton.disabled = false;
        createButton.textContent = "Create short link  →";
      }
    });

    async function fetchAndRender(url) {
      clearErrors();
      clearLookupOutputs();
      try {
        const response = await fetch(url, { headers: buildAuthHeaders(false) });
        const body = await response.json();
        if (!response.ok) {
          lookupError.textContent = body.detail || "Request failed";
          lookupResult.textContent = "";
          return;
        }
        showJson(lookupResult, body);
      } catch (error) {
        lookupError.textContent = "Could not reach the API. Confirm the server is running.";
        lookupResult.textContent = "";
      }
    }

    async function fetchAnalytics(code) {
      clearErrors();
      clearLookupOutputs();
      try {
        const response = await fetch(`/api/v1/analytics/${code}`, { headers: buildAuthHeaders(false) });
        const body = await response.json();
        if (!response.ok) {
          lookupError.textContent = body.detail || "Request failed";
          return;
        }
        showAnalytics(body);
      } catch (error) {
        lookupError.textContent = "Could not reach the API. Confirm the server is running.";
        clearLookupOutputs();
      }
    }

    copyButton.addEventListener("click", async () => {
      try {
        await navigator.clipboard.writeText(createdLink.textContent);
        copyButton.textContent = "Copied!";
        window.setTimeout(() => { copyButton.textContent = "Copy"; }, 1400);
      } catch (error) {
        createError.textContent = "Copy failed. Select the short URL and copy it manually.";
      }
    });

    document.getElementById("lookup-btn").addEventListener("click", async () => {
      const code = lookupInput.value.trim();
      if (!code) {
        clearLookupOutputs();
        lookupError.textContent = "Enter a short code first.";
        return;
      }
      await fetchAndRender(`/api/v1/urls/${code}`);
    });

    document.getElementById("analytics-btn").addEventListener("click", async () => {
      const code = lookupInput.value.trim();
      if (!code) {
        clearLookupOutputs();
        lookupError.textContent = "Enter a short code first.";
        return;
      }
      await fetchAnalytics(code);
    });

    document.getElementById("open-btn").addEventListener("click", () => {
      const code = lookupInput.value.trim();
      if (!code) {
        lookupError.textContent = "Enter a short code first.";
        return;
      }
      window.open(`/${code}`, "_blank");
    });

    fetch("/health")
      .then((response) => {
        if (!response.ok) throw new Error("Health check failed");
        const health = document.getElementById("health");
        health.classList.add("online");
        health.querySelector("span:last-child").textContent = "API online";
      })
      .catch(() => {
        document.querySelector("#health span:last-child").textContent = "API unavailable";
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

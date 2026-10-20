"""
Cloud CLI Skills Registry
=========================

51 concise engineering "skills" across 5 domains. Each skill carries:
  - name        : short label shown in the activation status line
  - triggers    : keywords matched against the user's prompt (case-insensitive)
  - directive   : concrete coding instruction injected into the model's system
                  context when the skill activates

The launcher picks the highest-scoring skills for a given prompt (plus a
directory-context pass) and injects their directives, so the user never needs
to type slash commands.

This module has no third-party dependencies and never performs I/O beyond
optionally inspecting a project directory for stack-detection hints.
"""

from __future__ import annotations

import os
import re
from dataclasses import dataclass, field
from typing import Iterable

# --------------------------------------------------------------------------
# Registry types
# --------------------------------------------------------------------------


@dataclass(frozen=True)
class Skill:
    name: str
    domain: str
    triggers: tuple[str, ...]
    directive: str


DOMAINS = (
    "UI/UX & Visual Design",
    "Frontend Engineering",
    "Backend & Logical Implementation",
    "System Design & Database",
    "DevOps, Infra & QA",
)


def _s(name, domain, triggers, directive) -> Skill:
    return Skill(name=name, domain=domain, triggers=tuple(triggers), directive=directive)


# --------------------------------------------------------------------------
# 1. UI/UX & Visual Design
# --------------------------------------------------------------------------

UIUX = [
    _s("Bento Grids", DOMAINS[0],
       ["bento", "grid layout", "dashboard layout", "tile grid", "modular grid"],
       "Lay out major sections as a bento grid: CSS Grid with "
       "`grid-template-columns: repeat(12, 1fr)`, uneven tile spans, 16-24px gaps. "
       "Make one hero tile span 2 rows/cols, keep supporting tiles uniform."),
    _s("Glassmorphism & Dark UI", DOMAINS[0],
       ["glassmorphism", "glass", "frosted", "dark mode", "dark ui", "blur backdrop"],
       "Use a dark base (#0a0a0b / slate-950), translucent surfaces "
       "(`background: rgba(255,255,255,0.04)`), `backdrop-filter: blur(16px)`, "
       "1px `rgba(255,255,255,0.08)` borders, and a soft outer glow on hover."),
    _s("Micro-Interactions", DOMAINS[0],
       ["animation", "micro-interaction", "transition", "hover effect", "motion"],
       "Add tasteful motion: 150-250ms ease-out transitions, a 4-8px translateY "
       "lift on hover, button scale of 0.97 on :active, and a 120ms opacity fade. "
       "Respect `@media (prefers-reduced-motion: reduce)`."),
    _s("Typography Hierarchy", DOMAINS[0],
       ["typography", "font", "type scale", "heading", "font pairing"],
       "Set a deliberate type scale (1.250 major third): 12/14/16/20/24/32/48px. "
       "Tighten letter-spacing as size grows (-0.02em on display text), keep body "
       "line-height at 1.6, and cap measure at ~65ch."),
    _s("Modern SaaS Palettes", DOMAINS[0],
       ["palette", "color scheme", "saas theme", "brand color", "color palette"],
       "Build a token-based palette: one primary (indigo/violet), one accent "
       "(emerald/cyan), semantic success/warn/danger, and 5-step neutral ramp. "
       "Define all of them as CSS custom properties; never hardcode hex in components."),
    _s("Mobile-First Responsive", DOMAINS[0],
       ["responsive", "mobile", "breakpoint", "adaptive", "small screen"],
       "Author mobile-first: base styles target 375px, then add "
       "`@media (min-width: 768px/1024px/1280px)` progressively. Use "
       "`clamp()` for fluid type and spacing; never rely on device sniffing."),
    _s("High-Converting Landing Pages", DOMAINS[0],
       ["landing page", "marketing page", "hero section", "conversion", "sales page"],
       "Structure as: sticky nav, hero with one clear value prop and two CTAs, "
       "social proof, 3 benefit blocks, objection-handling FAQ, closing CTA. "
       "Keep one action per viewport and repeat the primary CTA at 3 points."),
    _s("E-Commerce Cart & Checkout UX", DOMAINS[0],
       ["cart", "checkout", "shopping", "ecommerce", "store", "shop"],
       "Cart must show line items, quantity steppers, live subtotal/tax/shipping "
       "totals, and a persistent total. Checkout: single-page, inline validation, "
       "autofill-friendly inputs, guest checkout, and a clear order confirmation."),
    _s("Analytics Dashboard UI", DOMAINS[0],
       ["analytics", "dashboard", "metrics", "charts", "kpi", "reporting"],
       "Lead with 3-4 KPI cards (value, delta vs prior period, sparkline). Then "
       "charts with labelled axes and units, a date-range control, and no chart "
       "junk. Use accessible color pairs and never rely on color alone."),
    _s("Lucide Icons & Realistic Copy", DOMAINS[0],
       ["icon", "lucide", "placeholder", "copywriting", "realistic content"],
       "Use Lucide icons via `lucide-react` (or inline SVG), sized 16-24px, "
       "`stroke-width={2}`. Write realistic product copy with plausible names, "
       "prices and dates - never 'Product 1', 'Lorem ipsum', or 'John Doe'."),
]

# --------------------------------------------------------------------------
# 2. Frontend Engineering
# --------------------------------------------------------------------------

FRONTEND = [
    _s("React 19 & Hooks", DOMAINS[1],
       ["react", "hook", "component", "usestate", "useeffect", "jsx"],
       "Target React 19: function components only, use `use()` where relevant, "
       "and rely on the ref-as-prop cleanup. Keep effects for synchronization "
       "only - derive values during render instead."),
    _s("Next.js App Router", DOMAINS[1],
       ["next.js", "nextjs", "app router", "server component", "next app"],
       "Use the App Router: `app/` directory, server components by default, "
       "'use client' only at interaction boundaries, async `params`/`searchParams`, "
       "and `generateMetadata` for SEO. Fetch data in server components."),
    _s("Tailwind CSS Architecture", DOMAINS[1],
       ["tailwind", "css", "styling", "utility class", "design system css"],
       "Extend Tailwind in `tailwind.config` with design tokens (colors, spacing, "
       "radii, shadows). Order classes with the official prettier plugin; avoid "
       "`!important`; co-locate component styles with the component."),
    _s("State Management", DOMAINS[1],
       ["state management", "store", "redux", "zustand", "context", "global state"],
       "Lift state only as far as needed. Use local `useState` first, Context for "
       "stable cross-tree values, and a store (Zustand/Redux Toolkit) only for "
       "genuinely global, frequently-changing state. Keep reducers pure."),
    _s("Resilient API Fetching", DOMAINS[1],
       ["fetch", "api call", "loading state", "error handling ui", "request"],
       "Every request needs explicit loading, empty, error and success states. "
       "Abort stale requests with AbortController, retry transient failures with "
       "exponential backoff, and show a retry affordance - never a blank screen."),
    _s("Form Validation", DOMAINS[1],
       ["form", "validation", "input", "schema form", "zod"],
       "Validate on blur and on submit, with inline field-level errors tied via "
       "aria-describedby. Use a shared schema (Zod) for client and server. "
       "Disable submit only while invalid, and never clear valid input on error."),
    _s("Frontend Performance", DOMAINS[1],
       ["performance", "optimize", "slow", "lighthouse", "bundle size"],
       "Route-split with dynamic imports, memoize expensive components, lazy-load "
       "below-the-fold media, virtualize long lists, and ship images as "
       "next/image with explicit width/height to avoid layout shift."),
    _s("Clean Vanilla JS & DOM", DOMAINS[1],
       ["vanilla js", "plain javascript", "dom manipulation", "no framework"],
       "For framework-free code: use semantic elements, keep DOM refs explicit, "
       "debounce expensive handlers, delegate events for dynamic lists, and "
       "avoid innerHTML with untrusted data."),
    _s("Static Site, No Build Step", DOMAINS[1],
       ["static site", "static website", "html page", "html site", "landing page",
        "marketing page", "no build", "no npm", "no node", "open in browser"],
       "For a static HTML/CSS/JS site: do NOT create package.json, do NOT add "
       "npm dependencies, do NOT invent an `npx live` / `npx serve` dev server. "
       "Author `index.html`, `styles.css` (or `main.css`), and `main.js` as "
       "plain files in the current directory and reference them with relative "
       "paths. Tailwind is fine via the Play CDN `<script src=\"https://cdn.tailwindcss.com\">` "
       "tag in `<head>` - no install step. To preview, the user opens "
       "`index.html` directly in a browser, or runs `python3 -m http.server 8000` "
       "themselves. Output `/run python3 -m http.server 8000` only if the user "
       "explicitly asks for a server command. NEVER emit bare CDN URLs in "
       "chat or prose - mention them only inside the `<script>` tag of the "
       "produced HTML, so the auto-scraper never tries to fetch them."),
    _s("Modular Components", DOMAINS[1],
       ["component", "modular", "reusable", "architecture", "composition"],
       "Split by responsibility, not line count. One component per file, props "
       "typed at the boundary, and composition over configuration. Extract shared "
       "primitives into a design-system folder."),
    _s("SEO & Accessibility", DOMAINS[1],
       ["seo", "accessibility", "a11y", "semantic html", "aria", "wcag"],
       "Semantic landmarks (`header/nav/main/footer`), one `h1` per page, "
       "descriptive alt text, visible focus rings, and full keyboard operability. "
       "Add canonical URLs, Open Graph tags, and structured data."),
]

# --------------------------------------------------------------------------
# 3. Backend & Logical Implementation
# --------------------------------------------------------------------------

BACKEND = [
    _s("NestJS Modular Architecture", DOMAINS[2],
       ["nestjs", "nest", "typescript backend", "node backend", "decorator"],
       "Organize by feature module: controller (HTTP only) -> service (logic) -> "
       "repository (persistence). Use DTOs with class-validator, dependency "
       "injection throughout, and a global exception filter."),
    _s("Node.js & Express APIs", DOMAINS[2],
       ["express", "node api", "nodejs backend", "rest api node"],
       "Layer routes/controllers/middleware/services. Validate input at the edge, "
       "centralize error handling, use async wrappers so rejections reach the "
       "error middleware, and keep route handlers thin."),
    _s("Python FastAPI", DOMAINS[2],
       ["fastapi", "python api", "python backend", "uvicorn", "asgi"],
       "Define Pydantic models for request and response, use dependency injection "
       "for shared concerns, declare response_model everywhere, and add both "
       "`async def` and sync routes to the right threadpool."),
    _s("REST API Contracts", DOMAINS[2],
       ["rest", "api contract", "endpoint", "crud", "resource design"],
       "Use plural nouns, correct status codes (201 create, 204 delete, 409 "
       "conflict, 422 validation), consistent envelopes, cursor-free list "
       "pagination params, and an OpenAPI description for every route."),
    _s("Auth: JWT, OAuth & RBAC", DOMAINS[2],
       ["auth", "jwt", "oauth", "login", "rbac", "permission", "token"],
       "Hash passwords with bcrypt/argon2 (never SHA). Keep JWTs short-lived with "
       "refresh rotation, store them in httpOnly cookies, and enforce RBAC with a "
       "permission guard on the route - never only in the client."),
    _s("Idempotent Webhooks & Payments", DOMAINS[2],
       ["webhook", "payment", "stripe", "idempotent", "retry safety"],
       "Verify webhook signatures, de-duplicate by provider event id with a unique "
       "index, and make handlers idempotent so retries are safe. Acknowledge fast, "
       "process async, and reconcile against the provider on mismatch."),
    _s("Background Queues & Workers", DOMAINS[2],
       ["queue", "worker", "background job", "celery", "bullmq", "async job"],
       "Move slow work off the request path. Make jobs idempotent, give each a "
       "retry policy with backoff and a dead-letter state, and record enough "
       "metadata to replay or inspect a failed job."),
    _s("Strict DTO & Schema Validation", DOMAINS[2],
       ["dto", "schema", "validation", "type safety", "sanitization"],
       "Treat every input as hostile: validate shape, type, range and allowed "
       "values at the boundary. Whitelist fields explicitly to prevent mass "
       "assignment, and never pass raw request bodies into the ORM."),
    _s("Edge-Case Business Logic", DOMAINS[2],
       ["business logic", "edge case", "validation rules", "pricing", "rules"],
       "Explicitly handle: zero/negative quantities, duplicate submissions, "
       "concurrent edits, expired tokens, partial failure, and timezone/DST "
       "boundaries. Write the tests for these cases before the happy path."),
    _s("Structured Error Handling", DOMAINS[2],
       ["error handling", "exception", "logging", "debugging errors", "error format"],
       "Return a consistent error envelope (code, message, details, request id). "
       "Log with that request id, never leak stack traces or SQL to clients, and "
       "translate known domain errors at a single boundary."),
]

# --------------------------------------------------------------------------
# 4. System Design & Database
# --------------------------------------------------------------------------

SYSTEM = [
    _s("Microservices vs Modular Monolith", DOMAINS[3],
       ["microservice", "monolith", "service boundary", "modular architecture"],
       "Default to a modular monolith; split into services only when a boundary "
       "needs independent scaling, deployment or ownership. Define contracts "
       "before extracting, and never share a database across services."),
    _s("PostgreSQL Schema & Indexing", DOMAINS[3],
       ["postgres", "postgresql", "schema", "index", "sql", "migration"],
       "Model with explicit keys, `NOT NULL` and `CHECK` constraints, `timestamptz` "
       "for times, and UUID or bigint ids. Index every foreign key and filter "
       "column; use EXPLAIN ANALYZE before adding an index."),
    _s("Redis Caching, Rate Limiting & PubSub", DOMAINS[3],
       ["redis", "cache", "rate limit", "pubsub", "throttle"],
       "Cache with an explicit TTL and a clear invalidation strategy (or "
       "cache-aside). Rate limit per user/IP with a sliding window. Use Redis "
       "pub/sub for ephemeral fan-out only - never as a durable queue."),
    _s("Multi-Tenant SaaS Design", DOMAINS[3],
       ["multi-tenant", "multi tenant", "saas", "tenant", "workspace isolation"],
       "Scope every table by tenant_id with a composite index leading on it, and "
       "enforce isolation in the data-access layer (row-level security or a "
       "mandatory repository filter). Test cross-tenant access explicitly."),
    _s("Fault Tolerance & Retries", DOMAINS[3],
       ["retry", "resilience", "fault tolerance", "circuit breaker", "timeout"],
       "Set explicit connect/read timeouts on every call, retry only idempotent "
       "operations with exponential backoff plus jitter, cap total attempts, and "
       "put a circuit breaker in front of flaky dependencies."),
    _s("API Gateway Patterns", DOMAINS[3],
       ["api gateway", "gateway", "proxy", "reverse proxy", "ingress"],
       "Terminate TLS, enforce auth once at the edge, apply per-route rate limits, "
       "aggregate responses to cut round trips, and add correlation ids that "
       "propagate to every downstream call."),
    _s("Cursor Pagination", DOMAINS[3],
       ["pagination", "cursor", "infinite scroll", "paging", "load more"],
       "Prefer keyset (cursor) pagination over OFFSET for large tables: order by "
       "the indexed (created_at, id) tuple and encode the cursor as an opaque "
       "token. Never paginate with OFFSET on a mutating dataset."),
    _s("Concurrency Safety", DOMAINS[3],
       ["race condition", "concurrency", "locking", "transaction", "double spend"],
       "Assume concurrent writers: use optimistic locking via a version column or "
       "pessimistic SELECT ... FOR UPDATE. Wrap multi-statement invariants in one "
       "transaction and make it idempotent under retry."),
    _s("WebSockets & Real-time", DOMAINS[3],
       ["websocket", "real-time", "realtime", "socket", "live update", "sse"],
       "Prefer SSE for one-way updates and WebSockets for bidirectional streams. "
       "Add heartbeat pings, reconnect with backoff, and track which user owns "
       "which connection so a reconnect can replay missed events."),
    _s("Mermaid Architecture Diagrams", DOMAINS[3],
       ["diagram", "mermaid", "architecture diagram", "flowchart", "visualize architecture"],
       "Produce a ```mermaid block: `graph TD` for components, `sequenceDiagram` "
       "for request flows, `erDiagram` for the schema. Keep node labels short and "
       "show trust boundaries and data stores explicitly."),
]

# --------------------------------------------------------------------------
# 5. DevOps, Infra & QA
# --------------------------------------------------------------------------

DEVOPS = [
    _s("Multi-Stage Dockerfiles", DOMAINS[4],
       ["dockerfile", "docker", "container", "image", "multi-stage"],
       "Use a multi-stage build: builder stage installs deps and compiles, final "
       "stage copies only artifacts onto a slim runtime image. Run as a non-root "
       "user, pin base image tags, and use .dockerignore to exclude .git and node_modules."),
    _s("Docker Compose Production Stacks", DOMAINS[4],
       ["docker compose", "compose", "docker-compose", "stack", "services"],
       "Define app, database, cache and reverse proxy as named services with "
       "healthchecks, a private network, and named volumes for state. Gate "
       "startup with depends_on condition: service_healthy."),
    _s("Nginx Reverse Proxy", DOMAINS[4],
       ["nginx", "reverse proxy", "load balancer", "ssl", "tls"],
       "Terminate TLS, redirect HTTP to HTTPS, proxy to the app upstream, and set "
       "security headers (HSTS, X-Content-Type-Options, CSP). Enable gzip and "
       "serve static assets with long cache lifetimes."),
    _s("CI/CD with GitHub Actions", DOMAINS[4],
       ["github actions", "ci/cd", "pipeline", "workflow", "automation ci"],
       "Run lint, typecheck, tests and build on every PR with a pinned action "
       "version and a concurrency group to cancel superseded runs. Cache "
       "dependencies, and gate merges on required checks."),
    _s("Observability: Prometheus, Grafana, Sentry", DOMAINS[4],
       ["prometheus", "grafana", "sentry", "monitoring", "observability", "metrics"],
       "Expose RED metrics (rate, errors, duration) plus business KPIs, alert on "
       "symptoms rather than causes, and attach release/commit metadata to "
       "dashboards. Ship frontend errors to Sentry with user and release context."),
    _s("Ubuntu & PM2 Deployment", DOMAINS[4],
       ["deploy", "ubuntu", "pm2", "server", "vps", "production server"],
       "Provision with least privilege, enable the unattended-upgrades security "
       "updates, and firewall to 22/80/443 only. Run the app under PM2 with "
       "cluster mode, an ecosystem file, and log rotation configured."),
    _s("OWASP Top-10 Security", DOMAINS[4],
       ["security", "owasp", "xss", "sql injection", "csrf", "vulnerability"],
       "Parameterize every query, escape output by default, set CSP and anti-"
       "framing headers, use SameSite cookies plus CSRF tokens, hash secrets at "
       "rest, and never log credentials or full tokens."),
    _s("Automated Unit & Integration Tests", DOMAINS[4],
       ["test", "testing", "unit test", "integration test", "coverage", "jest", "pytest"],
       "Test behavior, not implementation. Unit-test domain logic exhaustively "
       "including edge cases; integration-test real HTTP and DB boundaries with a "
       "throwaway database per run. Keep tests deterministic and independent."),
    _s("Systematic Root-Cause Debugging", DOMAINS[4],
       ["debug", "bug", "not working", "crash", "error occurs", "fix issue"],
       "Reproduce first, then bisect: read the actual error and stack, form one "
       "hypothesis at a time, and verify with a targeted probe before editing. "
       "Fix the root cause rather than the symptom, and add a regression test."),
    _s("Clean Dependency Management", DOMAINS[4],
       ["dependencies", "package.json", "npm", "lockfile", "version"],
       "Pin exact versions and commit the lockfile. Remove unused dependencies, "
       "audit for known CVEs, separate dev from runtime dependencies, and group "
       "them logically with a documented update policy."),
]

ALL_SKILLS: tuple[Skill, ...] = tuple(UIUX + FRONTEND + BACKEND + SYSTEM + DEVOPS)

assert len(ALL_SKILLS) == 51, f"expected 51 skills, found {len(ALL_SKILLS)}"


# --------------------------------------------------------------------------
# Directory-context stack detection
# --------------------------------------------------------------------------

_STACK_HINTS: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("package.json", "node", ("react", "next", "node")),
    ("tsconfig.json", "typescript", ("typescript", "nestjs")),
    ("Dockerfile", "docker", ("docker",)),
    ("docker-compose.yml", "docker", ("docker",)),
    ("requirements.txt", "python", ("fastapi",)),
    ("pyproject.toml", "python", ("fastapi",)),
    ("go.mod", "go", ("go",)),
    ("Cargo.toml", "rust", ("rust",)),
    ("index.html", "static", ("vanilla js",)),
)

_CONTEXT_EXTENSIONS = {
    ".py": "python", ".ts": "typescript", ".tsx": "react", ".js": "node",
    ".jsx": "react", ".html": "static", ".css": "styling",
}


def detect_stack(root: str | os.PathLike = ".", max_files: int = 400) -> set[str]:
    """Cheaply sniff the project directory for stack hints."""
    root = os.path.abspath(root)
    hints: set[str] = set()

    for filename, hint, extra in _STACK_HINTS:
        if os.path.exists(os.path.join(root, filename)):
            hints.add(hint)
            if filename == "package.json":
                try:
                    with open(os.path.join(root, filename), encoding="utf-8") as fh:
                        blob = fh.read().lower()
                    hints.update(e for e in extra if e in blob)
                except OSError:
                    pass

    try:
        entries = os.listdir(root)[:max_files]
    except OSError:
        return hints

    counts: dict[str, int] = {}
    for entry in entries:
        ext = os.path.splitext(entry)[1].lower()
        hint = _CONTEXT_EXTENSIONS.get(ext)
        if hint:
            counts[hint] = counts.get(hint, 0) + 1

    # Only trust file-extension hints when they are actually dominant.
    for hint, count in counts.items():
        if count >= 3:
            hints.add(hint)

    return hints


# --------------------------------------------------------------------------
# Scoring / matching
# --------------------------------------------------------------------------

_WORD = re.compile(r"[a-z0-9+#.]+")

# The one skill whose advice is actively wrong when a framework is in play.
_NO_BUILD_SKILL = "Static Site, No Build Step"

# Any of these means the project genuinely needs a package manager, so the
# "do not create package.json" directive must not be injected.
_BUILD_TOOLING = (
    "next.js", "nextjs", "next ", "react", "vue", "nuxt", "svelte", "sveltekit",
    "angular", "remix", "astro", "gatsby", "vite", "webpack", "parcel",
    "rollup", "esbuild", "tailwind.config", "postcss.config", "typescript",
    "tsconfig", "package.json", "npm ", "pnpm", "yarn ", "bun ",
    "express", "nestjs", "fastify", "node_modules",
)


def _needs_a_build(prompt_l: str) -> bool:
    """True when the prompt names a framework/bundler/package manager."""
    return any(tool in prompt_l for tool in _BUILD_TOOLING)

# Stack hint -> skills that should be pulled in automatically.
_STACK_TO_SKILLS: dict[str, tuple[str, ...]] = {
    "react": ("React 19 & Hooks", "Modular Components", "Frontend Performance"),
    "next": ("Next.js App Router", "SEO & Accessibility", "Frontend Performance"),
    "typescript": ("Strict DTO & Schema Validation",),
    "nestjs": ("NestJS Modular Architecture", "Strict DTO & Schema Validation"),
    "node": ("Node.js & Express APIs", "Clean Dependency Management"),
    "python": ("Python FastAPI", "Strict DTO & Schema Validation"),
    "fastapi": ("Python FastAPI", "REST API Contracts"),
    "docker": ("Multi-Stage Dockerfiles", "Docker Compose Production Stacks"),
    "go": ("Microservices vs Modular Monolith",),
    "rust": ("Concurrency Safety",),
    "static": ("Clean Vanilla JS & DOM", "Static Site, No Build Step"),
    "html": ("Static Site, No Build Step",),
    "styling": ("Tailwind CSS Architecture", "Modern SaaS Palettes"),
}

# Broad "build me X" signals that should surface the matching domain.
_DOMAIN_SIGNALS: dict[str, tuple[str, ...]] = {
    DOMAINS[0]: ("ui", "ux", "design", "style", "theme", "color", "layout", "font",
                 "animation", "beautiful", "modern", "dark", "landing", "responsive",
                 "dashboard", "icon", "copy", "visual", "look", "site", "store",
                 "page", "checkout"),
    DOMAINS[1]: ("frontend", "react", "next", "component", "hook", "form", "state",
                 "tailwind", "css", "web", "spa", "interactive", "site", "page"),
    DOMAINS[2]: ("backend", "api", "endpoint", "server", "auth", "database logic",
                 "webhook", "queue", "worker", "validation", "rest", "crud"),
    DOMAINS[3]: ("architecture", "schema", "postgres", "redis", "cache", "microservice",
                 "pagination", "websocket", "scale", "system design", "diagram",
                 "multi-tenant", "tenant", "concurrency"),
    DOMAINS[4]: ("docker", "deploy", "ci/cd", "pipeline", "test", "monitoring",
                 "security", "performance", "devops", "nginx", "server", "infrastructure",
                 "observability", "debug"),
}


def _tokens(text: str) -> list[str]:
    return _WORD.findall(text.lower())


def match_skills(
    prompt: str,
    root: str | os.PathLike = ".",
    limit: int = 8,
    min_score: float = 1.0,
) -> list[tuple[Skill, float]]:
    """
    Score every skill against the prompt, then blend in directory-stack hints.

    Returns a list of (skill, score) sorted by descending score, capped at `limit`.
    """
    prompt_l = (prompt or "").lower()
    ptoks = set(_tokens(prompt))

    scored: dict[str, float] = {}

    # 1. Direct trigger matching.
    for skill in ALL_SKILLS:
        score = 0.0
        for trigger in skill.triggers:
            tl = trigger.lower()
            if tl in prompt_l:
                score += 3.0
            elif " " in tl:
                # Multi-word trigger: reward if all its words are present.
                words = [w for w in _tokens(tl) if len(w) > 3]
                if words and all(w in ptoks for w in words):
                    score += 2.0
        if score:
            scored[skill.name] = score

    # 2. Domain-level signals: activate an entire domain for broad phrasing.
    GENERIC_BUILD_TERMS = ("make ", "build ", "create ", "new ", "generate ",
                           "start ", "set up ", "setup ", "full ", "stack",
                           "i want a", "i need a", "i'd like a", "design ",
                           "need a ", "want a ", "ship ", "kickstart ")
    is_generic = any(term in prompt_l for term in GENERIC_BUILD_TERMS)

    for domain, signals in _DOMAIN_SIGNALS.items():
        hits = sum(1 for s in signals if s in prompt_l)
        if hits == 0:
            continue
        # When the prompt is broad AND this domain clearly applies, activate the
        # whole domain; otherwise scale by how many signals matched.
        # Require 2+ hits to avoid bleeding unrelated domains on short prompts.
        if is_generic and hits >= 2:
            bonus = 1.5
        elif is_generic and hits == 1:
            # Soft add so the matching domain still surfaces in a vague prompt,
            # but stays below a domain with a strong direct trigger.
            bonus = 0.6
        else:
            bonus = min(hits, 3) * 0.8
        for skill in ALL_SKILLS:
            if skill.domain == domain:
                scored[skill.name] = scored.get(skill.name, 0.0) + bonus

    # 3. Directory-context stack detection.
    stack = detect_stack(root)
    for hint in stack:
        for name in _STACK_TO_SKILLS.get(hint, ()):
            scored[name] = scored.get(name, 0.0) + 1.5

    # 4. Suppression: "Static Site, No Build Step" contradicts any real
    # framework/bundler request, so drop it whenever the user has explicitly
    # named one. A `static/` directory hint alone must not smuggle it into a
    # Next.js or React build.
    if _needs_a_build(prompt_l):
        scored.pop(_NO_BUILD_SKILL, None)

    ranked = [
        (skill, scored[skill.name])
        for skill in ALL_SKILLS
        if scored.get(skill.name, 0.0) >= min_score
    ]
    ranked.sort(key=lambda pair: pair[1], reverse=True)
    return ranked[:limit]


def format_activation_line(matched: Iterable[tuple[Skill, float]], total: int = 51) -> str:
    """Render the status line shown before each model call."""
    matched = list(matched)
    if not matched:
        return "🧠 Auto-Skills Activated (0/%d)" % total
    names = " • ".join(s.name for s, _ in matched)
    return f"🧠 Auto-Skills Activated ({len(matched)}/{total}): {names}"


def build_directive_block(matched: Iterable[tuple[Skill, float]]) -> str:
    """Render the matched skills as directives for the model's system context."""
    matched = list(matched)
    if not matched:
        return ""
    lines = ["Active skills (apply these conventions; do not narrate them):"]
    for skill, _ in matched:
        lines.append(f"- {skill.name} [{skill.domain}]: {skill.directive}")
    return "\n".join(lines)


# Phrases that indicate the user wants an immediate build, not clarification.
_BUILD_INTENTS = (
    "go", "yes", "build now", "just build", "make it", "create it", "do it",
    "implement", "scaffold", "start", "begin", "now",
)

# Broad, underspecified project requests that deserve clarifying questions.
_CLARIFY_INTENT_MARKERS = (
    "site", "website", "app", "application", "api", "backend", "frontend",
    "store", "shop", "platform", "tool", "dashboard", "system", "page",
)


def wants_clarification(prompt: str) -> bool:
    """
    True when the prompt is a short, broad 'build me X' request that has not
    committed to a stack and has not signalled an immediate build.
    """
    prompt_l = (prompt or "").strip().lower()
    if not prompt_l:
        return False

    words = prompt_l.split()
    # Already detailed enough: long, or containing concrete technical signals.
    if len(words) > 20:
        return False

    if any(intent in prompt_l for intent in _BUILD_INTENTS):
        return False

    # Concrete stack or file-type mentions mean the user has chosen.
    tech = (
        "react", "next", "vue", "svelte", "angular", "tailwind", "express",
        "nest", "fastapi", "django", "flask", "postgres", "postgresql",
        "mongo", "redis", "docker", "typescript", "javascript", "python",
        "node", ".tsx", ".jsx", ".py", ".sql", "api endpoint",
        # Plain-web stack counts as a concrete choice too. Without these,
        # "create index.html ... no JS, no CSS" was misread as underspecified
        # purely because it used the word "page".
        "html", "css", "vanilla", "bootstrap", "sass", "scss", "jquery",
        "static", "no js", "no css", "inline style",
    )
    if any(t in prompt_l for t in tech):
        return False

    # An explicitly named file is the strongest "just build it" signal there
    # is: `index.html`, `app.py`, `src/main.rs` and friends.
    if re.search(r"[A-Za-z0-9_][A-Za-z0-9_.-]*\.[A-Za-z0-9]{1,5}\b", prompt_l):
        return False

    return any(marker in prompt_l for marker in _CLARIFY_INTENT_MARKERS)


CLARIFY_INSTRUCTION = (
    "Before writing any files, ask 2-3 short, specific clarifying questions: "
    "(1) preferred stack, (2) which features matter most, (3) visual style or "
    "design direction. Keep them brief and offer a recommended default for each. "
    "Then say exactly: 'Reply with your choices, or type `go` to build immediately "
    "with my recommended stack.' Do not create files until they answer."
)


BUILD_INSTRUCTION = (
    "Write complete, production-ready files now. Include every import, package "
    "manifest and config needed to run it. Output each file in its own fenced "
    "block with the filename as the heading. Do not ask follow-up questions and "
    "do not narrate a plan - just build."
)


if __name__ == "__main__":  # pragma: no cover - manual smoke test
    for p in ("make an ecommerce site", "build a backend api with postgres",
              "dark glassy landing page with tailwind", "dockerize this next app"):
        m = match_skills(p, root=".")
        print("PROMPT:", p)
        print(" ", format_activation_line(m))
        print()
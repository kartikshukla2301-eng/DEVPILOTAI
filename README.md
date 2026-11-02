<div align="center">

<img src="frontend/public/favicon.svg" alt="DevPilot AI logo" width="72" height="72" />

# DevPilot AI

### Intelligent Code Review & Debugging System

Review, debug, explain, optimize and document code in one workspace.<br/>
Static analysis first, optional AI on top, and every result labelled with where it came from.

<p>
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white" />
  <img alt="FastAPI" src="https://img.shields.io/badge/FastAPI-0.115-009688?logo=fastapi&logoColor=white" />
  <img alt="React" src="https://img.shields.io/badge/React-19-61DAFB?logo=react&logoColor=black" />
  <img alt="TypeScript" src="https://img.shields.io/badge/TypeScript-5.9-3178C6?logo=typescript&logoColor=white" />
  <img alt="Tailwind CSS" src="https://img.shields.io/badge/Tailwind-4-06B6D4?logo=tailwindcss&logoColor=white" />
  <img alt="MongoDB" src="https://img.shields.io/badge/MongoDB-6%2B-47A248?logo=mongodb&logoColor=white" />
</p>

<p>
  <a href="#-features">Features</a> ·
  <a href="#-screenshots">Screenshots</a> ·
  <a href="#-quick-start">Quick start</a> ·
  <a href="#-architecture">Architecture</a> ·
  <a href="#-api-reference">API</a> ·
  <a href="#-security">Security</a>
</p>

<img src="docs/screenshots/dashboard.png" alt="DevPilot AI dashboard" width="100%" />

</div>

---

## Overview

DevPilot AI is a full-stack developer tool for programmers, students and teams. Paste or upload code in **Python, JavaScript, TypeScript, Java, C++, C or Go** and it will:

- find **bugs, code-quality problems, security vulnerabilities and performance issues**, each with a severity, line number and recommended fix;
- **diagnose runtime and compiler errors** from a stack trace and propose a patch;
- **explain code** line by line at beginner, intermediate or advanced level, with Big-O estimates;
- **suggest optimizations** as a before/after diff without touching your original;
- **generate Markdown documentation**;
- keep a searchable **history** of everything, stored per user in MongoDB.

It works fully **without an AI key**, using Python AST, Ruff, Bandit, Radon and DevPilot's own rule engines. Add any OpenAI-compatible key and AI findings are merged in, always marked separately from static findings.

> [!NOTE]
> Static analysis is heuristic. It can miss real problems and can report false positives, and it does not guarantee that code is bug-free or secure. Review AI output before using it.

---

## ✨ Features

| Module | What you get |
|---|---|
| 🔍 **Code Review** | Monaco editor with upload and drag-and-drop, and four analysis categories (bugs, quality, security, performance). Findings appear **inline under the offending line**, with a 0–100 health score, severity breakdown, prioritized action items, suggested corrected code as a diff, and Markdown/JSON export. |
| 🐞 **Debugging Assistant** | Paste code plus an error or stack trace. You get the error classification, root cause, crash line, step-by-step instructions, a patch, and prevention tips. A knowledge base covers about 45 common error patterns, and Python fixes are re-parsed before they are suggested. |
| 📖 **Code Explainer** | Purpose, line-by-line walkthrough, functions and types, variables, detected algorithm, and estimated time and space complexity. Click any line to jump to it in the editor. |
| ⚡ **Code Optimizer** | Safe rewrites on a copy of your code: comprehensions, `''.join`, `enumerate`, set membership, hoisting `strlen`, `===`, and more. Shown as a side-by-side diff with a list of suggestions. The original is never overwritten. |
| 📝 **Doc Generator** | Markdown with an overview, dependencies (stdlib vs third-party), classes, functions, parameter tables, return values, exceptions and usage examples. Live preview and `.md` download. |
| 🗂️ **Review History** | Search, filter by severity, language and project, sort, expand rows inline, open full reports, export and delete. An "All activity" feed covers every module. |
| 📊 **Dashboard** | Weekly activity, severity distribution, language mix, score trend, priority findings, recent reviews and projects. All figures are computed from your stored records, and new users see an empty state. |
| ⚙️ **Settings** | Profile, password change (signs out other sessions), dark/light/system theme, default language, explanation level, AI on/off, AI status, projects, logout everywhere and account deletion. |

**Also included**

- **Ctrl/⌘ + K command palette** for jumping to modules and searching your history.
- **Ctrl/⌘ + Enter** runs the current module.
- A public **landing page** at `/` for visitors.
- **Responsive layout** that switches to a bottom navigation bar on mobile.
- An **AI vs local mode** indicator in the top bar and on every result.

---

## 📸 Screenshots

<table>
  <tr>
    <td width="50%"><img src="docs/screenshots/code-review.png" alt="Code review workspace" /><p align="center"><b>Code Review:</b> inline findings and the inspector panel</p></td>
    <td width="50%"><img src="docs/screenshots/debugger.png" alt="Debugging assistant" /><p align="center"><b>Debugging Assistant:</b> root cause and patch</p></td>
  </tr>
  <tr>
    <td><img src="docs/screenshots/explainer.png" alt="Code explainer" /><p align="center"><b>Code Explainer:</b> synopsis, complexity and walkthrough</p></td>
    <td><img src="docs/screenshots/optimizer.png" alt="Code optimizer" /><p align="center"><b>Code Optimizer:</b> before/after diff</p></td>
  </tr>
  <tr>
    <td><img src="docs/screenshots/documentation.png" alt="Documentation generator" /><p align="center"><b>Doc Generator:</b> Markdown preview and download</p></td>
    <td><img src="docs/screenshots/history.png" alt="Review history" /><p align="center"><b>Review History:</b> filters, stats and audit trail</p></td>
  </tr>
  <tr>
    <td><img src="docs/screenshots/landing.png" alt="Landing page" /><p align="center"><b>Landing page</b></p></td>
    <td><img src="docs/screenshots/login.png" alt="Sign in" /><p align="center"><b>Sign in</b> with live API status</p></td>
  </tr>
  <tr>
    <td><img src="docs/screenshots/dashboard-light.png" alt="Light theme" /><p align="center"><b>Light theme</b></p></td>
    <td><img src="docs/screenshots/command-palette.png" alt="Command palette" /><p align="center"><b>Command palette</b> (Ctrl/⌘ + K)</p></td>
  </tr>
</table>

<p align="center"><img src="docs/screenshots/mobile.png" alt="Mobile layout" width="280" /><br/><b>Mobile layout</b> with bottom navigation</p>

---

## 🚀 Quick start

### Prerequisites

| Tool | Version |
|---|---|
| Python | 3.11 or newer |
| Node.js | 20 or newer |
| MongoDB | 6 or newer, local or [Atlas](https://www.mongodb.com/atlas) |

### 1. Backend

```bash
cd backend
python -m venv .venv
# Windows: .venv\Scripts\activate    ·    macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env               # Windows: copy .env.example .env
```

Set a strong `JWT_SECRET` in `backend/.env`:

```bash
python -c "import secrets; print(secrets.token_urlsafe(64))"
```

Start the API:

```bash
uvicorn app.main:app --reload --port 8000
```

Interactive API docs are at **http://127.0.0.1:8000/docs**, and the health check is at `/api/health`.

### 2. Frontend

```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173** and create an account. The Vite dev server proxies `/api` to the backend.

### Production build

```bash
cd frontend && npm run build      # output in frontend/dist
```

Serve `frontend/dist` behind the same origin as the API. Alternatively, set `VITE_API_URL` at build time and add the frontend origin to `CORS_ORIGINS`.

---

## 🔧 Configuration

All backend settings are read from `backend/.env`. See [`backend/.env.example`](backend/.env.example).

| Variable | Default | Description |
|---|---|---|
| `MONGODB_URI` | `mongodb://localhost:27017` | Local or Atlas URI (`mongodb+srv://user:pass@cluster/...`) |
| `MONGODB_DB` | `devpilot` | Database name |
| `JWT_SECRET` | *(required)* | HMAC secret for access tokens |
| `JWT_ALGORITHM` | `HS256` | Token signing algorithm |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | `1440` | Token lifetime |
| `CORS_ORIGINS` | `http://localhost:5173,…` | Comma-separated allowed origins |
| `AI_API_KEY` | *(empty)* | Leave empty for local analysis mode |
| `AI_BASE_URL` | `https://api.openai.com/v1` | Any OpenAI-compatible endpoint: OpenAI, OpenRouter, Groq, Together, Ollama (`http://localhost:11434/v1`), LM Studio… |
| `AI_MODEL` | `gpt-4o-mini` | Model name for your provider |
| `AI_TIMEOUT_SECONDS` | `60` | AI request timeout |
| `MAX_CODE_CHARS` | `200000` | Maximum submitted code size |

### AI mode vs local mode

| | Local mode (no key) | AI mode (key configured) |
|---|---|---|
| Static analyzers | ✅ always run | ✅ always run |
| AI findings and summary | — | ✅ added and labelled **AI suggestion** |
| Corrected code | Safe automatic fixes | Full AI-corrected version |
| If the AI call fails | — | Falls back to local results with a **Local · AI failed** badge and the reason |

The API key stays on the server. `/api/settings/ai-status` only reports whether AI is configured, plus the model and provider host.

---

## 🏗️ Architecture

```mermaid
flowchart LR
    subgraph Browser
      UI["React 19 + Vite<br/>Monaco · Recharts · Tailwind 4"]
    end
    subgraph API["FastAPI backend"]
      R["Routers<br/>auth · review · debug · explain<br/>optimize · docs · history · settings"]
      S["Services<br/>review · debugger · explainer<br/>optimizer · docgen · report"]
      A["Analyzer registry"]
      PY["Python analyzer<br/>AST · Ruff · Bandit · Radon"]
      CL["C-like rule engine<br/>JS · TS · Java · C · C++ · Go"]
      AI["AI client<br/>OpenAI-compatible (optional)"]
    end
    DB[("MongoDB<br/>local or Atlas")]
    LLM(["LLM provider"])

    UI -- "JWT · REST /api" --> R
    R --> S
    S --> A
    A --> PY
    A --> CL
    S -.-> AI
    AI -.-> LLM
    R <--> DB
```

**Request flow for a code review**

1. The frontend posts code to `/api/code-review/analyze`.
2. The analyzer registry selects the language analyzer. The analyzer **parses the code but never runs it**.
3. Findings are deduplicated, sorted by severity and scored.
4. If AI is enabled, the model receives the code and the static findings, and only *additional* issues are merged in, tagged `source: "ai"`.
5. The report is saved to `code_reviews` under the current user and returned to the UI.

### Analyzer engine

```
backend/app/analyzers/
├── base.py             # AnalysisContext, FindingCollector, source masking, secret scanning, duplicate detection
├── tools.py            # Ruff / Bandit / Radon / node --check / gofmt wrappers (parse only)
├── python_analyzer.py  # AST visitor + Ruff + Bandit + Radon, with built-in fallbacks when a tool is missing
├── clike.py            # Rule engine for JS/TS/Java/C/C++/Go on comment- and string-masked source
└── registry.py         # Language → analyzer map, metrics, scoring
```

**Adding a language:** implement `analyze_x(ctx: AnalysisContext) -> AnalyzerResult`, register it in `ANALYZERS`, and add the language to `SUPPORTED_LANGUAGES` (backend) and `LANGUAGES` (frontend). For brace-based languages, adding rules to `clike.RULES` is usually enough.

**Scoring:** findings are weighted by severity (critical 25, high 12, medium 5, low 1.5, info 0.25), normalized by code size, and mapped to 0–100 with `100·e^(−penalty/45)`. Any critical finding caps the score at 59, and any high finding caps it at 79. Grades: **A ≥ 90 · B ≥ 80 · C ≥ 70 · D ≥ 60 · F**.

---

## 🗄️ Database design

| Collection | Contents | Indexes |
|---|---|---|
| `users` | name, email (lowercased), bcrypt `password_hash`, bio, `token_version`, timestamps (JSON-schema validated) | unique `email` |
| `user_settings` | theme, default language, explanation level, AI preference | unique `user_id` |
| `projects` | name, description, language | `(user_id, updated_at)`, unique `(user_id, name)` |
| `code_reviews` | full report: findings, summaries, score, metrics, code, suggested code, `project_id` | `(user_id, created_at)`, `(user_id, language)`, `(user_id, max_severity)`, `(user_id, project_id)` |
| `debugging_sessions` | code, error, context and diagnosis | `(user_id, created_at)` |
| `code_explanations` | code and explanation | `(user_id, created_at)` |
| `code_artifacts` | optimization and documentation outputs (`kind` discriminator) | `(user_id, created_at)`, `(user_id, kind)` |

Every query is scoped to the authenticated `user_id`. Collections, validators and indexes are created on startup, and the setup is idempotent.

---

## 📡 API reference

All routes are under `/api`. Everything except `auth/register`, `auth/login` and `health` requires `Authorization: Bearer <token>`. Full schemas are at `/docs`.

| Prefix | Endpoints |
|---|---|
| `/auth` | `POST /register` · `POST /login` · `POST /logout` (revokes all tokens) · `GET /me` |
| `/users` | `GET` / `PATCH /me` · `POST /me/password` · `DELETE /me` |
| `/dashboard` | `GET /summary?tz_offset_minutes=` |
| `/projects` | `GET` · `POST` · `GET` / `PATCH` / `DELETE /{id}` |
| `/code-review` | `POST /analyze` · `POST /upload` · `GET /languages` · `GET /{id}` |
| `/debug` | `POST` · `GET /sessions` · `GET` / `DELETE /sessions/{id}` |
| `/explain` | `POST` · `GET /history` · `GET` / `DELETE /history/{id}` |
| `/optimize` | `POST` · `GET /history` · `GET` / `DELETE /history/{id}` |
| `/documentation` | `POST` · `GET /history` · `GET` / `DELETE /history/{id}` · `GET /history/{id}/download` |
| `/history` | `GET /reviews` (search, language, severity, project_id, sort, page, page_size) · `GET /stats` · `GET` / `DELETE /reviews/{id}` · `GET /reviews/{id}/export?format=md\|json` · `GET /activity` · `DELETE /activity/{type}/{id}` |
| `/settings` | `GET` · `PATCH` · `GET /ai-status` |

<details>
<summary><b>Example: run a review</b></summary>

```bash
curl -X POST http://127.0.0.1:8000/api/code-review/analyze \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{
        "code": "password = \"hunter22\"\nprint(eval(input()))",
        "language": "python",
        "filename": "demo.py",
        "categories": ["bug", "security"]
      }'
```

The response includes `score`, `grade`, `summary` (per severity), `findings[]` (with `severity`, `line`, `title`, `recommendation`, `snippet`, `source`), `metrics`, `suggested_code` and `ai_used`.
</details>

**Status codes:** 201 created · 204 deleted / logged out · 401 invalid or expired token · 404 missing record *or another user's record* · 409 duplicate · 413 too large · 415 unsupported upload · 422 validation error · 429 rate limited · 503 database unavailable.

---

## 🔒 Security

- **Passwords** are hashed with bcrypt. Plaintext is never stored or logged.
- **Sessions:** JWTs carry a `token_version`. Logout and password changes increment it, which revokes every outstanding token on every device.
- **Rate limiting:** login and registration allow 10 requests per minute per IP, and analysis endpoints allow 60. The limiter runs in-process, so use Redis or similar if you run multiple workers.
- **Timing-safe login:** a failed login takes the same time whether or not the email exists, so response times don't reveal registered emails.
- **Submitted code is never executed.** It is only parsed, and temporary files are deleted immediately.
- **Data isolation:** every record belongs to its user. Other users' records return 404.
- **Input handling:** search is regex-escaped, uploads are checked for extension, size and UTF-8, and Markdown renders without raw HTML.
- **Headers:** `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY` and `Referrer-Policy: no-referrer`.

> [!TIP]
> For public deployments, consider httpOnly cookies with CSRF protection instead of browser-stored tokens, add a Content-Security-Policy, and serve everything over HTTPS.

---

## 🧰 Tech stack

| Layer | Technologies |
|---|---|
| **Frontend** | React 19, Vite, TypeScript, Tailwind CSS 4, Monaco Editor (bundled locally, no CDN), Recharts, Lucide React, Axios, React Router, react-markdown |
| **Backend** | Python 3.11+, FastAPI, Pydantic v2, PyMongo, python-jose (JWT), Passlib + bcrypt, httpx |
| **Analysis** | Python `ast`, Ruff, Bandit, Radon, `node --check` and `gofmt -e` when available, DevPilot rule engines |
| **Database** | MongoDB (local or Atlas) |
| **Design** | DevPilot design system: layered dark canvas, Electric Violet `#8B5CF6` accent, Geist / Inter / JetBrains Mono. Tokens are in [`frontend/src/index.css`](frontend/src/index.css) |

---

## 📁 Project structure

```
DEVPILOTAI/
├── backend/
│   ├── app/
│   │   ├── core/          # config, database (collections, validators, indexes), security (JWT, hashing)
│   │   ├── analyzers/     # static analysis engines
│   │   ├── services/      # review, debugger, explainer, optimizer, docgen, report, ai client
│   │   ├── routes/        # auth, users, dashboard, projects, code_review, assistants, history, settings
│   │   ├── schemas.py     # Pydantic request/response models
│   │   └── main.py        # app factory, CORS, error handlers, routers
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── components/    # UI primitives, CodeEditor (Monaco), charts, layout, result views
│   │   ├── context/       # auth and notifications
│   │   ├── lib/           # API client, types, constants, samples, Monaco setup
│   │   └── pages/         # Landing, Auth, Dashboard, CodeReview, Debugger, Explainer, Optimizer, Documentation, History, Settings
│   └── package.json
└── docs/screenshots/      # images used in this README
```

---

## ⚠️ Known limitations

- Python gets the deepest analysis. JavaScript, TypeScript, Java, C, C++ and Go use pattern and structure heuristics rather than full compilers, and TypeScript is not type-checked.
- Complexity estimates are heuristics based on loop nesting, recursion and well-known operations.
- Code longer than about 24,000 characters is truncated before it is sent to the AI provider.
- The rate limiter is in-memory, so its limits apply per backend process.

---

<div align="center">
<sub>Built with FastAPI, React and MongoDB · DevPilot AI</sub>
</div>

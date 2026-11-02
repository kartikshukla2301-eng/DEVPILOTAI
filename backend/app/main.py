import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from pymongo.errors import PyMongoError, ServerSelectionTimeoutError

from app.core.config import get_settings
from app.core.database import close_client, get_client, init_db
from app.routes import auth, code_review, dashboard, history, projects, settings, users
from app.routes.assistants import debug_router, docs_router, explain_router, optimize_router
from app.services import ai

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("devpilot")


@asynccontextmanager
async def lifespan(app: FastAPI):
    s = get_settings()
    if s.jwt_secret in ("dev-insecure-secret-change-me", "change-me-to-a-long-random-string"):
        log.warning("JWT_SECRET is using a default value. Set a long random JWT_SECRET in backend/.env before deploying.")
    try:
        init_db()
        log.info("Connected to MongoDB database '%s'", s.mongodb_db)
    except PyMongoError as exc:
        log.error("MongoDB is not reachable (%s). API calls that need the database will return 503 until it is available.", exc.__class__.__name__)
    log.info("Analysis mode: %s", f"AI ({s.ai_model})" if s.ai_enabled else "local rule-based (no AI_API_KEY set)")
    yield
    close_client()


app = FastAPI(title="DevPilot AI API", version="1.0.0", lifespan=lifespan,
              description="Intelligent code review and debugging system.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().cors_origin_list,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type"],
)


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers.setdefault("X-Content-Type-Options", "nosniff")
    response.headers.setdefault("X-Frame-Options", "DENY")
    response.headers.setdefault("Referrer-Policy", "no-referrer")
    return response


@app.exception_handler(ServerSelectionTimeoutError)
async def db_unavailable(_: Request, __: ServerSelectionTimeoutError) -> JSONResponse:
    return JSONResponse(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, content={"detail": "Database is unavailable. Check that MongoDB is running and MONGODB_URI is correct."})


@app.exception_handler(PyMongoError)
async def db_error(_: Request, exc: PyMongoError) -> JSONResponse:
    log.exception("Database error: %s", exc.__class__.__name__)
    return JSONResponse(status_code=status.HTTP_500_INTERNAL_SERVER_ERROR, content={"detail": "A database error occurred."})


for r in (auth.router, users.router, dashboard.router, projects.router, code_review.router, debug_router, explain_router,
          optimize_router, docs_router, history.router, settings.router):
    app.include_router(r, prefix="/api")


@app.get("/api/health", tags=["health"])
def health() -> dict:
    db_ok = True
    try:
        get_client().admin.command("ping")
    except PyMongoError:
        db_ok = False
    return {"status": "ok" if db_ok else "degraded", "database": "up" if db_ok else "down",
            "analysis_mode": "ai" if ai.ai_available() else "local"}

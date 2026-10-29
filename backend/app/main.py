"""
backend/app/main.py

Production FastAPI application for SSQ-Quant-System.
Configures:
- Lifespan DB initialization (WAL mode & schema registration)
- CORS middleware for Frontend dark quant terminal
- RESTful API routers mounted under /api/v1 (History, Predict, Backtest, Adaptive)
- Health check endpoints at / and /api/health
"""

import starlette.routing

if not getattr(starlette.routing.Router, "_compat_patched", False):
    _orig_router_init = starlette.routing.Router.__init__

    def _compat_router_init(self, *args, on_startup=None, on_shutdown=None, **kwargs):
        self.on_startup = list(on_startup or [])
        self.on_shutdown = list(on_shutdown or [])
        return _orig_router_init(self, *args, **kwargs)

    starlette.routing.Router.__init__ = _compat_router_init
    starlette.routing.Router._compat_patched = True

from contextlib import asynccontextmanager
from typing import Any, Dict
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from sqlalchemy import select, func

from backend.app.database import init_db, SessionLocal
from backend.app.models import DrawHistory, PredictionBatch
from backend.app.api.history import router as history_router
from backend.app.api.predict import router as predict_router
from backend.app.api.backtest import router as backtest_router
from backend.app.api.adaptive import router as adaptive_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan context manager.
    Initializes database tables on startup and pre-warms cache.
    """
    init_db()
    with SessionLocal() as db:
        try:
            from backend.app.services.collision_cache import CollisionCache
            CollisionCache.get_instance().ensure_loaded(db)
        except Exception:
            pass
    yield


app = FastAPI(
    title="SSQ-Quant-System API",
    version="2.0.0",
    description="Discrete Sequence Quantitative Analysis & Prediction Platform RESTful Service",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

# CORS middleware for development and production dark terminal UI
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.exception_handler(ValueError)
async def value_error_handler(request: Request, exc: ValueError):
    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content={"detail": str(exc)},
    )


# Health check endpoints
@app.get("/", tags=["Health"])
def root_health():
    return {
        "status": "healthy",
        "service": "SSQ-Quant-System API",
        "version": "2.0.0",
    }


@app.get("/api/health", tags=["Health"])
@app.get("/api/v1/health", tags=["Health"])
def api_health():
    with SessionLocal() as db:
        total_draws = db.scalar(select(func.count(DrawHistory.id))) or 0
        latest_draw = db.scalar(select(DrawHistory).order_by(DrawHistory.issue_no.desc()).limit(1))
        latest_issue = latest_draw.issue_no if latest_draw else None
        total_batches = db.scalar(select(func.count(PredictionBatch.id))) or 0

    return {
        "status": "healthy",
        "engine": "Local-Quant-Ensemble",
        "version": "2.0.0",
        "database": {
            "dialect": "sqlite",
            "total_draws": total_draws,
            "latest_issue": latest_issue,
            "total_prediction_batches": total_batches,
        },
    }


# Mount API v1 routers
app.include_router(history_router, prefix="/api/v1/history", tags=["History & Trends"])
app.include_router(predict_router, prefix="/api/v1/predict", tags=["Prediction Lab & Archives"])
app.include_router(backtest_router, prefix="/api/v1/backtest", tags=["Backtest & Sandbox"])
app.include_router(adaptive_router, prefix="/api/v1/adaptive", tags=["Adaptive Strategy Loop"])

# Also mount verification under predict for URL flexibility (/api/v1/predict/verify/{issue_no})
app.include_router(backtest_router, prefix="/api/v1/predict", tags=["Verification"])

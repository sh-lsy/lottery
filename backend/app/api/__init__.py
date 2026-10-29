"""
backend/app/api/__init__.py

FastAPI RESTful API routers package.
Includes Starlette 1.x compatibility shim for FastAPI Router on_startup/on_shutdown.
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

from backend.app.api.history import router as history_router
from backend.app.api.predict import router as predict_router
from backend.app.api.backtest import router as backtest_router
from backend.app.api.adaptive import router as adaptive_router

__all__ = [
    "history_router",
    "predict_router",
    "backtest_router",
    "adaptive_router",
]

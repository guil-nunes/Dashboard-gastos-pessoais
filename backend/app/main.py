from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse

from app.api import (
    accounts,
    categories,
    dashboard,
    health,
    imports,
    installments,
    merchants,
    recurrences,
    rules,
    transactions,
)
from app.config import get_settings


def _serve_frontend(app: FastAPI, dist: Path) -> None:
    """Uso real (spec §7.5): serve o `frontend/dist`, com fallback do BrowserRouter."""
    root = dist.resolve()
    index = root / "index.html"

    @app.get("/{path:path}", include_in_schema=False)
    def frontend(path: str) -> FileResponse:
        if path == "api" or path.startswith("api/"):
            raise HTTPException(status_code=404, detail="Not Found")
        candidate = (root / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate)
        return FileResponse(index)


def create_app(frontend_dist: Path | None = None) -> FastAPI:
    app = FastAPI(title="Dashboard de Gastos Pessoais")
    for module in (
        health,
        imports,
        accounts,
        transactions,
        merchants,
        categories,
        rules,
        dashboard,
        installments,
        recurrences,
    ):
        app.include_router(module.router, prefix="/api")
    dist = frontend_dist if frontend_dist is not None else get_settings().frontend_dist
    if (dist / "index.html").is_file():
        _serve_frontend(app, dist)
    return app


app = create_app()

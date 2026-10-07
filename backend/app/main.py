from fastapi import FastAPI

from app.api import accounts, health, imports


def create_app() -> FastAPI:
    app = FastAPI(title="Dashboard de Gastos Pessoais")
    app.include_router(health.router, prefix="/api")
    app.include_router(imports.router, prefix="/api")
    app.include_router(accounts.router, prefix="/api")
    return app


app = create_app()

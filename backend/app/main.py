from fastapi import FastAPI

from app.api import health


def create_app() -> FastAPI:
    app = FastAPI(title="Dashboard de Gastos Pessoais")
    app.include_router(health.router, prefix="/api")
    return app


app = create_app()

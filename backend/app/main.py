from __future__ import annotations


from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api.v1 import appointments, auth, audit, diagnosis_codes, patients, visits
from app.core.config import settings
from app.db.session import get_session, init_db
from app.services import ensure_seed_data, start_background_services, stop_background_services

app = FastAPI(title=settings.project_name)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.on_event("startup")
def on_startup() -> None:
    init_db()
    with get_session() as session:
        ensure_seed_data(session)
    start_background_services()


@app.on_event("shutdown")
def on_shutdown() -> None:
    stop_background_services()


@app.get("/healthz", tags=["system"])
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(auth.router, prefix="/api/v1")
app.include_router(patients.router, prefix="/api/v1")
app.include_router(appointments.router, prefix="/api/v1")
app.include_router(audit.router, prefix="/api/v1")
app.include_router(visits.router, prefix="/api/v1")
app.include_router(diagnosis_codes.router, prefix="/api/v1")


build_path = Path(settings.frontend_build_path).resolve()

if build_path.exists() and build_path.is_dir():
    app.mount("/", StaticFiles(directory=build_path, html=True), name="frontend")

    @app.get("/{path:path}", include_in_schema=False)
    async def serve_spa(_path: str) -> FileResponse:  # pragma: no cover - filesystem dependent
        return FileResponse(build_path / "index.html")

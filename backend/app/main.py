from __future__ import annotations


from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import appointments, auth, audit, patients
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

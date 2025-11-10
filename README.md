# Potilastieto Backend MVP

This repository contains the first runnable slice of the Patient Information System specified in `specs/patient_system_requirements.csv`. The implementation follows the architecture and API descriptions in `docs/architecture.md` and `docs/api.md`, focusing on the backend services so that UI work can build on a stable foundation.

## Features in this version

- FastAPI backend with SQLModel/SQLite persistence (`REQ-NF-ARCH-001`).
- JWT authentication with refresh tokens and seeded roles (`REQ-NF-SEC-001`, `REQ-F-ADM-001`).
- Patient registry with contacts, consents, history snapshots, and soft-archive support (`REQ-F-REG-001` … `REQ-F-REG-005`).
- Appointment scheduling with conflict detection, rescheduling, and cancellation flows (`REQ-F-APPT-001`, `REQ-F-APPT-003`).
- Audit logging and background cleanup of expired tokens and overdue appointments (`REQ-NF-SEC-003`).
- Requirement status tracking via `specs/requirement_status.yml` and `tools/spec_loader.py`.

The first runnable version exposes the backend APIs and background services required for future frontend work.

## Installation (Windows 11)

1. **Install Python 3.11**
   - Download the Windows installer from [python.org](https://www.python.org/downloads/).
   - During installation, check “Add Python to PATH”.
2. **Create a virtual environment**
   ```powershell
   cd path\to\potilastieto
   python -m venv .venv
   .\.venv\Scripts\Activate.ps1
   ```
3. **Install dependencies**
   ```powershell
   pip install --upgrade pip
   pip install -e .[dev]
   ```
4. **Run database migrations & start the API**
   ```powershell
   uvicorn app.main:app --reload
   ```
   The API will be available at `http://127.0.0.1:8000` with interactive docs at `/docs`.
5. **Generate requirement status JSON (optional)**
   ```powershell
   python tools/spec_loader.py --output specs/spec.json
   ```
   > ℹ️ Install `PyYAML` via `pip install pyyaml` if the loader reports a missing dependency.

## API Overview

All endpoints live under `/api/v1` and are documented in `docs/api.md`. Authentication uses Bearer tokens returned by `/api/v1/auth/login`.

## Requirement Tracking Workflow

- Update requirement statuses in `specs/requirement_status.yml` to `done` once a requirement is implemented and tested.
- Regenerate `specs/spec.json` with `python tools/spec_loader.py` to obtain an aggregated view of coverage.
- Use the generated file during reviews to highlight remaining `todo` requirements.

## Development Notes

- The backend seeds three roles (`admin`, `doctor`, `nurse`) and a default admin account (`admin` / `admin123`) on startup. Change the credentials via environment variables before production use.
- Background services automatically purge expired refresh tokens and mark overdue appointments as completed.
- All audit events include basic request metadata; extend `get_audit_context` when the frontend is available.

Refer to `docs/implementation_plan.md` for the phased roadmap.

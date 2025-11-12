# Potilastieto Platform MVP

This repository contains the first runnable slice of the Patient Information System specified in `specs/patient_system_requirements.csv`. The implementation follows the architecture and API descriptions in `docs/architecture.md` and `docs/api.md`, focusing on the backend services so that UI work can build on a stable foundation while introducing a Vite-based frontend workspace.

## Features in this version

- FastAPI backend with SQLModel/SQLite persistence (`REQ-NF-ARCH-001`).
- JWT authentication with refresh tokens and seeded roles (`REQ-NF-SEC-001`, `REQ-F-ADM-001`).
- Patient registry with contacts, consents, history snapshots, and soft-archive support (`REQ-F-REG-001` … `REQ-F-REG-005`).
- Appointment scheduling with conflict detection, rescheduling, and cancellation flows (`REQ-F-APPT-001`, `REQ-F-APPT-003`).
- Audit logging and background cleanup of expired tokens and overdue appointments (`REQ-NF-SEC-003`).
- Requirement status tracking via `specs/requirement_status.yml` and `tools/spec_loader.py`.
- React + Vite + Tailwind frontend workspace for future UI stories (`REQ-NF-ARCH-001`).

The first runnable version exposes the backend APIs and background services required for future frontend work.

## Backend Installation (Windows 11)

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
   pip install -e ".[dev]"
   ```
   > ℹ️ The quoted `pip install -e ".[dev]"` command installs Alembic and the rest of the development dependencies needed for database migrations.
4. **Build the frontend assets for static hosting**
   ```powershell
   cd frontend
   npm run build
   cd ..
   ```
   Ensure the `frontend/dist` directory exists before launching Uvicorn so the compiled SPA can be served by FastAPI.
5. **Run database migrations & start the API**
   ```powershell
   uvicorn app.main:app --reload --app-dir backend
   ```
   The project code resides in the `backend` directory, so the `--app-dir backend` flag ensures Python can resolve the `app` package. The API will be available at `http://127.0.0.1:8000` with interactive docs at `/docs`.
5. **Generate requirement status JSON (optional)**
   ```powershell
   python tools/spec_loader.py --output specs/spec.json
   ```
   > ℹ️ Install `PyYAML` via `pip install pyyaml` if the loader reports a missing dependency.

## Frontend Installation (Windows 11 / macOS / Linux)

1. **Install Node.js 18+**
   - Download from [nodejs.org](https://nodejs.org/) or use a version manager such as `fnm`, `nvm`, or `asdf`.
2. **Install dependencies**
   ```bash
   cd frontend
   npm install
   ```
   This installs React, Vite, Tailwind CSS, and PostCSS tooling required for development builds.
3. **Start the development server**
   ```bash
   npm run dev
   ```
   Vite serves the bundle at `http://localhost:5173` by default and automatically reloads when files change.
4. **Create a production build**
   ```bash
   npm run build
   ```
   The output is written to `frontend/dist/` and is ready to be served by FastAPI or a CDN.
5. **Preview the production build**
   ```bash
   npm run preview
   ```
   This serves the optimized build for smoke testing before integrating with the backend.

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
- Frontend environment variables can be configured via a `.env` file in `frontend/` (e.g., `VITE_API_BASE_URL=https://localhost:8000/api`).

Refer to `docs/implementation_plan.md` for the phased roadmap.

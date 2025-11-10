# Implementation Plan

This plan translates the CSV requirements into an incremental delivery roadmap. Each work item references requirement identifiers from `specs/patient_system_requirements.csv` so their completion status can be tracked programmatically.

## Version Milestones

1. **V0 – Spec & Persistence Foundation (runnable backend skeleton)**  
   Delivers the requirement tracking tooling, database schema, and background services so that an empty FastAPI server can boot, persist data, and expose health/auth endpoints. This is the first runnable slice that other work will build upon.
2. **V1 – Core Clinical APIs**  
   Implements patients, appointments, audit logging, and lightweight RBAC-authentication aligned with `docs/api.md`. After V1 the backend is feature-complete for MVP functional requirements and suitable for frontend integration.
3. **V2 – Frontend and Experience Layers**  
   Provides the React UI, localization scaffolding, accessibility treatments, and workflow polish driven by remaining CSV requirements.
4. **V3 – Hardening & Extensions**  
   Adds advanced security, performance tuning, optional integrations (notifications, slot management), and automated testing breadth.

## Work Breakdown

### 1. Tooling & Requirement Tracking (V0)
- Parse the CSV and generate a normalized JSON tree (`tools/spec_loader.py`).
- Introduce a status override file where implemented requirements are marked `done` or `in_progress`. Missing entries default to `todo` for quick gap detection (`REQ-NF-ARCH-004`).
- Document how to run the generator and interpret the statuses in `README.md`.

### 2. Backend Platform Baseline (V0)
- Establish FastAPI app with configuration, dependency injection, and SQLModel session management (`REQ-NF-ARCH-001`).
- Define domain models for users, roles, patients, consents, contacts, patient history, appointments, and audit events (`REQ-F-REG-001`, `REQ-F-REG-002`, `REQ-F-REG-003`, `REQ-F-REG-004`, `REQ-F-REG-005`, `REQ-F-APPT-001`, `REQ-F-APPT-003`, `REQ-F-ADM-001`, `REQ-NF-SEC-003`).
- Create database migration bootstrap (automatic `create_all` for the MVP) and background scheduler for cleanup tasks such as expiring refresh tokens (`REQ-NF-ARCH-001`).
- Seed development roles and an administrator account for immediate access (`REQ-F-ADM-001`).
- Ship health and auth endpoints returning mock data so the backend can already be started (first runnable version).

### 3. Core Domain Services & APIs (V1)
- Implement JWT-based authentication and refresh token rotation with simple server-side storage (`REQ-NF-SEC-001`).
- Implement patient service with CRUD, history snapshots, consents, contacts, and archiving logic plus audit hooks (`REQ-F-REG-001`..`005`, `REQ-NF-SEC-003`, `REQ-NF-LEGAL-002`).
- Implement appointment scheduling, rescheduling, cancellation flows with slot conflict detection and audit logging (`REQ-F-APPT-001`, `REQ-F-APPT-003`).
- Provide audit query endpoints with filtering by actor/resource/time (`REQ-NF-SEC-003`).
- Centralize RBAC checks through dependency helpers (roles doctor/nurse/admin) (`REQ-F-ADM-001`, `REQ-NF-SEC-002`).
- Ensure every service raises structured errors and audit events capture metadata required by security/legal requirements.

### 4. Observability & Background Services (V1)
- Extend background worker to purge expired refresh tokens and transition long-overdue appointments to `completed` when needed (`REQ-NF-SEC-003`, `REQ-F-APPT-003`).
- Add structured logging and correlation IDs for audit context (`REQ-NF-LEGAL-001`).

### 5. Frontend Foundations (V2)
- Scaffold React + Vite app with routing, localization, and session management stubs.
- Implement login flow, patient registry screens, appointment board, and audit viewer aligned with API responses.
- Apply Tailwind for responsive layout per CSV usability requirements (`REQ-F-UX-DOCTOR`, `REQ-F-NURSE`, `REQ-F-USAB-001`).

### 6. Hardening & Extended Requirements (V3+)
- Replace in-memory background scheduler with pluggable job runner if needed.
- Integrate accessibility testing, data export/import, billing/reporting stubs, and EMR features as prioritized from the CSV.
- Expand automated test suites for backend and frontend with coverage reports per requirement ID.

## Requirement Tracking Approach

- `specs/requirement_status.yml` stores overrides such as:
  ```yaml
  REQ-F-REG-001: done
  REQ-F-APPT-001: in_progress
  ```
- `tools/spec_loader.py` reads the CSV and merges override statuses, defaulting to `todo` when no override exists. Output is written to `specs/spec.json` to support reporting and CI checks.
- Development workflow:
  1. Implement functionality tied to requirements.
  2. Update `specs/requirement_status.yml` entries to `done` when the code is merged.
  3. Regenerate `specs/spec.json` (`python tools/spec_loader.py --format json`).
  4. Use the generated file to identify gaps before releases.


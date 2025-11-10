# AGENTS.md

This document defines the shared operational rules and conventions for all OpenAI Codex agents contributing to this Patient Information System project. It remains valid throughout the full lifecycle of the system — from the initial MVP to extended releases.

---

## Mission
To build and maintain a modular, testable, and secure patient information system based on the CSV specification located at `specs/patient_system_requirements.csv`. Each agent uses this file as the single source of truth for requirements and system scope.

The system must remain:
- **Lightweight:** Installable and runnable locally without cloud dependencies.
- **Extensible:** Architecture supports feature expansion without major refactors.
- **Secure by design:** All data access audited, roles enforced, and PII protected.
- **Documented:** Architecture, API, and data model described and kept synchronized.

---

## Technology Stack
- **Backend:** FastAPI (Python 3.11) + SQLite, later extendable to PostgreSQL.
- **Frontend:** React + Vite + TypeScript + Tailwind.
- **Auth:** Local user database with JWT (development use only).
- **ORM:** SQLModel or SQLAlchemy.
- **Testing:** Pytest (backend), Vitest (frontend).
- **Optional:** Docker for local development.

Alternative frameworks are allowed only if a technical agent justifies the switch and consistency with the CSV specification is maintained.

---

## Repository Structure
```
/specs/
  patient_system_requirements.csv
  spec.json (generated)
/docs/
  architecture.md
  api.md
  tests.md
/backend/
  app/
    main.py
    models/
    schemas/
    api/v1/
    services/
    auth/
  tests/
/frontend/
  src/
    pages/
    components/
    features/
  public/
/tools/
  spec_loader.py
```

Agents must not alter `patient_system_requirements.csv` directly. Derived artifacts (e.g., JSON tree or documentation) must be generated from it programmatically.

---

## Core Entities
Typical domain objects expected from the CSV specification include:
- `Patient`
- `Appointment`
- `User`
- `Role`
- `AuditEvent`

Additional entities can be introduced when justified by new requirements or refactoring needs.

---

## Roles and Responsibilities

### Architect Agent
- Interpret the CSV structure to build a requirement tree.
- Maintain `docs/architecture.md` and `docs/api.md`.
- Ensure separation of concerns and modularity across backend and frontend.
- Keep diagrams and interface definitions synchronized with code.

### Backend Agent
- Implement all service endpoints as defined in `docs/api.md`.
- Maintain clear layering: API → Service → Model.
- Keep database schema migrations consistent.
- Write unit tests and data validation rules.
- Enforce authentication, authorization, and audit logging.

### Frontend Agent
- Build user‑facing components using React + TypeScript.
- Follow the layout, UX flow, and API contracts.
- Implement client‑side validation and error handling.
- Maintain reusability of UI components.

### Data Modeling Agent
- Parse the CSV and produce `specs/spec.json`.
- Validate required columns (id, parent, name, class, status, type, description).
- Expose CLI arguments for filtering or summarizing the spec.

### QA Agent
- Write acceptance and smoke tests linked to requirement IDs.
- Maintain `docs/tests.md`.
- Verify coverage and enforce DoD (Definition of Done).

### DevEx Agent
- Manage setup scripts, linting, and testing pipelines.
- Ensure consistent formatting across the repo.
- Maintain `Makefile`, `README.md`, and CI scripts.

---

## Definition of Done (DoD)
A task or requirement is considered done when:
- Code compiles and passes all automated tests.
- Corresponding documentation and API specs are updated.
- Security and privacy guidelines are respected.
- CSV reference ID is included in the commit message or PR description.

---

## Communication Principles
- Each agent commits small, isolated changes.
- Document reasoning for architectural decisions in markdown files.
- Never introduce hard‑coded secrets, credentials, or real patient data.
- Use pseudonymized data for testing.

---

## Prompt Templates
### General Template
```
You act as the [ROLE] agent. Follow AGENTS.md rules. Do not modify the CSV file.
Work only within your defined responsibility. Keep outputs modular and documented.
```

### Example Roles
**Architect Agent Prompt**
```
Create or update docs/architecture.md and docs/api.md.
Define entities, relationships, and endpoints based on specs/patient_system_requirements.csv.
Ensure consistency with the repository layout.
```

**Backend Agent Prompt**
```
Implement or update FastAPI backend modules according to docs/api.md.
Include data models, services, and endpoints. Maintain audit logging and role enforcement.
Document how to run the backend locally.
```

**Frontend Agent Prompt**
```
Implement or update the React + Vite + TypeScript frontend according to api.md endpoints.
Ensure clear UX flow for patient registration, appointment handling, and audit review.
```

---

## Data Security and Privacy
- All personal or medical data in development environments must be pseudonymized.
- Logging must never include sensitive values (only references or IDs).
- JWT authentication is for development only and must be replaced by a production‑grade mechanism later.

---

## Extension Guidelines
- New requirements must originate from the CSV file or an approved derived issue.
- Each new agent task must link to its requirement ID(s).
- Major architectural or stack changes require explicit reasoning by the Architect agent.

---

This AGENTS.md provides the unified behavioral and structural guide for all Codex agents throughout the project lifecycle.


# API Contract (MVP)

The REST API follows JSON over HTTPS (HTTP for local development) and aligns with the requirements defined in `specs/patient_system_requirements.csv`. All endpoints live under `/api/v1`. Requests and responses use snake_case keys.

## Common Conventions

- **Authentication**: Bearer JWT tokens obtained via `/api/v1/auth/login`. Refresh tokens rotate via `/api/v1/auth/refresh` (`REQ-NF-SEC-001`).
- **Authorization**: Role-based access control enforced per route (doctor, nurse, billing, admin) (`REQ-F-ADM-001`, `REQ-NF-SEC-002`).
- **Audit Logging**: Every read or write to patient or appointment data records an `AuditEvent` with actor, timestamp, resource, and action (`REQ-NF-SEC-003`). Metadata is filtered by `app.services.audit_policy` so only allow-listed keys such as `patient_ref`, `identifier_token`, `source_patient_ref`, `merged_into_ref`, `previous_start`, `previous_end`, `reason`, `notify`, `auto`, `result_count`, and `index` are persisted. Personal identifiers (e.g., hetu) are salted and hashed before storage to satisfy `REQ-NF-LEGAL-001`.
- **Pagination**: List endpoints accept `page` (default 1) and `page_size` (default 25, max 100).
- **Filtering**: Standard query parameters such as `search`, `status`, `start_date`, `end_date` are optional filters noted per resource.
- **Error Format**: Errors respond with `{ "detail": "message", "code": "ERROR_CODE", "errors": [...] }` and HTTP status codes (400, 401, 403, 404, 409, 422, 500).

## `/api/v1/patients`

Billing users have read-only access to patient data (list and detail). Write operations remain limited to clinical roles, while merges and archival continue to require admin permissions (`REQ-F-REG-002`).

### GET `/api/v1/patients`
- **Description**: List patients with optional filtering by `search` (name, identifier) and `status` (`active`, `archived`).
- **Roles**: doctor, nurse, billing, admin.
- **Responses**:
  - `200 OK`: `{ "items": [PatientSummary], "page": 1, "page_size": 25, "total": 2 }`.

### POST `/api/v1/patients`
- **Description**: Create a patient with demographics, consents, and contacts (`REQ-F-REG-001`, `REQ-F-REG-003`, `REQ-F-REG-004`).
- **Roles**: nurse, doctor, admin.
- **Request Body**:
  ```json
  {
    "identifier": "123456-789A",
    "first_name": "Anna",
    "last_name": "Example",
    "date_of_birth": "1990-05-20",
    "sex": "female",
    "contact_info": {
      "phone": "+358401234567",
      "email": "anna@example.com",
      "address": {
        "street": "Testikatu 1",
        "postal_code": "00100",
        "city": "Helsinki"
      }
    },
    "consents": [
      {"type": "general", "status": "granted", "granted_at": "2024-01-01T10:00:00Z"}
    ],
    "contacts": [
      {"name": "Mikko Example", "relationship": "spouse", "phone": "+358401234568", "is_guardian": false}
    ]
  }
  ```
- **Responses**:
  - `201 Created`: Returns full `PatientDetail` including generated `id`, `created_at`, `updated_at`.
  - `409 Conflict`: Duplicate identifier or demographics. Returns `{ "detail": "Potilas on jo olemassa", "code": "PATIENT_DUPLICATE", "matches": [{"match_type": "identifier", "patient": {...}}] }`.

### GET `/api/v1/patients/{patient_id}`
- **Description**: Fetch patient details with history pointers (`REQ-F-REG-002`).
- **Roles**: doctor, nurse, billing, admin.
- **Responses**:
  - `200 OK`: `PatientDetail` with embedded consents, contacts, latest history entry id.
  - `404 Not Found`: Invalid patient id or archived without admin role.

### PUT `/api/v1/patients/{patient_id}`
- **Description**: Replace patient demographics and contact info. Creates `PatientHistory` snapshot and logs audit (`REQ-F-REG-002`, `REQ-NF-SEC-003`).
- **Roles**: nurse, doctor, admin.
- **Responses**:
  - `200 OK`: Updated `PatientDetail`.
  - `409 Conflict`: Identifier collision.

### PATCH `/api/v1/patients/{patient_id}`
- **Description**: Partial update for status, contact info, or consent toggles. Records `PatientHistory` and `AuditEvent`.
- **Roles**: nurse, doctor, admin.

### POST `/api/v1/patients/{patient_id}/merge`
- **Description**: Merge duplicate patient records by consolidating consents, contacts, and history entries into the target (`REQ-F-REG-001`). The source record is archived and its identifier released.
- **Roles**: admin.
- **Request Body**:
  ```json
  {
    "source_patient_id": 42
  }
  ```
- **Responses**:
  - `200 OK`: Updated `PatientDetail` for the surviving patient including merged relationships.
  - `400 Bad Request`: `{ "detail": "Lähde- ja kohdepotilas ovat samat", "code": "MERGE_SAME_PATIENT" }`.
  - `404 Not Found`: Either patient id is invalid.

### DELETE `/api/v1/patients/{patient_id}`
- **Description**: Archive a patient (soft delete) per `REQ-F-REG-005` and `REQ-NF-LEGAL-002`. Admins must supply an audit reason that is persisted to both `PatientHistory` and `AuditEvent` records. Archived patients become read-only until restored.
- **Roles**: admin.
- **Request Body**:
  ```json
  {
    "reason": "Tietopyyntö asiakkaalta"
  }
  ```
- **Responses**:
  - `204 No Content` on success.
  - `409 Conflict`: `{ "detail": "Potilas on jo arkistoitu", "code": "PATIENT_ARCHIVED" }` when already archived.

### POST `/api/v1/patients/{patient_id}/restore`
- **Description**: Reactivate an archived patient after administrative review. Requires a textual reason which is stored in patient history and audit metadata (`REQ-F-REG-002`, `REQ-NF-LEGAL-002`).
- **Roles**: admin.
- **Request Body**:
  ```json
  {
    "reason": "Potilas palasi hoitoon"
  }
  ```
- **Responses**:
  - `200 OK`: Returns updated `PatientDetail` with `status` set to `active` and appended history entries for the archive and restore actions.
  - `409 Conflict`: `{ "detail": "Potilas ei ole arkistoitu", "code": "PATIENT_NOT_ARCHIVED" }` when attempting to restore an active patient.

## `/api/v1/appointments`

### GET `/api/v1/appointments/availability`
- **Description**: Return free appointment slots grouped by provider and optional location. Accepts repeated `provider_id` query parameters and requires `start_from`/`end_to` window boundaries. Optional filters: `location`, `slot_minutes` (default 30), and `exclude_appointment_id` when rescheduling an existing booking.
- **Roles**: doctor, nurse, admin.
- **Responses**:
  - `200 OK`: `[ { "provider_id": 5, "location": "Room 201", "slots": [ { "start_time": "2024-02-01T09:30:00Z", "end_time": "2024-02-01T10:00:00Z" } ] } ]`.
  - `400 Bad Request`: Missing provider filter or invalid time range.

### GET `/api/v1/appointments`
- **Description**: List appointments with filters `patient_id`, `provider_id`, `status`, `start_date`, `end_date`.
- **Roles**: doctor, nurse, admin.
- **Responses**:
  - `200 OK`: Paginated list of `AppointmentSummary` objects.

### POST `/api/v1/appointments`
- **Description**: Create an appointment for a patient and provider (`REQ-F-APPT-001`).
- **Roles**: nurse, doctor, admin.
- **Request Body**:
  ```json
  {
    "patient_id": 1,
    "provider_id": 5,
    "service_type": "initial_consultation",
    "start_time": "2024-02-01T09:00:00Z",
    "end_time": "2024-02-01T09:30:00Z",
    "location": "Room 201",
    "notes": "Bring lab results"
  }
  ```
- **Responses**:
  - `201 Created`: `AppointmentDetail` with status `scheduled`.
  - `409 Conflict`: Slot already booked. Response payload includes `{ "detail": { "message": "Aika on jo varattu", "code": "PROVIDER_OVERLAP" } }`.
- **Side effects**: Sends confirmation email/SMS when patient contact info is available.

### GET `/api/v1/appointments/{appointment_id}`
- **Description**: Retrieve appointment detail with audit trail references.
- **Roles**: doctor, nurse, admin.
- **Responses**:
  - `200 OK`: `AppointmentDetail` including `status_history` and `audit_ids`.
  - `404 Not Found`.

### PUT `/api/v1/appointments/{appointment_id}`
- **Description**: Replace appointment fields (provider, times). Validates slot availability and logs audit.
- **Roles**: nurse, doctor, admin.

### PATCH `/api/v1/appointments/{appointment_id}`
- **Description**: Update selective fields (notes, status) with audit logging.
- **Roles**: nurse, doctor, admin.

### POST `/api/v1/appointments/{appointment_id}/reschedule`
- **Description**: Explicit reschedule action recording previous slot (`REQ-F-APPT-003`).
- **Roles**: nurse, doctor, admin.
- **Request Body**:
  ```json
  {
    "start_time": "2024-02-02T10:00:00Z",
    "end_time": "2024-02-02T10:30:00Z",
    "reason": "Patient requested later time"
  }
  ```
- **Responses**:
  - `200 OK`: Updated `AppointmentDetail` with appended `status_history` entry `rescheduled`.
  - `409 Conflict`: `{ "detail": { "message": "Aika on jo varattu", "code": "PROVIDER_OVERLAP", "alternatives": [AvailabilitySlot] } }` when requested slot is busy.
- **Side effects**: Sends reschedule notification to the patient if email/phone is available.

### POST `/api/v1/appointments/{appointment_id}/cancel`
- **Description**: Cancel appointment with reason and optional notify flags (`REQ-F-APPT-003`).
- **Roles**: nurse, doctor, admin.
- **Request Body**:
  ```json
  {
    "reason": "Patient ill",
    "notify_patient": true
  }
  ```
- **Responses**:
  - `200 OK`: Appointment marked `cancelled`, `cancelled_at` timestamp returned.
  - `409 Conflict`: `{ "detail": { "message": "Aikaväli on virheellinen", "code": "INVALID_TIME_RANGE" } }` for invalid payloads.
- **Side effects**: Sends cancellation notification when `notify_patient` is true.

### DELETE `/api/v1/appointments/{appointment_id}`
- **Description**: Hard delete disabled; this endpoint returns `405 Method Not Allowed` to keep audit trail intact. Admins should use cancel or archive patterns.

## `/api/v1/visits`

### GET `/api/v1/visits/{visit_id}`
- **Description**: Fetch a single visit with basics, reason, anamnesis, status, diagnoses, orders, and summary panels populated from notes and orders.
- **Roles**: doctor, admin.
- **Responses**:
  - `200 OK`: `InitialVisitRead` payload.
  - `404 Not Found`: Visit id is invalid.

### POST `/api/v1/visits`
- **Description**: Create an initial visit either from an appointment or directly for a patient when no appointment exists.
- **Roles**: doctor, admin.
- **Request Body**:
  - `appointment_id` *(optional)*: When supplied, visit metadata defaults to the appointment slot and provider.
  - `patient_id` *(optional)*: When `appointment_id` is omitted you must provide the patient id so the visit can be associated. One of these identifiers is required.
  - `basics`, `reason`, `anamnesis`, `status`, `diagnoses`, `orders`, `summary`: Same panel payloads as exposed via the visit update routes. When creating directly via `patient_id`, include the necessary `basics` fields (location, visit_type, timing, provider) and reason text explicitly because there is no appointment to fall back to.
- **Example (appointment driven)**:
  ```json
  {
    "appointment_id": 42,
    "basics": {"location": "Room 201"},
    "reason": {"reason": "Päänsärky"}
  }
  ```
- **Example (patient only)**:
  ```json
  {
    "patient_id": 5,
    "basics": {
      "visit_type": "initial",
      "location": "Room 3",
      "started_at": "2024-05-10T09:00:00Z",
      "ended_at": "2024-05-10T09:45:00Z",
      "attending_provider_id": 12
    },
    "reason": {"reason": "Kontrollikäynti"}
  }
  ```
- **Responses**:
  - `201 Created`: Returns the assembled `InitialVisitRead` structure and records a `visit.create` audit event referencing the patient.
  - `404 Not Found`: Appointment or patient id is invalid.
  - `409 Conflict`: Visit already exists for the appointment.
  - `422 Unprocessable Entity`: Neither identifier supplied or payload fails validation.

## `/api/v1/auth`

### POST `/api/v1/auth/login`
- **Description**: Authenticate user with username/password. Issues access and refresh tokens (`REQ-NF-SEC-001`).
- **Request Body**:
  ```json
  {
    "username": "doctor.1",
    "password": "secret"
  }
  ```
- **Responses**:
  - `200 OK`: `{ "access_token": "...", "refresh_token": "...", "token_type": "bearer", "expires_in": 900, "role": "doctor" }`.
  - `401 Unauthorized`: Invalid credentials.

### POST `/api/v1/auth/refresh`
- **Description**: Exchange refresh token for new access token. Optionally rotates refresh token.
- **Request Body**:
  ```json
  {
    "refresh_token": "..."
  }
  ```
- **Responses**:
  - `200 OK`: `{ "access_token": "...", "refresh_token": "..." }`.
  - `401 Unauthorized`: Expired or revoked token.

### POST `/api/v1/auth/logout` (optional for future)
- **Description**: Accepts refresh token for revocation by inserting into blacklist. Not required for MVP but the endpoint stub may return `204 No Content`.

## `/api/v1/audit`

### GET `/api/v1/audit`
- **Description**: List audit events filtered by `resource_type`, `resource_id`, `actor_id`, `action`, `from`, `to` (`REQ-NF-SEC-003`). Pagination is capped at 100 rows per page to prevent bulk leakage.
- **Roles**: admin (full access). Doctors and nurses must provide `resource_type=patient|appointment` and a matching `resource_id`; responses are scoped to the resources they are allowed to read.
- **Query Parameters**:
  - `resource_type`, `resource_id`, `actor_id`, `action`, `from`, `to`, `page`, `page_size` (capped at 100 records per page).
  - `format=csv` exports the current page as `text/csv` with the same filters applied.
- **Errors**:
  - `400 Bad Request`: Missing `resource_id` for doctor/nurse query, unsupported `resource_type`, or unsupported export format.
- **Responses**:
  - `200 OK`: `{ "items": [AuditEvent], "page": 1, "page_size": 25, "total": 42 }` or CSV attachment when `format=csv`.

### GET `/api/v1/audit/{audit_id}`
- **Description**: Fetch a single audit event for deep inspection. Includes metadata such as request id and origin IP.
- **Roles**: admin.

## Data Transfer Objects (DTOs)

Sample schemas used across responses (actual OpenAPI definitions generated by FastAPI):

```json
// PatientSummary
{
  "id": 1,
  "identifier": "123456-789A",
  "full_name": "Anna Example",
  "date_of_birth": "1990-05-20",
  "status": "active",
  "updated_at": "2024-01-02T08:15:00Z"
}

// PatientDetail extends PatientSummary
{
  "id": 1,
  "identifier": "123456-789A",
  "first_name": "Anna",
  "last_name": "Example",
  "date_of_birth": "1990-05-20",
  "sex": "female",
  "contact_info": { ... },
  "consents": [ ... ],
  "contacts": [ ... ],
  "history": [{"id": 10, "changed_at": "2024-01-02T08:15:00Z", "changed_by": 5}],
  "status": "active",
  "created_at": "2024-01-01T10:00:00Z",
  "updated_at": "2024-01-02T08:15:00Z"
}

// AppointmentDetail
{
  "id": 55,
  "patient_id": 1,
  "provider_id": 5,
  "service_type": "initial_consultation",
  "location": "Room 201",
  "start_time": "2024-02-01T09:00:00Z",
  "end_time": "2024-02-01T09:30:00Z",
  "status": "scheduled",
  "notes": "Bring lab results",
  "status_history": [
    {"status": "scheduled", "changed_at": "2024-01-15T10:05:00Z", "changed_by": 7}
  ],
  "created_at": "2024-01-15T10:05:00Z",
  "updated_at": "2024-01-15T10:05:00Z"
}

// AuditEvent
{
  "id": 1001,
  "actor_id": 7,
  "action": "patient.read",
  "resource_type": "patient",
  "resource_id": 1,
  "timestamp": "2024-01-15T10:05:01Z",
  "context": {"role": "doctor", "request_id": "abc-123", "ip": "127.0.0.1"}
}
```

## Open Questions & Next Steps

- Decide whether appointment slot management is part of MVP or deferred. If deferred, availability validation can rely on querying overlapping appointments.
- Define notification hooks (email/SMS) as optional extensions once core MVP slices are complete.

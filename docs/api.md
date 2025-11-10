# API Contract (MVP)

The REST API follows JSON over HTTPS (HTTP for local development) and aligns with the requirements defined in `specs/patient_system_requirements.csv`. All endpoints live under `/api/v1`. Requests and responses use snake_case keys.

## Common Conventions

- **Authentication**: Bearer JWT tokens obtained via `/api/v1/auth/login`. Refresh tokens rotate via `/api/v1/auth/refresh` (`REQ-NF-SEC-001`).
- **Authorization**: Role-based access control enforced per route (doctor, nurse, admin) (`REQ-F-ADM-001`, `REQ-NF-SEC-002`).
- **Audit Logging**: Every read or write to patient or appointment data records an `AuditEvent` with actor, timestamp, resource, and action (`REQ-NF-SEC-003`).
- **Pagination**: List endpoints accept `page` (default 1) and `page_size` (default 25, max 100).
- **Filtering**: Standard query parameters such as `search`, `status`, `start_date`, `end_date` are optional filters noted per resource.
- **Error Format**: Errors respond with `{ "detail": "message", "code": "ERROR_CODE", "errors": [...] }` and HTTP status codes (400, 401, 403, 404, 409, 422, 500).

## `/api/v1/patients`

### GET `/api/v1/patients`
- **Description**: List patients with optional filtering by `search` (name, identifier) and `status` (`active`, `archived`).
- **Roles**: doctor, nurse, admin.
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
  - `409 Conflict`: Duplicate identifier.

### GET `/api/v1/patients/{patient_id}`
- **Description**: Fetch patient details with history pointers (`REQ-F-REG-002`).
- **Roles**: doctor, nurse, admin.
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

### DELETE `/api/v1/patients/{patient_id}`
- **Description**: Archive a patient (soft delete) per `REQ-F-REG-005` and `REQ-NF-LEGAL-002`. Only admin role can execute.
- **Roles**: admin.
- **Responses**:
  - `204 No Content`.

## `/api/v1/appointments`

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
  - `409 Conflict`: Slot already booked.

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

### DELETE `/api/v1/appointments/{appointment_id}`
- **Description**: Hard delete disabled; this endpoint returns `405 Method Not Allowed` to keep audit trail intact. Admins should use cancel or archive patterns.

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
- **Description**: List audit events filtered by `resource_type`, `resource_id`, `actor_id`, `action`, `from`, `to` (`REQ-NF-SEC-003`).
- **Roles**: admin (read-only), with doctor/nurse allowed to see events tied to patients they are permitted to view.
- **Responses**:
  - `200 OK`: `{ "items": [AuditEvent], "page": 1, "page_size": 25, "total": 42 }`.

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

# Phase 11 — Leave and Doctor's Notes

Status: **Complete**

## Employee workflow

- Staff and Intern navigation now includes Approvals so employees can submit and track leave.
- Leave uses a dedicated form with leave type, start date, end date, reason, supporting files, and optional Director review.
- Sick leave always requires a doctor note or medical certificate.
- The desktop uploads the selected file bytes first and links the returned private document IDs to the leave request.
- Employees can download documents attached to their own leave request through an authenticated request.

## Review workflow

- Operations Manager or Super Admin performs the Manager-stage review.
- Business Lead, Branch Manager, or Super Admin performs the Business-stage review.
- Director or Super Admin performs the Director stage when required.
- The authenticated reviewer identity is authoritative; editable reviewer-name claims were removed from the desktop flow.
- Review controls appear only for the role assigned to the current stage.
- Self-review is hidden in the desktop and rejected by the API.
- Rejection requires a reason and preserves that reason on the leave record.

## Secure documents

- Files are stored as real private bytes in MongoDB with SHA-256 integrity metadata.
- Supported content is validated by file signature or safe container structure, rather than filename alone.
- Sick-leave evidence is restricted to valid PDF, PNG, JPEG, or non-macro DOCX medical documents.
- Empty and oversized files are rejected; the maximum file size is 8 MB.
- Filenames are stripped of supplied directory paths.
- Metadata responses exclude file content and do not expose public download URLs.
- Downloads require an authenticated bearer session and return `Cache-Control: no-store` and `X-Content-Type-Options: nosniff`.
- Employees can access only their own documents.
- HR-authorized management can access managed documents.
- A Business Lead receives access only to documents linked to a pending leave request currently at the Business stage.

## Validation

- FastAPI suite: **25 passed**
- Desktop suite: **67 passed**
- Python compilation passed for all changed leave, approval, document, navigation, client, controller, model, and view modules.

Coverage verifies real byte persistence, hashes, filename sanitization, type and size validation, mandatory medical evidence, cross-employee rejection, authenticated retrieval, private response headers, staged document access, the full three-stage approval path, required rejection reasons, desktop upload-to-leave ID linking, and authenticated role controls.

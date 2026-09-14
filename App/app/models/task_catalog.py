"""Task templates and department mapping for the Tasks workspace."""

from __future__ import annotations

TASK_CATALOG: dict[str, list[str]] = {
    "Hardware Refurbishment": [
        "Diagnose laptop hardware fault",
        "Replace SSD / upgrade RAM",
        "Refurbish returned device",
        "QA test refurbished unit",
    ],
    "Website Merge": [
        "Fix merge conflict on main",
        "Resolve checkout bug",
        "Update catalog integration",
        "Regression test merged pages",
    ],
    "Service & Operations": [
        "Client site visit",
        "Prepare weekly ops report",
        "Follow up outstanding tickets",
        "Update internal SOP",
    ],
    "General Operations": [
        "Administrative task",
        "Internal process update",
        "Documentation update",
    ],
    "Administration": [
        "Admin request",
        "Policy review",
        "Staff onboarding support",
    ],
}

CATEGORY_DEPARTMENTS: dict[str, str] = {
    "Hardware Refurbishment": "Hardware",
    "Website Merge": "Development",
    "Service & Operations": "Operations",
    "General Operations": "Operations",
    "Administration": "Administration",
}

WORKSTREAM_CATEGORIES: dict[str, list[str]] = {
    "Website Merge": ["Website Merge"],
    "Hardware Refurbishment": ["Hardware Refurbishment"],
    "Service & Operations": ["Service & Operations", "General Operations", "Administration"],
}

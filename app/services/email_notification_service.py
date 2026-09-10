"""Optional SMTP email delivery for task assignments and meetings."""

from __future__ import annotations

import os
import re
import smtplib
import sqlite3
from contextlib import closing
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path

from app.database.database import Database

try:
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:
    # Packaged builds may inject environment values without python-dotenv.
    pass


class EmailNotificationService:
    """Send Nexus email without making task/calendar saves depend on SMTP."""

    EMPLOYEE_EMAILS = {
        "gift wesi": "g.wesi@untangledits.co.za",
        "gift": "g.wesi@untangledits.co.za",
        "dipuo tlowana": "dtlotlwana@untangledits.co.za",
        "dipuo tlotlwana": "dtlotlwana@untangledits.co.za",
        "dipuo": "dtlotlwana@untangledits.co.za",
        "bongiwe ngobese": "bngobese@untangledits.co.za",
        "bongiwe": "bngobese@untangledits.co.za",
        "siyanda nkosi": "snkosi@untangledits.co.za",
        "siyanda": "snkosi@untangledits.co.za",
        "ubuntu hadebe": "uhadebe@untangledits.co.za",
        "ubuntu": "uhadebe@untangledits.co.za",
        "nonhlanhla hlatshwayo": "nhlatshwayo@untangled.co.za",
        "nonhlanhla": "nhlatshwayo@untangled.co.za",
        "blehasa": "blehasa@untangleits.co.za",
        "botshelo lehasa": "blehasa@untangleits.co.za",
        "botshelo": "blehasa@untangleits.co.za",
    }

    def __init__(self, database: Database) -> None:
        self._database = database
        self._people_service = None
        self.enabled = os.getenv("NEXUS_EMAIL_ENABLED", "false").strip().lower() in {
            "1", "true", "yes", "on"
        }
        self.host = os.getenv("NEXUS_SMTP_HOST", "").strip()
        self.port = int(os.getenv("NEXUS_SMTP_PORT", "587") or 587)
        self.username = os.getenv("NEXUS_SMTP_USERNAME", "").strip()
        self.password = os.getenv("NEXUS_SMTP_PASSWORD", "")
        self.sender = os.getenv("NEXUS_SMTP_FROM", self.username).strip()
        self.use_tls = os.getenv("NEXUS_SMTP_USE_TLS", "true").strip().lower() in {
            "1", "true", "yes", "on"
        }

    def set_people_service(self, people_service: object) -> None:
        """Attach the employee directory after application services are composed."""
        self._people_service = people_service

    @property
    def db_path(self) -> Path:
        return self._database.db_path

    def resolve_email(self, identity: str) -> str:
        """Resolve an email address from an email, local employee, or approved directory."""
        key = str(identity or "").strip()
        if "@" in key:
            return key.lower()
        with closing(self._database.connection()) as connection:
            row = connection.execute(
                "SELECT email FROM employees WHERE LOWER(full_name) = LOWER(?) LIMIT 1;",
                (key,),
            ).fetchone()
        if row and row["email"] and "@" in row["email"]:
            local_email = str(row["email"]).strip().lower()
            if not local_email.endswith("@untangleditsolutions.co.za"):
                return local_email
        exact = self.EMPLOYEE_EMAILS.get(key.casefold(), "")
        if exact:
            return exact
        if key.casefold().split()[-1:] == ["lehasa"]:
            return "blehasa@untangleits.co.za"
        if self._people_service is not None:
            try:
                employee = self._people_service.get_employee_by_name(key)
                if employee and employee.email and "@" in employee.email:
                    return employee.email.strip().lower()
            except Exception as error:
                print(f"Employee email lookup failed: {error}")
        return ""

    def send_task_assignment(self, task: object) -> bool:
        recipient = self.resolve_email(getattr(task, "assigned_employee", ""))
        if not recipient:
            self._log("", "Task assignment", "Task", getattr(task, "id", None), "Skipped", "No employee email found")
            return False
        due_date = getattr(task, "due_date", "") or "No due date"
        body = (
            f"Hello {getattr(task, 'assigned_employee', 'team member')},\n\n"
            f"A Nexus task has been assigned to you.\n\n"
            f"Task: {getattr(task, 'title', '')}\n"
            f"Category: {getattr(task, 'category', '')}\n"
            f"Priority: {getattr(task, 'priority', '')}\n"
            f"Status: {getattr(task, 'status', '')}\n"
            f"Due date: {due_date}\n"
            f"Assigned by: {getattr(task, 'assigned_by', '')}\n\n"
            f"Open Untangled Nexus to review and update the task."
        )
        return self._send(
            [recipient], f"Nexus task assigned: {getattr(task, 'title', '')}", body,
            "Task", getattr(task, "id", None),
        )

    def send_meeting_invite(self, event: object) -> bool:
        recipients = self.resolve_recipients(getattr(event, "attendees", ""))
        body = self._meeting_body(event, include_summary=False)
        return self._send(
            recipients, f"Meeting invitation: {getattr(event, 'title', '')}", body,
            "CalendarEvent", getattr(event, "id", None), self._build_ics(event),
        )

    def send_meeting_summary(self, event: object) -> bool:
        recipients = self.resolve_recipients(getattr(event, "attendees", ""))
        body = self._meeting_body(event, include_summary=True)
        return self._send(
            recipients, f"Meeting summary: {getattr(event, 'title', '')}", body,
            "CalendarEvent", getattr(event, "id", None),
        )

    def send_meeting_report(
        self,
        recipients_text: str,
        meeting_title: str,
        summary: str,
        report_path: Path,
        reference_id: int | None = None,
    ) -> bool:
        """Email a written meeting summary with its Word transcript report."""
        recipients = self.resolve_recipients(recipients_text)
        body = (
            f"Meeting: {meeting_title}\n\n"
            f"Summary\n{summary}\n\n"
            "The complete written transcript and meeting report are attached. "
            "Please review AI-generated content for accuracy."
        )
        return self._send(
            recipients,
            f"Meeting report: {meeting_title}",
            body,
            "CalendarEvent",
            reference_id,
            report_attachment=report_path,
        )

    def resolve_recipients(self, attendees: str) -> list[str]:
        values = re.split(
            r"\s*(?:,|;|\n|\band\b)\s*",
            str(attendees or ""),
            flags=re.IGNORECASE,
        )
        resolved = [self.resolve_email(value) for value in values if value.strip()]
        return list(dict.fromkeys(email for email in resolved if email))

    def _send(
        self,
        recipients: list[str],
        subject: str,
        body: str,
        reference_type: str,
        reference_id: int | None,
        calendar_attachment: str | None = None,
        report_attachment: Path | None = None,
    ) -> bool:
        if not recipients:
            self._log("", subject, "Meeting", reference_id, "Skipped", "No valid recipients")
            return False
        if not self.enabled:
            for recipient in recipients:
                self._log(recipient, subject, reference_type, reference_id, "Skipped", "Email delivery is disabled")
            return False
        if not self.host or not self.sender:
            for recipient in recipients:
                self._log(recipient, subject, reference_type, reference_id, "Failed", "SMTP host or sender is missing")
            return False

        message = EmailMessage()
        message["From"] = self.sender
        message["To"] = ", ".join(recipients)
        message["Subject"] = subject
        message.set_content(body)
        if calendar_attachment:
            message.add_attachment(
                calendar_attachment.encode("utf-8"),
                maintype="text", subtype="calendar", filename="meeting.ics",
                params={"method": "REQUEST"},
            )
        if report_attachment is not None:
            message.add_attachment(
                report_attachment.read_bytes(),
                maintype="application",
                subtype="vnd.openxmlformats-officedocument.wordprocessingml.document",
                filename=report_attachment.name,
            )
        try:
            with smtplib.SMTP(self.host, self.port, timeout=20) as smtp:
                if self.use_tls:
                    smtp.starttls()
                if self.username:
                    smtp.login(self.username, self.password)
                smtp.send_message(message)
        except Exception as error:
            for recipient in recipients:
                self._log(recipient, subject, reference_type, reference_id, "Failed", str(error)[:500])
            print(f"Email delivery failed: {error}")
            return False
        for recipient in recipients:
            self._log(recipient, subject, reference_type, reference_id, "Sent", "")
        return True

    @staticmethod
    def _meeting_body(event: object, include_summary: bool) -> str:
        lines = [
            f"Meeting: {getattr(event, 'title', '')}",
            f"Date: {getattr(event, 'start_date', '')}",
            f"Time: {getattr(event, 'start_time', '') or 'Not specified'} - {getattr(event, 'end_time', '') or 'Not specified'}",
            f"Location/link: {getattr(event, 'location', '') or 'Not specified'}",
            "",
            f"Agenda: {getattr(event, 'agenda', '') or getattr(event, 'details', '') or 'Not supplied'}",
        ]
        if include_summary:
            lines.extend([
                "", f"Summary: {getattr(event, 'summary', '') or 'Not supplied'}",
                "", f"Decisions: {getattr(event, 'decisions', '') or 'None recorded'}",
                "", f"Action items: {getattr(event, 'action_items', '') or 'None recorded'}",
                "", f"Minutes: {getattr(event, 'minutes', '') or 'No detailed minutes recorded'}",
            ])
        return "\n".join(lines)

    @staticmethod
    def _build_ics(event: object) -> str:
        start_date = str(getattr(event, "start_date", "")).replace("-", "")
        end_date = str(getattr(event, "end_date", "") or getattr(event, "start_date", "")).replace("-", "")
        start_time = EmailNotificationService._ics_time(
            str(getattr(event, "start_time", "")), "090000"
        )
        end_time = EmailNotificationService._ics_time(
            str(getattr(event, "end_time", "")), "100000"
        )
        uid = f"nexus-{getattr(event, 'id', 'new')}@untangledits.co.za"
        return "\r\n".join([
            "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Untangled Nexus//EN", "METHOD:REQUEST",
            "BEGIN:VEVENT", f"UID:{uid}", f"DTSTAMP:{datetime.utcnow().strftime('%Y%m%dT%H%M%SZ')}",
            f"DTSTART:{start_date}T{start_time}", f"DTEND:{end_date}T{end_time}",
            f"SUMMARY:{getattr(event, 'title', '')}", f"LOCATION:{getattr(event, 'location', '')}",
            f"DESCRIPTION:{getattr(event, 'agenda', '') or getattr(event, 'details', '')}",
            "END:VEVENT", "END:VCALENDAR", "",
        ])

    @staticmethod
    def _ics_time(value: str, default: str) -> str:
        """Convert common human time formats for calendar attachments only."""
        cleaned = value.strip().lower().replace(".", "").replace("h", ":")
        if not cleaned:
            return default
        for time_format in ("%H:%M", "%H", "%I:%M %p", "%I %p", "%I%p"):
            try:
                parsed = datetime.strptime(cleaned, time_format)
                return parsed.strftime("%H%M%S")
            except ValueError:
                continue
        return default

    def _log(
        self, recipient: str, subject: str, reference_type: str,
        reference_id: int | None, status: str, error: str,
    ) -> None:
        try:
            with closing(self._database.connection()) as connection:
                connection.execute(
                    """
                    INSERT INTO email_delivery_log
                        (recipient, subject, category, reference_type, reference_id, status, error, sent_at)
                    VALUES (?, ?, ?, ?, ?, ?, ?, CASE WHEN ? = 'Sent' THEN CURRENT_TIMESTAMP ELSE NULL END);
                    """,
                    (recipient, subject, reference_type, reference_type, reference_id, status, error, status),
                )
                connection.commit()
        except sqlite3.Error as log_error:
            print(f"Email audit log failed: {log_error}")

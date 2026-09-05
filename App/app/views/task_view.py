"""Tasks workspace – inline list + detail (no popups for day-to-day work)."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, Optional
import base64
import mimetypes
from pathlib import Path as FsPath
from tkinter import filedialog

import customtkinter as ctk

from app.controllers.task_controller import TaskController
from app.models.task import Task
from app.utils.theme import Theme

TASK_CATEGORIES = [
    "Administration",
    "Software Development",
    "Technical Support",
    "IT Infrastructure",
    "Network & Security",
    "Project Management",
    "Human Resources",
    "Finance & Billing",
    "Sales & CRM",
    "Customer Success",
    "Quality Assurance",
    "Training & Onboarding",
    "Facilities",
    "Executive / Strategy",
    "Other",
]


def _fmt_due(value: Any) -> str:
    if value is None or value == "":
        return "No due date"
    text = str(value)
    if "T" in text:
        text = text.split("T", 1)[0]
    return text


def _status_color(status: str) -> str:
    colors = {
        "New": Theme.ACCENT,
        "Assigned": Theme.PURPLE,
        "In Progress": Theme.WARNING,
        "Waiting Review": Theme.INFO,
        "Completed": Theme.SUCCESS,
        "Cancelled": Theme.DANGER,
    }
    return colors.get(status or "", Theme.PANEL_ALT)


class TaskView(ctk.CTkFrame):
    """Split view: task list on the left, full detail + actions on the right."""

    def __init__(
        self,
        master: object,
        controller: TaskController,
        filters: dict[str, object] | None = None,
    ) -> None:
        super().__init__(master, fg_color=Theme.BG, corner_radius=0)
        self._controller = controller
        self._filters = filters or {}
        self._is_manager = bool(getattr(controller, "is_manager", lambda: True)())
        self._tasks: list[Task] = []
        self._selected: Optional[Task] = None
        self._status_msg: Optional[ctk.CTkLabel] = None

        self.grid_columnconfigure(0, weight=2, minsize=300)
        self.grid_columnconfigure(1, weight=3, minsize=420)
        self.grid_rowconfigure(2, weight=1)

        self._build_header()
        self._build_body()
        self.refresh()

    # ------------------------------------------------------------------ header
    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, columnspan=2, sticky="ew", padx=4, pady=(0, 4))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header, text="Tasks", text_color=Theme.TEXT, font=Theme.FONT_TITLE
        ).grid(row=0, column=0, sticky="w")

        right = ctk.CTkFrame(header, fg_color="transparent")
        right.grid(row=0, column=1, sticky="e")

        if self._is_manager:
            scopes = ["Inbox", "Reviews", "Overdue", "All", "Personal", "Department"]
            default = "Inbox"
            blurb = "Select a task to view details and take action. Create new work with + New Task."
        else:
            scopes = ["My Tasks"]
            default = "My Tasks"
            blurb = "Your assigned work. Open a task, then mark it complete when finished."

        self.scope = ctk.CTkSegmentedButton(
            right,
            values=scopes,
            command=lambda _v: self.refresh(),
            height=36,
            selected_color=Theme.ACCENT,
            selected_hover_color=Theme.ACCENT_HOVER,
            unselected_color="#FFFFFF",
            unselected_hover_color=Theme.PANEL_ALT,
            text_color=Theme.TEXT,
            font=("Segoe UI", 12),
        )
        self.scope.set(default)
        self.scope.pack(side="left", padx=(0, 8))

        if self._is_manager:
            ctk.CTkButton(
                right,
                text="+ New Task",
                width=110,
                height=34,
                fg_color=Theme.ACCENT,
                hover_color=Theme.ACCENT_HOVER,
                command=self._open_create,
            ).pack(side="left")

        ctk.CTkLabel(
            self, text=blurb, text_color=Theme.MUTED_TEXT, font=Theme.FONT_BODY, anchor="w"
        ).grid(row=1, column=0, columnspan=2, sticky="ew", padx=4, pady=(0, 8))

    # ------------------------------------------------------------------- body
    def _build_body(self) -> None:
        # Left: list
        left = ctk.CTkFrame(self, fg_color=Theme.PANEL, corner_radius=Theme.RADIUS)
        left.grid(row=2, column=0, sticky="nsew", padx=(8, 8), pady=(4, 8))
        left.grid_rowconfigure(1, weight=1)
        left.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            left, text="Task list", text_color=Theme.MUTED_TEXT, font=("Segoe UI", 12), anchor="w"
        ).grid(row=0, column=0, padx=14, pady=(12, 4), sticky="w")

        self.list_frame = ctk.CTkScrollableFrame(left, fg_color="transparent")
        self.list_frame.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 10))
        self.list_frame.grid_columnconfigure(0, weight=1)

        # Right: detail
        self.detail = ctk.CTkFrame(self, fg_color=Theme.PANEL, corner_radius=Theme.RADIUS)
        self.detail.grid(row=2, column=1, sticky="nsew", padx=(8, 8), pady=(4, 8))
        self.detail.grid_columnconfigure(0, weight=1)
        self.detail.grid_rowconfigure(0, weight=1)

        self._show_empty_detail()

    def _show_empty_detail(self) -> None:
        for child in self.detail.winfo_children():
            child.destroy()
        ctk.CTkLabel(
            self.detail,
            text="Select a task from the list\nto see details and actions.",
            text_color=Theme.MUTED_TEXT,
            font=("Segoe UI", 15),
            justify="center",
        ).place(relx=0.5, rely=0.45, anchor="center")

    # ----------------------------------------------------------------- refresh
    def refresh(self) -> None:
        for child in self.list_frame.winfo_children():
            child.destroy()

        scope = self.scope.get()
        if scope == "My Tasks":
            scope = "Personal"
        self._tasks = self._controller.get_tasks(scope)

        if not self._tasks:
            ctk.CTkLabel(
                self.list_frame,
                text="No tasks here yet.",
                text_color=Theme.MUTED_TEXT,
            ).grid(row=0, column=0, sticky="w", padx=8, pady=12)
            self._selected = None
            self._show_empty_detail()
            return

        # Keep selection if still present
        selected_id = str(getattr(self._selected, "id", "") or "")
        keep: Optional[Task] = None
        for row, task in enumerate(self._tasks):
            if selected_id and str(task.id) == selected_id:
                keep = task
            self._add_list_row(row, task)

        if keep is not None:
            self._select_task(keep)
        else:
            self._select_task(self._tasks[0])

    def _add_list_row(self, row: int, task: Task) -> None:
        is_sel = self._selected is not None and str(self._selected.id) == str(task.id)
        card = ctk.CTkFrame(
            self.list_frame,
            fg_color=Theme.ACCENT if is_sel else Theme.PANEL_ALT,
            corner_radius=10,
            cursor="hand2",
        )
        card.grid(row=row, column=0, sticky="ew", pady=(0, 8), padx=2)
        card.grid_columnconfigure(0, weight=1)

        title_color = "#FFFFFF" if is_sel else Theme.TEXT
        muted = "#E8EEF5" if is_sel else Theme.MUTED_TEXT

        ctk.CTkLabel(
            card,
            text=task.title or "Untitled",
            text_color=title_color,
            font=("Segoe UI", 14, "bold"),
            anchor="w",
        ).grid(row=0, column=0, padx=12, pady=(10, 2), sticky="ew")

        meta = f"{task.priority or 'Normal'}  ·  {_fmt_due(task.due_date)}  ·  {float(task.estimated_hours or 0):g}h"
        ctk.CTkLabel(
            card, text=meta, text_color=muted, font=("Segoe UI", 11), anchor="w"
        ).grid(row=1, column=0, padx=12, pady=(0, 4), sticky="w")

        badge = ctk.CTkLabel(
            card,
            text=task.status or "Pending",
            text_color=Theme.TEXT,
            fg_color=_status_color(task.status or ""),
            corner_radius=8,
            width=100,
            height=22,
            font=("Segoe UI", 11, "bold"),
        )
        badge.grid(row=0, column=1, rowspan=2, padx=10, pady=8)

        def on_click(_e=None, t=task):
            self._select_task(t)

        card.bind("<Button-1>", on_click)
        for child in card.winfo_children():
            child.bind("<Button-1>", on_click)

    # --------------------------------------------------------------- detail

    @staticmethod
    def _parse_attachments(task: Task) -> list[dict]:
        """Return list of {name, mime, size, content_base64?} from task."""
        import json as _json
        candidates = [
            getattr(task, "attachments", None),
            (task.raw or {}).get("attachments") if getattr(task, "raw", None) else None,
            (task.raw or {}).get("attachments_json") if getattr(task, "raw", None) else None,
        ]
        items = []
        for raw in candidates:
            if raw is None or raw == "":
                continue
            try:
                if isinstance(raw, list):
                    items = raw
                    break
                if isinstance(raw, str):
                    s = raw.strip()
                    if not s:
                        continue
                    parsed = _json.loads(s)
                    if isinstance(parsed, list):
                        items = parsed
                        break
            except Exception:
                continue
        out = []
        for a in items:
            if isinstance(a, dict):
                out.append(
                    {
                        "name": str(a.get("name") or a.get("filename") or "file"),
                        "mime": str(a.get("mime") or a.get("content_type") or ""),
                        "size": a.get("size"),
                        "content_base64": a.get("content_base64") or a.get("data") or "",
                        "url": a.get("url") or a.get("path") or "",
                    }
                )
            else:
                out.append({"name": str(a), "mime": "", "size": None, "content_base64": "", "url": ""})
        return out

    @staticmethod
    def _attachment_names(task: Task) -> list[str]:
        return [a["name"] for a in TaskView._parse_attachments(task)]

    def _open_attachment(self, att: dict) -> None:
        """Save/open an attachment for the employee (base64 or URL)."""
        import base64
        import os
        import tempfile
        import webbrowser
        from tkinter import filedialog, messagebox

        name = att.get("name") or "attachment.bin"
        data_b64 = att.get("content_base64") or ""
        url = att.get("url") or ""
        try:
            if data_b64:
                raw = base64.b64decode(data_b64)
                path = filedialog.asksaveasfilename(
                    parent=self,
                    title="Save attachment",
                    initialfile=name,
                )
                if not path:
                    # still allow quick open via temp
                    path = os.path.join(tempfile.gettempdir(), name)
                    with open(path, "wb") as f:
                        f.write(raw)
                    os.startfile(path) if os.name == "nt" else webbrowser.open(path)
                    return
                with open(path, "wb") as f:
                    f.write(raw)
                try:
                    if os.name == "nt":
                        os.startfile(path)
                    else:
                        webbrowser.open(path)
                except Exception:
                    messagebox.showinfo("Saved", f"File saved to:\n{path}", parent=self)
                return
            if url:
                webbrowser.open(str(url))
                return
            messagebox.showwarning(
                "Attachment",
                "This file has no downloadable content stored on the server.\n"
                "Ask the manager to re-attach and save the task.",
                parent=self,
            )
        except Exception as exc:
            messagebox.showerror("Attachment", str(exc), parent=self)


    def _select_task(self, task: Task) -> None:
        self._selected = task
        # Re-render list selection state cheaply
        for child in self.list_frame.winfo_children():
            child.destroy()
        for row, t in enumerate(self._tasks):
            self._add_list_row(row, t)
        self._render_detail(task)

    def _render_detail(self, task: Task) -> None:
        for child in self.detail.winfo_children():
            child.destroy()

        shell = ctk.CTkScrollableFrame(self.detail, fg_color="transparent")
        shell.pack(fill="both", expand=True, padx=8, pady=8)
        shell.grid_columnconfigure(0, weight=1)

        # Title + status
        top = ctk.CTkFrame(shell, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", pady=(4, 8))
        top.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            top,
            text=task.title or "Untitled",
            text_color=Theme.TEXT,
            font=("Segoe UI", 22, "bold"),
            anchor="w",
            wraplength=420,
            justify="left",
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            top,
            text=task.status or "Pending",
            text_color=Theme.TEXT,
            fg_color=_status_color(task.status or ""),
            corner_radius=10,
            width=120,
            height=30,
            font=("Segoe UI", 12, "bold"),
        ).grid(row=0, column=1, sticky="e", padx=(8, 0))

        # Info grid
        info = ctk.CTkFrame(shell, fg_color=Theme.PANEL_ALT, corner_radius=12)
        info.grid(row=1, column=0, sticky="ew", pady=(0, 12))
        for c in range(2):
            info.grid_columnconfigure(c, weight=1)

        facts = [
            ("Priority", task.priority or "Normal"),
            ("Category", task.category or "—"),
            ("Assigned to", task.assigned_employee or "—"),
            ("Assigned by", getattr(task, "assigned_by", None) or "—"),
            ("Due date", _fmt_due(task.due_date)),
            (
                "Time",
                f"{float(task.estimated_hours or 0):g}h allocated · {float(task.actual_hours or 0):g}h logged",
            ),
        ]
        for i, (label, value) in enumerate(facts):
            r, c = divmod(i, 2)
            cell = ctk.CTkFrame(info, fg_color="transparent")
            cell.grid(row=r, column=c, sticky="ew", padx=14, pady=10)
            ctk.CTkLabel(cell, text=label, text_color=Theme.MUTED_TEXT, font=("Segoe UI", 11), anchor="w").pack(anchor="w")
            ctk.CTkLabel(cell, text=str(value), text_color=Theme.TEXT, font=("Segoe UI", 13, "bold"), anchor="w", wraplength=240).pack(anchor="w")

        # Description
        ctk.CTkLabel(
            shell, text="What needs to be done", text_color=Theme.MUTED_TEXT, font=("Segoe UI", 12), anchor="w"
        ).grid(row=2, column=0, sticky="w", pady=(4, 2))
        ctk.CTkLabel(
            shell,
            text=(task.description or "No description provided.").strip(),
            text_color=Theme.TEXT,
            font=("Segoe UI", 14),
            anchor="w",
            justify="left",
            wraplength=480,
        ).grid(row=3, column=0, sticky="ew", pady=(0, 8))

        attachments = self._parse_attachments(task)
        if attachments:
            ctk.CTkLabel(
                shell,
                text="Attachments",
                text_color=Theme.MUTED_TEXT,
                font=("Segoe UI", 12),
                anchor="w",
            ).grid(row=4, column=0, sticky="w", pady=(4, 2))
            att_box = ctk.CTkFrame(shell, fg_color=Theme.PANEL_ALT, corner_radius=8)
            att_box.grid(row=5, column=0, sticky="ew", pady=(0, 10))
            att_box.grid_columnconfigure(0, weight=1)
            for i, att in enumerate(attachments):
                name = att.get("name") or "file"
                size = att.get("size")
                size_txt = f" ({int(size)/1024:.0f} KB)" if size else ""
                ctk.CTkLabel(
                    att_box,
                    text=f"📎  {name}{size_txt}",
                    text_color=Theme.TEXT,
                    font=("Segoe UI", 12),
                    anchor="w",
                ).grid(row=i, column=0, padx=12, pady=6, sticky="w")
                ctk.CTkButton(
                    att_box,
                    text="Open / Save",
                    width=100,
                    height=30,
                    fg_color=Theme.ACCENT,
                    hover_color=Theme.ACCENT_HOVER,
                    text_color="#FFFFFF",
                    command=lambda a=att: self._open_attachment(a),
                ).grid(row=i, column=1, padx=12, pady=6, sticky="e")
            note_label_row, note_box_row, status_row = 6, 7, 8
        else:
            note_label_row, note_box_row, status_row = 4, 5, 6

        # Note field
        ctk.CTkLabel(
            shell, text="Your note (optional)", text_color=Theme.MUTED_TEXT, font=("Segoe UI", 12), anchor="w"
        ).grid(row=note_label_row, column=0, sticky="w")
        self.note_box = ctk.CTkTextbox(
            shell,
            height=80,
            fg_color=Theme.PANEL,
            border_color=Theme.BORDER,
            border_width=1,
            text_color=Theme.TEXT,
            font=("Segoe UI", 13),
            corner_radius=8,
        )
        self.note_box.grid(row=note_box_row, column=0, sticky="ew", pady=(4, 12))

        self.status_label = ctk.CTkLabel(
            shell, text="", text_color=Theme.MUTED_TEXT, font=("Segoe UI", 12), anchor="w"
        )
        self.status_label.grid(row=status_row, column=0, sticky="ew", pady=(0, 8))
        self._action_base_row = status_row + 1

        # Actions
        if self._is_manager:
            self._build_manager_actions(shell, task)
        else:
            self._build_employee_actions(shell, task)

    def _note(self) -> str:
        try:
            return self.note_box.get("1.0", "end").strip()
        except Exception:
            return ""

    def _set_status(self, text: str, ok: bool = True) -> None:
        try:
            self.status_label.configure(
                text=text, text_color=Theme.SUCCESS if ok else Theme.DANGER
            )
        except Exception:
            pass

    def _run(self, action: str, fn: Callable[[], None]) -> None:
        try:
            fn()
            self._set_status(f"Done: {action}", ok=True)
            # Refresh list but keep focusing the same task if still present
            self.refresh()
        except Exception as exc:
            self._set_status(str(exc), ok=False)
            print(f"❌ Task action failed ({action}): {exc}")

    def _build_employee_actions(self, shell: ctk.CTkFrame, task: Task) -> None:
        # Same work-progress actions as managers (no assign / no manager decisions)
        base = getattr(self, "_action_base_row", 7)
        ctk.CTkLabel(
            shell,
            text="Work progress",
            text_color=Theme.MUTED_TEXT,
            font=("Segoe UI", 12),
            anchor="w",
        ).grid(row=base, column=0, sticky="w", pady=(4, 4))

        progress = ctk.CTkFrame(shell, fg_color="transparent")
        progress.grid(row=base + 1, column=0, sticky="ew", pady=(0, 8))
        for i in range(4):
            progress.grid_columnconfigure(i, weight=1)

        ctk.CTkButton(
            progress,
            text="Start",
            height=42,
            corner_radius=8,
            fg_color=Theme.SUCCESS,
            hover_color=Theme.SUCCESS_HOVER,
            text_color="#FFFFFF",
            font=("Segoe UI", 13, "bold"),
            command=lambda: self._run(
                "Started",
                lambda: self._controller.start_work(task.id, self._note()),
            ),
        ).grid(row=0, column=0, padx=(0, 4), sticky="ew")

        ctk.CTkButton(
            progress,
            text="Pause",
            height=42,
            corner_radius=8,
            fg_color=Theme.WARNING,
            hover_color=Theme.WARNING,
            text_color="#FFFFFF",
            font=("Segoe UI", 13, "bold"),
            command=lambda: self._run(
                "Paused",
                lambda: self._controller.pause_work(task.id, self._note()),
            ),
        ).grid(row=0, column=1, padx=4, sticky="ew")

        ctk.CTkButton(
            progress,
            text="Submit review",
            height=42,
            corner_radius=8,
            fg_color=Theme.INFO,
            hover_color=Theme.INFO,
            text_color="#FFFFFF",
            font=("Segoe UI", 13, "bold"),
            command=lambda: self._run(
                "Submitted for review",
                lambda: self._controller.submit_for_review(task.id, self._note()),
            ),
        ).grid(row=0, column=2, padx=4, sticky="ew")

        ctk.CTkButton(
            progress,
            text="Complete",
            height=42,
            corner_radius=8,
            fg_color=Theme.PURPLE,
            hover_color=Theme.PURPLE,
            text_color="#FFFFFF",
            font=("Segoe UI", 13, "bold"),
            command=lambda: self._run(
                "Completed",
                lambda: self._controller.complete_work(task.id, self._note()),
            ),
        ).grid(row=0, column=3, padx=(4, 0), sticky="ew")

        ctk.CTkLabel(
            shell,
            text="Start work when you begin, pause if needed, submit for review, or mark complete when finished.",
            text_color=Theme.MUTED_TEXT,
            font=("Segoe UI", 11),
            anchor="w",
            wraplength=480,
            justify="left",
        ).grid(row=base + 2, column=0, sticky="w", pady=(4, 8))

    def _build_manager_actions(self, shell: ctk.CTkFrame, task: Task) -> None:
        base = getattr(self, "_action_base_row", 7)
        # Log time row
        time_row = ctk.CTkFrame(shell, fg_color="transparent")
        time_row.grid(row=base, column=0, sticky="ew", pady=(0, 10))
        time_row.grid_columnconfigure(0, weight=1)
        self.hours_entry = ctk.CTkEntry(
            time_row,
            height=40,
            placeholder_text="Hours worked (e.g. 1.5)",
            fg_color=Theme.PANEL,
            border_color=Theme.BORDER,
            border_width=1,
            text_color=Theme.TEXT,
            placeholder_text_color=Theme.MUTED_TEXT,
            font=("Segoe UI", 13),
        )
        self.hours_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkButton(
            time_row,
            text="Log time",
            width=100,
            height=38,
            fg_color=Theme.ACCENT,
            hover_color=Theme.ACCENT_HOVER,
            command=lambda: self._run(
                "Time logged",
                lambda: self._controller.log_time(
                    task.id, float(self.hours_entry.get() or 0), self._note()
                ),
            ),
        ).grid(row=0, column=1)

        # Assign row
        people = self._controller.get_people_names() or [task.assigned_employee or "Unassigned"]
        assign_row = ctk.CTkFrame(shell, fg_color="transparent")
        assign_row.grid(row=base + 1, column=0, sticky="ew", pady=(0, 12))
        assign_row.grid_columnconfigure(0, weight=1)
        self.assignee_menu = ctk.CTkOptionMenu(
            assign_row,
            values=people,
            height=40,
            fg_color=Theme.PANEL,
            text_color=Theme.TEXT,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER,
            dropdown_fg_color=Theme.PANEL,
            dropdown_text_color=Theme.TEXT,
            dropdown_hover_color=Theme.PANEL_ALT,
            font=("Segoe UI", 13),
        )
        if task.assigned_employee and task.assigned_employee in people:
            self.assignee_menu.set(task.assigned_employee)
        elif people:
            self.assignee_menu.set(people[0])
        self.assignee_menu.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkButton(
            assign_row,
            text="Assign",
            width=100,
            height=38,
            fg_color=Theme.ACCENT,
            hover_color=Theme.ACCENT_HOVER,
            command=lambda: self._run(
                "Assigned",
                lambda: self._controller.assign_task(task.id, self.assignee_menu.get()),
            ),
        ).grid(row=0, column=1)

        # Primary workflow
        ctk.CTkLabel(
            shell, text="Work progress", text_color=Theme.MUTED_TEXT, font=("Segoe UI", 12), anchor="w"
        ).grid(row=base + 2, column=0, sticky="w", pady=(4, 4))

        progress = ctk.CTkFrame(shell, fg_color="transparent")
        progress.grid(row=base + 3, column=0, sticky="ew", pady=(0, 10))
        for i in range(4):
            progress.grid_columnconfigure(i, weight=1)

        ctk.CTkButton(
            progress, text="Start", height=40, fg_color=Theme.SUCCESS, hover_color=Theme.SUCCESS_HOVER,
            command=lambda: self._run("Started", lambda: self._controller.start_work(task.id, self._note())),
        ).grid(row=0, column=0, padx=(0, 4), sticky="ew")
        ctk.CTkButton(
            progress, text="Pause", height=40, fg_color=Theme.WARNING, hover_color=Theme.WARNING,
            command=lambda: self._run("Paused", lambda: self._controller.pause_work(task.id, self._note())),
        ).grid(row=0, column=1, padx=4, sticky="ew")
        ctk.CTkButton(
            progress, text="Submit review", height=40, fg_color=Theme.INFO, hover_color=Theme.INFO,
            command=lambda: self._run("Submitted", lambda: self._controller.submit_for_review(task.id, self._note())),
        ).grid(row=0, column=2, padx=4, sticky="ew")
        ctk.CTkButton(
            progress, text="Complete", height=40, fg_color=Theme.PURPLE, hover_color=Theme.PURPLE,
            command=lambda: self._run("Completed", lambda: self._controller.complete_work(task.id, self._note())),
        ).grid(row=0, column=3, padx=(4, 0), sticky="ew")

        # Manager decisions
        ctk.CTkLabel(
            shell, text="Manager decisions", text_color=Theme.MUTED_TEXT, font=("Segoe UI", 12), anchor="w"
        ).grid(row=base + 4, column=0, sticky="w", pady=(8, 4))

        decisions = ctk.CTkFrame(shell, fg_color="transparent")
        decisions.grid(row=base + 5, column=0, sticky="ew", pady=(0, 12))
        for i in range(4):
            decisions.grid_columnconfigure(i, weight=1)

        ctk.CTkButton(
            decisions, text="Approve", height=36, fg_color=Theme.SUCCESS, hover_color=Theme.SUCCESS_HOVER,
            command=lambda: self._run("Approved", lambda: self._controller.approve_review(task.id, self._note())),
        ).grid(row=0, column=0, padx=(0, 4), sticky="ew")
        ctk.CTkButton(
            decisions, text="Return", height=36, fg_color=Theme.WARNING, hover_color=Theme.WARNING,
            command=lambda: self._run("Returned", lambda: self._controller.return_to_work(task.id, self._note())),
        ).grid(row=0, column=1, padx=4, sticky="ew")
        ctk.CTkButton(
            decisions, text="Ask director", height=36, fg_color=Theme.INFO, hover_color=Theme.INFO,
            command=lambda: self._run("Escalated", lambda: self._controller.escalate_to_director(task.id, self._note())),
        ).grid(row=0, column=2, padx=4, sticky="ew")
        ctk.CTkButton(
            decisions, text="Cancel task", height=36, fg_color=Theme.DANGER, hover_color=Theme.DANGER_HOVER,
            command=lambda: self._run("Cancelled", lambda: self._controller.cancel_task(task.id, self._note())),
        ).grid(row=0, column=3, padx=(4, 0), sticky="ew")

    def _open_create(self) -> None:
        if not self._is_manager:
            return
        CreateTaskModal(self, self._controller, self.refresh)



class CreateTaskModal(ctk.CTkToplevel):
    """Create & assign task – wide professional form with fixed footer."""

    # Shared control styles (readable, clearly editable)
    _ENTRY_KW = {
        "height": 40,
        "corner_radius": 8,
        "border_width": 1,
        "border_color": Theme.BORDER,
        "fg_color": Theme.PANEL,
        "text_color": Theme.TEXT,
        "placeholder_text_color": Theme.MUTED_TEXT,
        "font": ("Segoe UI", 13),
    }
    _MENU_KW = {
        "height": 40,
        "corner_radius": 8,
        "fg_color": Theme.PANEL,
        "text_color": Theme.TEXT,
        "button_color": Theme.ACCENT,
        "button_hover_color": Theme.ACCENT_HOVER,
        "dropdown_fg_color": Theme.PANEL,
        "dropdown_hover_color": Theme.PANEL_ALT,
        "dropdown_text_color": Theme.TEXT,
        "font": ("Segoe UI", 13),
    }

    def __init__(self, master, controller: TaskController, on_created) -> None:
        super().__init__(master)
        self._controller = controller
        self._on_created = on_created
        self._busy = False
        self._attachments: list[dict] = []
        self.title("New Task")
        self.configure(fg_color=Theme.BG)
        self.resizable(True, True)
        self.minsize(640, 560)
        self.geometry("720x640")
        self.transient(master)
        self.grab_set()
        self._center_on_parent(master)
        try:
            self.lift()
            self.focus_force()
        except Exception:
            pass
        self._build()

    def _center_on_parent(self, master) -> None:
        try:
            self.update_idletasks()
            w, h = 720, 640
            if master is not None:
                mx = master.winfo_rootx()
                my = master.winfo_rooty()
                mw = master.winfo_width()
                mh = master.winfo_height()
                x = mx + max(0, (mw - w) // 2)
                y = my + max(0, (mh - h) // 2)
            else:
                sw = self.winfo_screenwidth()
                sh = self.winfo_screenheight()
                x = max(0, (sw - w) // 2)
                y = max(0, (sh - h) // 2)
            self.geometry(f"{w}x{h}+{x}+{y}")
        except Exception:
            self.geometry("720x640")

    def _label(self, parent, text: str, row: int, col: int = 0, **grid) -> None:
        ctk.CTkLabel(
            parent,
            text=text,
            text_color=Theme.MUTED_TEXT,
            font=("Segoe UI", 12),
            anchor="w",
        ).grid(row=row, column=col, sticky="w", **grid)

    def _build(self) -> None:
        shell = ctk.CTkFrame(self, fg_color=Theme.PANEL, corner_radius=Theme.RADIUS)
        shell.pack(fill="both", expand=True, padx=18, pady=18)
        shell.grid_columnconfigure(0, weight=1)
        shell.grid_rowconfigure(1, weight=1)

        # Header
        ctk.CTkLabel(
            shell,
            text="Create & assign a task",
            font=("Segoe UI", 22, "bold"),
            text_color=Theme.TEXT,
            anchor="w",
        ).grid(row=0, column=0, padx=24, pady=(18, 10), sticky="ew")

        # Scrollable body (footer stays fixed)
        body = ctk.CTkScrollableFrame(
            shell,
            fg_color="transparent",
            scrollbar_button_color=Theme.BORDER,
            scrollbar_button_hover_color=Theme.MUTED_TEXT,
        )
        body.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 4))
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)

        # Title (full width)
        self._label(body, "Title *", 0, 0, padx=16, pady=(8, 0))
        self.title_entry = ctk.CTkEntry(
            body,
            placeholder_text="e.g. Prepare client quote",
            **self._ENTRY_KW,
        )
        self.title_entry.grid(row=1, column=0, columnspan=2, padx=16, pady=(4, 12), sticky="ew")

        # Description
        self._label(body, "Description", 2, 0, padx=16, pady=(4, 0))
        self.desc_entry = ctk.CTkTextbox(
            body,
            height=96,
            corner_radius=8,
            border_width=1,
            border_color=Theme.BORDER,
            fg_color=Theme.PANEL,
            text_color=Theme.TEXT,
            font=("Segoe UI", 13),
        )
        self.desc_entry.grid(row=3, column=0, columnspan=2, padx=16, pady=(4, 12), sticky="ew")

        # Assign to | Priority  (two columns)
        self._label(body, "Assign to", 4, 0, padx=16, pady=(4, 0))
        self._label(body, "Priority", 4, 1, padx=16, pady=(4, 0))

        people = self._controller.get_people_names() or ["Unassigned"]
        self.assignee = ctk.CTkOptionMenu(body, values=people, **self._MENU_KW)
        default_person = (
            people[1] if len(people) > 1 and people[0] == "Unassigned" else people[0]
        )
        self.assignee.set(default_person)
        self.assignee.grid(row=5, column=0, padx=(16, 8), pady=(4, 12), sticky="ew")

        self.priority = ctk.CTkOptionMenu(
            body, values=["Low", "Normal", "High", "Urgent"], **self._MENU_KW
        )
        self.priority.set("Normal")
        self.priority.grid(row=5, column=1, padx=(8, 16), pady=(4, 12), sticky="ew")

        # Category | Due date
        self._label(body, "Category", 6, 0, padx=16, pady=(4, 0))
        self._label(body, "Due date (YYYY-MM-DD)", 6, 1, padx=16, pady=(4, 0))

        self.category = ctk.CTkOptionMenu(body, values=TASK_CATEGORIES, **self._MENU_KW)
        self.category.set("Administration")
        self.category.grid(row=7, column=0, padx=(16, 8), pady=(4, 12), sticky="ew")

        self.due_entry = ctk.CTkEntry(
            body, placeholder_text="2026-09-15", **self._ENTRY_KW
        )
        self.due_entry.grid(row=7, column=1, padx=(8, 16), pady=(4, 12), sticky="ew")

        # Estimated hours (half width left)
        self._label(body, "Estimated hours", 8, 0, padx=16, pady=(4, 0))
        self.hours_entry = ctk.CTkEntry(
            body, placeholder_text="e.g. 2", **self._ENTRY_KW
        )
        self.hours_entry.grid(row=9, column=0, padx=(16, 8), pady=(4, 12), sticky="ew")

        # Attachments
        self._label(body, "Attachments (PDF, Office, images)", 10, 0, padx=16, pady=(4, 0))
        att_row = ctk.CTkFrame(body, fg_color="transparent")
        att_row.grid(row=11, column=0, columnspan=2, padx=16, pady=(4, 16), sticky="ew")
        att_row.grid_columnconfigure(0, weight=1)
        self._att_label = ctk.CTkLabel(
            att_row,
            text="No files attached",
            text_color=Theme.MUTED_TEXT,
            font=("Segoe UI", 12),
            anchor="w",
        )
        self._att_label.grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            att_row,
            text="Add files…",
            width=110,
            height=36,
            fg_color=Theme.PANEL_ALT,
            text_color=Theme.TEXT,
            hover_color=Theme.BORDER,
            command=self._pick_attachments,
        ).grid(row=0, column=1, padx=(8, 0))

        # Fixed footer
        footer = ctk.CTkFrame(shell, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=16, pady=(8, 16))
        footer.grid_columnconfigure(0, weight=1)
        footer.grid_columnconfigure(1, weight=1)

        self.error = ctk.CTkLabel(
            footer,
            text="",
            text_color=Theme.DANGER,
            font=("Segoe UI", 12),
            anchor="w",
        )
        self.error.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        self._cancel_btn = ctk.CTkButton(
            footer,
            text="Cancel",
            height=44,
            corner_radius=8,
            fg_color=Theme.PANEL_ALT,
            text_color=Theme.TEXT,
            hover_color=Theme.BORDER,
            font=("Segoe UI", 14),
            command=self.destroy,
        )
        self._cancel_btn.grid(row=1, column=0, padx=(0, 8), sticky="ew")

        self._save_btn = ctk.CTkButton(
            footer,
            text="Create & Assign",
            height=44,
            corner_radius=8,
            fg_color=Theme.ACCENT,
            hover_color=Theme.ACCENT_HOVER,
            text_color="#FFFFFF",
            font=("Segoe UI", 14, "bold"),
            command=self._submit,
        )
        self._save_btn.grid(row=1, column=1, padx=(8, 0), sticky="ew")

        self.bind("<Return>", lambda _e: self._submit())
        self.bind("<Escape>", lambda _e: self.destroy())
        self.after(50, lambda: self.title_entry.focus_set())

    def _pick_attachments(self) -> None:
        paths = filedialog.askopenfilenames(
            parent=self,
            title="Attach files to task",
            filetypes=[
                ("Documents & images", "*.pdf *.doc *.docx *.xls *.xlsx *.csv *.png *.jpg *.jpeg *.gif *.webp *.txt"),
                ("PDF", "*.pdf"),
                ("Word", "*.doc *.docx"),
                ("Excel", "*.xls *.xlsx *.csv"),
                ("Images", "*.png *.jpg *.jpeg *.gif *.webp"),
                ("All files", "*.*"),
            ],
        )
        if not paths:
            return
        max_each = 4 * 1024 * 1024  # 4 MB per file
        for p in paths:
            try:
                fp = FsPath(p)
                data = fp.read_bytes()
                if len(data) > max_each:
                    self.error.configure(
                        text=f"{fp.name} is larger than 4 MB – skipped.",
                        text_color=Theme.DANGER,
                    )
                    continue
                mime = mimetypes.guess_type(fp.name)[0] or "application/octet-stream"
                self._attachments.append(
                    {
                        "name": fp.name,
                        "mime": mime,
                        "size": len(data),
                        "content_base64": base64.b64encode(data).decode("ascii"),
                    }
                )
            except Exception as exc:
                self.error.configure(text=f"Could not read file: {exc}", text_color=Theme.DANGER)
        self._refresh_att_label()

    def _refresh_att_label(self) -> None:
        if not self._attachments:
            self._att_label.configure(text="No files attached", text_color=Theme.MUTED_TEXT)
        else:
            names = ", ".join(a["name"] for a in self._attachments)
            self._att_label.configure(
                text=f"{len(self._attachments)} file(s): {names}",
                text_color=Theme.TEXT,
            )

    def _submit(self) -> None:
        if self._busy:
            return
        title = self.title_entry.get().strip()
        if not title:
            self.error.configure(text="Title is required.", text_color=Theme.DANGER)
            self.title_entry.focus_set()
            return
        try:
            hours = float(self.hours_entry.get() or 0)
        except ValueError:
            hours = 0.0
        assignee = (self.assignee.get() or "").strip()
        data = {
            "title": title,
            "description": self.desc_entry.get("1.0", "end").strip(),
            "assigned_employee": assignee,
            "priority": self.priority.get(),
            "due_date": self.due_entry.get().strip() or None,
            "estimated_hours": hours,
            "status": "Assigned" if assignee and assignee.lower() != "unassigned" else "Pending",
            "category": self.category.get() or "Administration",
            "attachments": list(self._attachments),
        }
        self._busy = True
        try:
            self._save_btn.configure(state="disabled", text="Saving…")
            self._cancel_btn.configure(state="disabled")
        except Exception:
            pass
        self.error.configure(text="Saving to server…", text_color=Theme.MUTED_TEXT)
        self.update_idletasks()
        try:
            self._controller.create_task(data)
            self._on_created()
            self.destroy()
        except Exception as exc:
            self._busy = False
            try:
                self._save_btn.configure(state="normal", text="Create & Assign")
                self._cancel_btn.configure(state="normal")
            except Exception:
                pass
            self.error.configure(text=str(exc), text_color=Theme.DANGER)

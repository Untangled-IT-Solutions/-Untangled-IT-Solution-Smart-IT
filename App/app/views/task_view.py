"""Tasks workspace – modern SaaS split view (list + detail).

Preserves all TaskController methods, CreateTaskModal, attachments,
and work-progress / manager decision actions.
"""

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


# ── Design tokens (match Operations Workspace mockup) ──────────────────────
BG = "#F5F7FA"
CARD = "#FFFFFF"
BORDER = "#E5E7EB"
TEXT = "#0F172A"
MUTED = "#64748B"
GREEN = "#16A34A"
GREEN_HOVER = "#15803D"
BLUE = "#2563EB"
ORANGE = "#F59E0B"
RED = "#DC2626"
PURPLE = "#7C3AED"
SOFT_GREEN = "#DCFCE7"
SOFT_BLUE = "#DBEAFE"
SOFT_ORANGE = "#FEF3C7"
SOFT_RED = "#FEE2E2"
SOFT_PURPLE = "#EDE9FE"
SOFT_GRAY = "#F1F5F9"

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


def _priority_style(priority: str) -> tuple[str, str]:
    p = (priority or "Normal").strip().lower()
    if p in ("urgent", "critical"):
        return RED, SOFT_RED
    if p == "high":
        return ORANGE, SOFT_ORANGE
    if p == "low":
        return MUTED, SOFT_GRAY
    return BLUE, SOFT_BLUE


def _status_color(status: str) -> str:
    colors = {
        "New": BLUE,
        "Assigned": PURPLE,
        "In Progress": ORANGE,
        "Waiting Review": BLUE,
        "Completed": GREEN,
        "Cancelled": RED,
        "Pending": MUTED,
    }
    return colors.get(status or "", MUTED)


def _status_soft(status: str) -> str:
    colors = {
        "New": SOFT_BLUE,
        "Assigned": SOFT_PURPLE,
        "In Progress": SOFT_ORANGE,
        "Waiting Review": SOFT_BLUE,
        "Completed": SOFT_GREEN,
        "Cancelled": SOFT_RED,
        "Pending": SOFT_GRAY,
    }
    return colors.get(status or "", SOFT_GRAY)


def _left_border_color(task: Task) -> str:
    status = (task.status or "").lower()
    priority = (task.priority or "").lower()
    if status == "completed":
        return GREEN
    if priority in ("urgent", "critical"):
        return RED
    if priority == "high":
        return ORANGE
    if priority == "low":
        return MUTED
    return BLUE


def _progress_pct(task: Task) -> int:
    """Best-effort progress 0–100 from task fields."""
    try:
        raw = getattr(task, "raw", None) or {}
        if isinstance(raw, dict):
            for key in ("progress", "progress_pct", "percent_complete", "completion"):
                if key in raw and raw[key] is not None:
                    return max(0, min(100, int(float(raw[key]))))
        est = float(task.estimated_hours or 0)
        act = float(task.actual_hours or 0)
        if est > 0:
            return max(0, min(100, int(round(100 * act / est))))
        status = (task.status or "").lower()
        if status == "completed":
            return 100
        if status in ("in progress", "waiting review"):
            return 45
        if status == "assigned":
            return 10
        return 0
    except Exception:
        return 0


def _initials(name: str) -> str:
    parts = [p for p in (name or "").split() if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


class TaskView(ctk.CTkFrame):
    """Modern enterprise Tasks workspace – list + detail split."""

    def __init__(
        self,
        master: object,
        controller: TaskController,
        filters: dict[str, object] | None = None,
    ) -> None:
        super().__init__(master, fg_color=BG, corner_radius=0)
        self._controller = controller
        self._filters = filters or {}
        self._is_manager = bool(getattr(controller, "is_manager", lambda: True)())
        self._tasks: list[Task] = []
        self._filtered: list[Task] = []
        self._selected: Optional[Task] = None
        self._status_msg: Optional[ctk.CTkLabel] = None
        self._scope_counts: dict[str, int] = {}
        self._search_var = ctk.StringVar(value="")
        self._priority_filter = "All Priorities"

        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)  # KPI
        self.grid_rowconfigure(3, weight=6)  # main body

        self._build_header()
        self._build_kpis()
        self._build_body()
        self.refresh()

    # ------------------------------------------------------------------ header
    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew", padx=24, pady=(16, 8))
        header.grid_columnconfigure(0, weight=1)
        header.grid_columnconfigure(1, weight=0)

        left = ctk.CTkFrame(header, fg_color="transparent")
        left.grid(row=0, column=0, sticky="w")

        icon = ctk.CTkFrame(left, width=48, height=48, corner_radius=24, fg_color=GREEN)
        icon.pack(side="left")
        icon.pack_propagate(False)
        ctk.CTkLabel(icon, text="✓", font=ctk.CTkFont(size=22, weight="bold"), text_color="#FFFFFF").place(
            relx=0.5, rely=0.5, anchor="center"
        )

        titles = ctk.CTkFrame(left, fg_color="transparent")
        titles.pack(side="left", padx=(14, 0))
        ctk.CTkLabel(
            titles, text="Tasks", font=ctk.CTkFont(size=28, weight="bold"), text_color=TEXT
        ).pack(anchor="w")
        ctk.CTkLabel(
            titles,
            text="Manage team work, priorities and deadlines.",
            font=ctk.CTkFont(size=13),
            text_color=MUTED,
        ).pack(anchor="w")

        right = ctk.CTkFrame(header, fg_color="transparent")
        right.grid(row=0, column=1, sticky="e")

        # Scope pills
        if self._is_manager:
            scopes = ["Inbox", "Reviews", "Overdue", "My Tasks", "Team", "Completed"]
            default = "Inbox"
        else:
            scopes = ["My Tasks"]
            default = "My Tasks"

        self._pill_frame = ctk.CTkFrame(right, fg_color="transparent")
        self._pill_frame.pack(side="left", padx=(0, 10))
        self._scope_buttons: dict[str, ctk.CTkButton] = {}
        self._active_scope = default

        for scope in scopes:
            btn = ctk.CTkButton(
                self._pill_frame,
                text=scope,
                height=34,
                corner_radius=18,
                fg_color=GREEN if scope == default else CARD,
                hover_color=GREEN_HOVER if scope == default else SOFT_GRAY,
                text_color="#FFFFFF" if scope == default else TEXT,
                border_width=1 if scope != default else 0,
                border_color=BORDER,
                font=ctk.CTkFont(size=12, weight="bold"),
                command=lambda s=scope: self._set_scope(s),
            )
            btn.pack(side="left", padx=3)
            self._scope_buttons[scope] = btn

        if self._is_manager:
            ctk.CTkButton(
                right,
                text="+  New Task",
                width=120,
                height=36,
                corner_radius=12,
                fg_color=GREEN,
                hover_color=GREEN_HOVER,
                text_color="#FFFFFF",
                font=ctk.CTkFont(size=13, weight="bold"),
                command=self._open_create,
            ).pack(side="left", padx=(6, 0))

    def _set_scope(self, scope: str) -> None:
        self._active_scope = scope
        for name, btn in self._scope_buttons.items():
            active = name == scope
            btn.configure(
                fg_color=GREEN if active else CARD,
                hover_color=GREEN_HOVER if active else SOFT_GRAY,
                text_color="#FFFFFF" if active else TEXT,
                border_width=0 if active else 1,
            )
        self.refresh()

    def _update_pill_badges(self) -> None:
        """Refresh pill labels with counts when available."""
        for name, btn in self._scope_buttons.items():
            count = self._scope_counts.get(name)
            label = name if count is None else f"{name}  {count}"
            try:
                btn.configure(text=label)
            except Exception:
                pass

    # -------------------------------------------------------------------- KPIs
    def _build_kpis(self) -> None:
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.grid(row=1, column=0, sticky="ew", padx=24, pady=(4, 12))
        for i in range(4):
            row.grid_columnconfigure(i, weight=1, uniform="kpi")

        self._kpi_total = self._kpi_card(row, 0, "📋", BLUE, SOFT_BLUE, "Total Tasks", "0", "")
        self._kpi_progress = self._kpi_card(row, 1, "⏱", ORANGE, SOFT_ORANGE, "In Progress", "0", "")
        self._kpi_due = self._kpi_card(row, 2, "📅", RED, SOFT_RED, "Due Today", "0", "")
        self._kpi_done = self._kpi_card(row, 3, "✓", GREEN, SOFT_GREEN, "Completed This Week", "0", "")

    def _kpi_card(self, parent, col, icon, color, soft, title, value, sub):
        card = ctk.CTkFrame(
            parent, fg_color=CARD, corner_radius=16, border_width=1, border_color=BORDER
        )
        card.grid(row=0, column=col, sticky="ew", padx=(0 if col == 0 else 8, 0 if col == 3 else 8))
        card.grid_columnconfigure(1, weight=1)

        badge = ctk.CTkFrame(card, width=40, height=40, corner_radius=12, fg_color=soft)
        badge.grid(row=0, column=0, rowspan=2, padx=(16, 10), pady=16)
        badge.pack_propagate(False)
        ctk.CTkLabel(badge, text=icon, font=ctk.CTkFont(size=16), text_color=color).place(
            relx=0.5, rely=0.5, anchor="center"
        )

        ctk.CTkLabel(
            card, text=title, font=ctk.CTkFont(size=12), text_color=MUTED, anchor="w"
        ).grid(row=0, column=1, sticky="sw", pady=(14, 0))

        val = ctk.CTkLabel(
            card, text=value, font=ctk.CTkFont(size=26, weight="bold"), text_color=TEXT, anchor="w"
        )
        val.grid(row=1, column=1, sticky="nw", pady=(0, 14))

        sub_lbl = ctk.CTkLabel(
            card, text=sub, font=ctk.CTkFont(size=11), text_color=GREEN, anchor="e"
        )
        sub_lbl.grid(row=0, column=2, rowspan=2, padx=16, sticky="e")
        return val, sub_lbl

    def _refresh_kpis(self, tasks: list[Task]) -> None:
        total = len(tasks)
        in_prog = sum(1 for t in tasks if (t.status or "").lower() == "in progress")
        from datetime import date

        today = date.today().isoformat()
        due_today = 0
        completed = 0
        for t in tasks:
            due = str(t.due_date or "")
            if "T" in due:
                due = due.split("T", 1)[0]
            if due == today:
                due_today += 1
            if (t.status or "").lower() == "completed":
                completed += 1

        try:
            self._kpi_total[0].configure(text=str(total))
            self._kpi_progress[0].configure(text=str(in_prog))
            self._kpi_due[0].configure(text=str(due_today))
            self._kpi_done[0].configure(text=str(completed))
        except Exception:
            pass

    # -------------------------------------------------------------------- body
    def _build_body(self) -> None:
        body = ctk.CTkFrame(self, fg_color="transparent")
        body.grid(row=2, column=0, sticky="nsew", padx=24, pady=(0, 20))
        body.grid_columnconfigure(0, weight=55)
        body.grid_columnconfigure(1, weight=45)
        body.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)

        # ── Left: My Tasks ──────────────────────────────────────────────
        left = ctk.CTkFrame(
            body, fg_color=CARD, corner_radius=16, border_width=1, border_color=BORDER
        )
        left.grid(row=0, column=0, sticky="nsew", padx=(0, 10))
        left.grid_columnconfigure(0, weight=1)
        left.grid_rowconfigure(2, weight=1)

        ctk.CTkLabel(
            left,
            text="My Tasks",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=TEXT,
            anchor="w",
        ).grid(row=0, column=0, sticky="w", padx=20, pady=(18, 8))

        controls = ctk.CTkFrame(left, fg_color="transparent")
        controls.grid(row=1, column=0, sticky="ew", padx=16, pady=(0, 8))
        controls.grid_columnconfigure(0, weight=1)

        search = ctk.CTkEntry(
            controls,
            height=38,
            corner_radius=10,
            border_width=1,
            border_color=BORDER,
            fg_color=SOFT_GRAY,
            text_color=TEXT,
            placeholder_text="🔍  Search tasks...",
            placeholder_text_color=MUTED,
            font=ctk.CTkFont(size=13),
            textvariable=self._search_var,
        )
        search.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        search.bind("<KeyRelease>", lambda _e: self._apply_filters())

        self._priority_menu = ctk.CTkOptionMenu(
            controls,
            values=["All Priorities", "Urgent", "High", "Normal", "Low"],
            height=38,
            corner_radius=10,
            fg_color=SOFT_GRAY,
            text_color=TEXT,
            button_color=BLUE,
            button_hover_color="#1D4ED8",
            dropdown_fg_color=CARD,
            dropdown_text_color=TEXT,
            dropdown_hover_color=SOFT_GRAY,
            font=ctk.CTkFont(size=12),
            command=lambda v: self._on_priority_filter(v),
        )
        self._priority_menu.set("All Priorities")
        self._priority_menu.grid(row=0, column=1)

        self.list_frame = ctk.CTkScrollableFrame(left, fg_color="transparent", corner_radius=0)
        self.list_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=(0, 14))
        self.list_frame.grid_columnconfigure(0, weight=1)

        # ── Right: detail ───────────────────────────────────────────────
        self.detail = ctk.CTkFrame(
            body, fg_color=CARD, corner_radius=16, border_width=1, border_color=BORDER
        )
        self.detail.grid(row=0, column=1, sticky="nsew", padx=(10, 0))
        self.detail.grid_columnconfigure(0, weight=1)
        self.detail.grid_rowconfigure(0, weight=1)

        self._show_empty_detail()

    def _on_priority_filter(self, value: str) -> None:
        self._priority_filter = value
        self._apply_filters()

    def _show_empty_detail(self) -> None:
        for child in self.detail.winfo_children():
            child.destroy()
        ctk.CTkLabel(
            self.detail,
            text="Select a task from the list\nto see details and actions.",
            text_color=MUTED,
            font=ctk.CTkFont(size=15),
            justify="center",
        ).place(relx=0.5, rely=0.45, anchor="center")

    # ----------------------------------------------------------------- refresh
    def refresh(self) -> None:
        scope = self._active_scope
        # Map UI scopes to controller scopes
        scope_map = {
            "Inbox": "Inbox",
            "Reviews": "Reviews",
            "Overdue": "Overdue",
            "My Tasks": "Personal",
            "Team": "Department",
            "Completed": "All",
            "All": "All",
            "Personal": "Personal",
            "Department": "Department",
        }
        api_scope = scope_map.get(scope, "Inbox")
        try:
            self._tasks = self._controller.get_tasks(api_scope) or []
        except Exception as exc:
            print(f"⚠️ get_tasks failed: {exc}")
            self._tasks = []

        # For "Completed" filter client-side
        if scope == "Completed":
            self._tasks = [t for t in self._tasks if (t.status or "").lower() == "completed"]

        self._refresh_kpis(self._tasks)
        self._scope_counts[scope] = len(self._tasks)
        self._update_pill_badges()
        self._apply_filters()

    def _apply_filters(self) -> None:
        q = (self._search_var.get() or "").strip().lower()
        pri = (self._priority_filter or "All Priorities").lower()
        filtered: list[Task] = []
        for t in self._tasks:
            if q:
                blob = f"{t.title or ''} {t.description or ''} {t.assigned_employee or ''}".lower()
                if q not in blob:
                    continue
            if pri != "all priorities":
                if (t.priority or "normal").lower() != pri:
                    continue
            filtered.append(t)
        self._filtered = filtered
        self._render_list()

    def _render_list(self) -> None:
        for child in self.list_frame.winfo_children():
            child.destroy()

        if not self._filtered:
            ctk.CTkLabel(
                self.list_frame,
                text="No tasks match this filter.",
                text_color=MUTED,
                font=ctk.CTkFont(size=13),
            ).grid(row=0, column=0, sticky="w", padx=12, pady=16)
            self._selected = None
            self._show_empty_detail()
            return

        selected_id = str(getattr(self._selected, "id", "") or "")
        keep: Optional[Task] = None
        for row, task in enumerate(self._filtered):
            if selected_id and str(task.id) == selected_id:
                keep = task
            self._add_list_row(row, task)

        if keep is not None:
            self._select_task(keep)
        else:
            self._select_task(self._filtered[0])

    def _add_list_row(self, row: int, task: Task) -> None:
        is_sel = self._selected is not None and str(self._selected.id) == str(task.id)
        border_c = _left_border_color(task)

        outer = ctk.CTkFrame(
            self.list_frame,
            fg_color=SOFT_GREEN if is_sel else CARD,
            corner_radius=12,
            border_width=1,
            border_color=GREEN if is_sel else BORDER,
        )
        outer.grid(row=row, column=0, sticky="ew", pady=(0, 8), padx=4)
        outer.grid_columnconfigure(1, weight=1)

        # Colored left accent
        accent = ctk.CTkFrame(outer, width=4, corner_radius=2, fg_color=border_c)
        accent.grid(row=0, column=0, sticky="ns", padx=(0, 0), pady=0)
        accent.grid_propagate(False)

        body = ctk.CTkFrame(outer, fg_color="transparent")
        body.grid(row=0, column=1, sticky="ew", padx=12, pady=10)
        body.grid_columnconfigure(1, weight=1)

        # Icon by category-ish
        icon_bg = ctk.CTkFrame(body, width=36, height=36, corner_radius=10, fg_color=SOFT_BLUE)
        icon_bg.grid(row=0, column=0, rowspan=3, padx=(0, 10), sticky="n")
        icon_bg.pack_propagate(False)
        ctk.CTkLabel(icon_bg, text="📄", font=ctk.CTkFont(size=14)).place(
            relx=0.5, rely=0.5, anchor="center"
        )

        # Title row
        title_row = ctk.CTkFrame(body, fg_color="transparent")
        title_row.grid(row=0, column=1, sticky="ew")
        title_row.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            title_row,
            text=task.title or "Untitled",
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=TEXT,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        p_fg, p_bg = _priority_style(task.priority or "Normal")
        ctk.CTkLabel(
            title_row,
            text=task.priority or "Normal",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=p_fg,
            fg_color=p_bg,
            corner_radius=8,
            padx=8,
            pady=2,
        ).grid(row=0, column=1, padx=(8, 0))

        # Description
        desc = (task.description or "").strip()
        if len(desc) > 90:
            desc = desc[:87] + "…"
        ctk.CTkLabel(
            body,
            text=desc or "No description",
            font=ctk.CTkFont(size=12),
            text_color=MUTED,
            anchor="w",
        ).grid(row=1, column=1, sticky="w", pady=(2, 4))

        # Meta row: avatar · due · progress
        meta = ctk.CTkFrame(body, fg_color="transparent")
        meta.grid(row=2, column=1, sticky="ew")
        meta.grid_columnconfigure(2, weight=1)

        # Avatar initials
        av = ctk.CTkFrame(meta, width=24, height=24, corner_radius=12, fg_color=SOFT_BLUE)
        av.grid(row=0, column=0, padx=(0, 6))
        av.pack_propagate(False)
        ctk.CTkLabel(
            av,
            text=_initials(task.assigned_employee or "?"),
            font=ctk.CTkFont(size=9, weight="bold"),
            text_color=BLUE,
        ).place(relx=0.5, rely=0.5, anchor="center")

        ctk.CTkLabel(
            meta,
            text=task.assigned_employee or "Unassigned",
            font=ctk.CTkFont(size=11),
            text_color=MUTED,
        ).grid(row=0, column=1, padx=(0, 10))

        ctk.CTkLabel(
            meta,
            text=f"📅  {_fmt_due(task.due_date)}",
            font=ctk.CTkFont(size=11),
            text_color=MUTED,
        ).grid(row=0, column=2, sticky="w")

        pct = _progress_pct(task)
        prog_wrap = ctk.CTkFrame(meta, fg_color="transparent", width=90)
        prog_wrap.grid(row=0, column=3, sticky="e", padx=(8, 0))
        bar = ctk.CTkProgressBar(
            prog_wrap, width=70, height=6, progress_color=GREEN if pct >= 70 else ORANGE if pct >= 30 else RED,
            fg_color=SOFT_GRAY,
        )
        bar.set(pct / 100.0)
        bar.pack(side="left")
        ctk.CTkLabel(
            prog_wrap, text=f"{pct}%", font=ctk.CTkFont(size=11, weight="bold"), text_color=TEXT
        ).pack(side="left", padx=(6, 0))

        def on_click(_e=None, t=task):
            self._select_task(t)

        outer.bind("<Button-1>", on_click)
        for child in outer.winfo_children():
            try:
                child.bind("<Button-1>", on_click)
            except Exception:
                pass
        for child in body.winfo_children():
            try:
                child.bind("<Button-1>", on_click)
            except Exception:
                pass

    # --------------------------------------------------------------- detail
    @staticmethod
    def _parse_attachments(task: Task) -> list[dict]:
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
        import os
        import tempfile
        import webbrowser
        from tkinter import messagebox

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
        for child in self.list_frame.winfo_children():
            child.destroy()
        for row, t in enumerate(self._filtered):
            self._add_list_row(row, t)
        self._render_detail(task)

    def _render_detail(self, task: Task) -> None:
        for child in self.detail.winfo_children():
            child.destroy()

        shell = ctk.CTkScrollableFrame(self.detail, fg_color="transparent")
        shell.pack(fill="both", expand=True, padx=16, pady=14)
        shell.grid_columnconfigure(0, weight=1)

        # Title + priority badge
        top = ctk.CTkFrame(shell, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", pady=(4, 6))
        top.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            top,
            text=task.title or "Untitled",
            text_color=TEXT,
            font=ctk.CTkFont(size=20, weight="bold"),
            anchor="w",
            wraplength=380,
            justify="left",
        ).grid(row=0, column=0, sticky="w")

        p_fg, p_bg = _priority_style(task.priority or "Normal")
        ctk.CTkLabel(
            top,
            text=f"★  {task.priority or 'Normal'} Priority",
            text_color=p_fg,
            fg_color=p_bg,
            corner_radius=10,
            font=ctk.CTkFont(size=11, weight="bold"),
            padx=10,
            pady=4,
        ).grid(row=0, column=1, sticky="e", padx=(8, 0))

        # Description
        ctk.CTkLabel(
            shell,
            text=(task.description or "No description provided.").strip(),
            text_color=MUTED,
            font=ctk.CTkFont(size=13),
            anchor="w",
            justify="left",
            wraplength=420,
        ).grid(row=1, column=0, sticky="ew", pady=(0, 12))

        # Meta chips: assignee · due · status
        chips = ctk.CTkFrame(shell, fg_color="transparent")
        chips.grid(row=2, column=0, sticky="ew", pady=(0, 12))
        chips.grid_columnconfigure(2, weight=1)

        av = ctk.CTkFrame(chips, width=32, height=32, corner_radius=16, fg_color=SOFT_BLUE)
        av.grid(row=0, column=0, padx=(0, 8))
        av.pack_propagate(False)
        ctk.CTkLabel(
            av,
            text=_initials(task.assigned_employee or "?"),
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=BLUE,
        ).place(relx=0.5, rely=0.5, anchor="center")

        who = ctk.CTkFrame(chips, fg_color="transparent")
        who.grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(
            who, text=task.assigned_employee or "Unassigned", font=ctk.CTkFont(size=12, weight="bold"), text_color=TEXT
        ).pack(anchor="w")
        ctk.CTkLabel(who, text="Assigned To", font=ctk.CTkFont(size=10), text_color=MUTED).pack(anchor="w")

        due_box = ctk.CTkFrame(chips, fg_color="transparent")
        due_box.grid(row=0, column=2, sticky="w", padx=(16, 0))
        ctk.CTkLabel(
            due_box, text=f"📅  {_fmt_due(task.due_date)}", font=ctk.CTkFont(size=12), text_color=TEXT
        ).pack(anchor="w")
        ctk.CTkLabel(due_box, text="Due Date", font=ctk.CTkFont(size=10), text_color=MUTED).pack(anchor="w")

        # Status dropdown
        statuses = ["New", "Assigned", "In Progress", "Waiting Review", "Completed", "Cancelled"]
        status_menu = ctk.CTkOptionMenu(
            chips,
            values=statuses,
            height=32,
            corner_radius=10,
            fg_color=_status_soft(task.status or ""),
            text_color=_status_color(task.status or ""),
            button_color=_status_color(task.status or ""),
            button_hover_color=_status_color(task.status or ""),
            dropdown_fg_color=CARD,
            dropdown_text_color=TEXT,
            font=ctk.CTkFont(size=12, weight="bold"),
            command=lambda v, t=task: self._change_status(t, v),
        )
        cur = task.status if task.status in statuses else "Assigned"
        status_menu.set(cur)
        status_menu.grid(row=0, column=3, sticky="e")

        # Progress
        pct = _progress_pct(task)
        ctk.CTkLabel(
            shell, text="Overall Progress", font=ctk.CTkFont(size=12, weight="bold"), text_color=TEXT, anchor="w"
        ).grid(row=3, column=0, sticky="w")
        prog_row = ctk.CTkFrame(shell, fg_color="transparent")
        prog_row.grid(row=4, column=0, sticky="ew", pady=(4, 14))
        prog_row.grid_columnconfigure(0, weight=1)
        bar = ctk.CTkProgressBar(
            prog_row,
            height=10,
            corner_radius=6,
            progress_color=GREEN,
            fg_color=SOFT_GRAY,
        )
        bar.set(pct / 100.0)
        bar.grid(row=0, column=0, sticky="ew", padx=(0, 10))
        ctk.CTkLabel(
            prog_row, text=f"{pct}%", font=ctk.CTkFont(size=13, weight="bold"), text_color=TEXT
        ).grid(row=0, column=1)

        # Checklist (from raw if present)
        checklist = self._parse_checklist(task)
        if checklist:
            done = sum(1 for c in checklist if c.get("done"))
            ctk.CTkLabel(
                shell,
                text=f"☑  Checklist    {done} of {len(checklist)} completed",
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=TEXT,
                anchor="w",
            ).grid(row=5, column=0, sticky="w", pady=(4, 6))
            cl_box = ctk.CTkFrame(shell, fg_color=SOFT_GRAY, corner_radius=12)
            cl_box.grid(row=6, column=0, sticky="ew", pady=(0, 12))
            for i, item in enumerate(checklist):
                row_f = ctk.CTkFrame(cl_box, fg_color="transparent")
                row_f.pack(fill="x", padx=12, pady=6)
                mark = "✓" if item.get("done") else "○"
                color = GREEN if item.get("done") else MUTED
                ctk.CTkLabel(
                    row_f,
                    text=f"{mark}  {item.get('text', 'Item')}",
                    font=ctk.CTkFont(size=12),
                    text_color=color,
                    anchor="w",
                ).pack(anchor="w")
            next_row = 7
        else:
            next_row = 5

        # Attachments
        attachments = self._parse_attachments(task)
        if attachments:
            ctk.CTkLabel(
                shell,
                text=f"📎  Attachments    {len(attachments)}",
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=TEXT,
                anchor="w",
            ).grid(row=next_row, column=0, sticky="w", pady=(4, 6))
            att_box = ctk.CTkFrame(shell, fg_color="transparent")
            att_box.grid(row=next_row + 1, column=0, sticky="ew", pady=(0, 12))
            att_box.grid_columnconfigure(0, weight=1)
            for i, att in enumerate(attachments):
                name = att.get("name") or "file"
                size = att.get("size")
                size_txt = f" {int(size) / 1024:.1f} MB" if size and int(size) > 1024 * 100 else (
                    f" {int(size) / 1024:.0f} KB" if size else ""
                )
                ext = name.rsplit(".", 1)[-1].upper() if "." in name else "FILE"
                icon = "PDF" if ext == "PDF" else "XLS" if ext in ("XLS", "XLSX", "CSV") else "DOC"

                card = ctk.CTkFrame(
                    att_box, fg_color=SOFT_GRAY, corner_radius=10, border_width=1, border_color=BORDER
                )
                card.grid(row=i, column=0, sticky="ew", pady=4)
                card.grid_columnconfigure(1, weight=1)
                ctk.CTkLabel(
                    card,
                    text=icon,
                    font=ctk.CTkFont(size=11, weight="bold"),
                    text_color=RED if icon == "PDF" else GREEN,
                    fg_color=SOFT_RED if icon == "PDF" else SOFT_GREEN,
                    corner_radius=6,
                    width=40,
                    height=28,
                ).grid(row=0, column=0, padx=10, pady=10)
                ctk.CTkLabel(
                    card,
                    text=f"{name}{size_txt}",
                    font=ctk.CTkFont(size=12),
                    text_color=TEXT,
                    anchor="w",
                ).grid(row=0, column=1, sticky="w")
                ctk.CTkButton(
                    card,
                    text="↓",
                    width=36,
                    height=32,
                    corner_radius=8,
                    fg_color=CARD,
                    hover_color=SOFT_GRAY,
                    text_color=TEXT,
                    border_width=1,
                    border_color=BORDER,
                    command=lambda a=att: self._open_attachment(a),
                ).grid(row=0, column=2, padx=10, pady=8)
            next_row = next_row + 2
        else:
            pass

        # Comments / activity (from raw)
        ctk.CTkLabel(
            shell,
            text="💬  Comments & Activity",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=TEXT,
            anchor="w",
        ).grid(row=next_row, column=0, sticky="w", pady=(8, 6))
        activity = self._parse_activity(task)
        act_box = ctk.CTkFrame(shell, fg_color="transparent")
        act_box.grid(row=next_row + 1, column=0, sticky="ew", pady=(0, 8))
        if not activity:
            ctk.CTkLabel(
                act_box, text="No activity yet.", font=ctk.CTkFont(size=12), text_color=MUTED
            ).pack(anchor="w")
        else:
            for ev in activity[:8]:
                line = ctk.CTkFrame(act_box, fg_color="transparent")
                line.pack(fill="x", pady=4)
                av2 = ctk.CTkFrame(line, width=28, height=28, corner_radius=14, fg_color=SOFT_BLUE)
                av2.pack(side="left", padx=(0, 8))
                av2.pack_propagate(False)
                ctk.CTkLabel(
                    av2,
                    text=_initials(ev.get("who", "?")),
                    font=ctk.CTkFont(size=9, weight="bold"),
                    text_color=BLUE,
                ).place(relx=0.5, rely=0.5, anchor="center")
                mid = ctk.CTkFrame(line, fg_color="transparent")
                mid.pack(side="left", fill="x", expand=True)
                ctk.CTkLabel(
                    mid,
                    text=ev.get("who", "Someone"),
                    font=ctk.CTkFont(size=12, weight="bold"),
                    text_color=TEXT,
                    anchor="w",
                ).pack(anchor="w")
                ctk.CTkLabel(
                    mid,
                    text=ev.get("text", ""),
                    font=ctk.CTkFont(size=11),
                    text_color=MUTED,
                    anchor="w",
                ).pack(anchor="w")
                ctk.CTkLabel(
                    line,
                    text=ev.get("when", ""),
                    font=ctk.CTkFont(size=10),
                    text_color=MUTED,
                ).pack(side="right")

        # Comment input
        comment_row = ctk.CTkFrame(shell, fg_color="transparent")
        comment_row.grid(row=next_row + 2, column=0, sticky="ew", pady=(4, 8))
        comment_row.grid_columnconfigure(0, weight=1)
        self.note_box = ctk.CTkEntry(
            comment_row,
            height=40,
            corner_radius=10,
            border_width=1,
            border_color=BORDER,
            fg_color=SOFT_GRAY,
            text_color=TEXT,
            placeholder_text="Add a comment...",
            placeholder_text_color=MUTED,
            font=ctk.CTkFont(size=13),
        )
        self.note_box.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        # Hidden textbox compat for _note() used by actions
        self._note_text_fallback = ""

        ctk.CTkButton(
            comment_row,
            text="➤",
            width=44,
            height=40,
            corner_radius=10,
            fg_color=GREEN,
            hover_color=GREEN_HOVER,
            text_color="#FFFFFF",
            font=ctk.CTkFont(size=16),
            command=lambda: self._set_status("Comment noted (use action buttons to save with work)", ok=True),
        ).grid(row=0, column=1)

        self.status_label = ctk.CTkLabel(
            shell, text="", text_color=MUTED, font=ctk.CTkFont(size=12), anchor="w"
        )
        self.status_label.grid(row=next_row + 3, column=0, sticky="ew", pady=(4, 4))
        self._action_base_row = next_row + 4

        # Actions
        if self._is_manager:
            self._build_manager_actions(shell, task)
        else:
            self._build_employee_actions(shell, task)

    def _change_status(self, task: Task, status: str) -> None:
        """Best-effort status change via controller if available."""
        try:
            if hasattr(self._controller, "update_status"):
                self._controller.update_status(task.id, status)
            elif hasattr(self._controller, "set_status"):
                self._controller.set_status(task.id, status)
            else:
                # Fall back to work actions
                mapping = {
                    "In Progress": lambda: self._controller.start_work(task.id, self._note()),
                    "Completed": lambda: self._controller.complete_work(task.id, self._note()),
                    "Waiting Review": lambda: self._controller.submit_for_review(task.id, self._note()),
                }
                fn = mapping.get(status)
                if fn:
                    fn()
            self._set_status(f"Status → {status}", ok=True)
            self.refresh()
        except Exception as exc:
            self._set_status(str(exc), ok=False)

    @staticmethod
    def _parse_checklist(task: Task) -> list[dict]:
        raw = getattr(task, "raw", None) or {}
        if not isinstance(raw, dict):
            return []
        items = raw.get("checklist") or raw.get("todos") or raw.get("items") or []
        out = []
        for it in items:
            if isinstance(it, dict):
                out.append(
                    {
                        "text": it.get("text") or it.get("title") or it.get("label") or "Item",
                        "done": bool(it.get("done") or it.get("completed") or it.get("checked")),
                    }
                )
            elif isinstance(it, str):
                out.append({"text": it, "done": False})
        return out

    @staticmethod
    def _parse_activity(task: Task) -> list[dict]:
        raw = getattr(task, "raw", None) or {}
        if not isinstance(raw, dict):
            return []
        items = raw.get("activity") or raw.get("comments") or raw.get("history") or []
        out = []
        for it in items:
            if not isinstance(it, dict):
                continue
            out.append(
                {
                    "who": it.get("user") or it.get("author") or it.get("name") or "User",
                    "text": it.get("text") or it.get("message") or it.get("action") or "",
                    "when": str(it.get("at") or it.get("time") or it.get("created_at") or "")[:16],
                }
            )
        return out

    def _note(self) -> str:
        try:
            # Prefer entry (new UI)
            if hasattr(self, "note_box") and self.note_box is not None:
                if isinstance(self.note_box, ctk.CTkEntry):
                    return self.note_box.get().strip()
                return self.note_box.get("1.0", "end").strip()
        except Exception:
            pass
        return ""

    def _set_status(self, text: str, ok: bool = True) -> None:
        try:
            self.status_label.configure(text=text, text_color=GREEN if ok else RED)
        except Exception:
            pass

    def _run(self, action: str, fn: Callable[[], None]) -> None:
        try:
            fn()
            self._set_status(f"Done: {action}", ok=True)
            self.refresh()
        except Exception as exc:
            self._set_status(str(exc), ok=False)
            print(f"❌ Task action failed ({action}): {exc}")

    def _build_employee_actions(self, shell: ctk.CTkFrame, task: Task) -> None:
        base = getattr(self, "_action_base_row", 10)
        ctk.CTkLabel(
            shell, text="Work progress", text_color=MUTED, font=ctk.CTkFont(size=12), anchor="w"
        ).grid(row=base, column=0, sticky="w", pady=(8, 4))

        progress = ctk.CTkFrame(shell, fg_color="transparent")
        progress.grid(row=base + 1, column=0, sticky="ew", pady=(0, 8))
        for i in range(4):
            progress.grid_columnconfigure(i, weight=1, uniform="act")

        actions = [
            ("Start", GREEN, GREEN_HOVER, lambda: self._controller.start_work(task.id, self._note())),
            ("Pause", ORANGE, "#D97706", lambda: self._controller.pause_work(task.id, self._note())),
            ("Submit review", BLUE, "#1D4ED8", lambda: self._controller.submit_for_review(task.id, self._note())),
            ("Complete", PURPLE, "#6D28D9", lambda: self._controller.complete_work(task.id, self._note())),
        ]
        for i, (label, fg, hover, fn) in enumerate(actions):
            ctk.CTkButton(
                progress,
                text=label,
                height=40,
                corner_radius=10,
                fg_color=fg,
                hover_color=hover,
                text_color="#FFFFFF",
                font=ctk.CTkFont(size=12, weight="bold"),
                command=lambda a=label, f=fn: self._run(a, f),
            ).grid(row=0, column=i, padx=3, sticky="ew")

    def _build_manager_actions(self, shell: ctk.CTkFrame, task: Task) -> None:
        base = getattr(self, "_action_base_row", 10)

        # Log time
        time_row = ctk.CTkFrame(shell, fg_color="transparent")
        time_row.grid(row=base, column=0, sticky="ew", pady=(8, 8))
        time_row.grid_columnconfigure(0, weight=1)
        self.hours_entry = ctk.CTkEntry(
            time_row,
            height=38,
            corner_radius=10,
            border_width=1,
            border_color=BORDER,
            fg_color=SOFT_GRAY,
            text_color=TEXT,
            placeholder_text="Hours worked (e.g. 1.5)",
            placeholder_text_color=MUTED,
            font=ctk.CTkFont(size=13),
        )
        self.hours_entry.grid(row=0, column=0, sticky="ew", padx=(0, 8))
        ctk.CTkButton(
            time_row,
            text="Log time",
            width=100,
            height=38,
            corner_radius=10,
            fg_color=BLUE,
            hover_color="#1D4ED8",
            command=lambda: self._run(
                "Time logged",
                lambda: self._controller.log_time(
                    task.id, float(self.hours_entry.get() or 0), self._note()
                ),
            ),
        ).grid(row=0, column=1)

        # Assign
        people = self._controller.get_people_names() or [task.assigned_employee or "Unassigned"]
        assign_row = ctk.CTkFrame(shell, fg_color="transparent")
        assign_row.grid(row=base + 1, column=0, sticky="ew", pady=(0, 10))
        assign_row.grid_columnconfigure(0, weight=1)
        self.assignee_menu = ctk.CTkOptionMenu(
            assign_row,
            values=people,
            height=38,
            corner_radius=10,
            fg_color=SOFT_GRAY,
            text_color=TEXT,
            button_color=BLUE,
            button_hover_color="#1D4ED8",
            dropdown_fg_color=CARD,
            dropdown_text_color=TEXT,
            font=ctk.CTkFont(size=13),
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
            corner_radius=10,
            fg_color=BLUE,
            hover_color="#1D4ED8",
            command=lambda: self._run(
                "Assigned",
                lambda: self._controller.assign_task(task.id, self.assignee_menu.get()),
            ),
        ).grid(row=0, column=1)

        # Work progress
        ctk.CTkLabel(
            shell, text="Work progress", text_color=MUTED, font=ctk.CTkFont(size=12), anchor="w"
        ).grid(row=base + 2, column=0, sticky="w", pady=(4, 4))
        progress = ctk.CTkFrame(shell, fg_color="transparent")
        progress.grid(row=base + 3, column=0, sticky="ew", pady=(0, 8))
        for i in range(4):
            progress.grid_columnconfigure(i, weight=1, uniform="mact")
        for i, (label, fg, hover, fn) in enumerate(
            [
                ("Start", GREEN, GREEN_HOVER, lambda: self._controller.start_work(task.id, self._note())),
                ("Pause", ORANGE, "#D97706", lambda: self._controller.pause_work(task.id, self._note())),
                ("Submit review", BLUE, "#1D4ED8", lambda: self._controller.submit_for_review(task.id, self._note())),
                ("Complete", PURPLE, "#6D28D9", lambda: self._controller.complete_work(task.id, self._note())),
            ]
        ):
            ctk.CTkButton(
                progress,
                text=label,
                height=38,
                corner_radius=10,
                fg_color=fg,
                hover_color=hover,
                text_color="#FFFFFF",
                font=ctk.CTkFont(size=12, weight="bold"),
                command=lambda a=label, f=fn: self._run(a, f),
            ).grid(row=0, column=i, padx=3, sticky="ew")

        # Manager decisions
        ctk.CTkLabel(
            shell, text="Manager decisions", text_color=MUTED, font=ctk.CTkFont(size=12), anchor="w"
        ).grid(row=base + 4, column=0, sticky="w", pady=(8, 4))
        decisions = ctk.CTkFrame(shell, fg_color="transparent")
        decisions.grid(row=base + 5, column=0, sticky="ew", pady=(0, 12))
        for i in range(4):
            decisions.grid_columnconfigure(i, weight=1, uniform="mdec")
        for i, (label, fg, hover, fn) in enumerate(
            [
                ("Approve", GREEN, GREEN_HOVER, lambda: self._controller.approve_review(task.id, self._note())),
                ("Return", ORANGE, "#D97706", lambda: self._controller.return_to_work(task.id, self._note())),
                ("Ask director", BLUE, "#1D4ED8", lambda: self._controller.escalate_to_director(task.id, self._note())),
                ("Cancel task", RED, "#B91C1C", lambda: self._controller.cancel_task(task.id, self._note())),
            ]
        ):
            ctk.CTkButton(
                decisions,
                text=label,
                height=36,
                corner_radius=10,
                fg_color=fg,
                hover_color=hover,
                text_color="#FFFFFF",
                font=ctk.CTkFont(size=12, weight="bold"),
                command=lambda a=label, f=fn: self._run(a, f),
            ).grid(row=0, column=i, padx=3, sticky="ew")

    def _open_create(self) -> None:
        if not self._is_manager:
            return
        CreateTaskModal(self, self._controller, self.refresh)


class CreateTaskModal(ctk.CTkToplevel):
    """Create & assign task – wide professional form with fixed footer."""

    _ENTRY_KW = {
        "height": 40,
        "corner_radius": 8,
        "border_width": 1,
        "border_color": BORDER,
        "fg_color": CARD,
        "text_color": TEXT,
        "placeholder_text_color": MUTED,
        "font": ("Segoe UI", 13),
    }
    _MENU_KW = {
        "height": 40,
        "corner_radius": 8,
        "fg_color": CARD,
        "text_color": TEXT,
        "button_color": GREEN,
        "button_hover_color": GREEN_HOVER,
        "dropdown_fg_color": CARD,
        "dropdown_hover_color": SOFT_GRAY,
        "dropdown_text_color": TEXT,
        "font": ("Segoe UI", 13),
    }

    def __init__(self, master, controller: TaskController, on_created) -> None:
        super().__init__(master)
        self._controller = controller
        self._on_created = on_created
        self._busy = False
        self._attachments: list[dict] = []
        self.title("New Task")
        self.configure(fg_color=BG)
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
            parent, text=text, text_color=MUTED, font=("Segoe UI", 12), anchor="w"
        ).grid(row=row, column=col, sticky="w", **grid)

    def _build(self) -> None:
        shell = ctk.CTkFrame(self, fg_color=CARD, corner_radius=16)
        shell.pack(fill="both", expand=True, padx=18, pady=18)
        shell.grid_columnconfigure(0, weight=1)
        shell.grid_rowconfigure(1, weight=1)

        ctk.CTkLabel(
            shell,
            text="Create & assign a task",
            font=("Segoe UI", 22, "bold"),
            text_color=TEXT,
            anchor="w",
        ).grid(row=0, column=0, padx=24, pady=(18, 10), sticky="ew")

        body = ctk.CTkScrollableFrame(shell, fg_color="transparent")
        body.grid(row=1, column=0, sticky="nsew", padx=8, pady=(0, 4))
        body.grid_columnconfigure(0, weight=1)
        body.grid_columnconfigure(1, weight=1)

        self._label(body, "Title *", 0, 0, padx=16, pady=(8, 0))
        self.title_entry = ctk.CTkEntry(
            body, placeholder_text="e.g. Prepare client quote", **self._ENTRY_KW
        )
        self.title_entry.grid(row=1, column=0, columnspan=2, padx=16, pady=(4, 12), sticky="ew")

        self._label(body, "Description", 2, 0, padx=16, pady=(4, 0))
        self.desc_entry = ctk.CTkTextbox(
            body,
            height=96,
            corner_radius=8,
            border_width=1,
            border_color=BORDER,
            fg_color=CARD,
            text_color=TEXT,
            font=("Segoe UI", 13),
        )
        self.desc_entry.grid(row=3, column=0, columnspan=2, padx=16, pady=(4, 12), sticky="ew")

        self._label(body, "Assign to", 4, 0, padx=16, pady=(4, 0))
        self._label(body, "Priority", 4, 1, padx=16, pady=(4, 0))

        people = self._controller.get_people_names() or ["Unassigned"]
        self.assignee = ctk.CTkOptionMenu(body, values=people, **self._MENU_KW)
        default_person = people[1] if len(people) > 1 and people[0] == "Unassigned" else people[0]
        self.assignee.set(default_person)
        self.assignee.grid(row=5, column=0, padx=(16, 8), pady=(4, 12), sticky="ew")

        self.priority = ctk.CTkOptionMenu(
            body, values=["Low", "Normal", "High", "Urgent"], **self._MENU_KW
        )
        self.priority.set("Normal")
        self.priority.grid(row=5, column=1, padx=(8, 16), pady=(4, 12), sticky="ew")

        self._label(body, "Category", 6, 0, padx=16, pady=(4, 0))
        self._label(body, "Due date (YYYY-MM-DD)", 6, 1, padx=16, pady=(4, 0))

        self.category = ctk.CTkOptionMenu(body, values=TASK_CATEGORIES, **self._MENU_KW)
        self.category.set("Administration")
        self.category.grid(row=7, column=0, padx=(16, 8), pady=(4, 12), sticky="ew")

        self.due_entry = ctk.CTkEntry(body, placeholder_text="2026-09-15", **self._ENTRY_KW)
        self.due_entry.grid(row=7, column=1, padx=(8, 16), pady=(4, 12), sticky="ew")

        self._label(body, "Estimated hours", 8, 0, padx=16, pady=(4, 0))
        self.hours_entry = ctk.CTkEntry(body, placeholder_text="e.g. 2", **self._ENTRY_KW)
        self.hours_entry.grid(row=9, column=0, padx=(16, 8), pady=(4, 12), sticky="ew")

        self._label(body, "Attachments (PDF, Office, images)", 10, 0, padx=16, pady=(4, 0))
        att_row = ctk.CTkFrame(body, fg_color="transparent")
        att_row.grid(row=11, column=0, columnspan=2, padx=16, pady=(4, 16), sticky="ew")
        att_row.grid_columnconfigure(0, weight=1)
        self._att_label = ctk.CTkLabel(
            att_row, text="No files attached", text_color=MUTED, font=("Segoe UI", 12), anchor="w"
        )
        self._att_label.grid(row=0, column=0, sticky="w")
        ctk.CTkButton(
            att_row,
            text="Add files…",
            width=110,
            height=36,
            fg_color=SOFT_GRAY,
            text_color=TEXT,
            hover_color=BORDER,
            command=self._pick_attachments,
        ).grid(row=0, column=1, padx=(8, 0))

        footer = ctk.CTkFrame(shell, fg_color="transparent")
        footer.grid(row=2, column=0, sticky="ew", padx=16, pady=(8, 16))
        footer.grid_columnconfigure(0, weight=1)
        footer.grid_columnconfigure(1, weight=1)

        self.error = ctk.CTkLabel(footer, text="", text_color=RED, font=("Segoe UI", 12), anchor="w")
        self.error.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        self._cancel_btn = ctk.CTkButton(
            footer,
            text="Cancel",
            height=44,
            corner_radius=8,
            fg_color=SOFT_GRAY,
            text_color=TEXT,
            hover_color=BORDER,
            font=("Segoe UI", 14),
            command=self.destroy,
        )
        self._cancel_btn.grid(row=1, column=0, padx=(0, 8), sticky="ew")

        self._save_btn = ctk.CTkButton(
            footer,
            text="Create & Assign",
            height=44,
            corner_radius=8,
            fg_color=GREEN,
            hover_color=GREEN_HOVER,
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
                (
                    "Documents & images",
                    "*.pdf *.doc *.docx *.xls *.xlsx *.csv *.png *.jpg *.jpeg *.gif *.webp *.txt",
                ),
                ("PDF", "*.pdf"),
                ("Word", "*.doc *.docx"),
                ("Excel", "*.xls *.xlsx *.csv"),
                ("Images", "*.png *.jpg *.jpeg *.gif *.webp"),
                ("All files", "*.*"),
            ],
        )
        if not paths:
            return
        max_each = 4 * 1024 * 1024
        for p in paths:
            try:
                fp = FsPath(p)
                data = fp.read_bytes()
                if len(data) > max_each:
                    self.error.configure(
                        text=f"{fp.name} is larger than 4 MB – skipped.", text_color=RED
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
                self.error.configure(text=f"Could not read file: {exc}", text_color=RED)
        self._refresh_att_label()

    def _refresh_att_label(self) -> None:
        if not self._attachments:
            self._att_label.configure(text="No files attached", text_color=MUTED)
        else:
            names = ", ".join(a["name"] for a in self._attachments)
            self._att_label.configure(
                text=f"{len(self._attachments)} file(s): {names}", text_color=TEXT
            )

    def _submit(self) -> None:
        if self._busy:
            return
        title = self.title_entry.get().strip()
        if not title:
            self.error.configure(text="Title is required.", text_color=RED)
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
        self.error.configure(text="Saving to server…", text_color=MUTED)
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
            self.error.configure(text=str(exc), text_color=RED)
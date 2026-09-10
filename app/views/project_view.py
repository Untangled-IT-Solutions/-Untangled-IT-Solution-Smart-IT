"""Searchable Projects workspace with files, updates, and role-aware actions."""

from __future__ import annotations

import os
from pathlib import Path
from tkinter import filedialog, messagebox
from typing import TYPE_CHECKING, Callable

import customtkinter as ctk

from app.controllers.project_controller import ProjectController
from app.models.project import Project
from app.utils.theme import Theme

if TYPE_CHECKING:
    from app.models.account import UserAccount

try:
    from PIL import Image
except ImportError:  # pragma: no cover - application already includes Pillow
    Image = None


class ProjectView(ctk.CTkFrame):
    """Project portfolio for all staff, with management actions for super users."""

    CATEGORY_COLORS = {
        "Internal Project": Theme.ACCENT,
        "Client Project": Theme.INFO,
        "Upcoming Project": Theme.PURPLE,
    }
    STATUS_COLORS = {
        "Active": Theme.SUCCESS, "Planning": Theme.INFO, "On Hold": Theme.WARNING,
        "Completed": Theme.ACCENT, "Archived": Theme.MUTED_TEXT,
    }

    def __init__(
        self,
        master: object,
        controller: ProjectController,
        current_account: "UserAccount | None" = None,
    ) -> None:
        super().__init__(master, fg_color=Theme.BG, corner_radius=0)
        self._controller = controller
        self._account = current_account
        self._actor = str(
            getattr(current_account, "full_name", "")
            or getattr(current_account, "username", "") or "Nexus user"
        )
        self._role = str(getattr(current_account, "role", "") or "Staff")
        self._can_manage = controller.can_manage_projects(self._role, self._actor)
        self._refresh_job = None
        self._brand_images: dict[str, ctk.CTkImage] = {}
        self.search_var = ctk.StringVar()
        self.category_var = ctk.StringVar(value="All")
        self.status_var = ctk.StringVar(value="All")
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(3, weight=1)
        self._build_header()
        self._build_filters()
        self.summary = ctk.CTkFrame(self, fg_color="transparent")
        self.summary.grid(row=2, column=0, sticky="ew", pady=(12, 8))
        self.list_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.list_frame.grid(row=3, column=0, sticky="nsew")
        self.list_frame.grid_columnconfigure((0, 1), weight=1, uniform="projects")
        self.search_var.trace_add("write", self._schedule_refresh)
        self.refresh()

    def _build_header(self) -> None:
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="Projects", text_color=Theme.TEXT, font=Theme.FONT_TITLE).grid(
            row=0, column=0, sticky="sw"
        )
        access = "Full project access" if self._can_manage else "View-only project access"
        ctk.CTkLabel(
            header,
            text=f"Project plans, documents and progress updates  •  {access}",
            text_color=Theme.MUTED_TEXT,
            font=Theme.FONT_BODY,
        ).grid(row=1, column=0, sticky="nw", pady=(2, 0))
        if self._can_manage:
            ctk.CTkButton(
                header, text="+ Add Project", width=140, height=42,
                fg_color=Theme.ACCENT, hover_color=Theme.ACCENT_HOVER,
                font=Theme.FONT_BUTTON, command=self._add_project,
            ).grid(row=0, column=1, rowspan=2, padx=(12, 0))

    def _build_filters(self) -> None:
        bar = ctk.CTkFrame(self, fg_color=Theme.PANEL, corner_radius=Theme.RADIUS)
        bar.grid(row=1, column=0, sticky="ew", pady=(18, 0))
        bar.grid_columnconfigure(0, weight=1)
        search = ctk.CTkEntry(
            bar, textvariable=self.search_var,
            placeholder_text="Search project, owner, client or team member…", height=40,
        )
        search.grid(row=0, column=0, padx=(14, 8), pady=14, sticky="ew")
        ctk.CTkOptionMenu(
            bar, variable=self.category_var,
            values=["All", *self._controller.CATEGORIES], width=165, height=40,
            command=lambda _value: self.refresh(),
        ).grid(row=0, column=1, padx=8, pady=14)
        ctk.CTkOptionMenu(
            bar, variable=self.status_var,
            values=["All", *self._controller.STATUSES], width=125, height=40,
            command=lambda _value: self.refresh(),
        ).grid(row=0, column=2, padx=8, pady=14)
        ctk.CTkButton(
            bar, text="Clear", width=76, height=40, fg_color=Theme.PANEL_ALT,
            text_color=Theme.TEXT, hover_color=Theme.BORDER, command=self._clear_filters,
        ).grid(row=0, column=3, padx=(8, 14), pady=14)

    def _schedule_refresh(self, *_args) -> None:
        if self._refresh_job:
            self.after_cancel(self._refresh_job)
        self._refresh_job = self.after(250, self.refresh)

    def _clear_filters(self) -> None:
        self.search_var.set("")
        self.category_var.set("All")
        self.status_var.set("All")
        self.refresh()

    def refresh(self) -> None:
        self._refresh_job = None
        try:
            projects = self._controller.get_projects(
                self.search_var.get(), self.category_var.get(), self.status_var.get()
            )
            all_projects = self._controller.get_projects()
        except Exception as exc:
            messagebox.showerror("Projects", f"Projects could not be loaded.\n\n{exc}")
            return
        self._render_summary(all_projects)
        for child in self.list_frame.winfo_children():
            child.destroy()
        if not projects:
            empty = ctk.CTkFrame(self.list_frame, fg_color=Theme.PANEL, corner_radius=Theme.RADIUS)
            empty.grid(row=0, column=0, columnspan=2, sticky="ew", pady=8)
            ctk.CTkLabel(
                empty, text="No projects match these filters.",
                text_color=Theme.MUTED_TEXT, font=Theme.FONT_BODY,
            ).pack(pady=38)
            return
        for index, project in enumerate(projects):
            self._project_card(project, index)

    def _render_summary(self, projects: list[Project]) -> None:
        for child in self.summary.winfo_children():
            child.destroy()
        values = (
            ("Total", len(projects), Theme.INFO),
            ("Active", sum(p.status == "Active" for p in projects), Theme.SUCCESS),
            ("Upcoming", sum(p.category == "Upcoming Project" for p in projects), Theme.PURPLE),
            ("Completed", sum(p.status == "Completed" for p in projects), Theme.ACCENT),
        )
        for index, (label, value, color) in enumerate(values):
            tile = ctk.CTkFrame(self.summary, fg_color=Theme.PANEL, corner_radius=Theme.RADIUS)
            tile.grid(row=0, column=index, padx=(0 if index == 0 else 6, 0), sticky="ew")
            self.summary.grid_columnconfigure(index, weight=1, uniform="summary")
            ctk.CTkLabel(tile, text=str(value), text_color=color, font=Theme.FONT_HEADING).pack(pady=(10, 0))
            ctk.CTkLabel(tile, text=label, text_color=Theme.MUTED_TEXT, font=Theme.FONT_SMALL).pack(pady=(0, 10))

    def _project_card(self, project: Project, index: int) -> None:
        column = index % 2
        card = ctk.CTkFrame(self.list_frame, fg_color=Theme.PANEL, corner_radius=Theme.RADIUS)
        card.grid(
            row=index // 2, column=column,
            padx=(0, 7) if column == 0 else (7, 0), pady=(0, 14), sticky="nsew",
        )
        card.grid_columnconfigure(0, weight=1)
        top = ctk.CTkFrame(card, fg_color="transparent")
        top.grid(row=0, column=0, sticky="ew", padx=16, pady=(16, 4))
        top.grid_columnconfigure(1, weight=1)
        brand_image = self._brand_image_for(project)
        if brand_image is not None:
            ctk.CTkLabel(top, text="", image=brand_image).grid(
                row=0, column=0, padx=(0, 12), sticky="w"
            )
        ctk.CTkLabel(
            top, text=project.name, text_color=Theme.TEXT,
            font=Theme.FONT_HEADING, justify="left", wraplength=270,
        ).grid(row=0, column=1, sticky="w")
        ctk.CTkLabel(
            top, text=project.status, text_color="white",
            fg_color=self.STATUS_COLORS.get(project.status, Theme.MUTED_TEXT),
            corner_radius=10, padx=10, pady=4, font=Theme.FONT_SMALL,
        ).grid(row=0, column=2, sticky="e")
        ctk.CTkLabel(
            card, text=project.category,
            text_color=self.CATEGORY_COLORS.get(project.category, Theme.INFO),
            font=Theme.FONT_BUTTON,
        ).grid(row=1, column=0, sticky="w", padx=16)
        description = " ".join(
            (project.description or "No description added.").strip().split()
        )
        if len(description) > 260:
            description = f"{description[:257].rstrip()}…"
        ctk.CTkLabel(
            card, text=description, text_color=Theme.MUTED_TEXT,
            font=Theme.FONT_SMALL, justify="left", wraplength=480,
        ).grid(row=2, column=0, sticky="w", padx=16, pady=(8, 10))
        progress = ctk.CTkProgressBar(card, progress_color=Theme.ACCENT, height=8)
        progress.grid(row=3, column=0, sticky="ew", padx=16)
        progress.set(project.progress / 100)
        ctk.CTkLabel(
            card, text=f"{project.progress}% complete", text_color=Theme.MUTED_TEXT,
            font=Theme.FONT_SMALL,
        ).grid(row=4, column=0, sticky="w", padx=16, pady=(4, 8))
        details = (
            f"Owner: {project.owner or 'Not assigned'}\n"
            f"Department: {project.department or 'Not specified'}\n"
            f"Due: {project.due_date or 'Not set'}   •   Documents: {project.document_count}"
        )
        ctk.CTkLabel(
            card, text=details, text_color=Theme.MUTED_TEXT,
            font=Theme.FONT_SMALL, justify="left",
        ).grid(row=5, column=0, sticky="w", padx=16)
        if project.latest_update:
            ctk.CTkLabel(
                card, text=f"Latest: {project.latest_update}", text_color=Theme.TEXT,
                fg_color=Theme.PANEL_ALT, corner_radius=6, padx=9, pady=7,
                font=Theme.FONT_SMALL, justify="left", wraplength=475,
            ).grid(row=6, column=0, sticky="ew", padx=16, pady=(10, 4))
        buttons = ctk.CTkFrame(card, fg_color="transparent")
        buttons.grid(row=7, column=0, sticky="ew", padx=16, pady=(12, 16))
        ctk.CTkButton(
            buttons, text="Open Project", height=34, fg_color=Theme.INFO,
            command=lambda p=project: self._open_project(p),
        ).pack(side="left")
        if self._can_manage:
            ctk.CTkButton(
                buttons, text="Edit", width=70, height=34,
                fg_color=Theme.PANEL_ALT, text_color=Theme.TEXT, hover_color=Theme.BORDER,
                command=lambda p=project: self._edit_project(p),
            ).pack(side="left", padx=8)
            ctk.CTkButton(
                buttons, text="Delete", width=70, height=34,
                fg_color=Theme.DANGER, hover_color=Theme.DANGER_HOVER,
                command=lambda p=project: self._delete_project(p),
            ).pack(side="right")

    def _brand_image_for(self, project: Project):
        """Return the correct supplied brand image for each Untangled project."""
        branding = {
            "Untangled Main Website": ("website_project_logo.png", (112, 80)),
            "Untangled Nexus": ("nexus_project_icon.png", (92, 62)),
        }
        selection = branding.get(project.name)
        if Image is None or selection is None:
            return None
        filename, size = selection
        if filename in self._brand_images:
            return self._brand_images[filename]
        path = Theme.PROJECT_ROOT / "assets" / "logo" / filename
        if not path.exists():
            return None
        try:
            with Image.open(path) as source:
                picture = source.copy()
            self._brand_images[filename] = ctk.CTkImage(picture, size=size)
            return self._brand_images[filename]
        except OSError:
            return None

    def _add_project(self) -> None:
        ProjectEditorDialog(self, self._controller, self._actor, self._role, None, self.refresh)

    def _edit_project(self, project: Project) -> None:
        ProjectEditorDialog(self, self._controller, self._actor, self._role, project, self.refresh)

    def _open_project(self, project: Project) -> None:
        ProjectDetailDialog(
            self, self._controller, project, self._actor, self._role,
            self._can_manage, self.refresh,
        )

    def _delete_project(self, project: Project) -> None:
        if not messagebox.askyesno(
            "Delete project",
            f"Delete ‘{project.name}’?\n\nThe project record will be removed. Stored files will be moved to the recoverable project trash folder.",
        ):
            return
        try:
            recovery = self._controller.delete_project(project.id or 0, self._actor, self._role)
            detail = f"\n\nFiles were moved to:\n{recovery}" if recovery else ""
            messagebox.showinfo("Project deleted", f"The project was deleted.{detail}")
            self.refresh()
        except Exception as exc:
            messagebox.showerror("Delete project", str(exc))


class ProjectEditorDialog(ctk.CTkToplevel):
    """Screen-safe create/edit project form."""

    def __init__(self, parent, controller, actor, role, project, on_saved: Callable[[], None]):
        super().__init__(parent)
        self.controller, self.actor, self.role = controller, actor, role
        self.project, self.on_saved = project, on_saved
        self.title("Edit project" if project else "Add project")
        self.geometry("920x720")
        self.minsize(760, 600)
        self.transient(parent.winfo_toplevel())
        self.grab_set()
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        ctk.CTkLabel(
            self, text="Edit Project" if project else "Add New Project",
            font=Theme.FONT_TITLE, text_color=Theme.TEXT,
        ).grid(row=0, column=0, padx=24, pady=(20, 8), sticky="w")
        form = ctk.CTkScrollableFrame(self, fg_color=Theme.BG)
        form.grid(row=1, column=0, sticky="nsew", padx=20)
        form.grid_columnconfigure((0, 1), weight=1, uniform="form")
        self.fields = {}
        defaults = project or Project(None, "", "", "Planning", "")
        self._entry(form, "Project name *", "name", defaults.name, 0, 0)
        self._menu(form, "Category *", "category", controller.CATEGORIES, defaults.category, 0, 1)
        self._menu(form, "Status *", "status", controller.STATUSES, defaults.status, 1, 0)
        self._entry(form, "Progress (0–100)", "progress", str(defaults.progress), 1, 1)
        self._entry(form, "Department", "department", defaults.department or "", 2, 0)
        self._entry(form, "Project owner", "owner", defaults.owner, 2, 1)
        self._entry(form, "Client name (client projects)", "client_name", defaults.client_name, 3, 0)
        self._entry(form, "Budget / cost note", "budget_placeholder", defaults.budget_placeholder, 3, 1)
        self._entry(form, "Start date (YYYY-MM-DD, optional)", "start_date", defaults.start_date, 4, 0)
        self._entry(form, "Due date (YYYY-MM-DD, optional)", "due_date", defaults.due_date, 4, 1)
        self._textbox(form, "Description", "description", defaults.description or "", 5)
        self._textbox(form, "Team members (comma-separated)", "members", defaults.members, 6)
        self._textbox(form, "Milestones", "milestones", defaults.milestones, 7)
        self._textbox(form, "Timeline / delivery plan", "timeline", defaults.timeline, 8)
        actions = ctk.CTkFrame(self, fg_color=Theme.PANEL)
        actions.grid(row=2, column=0, sticky="ew", padx=20, pady=(10, 20))
        ctk.CTkButton(actions, text="Cancel", fg_color=Theme.PANEL_ALT, text_color=Theme.TEXT, command=self.destroy).pack(side="left", padx=12, pady=12)
        ctk.CTkButton(actions, text="Save Project", width=180, fg_color=Theme.ACCENT, hover_color=Theme.ACCENT_HOVER, command=self._save).pack(side="right", padx=12, pady=12)

    def _entry(self, form, label, key, value, row, column):
        box = ctk.CTkFrame(form, fg_color="transparent")
        box.grid(row=row, column=column, padx=8, pady=7, sticky="ew")
        ctk.CTkLabel(box, text=label, text_color=Theme.TEXT).pack(anchor="w")
        widget = ctk.CTkEntry(box, height=38)
        widget.insert(0, value or "")
        widget.pack(fill="x", pady=(4, 0))
        self.fields[key] = widget

    def _menu(self, form, label, key, values, value, row, column):
        box = ctk.CTkFrame(form, fg_color="transparent")
        box.grid(row=row, column=column, padx=8, pady=7, sticky="ew")
        ctk.CTkLabel(box, text=label, text_color=Theme.TEXT).pack(anchor="w")
        widget = ctk.CTkOptionMenu(box, values=list(values), height=38)
        widget.set(value if value in values else values[0])
        widget.pack(fill="x", pady=(4, 0))
        self.fields[key] = widget

    def _textbox(self, form, label, key, value, row):
        box = ctk.CTkFrame(form, fg_color="transparent")
        box.grid(row=row, column=0, columnspan=2, padx=8, pady=7, sticky="ew")
        ctk.CTkLabel(box, text=label, text_color=Theme.TEXT).pack(anchor="w")
        widget = ctk.CTkTextbox(box, height=76)
        widget.insert("1.0", value or "")
        widget.pack(fill="x", pady=(4, 0))
        self.fields[key] = widget

    def _save(self) -> None:
        values = {}
        for key, widget in self.fields.items():
            values[key] = widget.get("1.0", "end").strip() if isinstance(widget, ctk.CTkTextbox) else widget.get().strip()
        try:
            if self.project:
                self.controller.update_project(self.project.id, values, self.actor, self.role)
            else:
                self.controller.create_project(values, self.actor, self.role)
            self.on_saved()
            self.destroy()
            messagebox.showinfo("Projects", "Project saved successfully.")
        except Exception as exc:
            messagebox.showerror("Save project", str(exc), parent=self)


class ProjectDetailDialog(ctk.CTkToplevel):
    """Project details, stored documents, and dated progress updates."""

    def __init__(self, parent, controller, project, actor, role, can_manage, on_changed):
        super().__init__(parent)
        self.controller, self.project = controller, project
        self.actor, self.role, self.can_manage = actor, role, can_manage
        self.on_changed = on_changed
        self.title(project.name)
        self.geometry("1040x760")
        self.minsize(820, 620)
        self.transient(parent.winfo_toplevel())
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=1)
        head = ctk.CTkFrame(self, fg_color=Theme.PANEL)
        head.grid(row=0, column=0, sticky="ew", padx=18, pady=(18, 8))
        head.grid_columnconfigure(0, weight=1)
        self.title_label = ctk.CTkLabel(head, text=project.name, font=Theme.FONT_TITLE, text_color=Theme.TEXT)
        self.title_label.grid(row=0, column=0, padx=18, pady=(14, 0), sticky="w")
        self.subtitle = ctk.CTkLabel(head, text="", text_color=Theme.MUTED_TEXT)
        self.subtitle.grid(row=1, column=0, padx=18, pady=(2, 14), sticky="w")
        if can_manage:
            ctk.CTkButton(head, text="Edit Project", width=120, command=self._edit).grid(row=0, column=1, rowspan=2, padx=18)
        self.body = ctk.CTkScrollableFrame(self, fg_color=Theme.BG)
        self.body.grid(row=1, column=0, sticky="nsew", padx=18, pady=(0, 18))
        self.body.grid_columnconfigure(0, weight=1)
        self._render()

    def _render(self) -> None:
        fresh = self.controller.get_project(self.project.id)
        if fresh:
            self.project = fresh
        self.title_label.configure(text=self.project.name)
        self.subtitle.configure(text=f"{self.project.category}  •  {self.project.status}  •  {self.project.progress}% complete")
        for child in self.body.winfo_children():
            child.destroy()
        details = ctk.CTkFrame(self.body, fg_color=Theme.PANEL, corner_radius=Theme.RADIUS)
        details.grid(row=0, column=0, sticky="ew", pady=(0, 12))
        detail_text = (
            f"Description\n{self.project.description or 'No description'}\n\n"
            f"Owner: {self.project.owner or 'Not assigned'}     Department: {self.project.department or 'Not specified'}\n"
            f"Client: {self.project.client_name or 'Not applicable'}     Dates: {self.project.start_date or 'Not set'} to {self.project.due_date or 'Not set'}\n"
            f"Budget: {self.project.budget_placeholder}\n\n"
            f"Team\n{self.project.members or 'No members listed'}\n\n"
            f"Milestones\n{self.project.milestones or 'No milestones listed'}\n\n"
            f"Timeline\n{self.project.timeline or 'No timeline added'}"
        )
        ctk.CTkLabel(details, text=detail_text, text_color=Theme.TEXT, justify="left", anchor="w", wraplength=900).pack(fill="x", padx=18, pady=16)
        self._documents_section(1)
        self._updates_section(2)

    def _documents_section(self, row: int) -> None:
        section = ctk.CTkFrame(self.body, fg_color=Theme.PANEL, corner_radius=Theme.RADIUS)
        section.grid(row=row, column=0, sticky="ew", pady=(0, 12))
        section.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(section, text="Project Documents", font=Theme.FONT_HEADING, text_color=Theme.TEXT).grid(row=0, column=0, padx=18, pady=(14, 8), sticky="w")
        if self.can_manage:
            self.doc_type = ctk.StringVar(value="General")
            ctk.CTkOptionMenu(section, variable=self.doc_type, values=list(self.controller.DOCUMENT_TYPES), width=160).grid(row=0, column=1, padx=8)
            ctk.CTkButton(section, text="+ Add Document", width=130, command=self._add_document).grid(row=0, column=2, padx=(0, 18))
        documents = self.controller.get_documents(self.project.id)
        if not documents:
            ctk.CTkLabel(section, text="No documents stored yet.", text_color=Theme.MUTED_TEXT).grid(row=1, column=0, columnspan=3, padx=18, pady=(4, 16), sticky="w")
        for index, document in enumerate(documents, start=1):
            line = ctk.CTkFrame(section, fg_color=Theme.PANEL_ALT, corner_radius=6)
            line.grid(row=index, column=0, columnspan=3, padx=18, pady=(0, 7), sticky="ew")
            line.grid_columnconfigure(0, weight=1)
            ctk.CTkLabel(line, text=f"{document.name}\n{document.document_type} • Added by {document.added_by or 'Unknown'} • {document.added_at}", justify="left", text_color=Theme.TEXT).grid(row=0, column=0, padx=12, pady=8, sticky="w")
            ctk.CTkButton(line, text="Open", width=68, command=lambda path=document.file_path: self._open_file(path)).grid(row=0, column=1, padx=10)

    def _updates_section(self, row: int) -> None:
        section = ctk.CTkFrame(self.body, fg_color=Theme.PANEL, corner_radius=Theme.RADIUS)
        section.grid(row=row, column=0, sticky="ew", pady=(0, 12))
        section.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(section, text="Project Updates", font=Theme.FONT_HEADING, text_color=Theme.TEXT).grid(row=0, column=0, padx=18, pady=(14, 8), sticky="w")
        if self.can_manage:
            ctk.CTkButton(section, text="+ Add Update", width=130, fg_color=Theme.ACCENT, command=self._add_update).grid(row=0, column=1, padx=18)
        updates = self.controller.get_updates(self.project.id)
        if not updates:
            ctk.CTkLabel(section, text="No updates recorded yet.", text_color=Theme.MUTED_TEXT).grid(row=1, column=0, columnspan=2, padx=18, pady=(4, 16), sticky="w")
        for index, update in enumerate(updates, start=1):
            text = f"{update.update_text}\n{update.status} • {update.progress}% • {update.added_by or 'Unknown'} • {update.created_at}"
            ctk.CTkLabel(section, text=text, justify="left", anchor="w", wraplength=850, fg_color=Theme.PANEL_ALT, corner_radius=6, padx=12, pady=8, text_color=Theme.TEXT).grid(row=index, column=0, columnspan=2, padx=18, pady=(0, 7), sticky="ew")

    def _add_document(self) -> None:
        path = filedialog.askopenfilename(title="Choose a project document", parent=self)
        if not path:
            return
        try:
            self.controller.add_document(self.project.id, path, self.doc_type.get(), self.actor, self.role)
            self.on_changed()
            self._render()
        except Exception as exc:
            messagebox.showerror("Add document", str(exc), parent=self)

    @staticmethod
    def _open_file(path: str) -> None:
        try:
            if not Path(path).is_file():
                raise FileNotFoundError("This stored document could not be found.")
            os.startfile(path)
        except Exception as exc:
            messagebox.showerror("Open document", str(exc))

    def _add_update(self) -> None:
        ProjectUpdateDialog(self, self.controller, self.project, self.actor, self.role, self._after_change)

    def _edit(self) -> None:
        ProjectEditorDialog(self, self.controller, self.actor, self.role, self.project, self._after_change)

    def _after_change(self) -> None:
        self.on_changed()
        self._render()


class ProjectUpdateDialog(ctk.CTkToplevel):
    """Add one dated project update and optionally advance status/progress."""

    def __init__(self, parent, controller, project, actor, role, on_saved):
        super().__init__(parent)
        self.controller, self.project = controller, project
        self.actor, self.role, self.on_saved = actor, role, on_saved
        self.title("Add project update")
        self.geometry("620x470")
        self.transient(parent)
        self.grab_set()
        self.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(self, text="Add Project Update", font=Theme.FONT_HEADING).grid(row=0, column=0, padx=22, pady=(20, 12), sticky="w")
        ctk.CTkLabel(self, text="Update details *").grid(row=1, column=0, padx=22, sticky="w")
        self.text = ctk.CTkTextbox(self, height=170)
        self.text.grid(row=2, column=0, padx=22, pady=(5, 12), sticky="ew")
        fields = ctk.CTkFrame(self, fg_color="transparent")
        fields.grid(row=3, column=0, padx=22, sticky="ew")
        fields.grid_columnconfigure((0, 1), weight=1)
        self.status = ctk.CTkOptionMenu(fields, values=list(controller.STATUSES))
        self.status.set(project.status)
        self.status.grid(row=0, column=0, padx=(0, 6), sticky="ew")
        self.progress = ctk.CTkEntry(fields, placeholder_text="Progress 0–100")
        self.progress.insert(0, str(project.progress))
        self.progress.grid(row=0, column=1, padx=(6, 0), sticky="ew")
        actions = ctk.CTkFrame(self, fg_color="transparent")
        actions.grid(row=4, column=0, padx=22, pady=22, sticky="ew")
        ctk.CTkButton(actions, text="Cancel", fg_color=Theme.PANEL_ALT, text_color=Theme.TEXT, command=self.destroy).pack(side="left")
        ctk.CTkButton(actions, text="Save Update", width=160, fg_color=Theme.ACCENT, command=self._save).pack(side="right")

    def _save(self) -> None:
        try:
            self.controller.add_update(self.project.id, self.text.get("1.0", "end").strip(), self.status.get(), self.progress.get(), self.actor, self.role)
            self.on_saved()
            self.destroy()
        except Exception as exc:
            messagebox.showerror("Add update", str(exc), parent=self)

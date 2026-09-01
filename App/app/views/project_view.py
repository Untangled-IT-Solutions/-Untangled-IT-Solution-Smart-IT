"""Projects workspace view."""

import customtkinter as ctk

from app.controllers.project_controller import ProjectController
from app.utils.theme import Theme


class ProjectView(ctk.CTkFrame):
    """Shows project progress, members, milestones, timeline, documents, and activity."""

    def __init__(self, master: object, controller: ProjectController) -> None:
        super().__init__(master, fg_color=Theme.BG, corner_radius=0)
        self._controller = controller
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        ctk.CTkLabel(self, text="Projects", text_color=Theme.TEXT, font=Theme.FONT_TITLE).grid(
            row=0, column=0, sticky="w"
        )
        ctk.CTkLabel(self, text="Live project streams from Work records", text_color=Theme.MUTED_TEXT, font=Theme.FONT_BODY).grid(
            row=1, column=0, pady=(8, 18), sticky="w"
        )
        self.list_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.list_frame.grid(row=2, column=0, sticky="nsew")
        self.list_frame.grid_columnconfigure((0, 1), weight=1, uniform="projects")
        self.refresh()

    def refresh(self) -> None:
        for child in self.list_frame.winfo_children():
            child.destroy()
        projects = self._controller.get_projects()
        if not projects:
            ctk.CTkLabel(self.list_frame, text="No projects found.", text_color=Theme.MUTED_TEXT).grid(
                row=0, column=0, sticky="w"
            )
            return
        for index, project in enumerate(projects):
            card = ctk.CTkFrame(self.list_frame, fg_color=Theme.PANEL, corner_radius=Theme.RADIUS)
            card.grid(row=index // 2, column=index % 2, padx=(0 if index % 2 == 0 else 10, 10 if index % 2 == 0 else 0), pady=(0, 14), sticky="ew")
            ctk.CTkLabel(card, text=project.name, text_color=Theme.TEXT, font=Theme.FONT_HEADING, wraplength=440, justify="left").pack(anchor="w", padx=16, pady=(16, 4))
            ctk.CTkProgressBar(card, progress_color=Theme.ACCENT).pack(fill="x", padx=16, pady=(4, 8))
            card.winfo_children()[1].set(project.progress / 100)
            details = (
                f"{project.status} | {project.department} | {project.progress}%\n"
                f"Members: {project.members or 'Unassigned'}\n"
                f"Milestones: {project.milestones or 'No milestones'}\n"
                f"Timeline: {project.timeline or 'No timeline'}\n"
                f"Budget: {project.budget_placeholder}\n"
                f"Documents: {project.documents or 'No documents'}\n"
                f"Activity: {project.activity_feed or 'No activity'}"
            )
            ctk.CTkLabel(card, text=details, text_color=Theme.MUTED_TEXT, font=Theme.FONT_SMALL, justify="left", wraplength=480).pack(anchor="w", padx=16, pady=(0, 16))

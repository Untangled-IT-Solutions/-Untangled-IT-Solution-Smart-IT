"""Tasks workspace view."""

import customtkinter as ctk

from app.controllers.task_controller import TaskController
from app.utils.theme import Theme
from app.widgets.work_item_card import WorkItemCard


class TaskView(ctk.CTkFrame):
    """Shows personal, department, and all task views from unified Work."""

    def __init__(
        self,
        master: object,
        controller: TaskController,
        filters: dict[str, object] | None = None,
    ) -> None:
        super().__init__(master, fg_color=Theme.BG, corner_radius=0)
        self._controller = controller
        self._filters = filters or {}
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(2, weight=1)
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.grid(row=0, column=0, sticky="ew")
        header.grid_columnconfigure(0, weight=1)
        ctk.CTkLabel(header, text="Tasks", text_color=Theme.TEXT, font=Theme.FONT_TITLE).grid(row=0, column=0, sticky="w")
        self.scope = ctk.CTkSegmentedButton(
            header, values=["All", "Personal", "Department"], command=lambda _value: self.refresh(),
            selected_color=Theme.ACCENT, selected_hover_color=Theme.ACCENT_HOVER,
            unselected_color=Theme.PANEL_ALT, unselected_hover_color=Theme.BORDER,
        )
        self.scope.grid(row=0, column=1, sticky="e")
        self.scope.set("All")
        ctk.CTkLabel(self, text="Recurring and linked tasks are tracked through Work items", text_color=Theme.MUTED_TEXT, font=Theme.FONT_BODY).grid(row=1, column=0, pady=(8, 18), sticky="w")
        self.list_frame = ctk.CTkScrollableFrame(self, fg_color="transparent")
        self.list_frame.grid(row=2, column=0, sticky="nsew")
        self.list_frame.grid_columnconfigure(0, weight=1)
        self.refresh()

    def refresh(self) -> None:
        for child in self.list_frame.winfo_children():
            child.destroy()
        tasks = self._controller.get_tasks(self.scope.get())
        if not tasks:
            ctk.CTkLabel(self.list_frame, text="No tasks found.", text_color=Theme.MUTED_TEXT).grid(row=0, column=0, sticky="w")
            return
        for row, task in enumerate(tasks):
            WorkItemCard(self.list_frame, task).grid(row=row, column=0, pady=(0, 12), sticky="ew")

# app/views/login_view.py
"""Login window view."""

import customtkinter as ctk

try:
    from PIL import Image
except ModuleNotFoundError:
    Image = None

from app.controllers.login_controller import LoginController
from app.utils.theme import Theme


class LoginView(ctk.CTk):
    """Standalone login window."""

    def __init__(self, controller: LoginController) -> None:
        super().__init__()
        self._controller = controller
        self._logo_image: ctk.CTkImage | None = None
        self._is_destroyed = False

        self.title(f"{Theme.COMPANY_NAME} | Login")
        self.geometry("460x520")
        self.minsize(420, 500)
        self.configure(fg_color=Theme.BG)

        self._build_layout()

    def _build_layout(self) -> None:
        if self._is_destroyed:
            return
        self.grid_columnconfigure(0, weight=1)
        self.grid_rowconfigure(0, weight=1)

        panel = ctk.CTkFrame(self, fg_color=Theme.PANEL, corner_radius=Theme.RADIUS)
        panel.grid(row=0, column=0, padx=36, pady=36, sticky="nsew")
        panel.grid_columnconfigure(0, weight=1)

        logo_path = Theme.logo_for_current_mode()
        if Image is not None and logo_path.exists():
            logo = Image.open(logo_path)
            self._logo_image = ctk.CTkImage(logo, size=self._fit_image(logo.size, 210, 140))
            ctk.CTkLabel(panel, image=self._logo_image, text="").grid(
                row=0, column=0, padx=32, pady=(42, 8), sticky="w"
            )
        else:
            ctk.CTkLabel(
                panel,
                text=Theme.COMPANY_NAME,
                text_color=Theme.TEXT,
                font=Theme.FONT_TITLE,
            ).grid(row=0, column=0, padx=32, pady=(44, 8), sticky="w")

        ctk.CTkLabel(
            panel,
            text=Theme.SUBTITLE,
            text_color=Theme.MUTED_TEXT,
            font=Theme.FONT_BODY,
        ).grid(row=1, column=0, padx=32, pady=(0, 34), sticky="w")

        self.username_entry = ctk.CTkEntry(
            panel,
            height=44,
            placeholder_text="Username",
            border_color=Theme.BORDER,
            fg_color=Theme.PANEL_ALT,
        )
        self.username_entry.grid(row=2, column=0, padx=32, pady=(0, 14), sticky="ew")

        self.password_entry = ctk.CTkEntry(
            panel,
            height=44,
            placeholder_text="Password",
            show="*",
            border_color=Theme.BORDER,
            fg_color=Theme.PANEL_ALT,
        )
        self.password_entry.grid(row=3, column=0, padx=32, pady=(0, 12), sticky="ew")

        self.error_label = ctk.CTkLabel(
            panel,
            text="",
            text_color=Theme.DANGER,
            font=("Segoe UI", 13),
        )
        self.error_label.grid(row=4, column=0, padx=32, pady=(0, 12), sticky="w")

        login_button = ctk.CTkButton(
            panel,
            text="Sign in",
            height=44,
            fg_color=Theme.ACCENT,
            hover_color=Theme.ACCENT_HOVER,
            command=self._submit,
        )
        login_button.grid(row=5, column=0, padx=32, pady=(8, 0), sticky="ew")

        self.bind("<Return>", lambda _: self._submit())

    def _submit(self) -> None:
        """Handle login submission."""
        if self._is_destroyed:
            return
        try:
            success, message = self._controller.login(
                self.username_entry.get(),
                self.password_entry.get(),
            )
            if not self._is_destroyed and self.winfo_exists():
                if not success:
                    self.error_label.configure(text=message, text_color=Theme.DANGER)
                else:
                    self.error_label.configure(text="", text_color=Theme.TEXT)
        except Exception as e:
            if not self._is_destroyed and self.winfo_exists():
                self.error_label.configure(text=f"Login error: {str(e)}", text_color=Theme.DANGER)

    def destroy(self) -> None:
        """Clean up when window is destroyed."""
        self._is_destroyed = True
        super().destroy()

    @staticmethod
    def _fit_image(size: tuple[int, int], max_width: int, max_height: int) -> tuple[int, int]:
        width, height = size
        if width <= 0 or height <= 0:
            return max_width, max_height
        scale = min(max_width / width, max_height / height)
        return max(1, int(width * scale)), max(1, int(height * scale))
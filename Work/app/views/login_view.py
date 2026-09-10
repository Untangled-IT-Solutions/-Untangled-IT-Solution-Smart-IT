# app/views/login_view.py
"""Untangled Nexus Login View.

Responsive desktop, tablet and mobile login screen.

Important:
- Preserves the original Untangled Nexus visual design.
- Does not modify authentication logic.
- Authentication is handled by LoginController.
- Responsive sizing prevents the login card from being clipped.
"""

from pathlib import Path

import customtkinter as ctk

try:
    from PIL import Image
except ModuleNotFoundError:
    Image = None

from app.controllers.login_controller import LoginController
from app.utils.theme import Theme


class LoginView(ctk.CTk):
    """Responsive Untangled Nexus login window."""

    # ============================================================
    # BRAND
    # ============================================================

    PRIMARY_GREEN = "#60920D"
    BRIGHT_GREEN = "#6CE000"
    HOVER_GREEN = "#74AE10"
    DARK_GREEN = "#3F6508"
    LIGHT_GREEN = "#E8F5E0"

    # Light theme
    LIGHT_BACKGROUND = "#F3F6F0"
    LIGHT_PANEL = "#FFFFFF"
    LIGHT_INPUT = "#FFFFFF"
    LIGHT_BORDER = "#D7DDD2"
    LIGHT_DEMO_BG = "#F1F8EC"
    LIGHT_DEMO_BORDER = "#D7E6CF"

    # Dark theme
    DARK_BACKGROUND = "#080D0A"
    DARK_PANEL = "#111812"
    DARK_INPUT = "#182119"
    DARK_BORDER = "#2B382D"
    DARK_DEMO_BG = "#182219"
    DARK_DEMO_BORDER = "#304333"

    ERROR_RED = "#D64545"
    SUCCESS_GREEN = "#60920D"
    DISABLED_GREY = "#7D897F"

    FONT_FAMILY = "Segoe UI"

    # ============================================================
    # RESPONSIVE BREAKPOINTS
    # ============================================================

    MOBILE_WIDTH = 480
    TABLET_WIDTH = 800

    # Minimum usable window
    MIN_WIDTH = 360
    MIN_HEIGHT = 480

    # ============================================================
    # INIT
    # ============================================================

    def __init__(
        self,
        controller: LoginController,
    ) -> None:

        super().__init__()

        self._controller = controller

        self._logo_image = None
        self._logo_label = None

        self._resize_job = None
        self._reset_border_job = None

        self._is_destroyed = False
        self._login_success = False
        self._password_visible = False

        # --------------------------------------------------------
        # Window
        # --------------------------------------------------------

        self.title(
            f"{Theme.COMPANY_NAME} | Login"
        )

        self.minsize(
            self.MIN_WIDTH,
            self.MIN_HEIGHT,
        )

        self.configure(
            fg_color=self._root_background()
        )

        self.protocol(
            "WM_DELETE_WINDOW",
            self.destroy,
        )

        self._set_initial_geometry()

        # --------------------------------------------------------
        # Layout
        # --------------------------------------------------------

        self.grid_rowconfigure(
            0,
            weight=1,
        )

        self.grid_columnconfigure(
            0,
            weight=1,
        )

        self._build_layout()

        # --------------------------------------------------------
        # Keyboard
        # --------------------------------------------------------

        self.bind(
            "<Return>",
            lambda event: self._submit(),
        )

        self.bind(
            "<Escape>",
            lambda event: self.destroy(),
        )

        # --------------------------------------------------------
        # Resize handling
        # --------------------------------------------------------

        self.bind(
            "<Configure>",
            self._on_window_resize,
            add="+",
        )

        self.after_idle(
            self._apply_responsive_layout
        )

        self.after(
            300,
            self._focus_username,
        )

        self.deiconify()
        self.lift()
        self.focus_force()

    # ============================================================
    # INITIAL WINDOW SIZE
    # ============================================================

    def _set_initial_geometry(self) -> None:
        """Set a sensible initial window size."""

        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        # Desktop
        if screen_width >= self.TABLET_WIDTH:

            width = 600
            height = min(
                720,
                screen_height - 100,
            )

        # Tablet
        elif screen_width > self.MOBILE_WIDTH:

            width = min(
                580,
                screen_width - 30,
            )

            height = min(
                720,
                screen_height - 60,
            )

        # Mobile
        else:

            width = max(
                self.MIN_WIDTH,
                screen_width - 10,
            )

            height = max(
                self.MIN_HEIGHT,
                screen_height - 20,
            )

        width = min(
            width,
            screen_width,
        )

        height = min(
            height,
            screen_height,
        )

        x = max(
            0,
            (screen_width - width) // 2,
        )

        y = max(
            0,
            (screen_height - height) // 2,
        )

        self.geometry(
            f"{width}x{height}+{x}+{y}"
        )

    # ============================================================
    # THEME
    # ============================================================

    def _is_dark_mode(self) -> bool:

        try:

            return (
                Theme.CURRENT_MODE.lower()
                == "dark"
            )

        except Exception:

            try:

                return (
                    ctk.get_appearance_mode().lower()
                    == "dark"
                )

            except Exception:

                return False

    def _pick(
        self,
        light: str,
        dark: str,
    ) -> str:

        if self._is_dark_mode():
            return dark

        return light

    def _root_background(self) -> str:

        return self._pick(
            self.LIGHT_BACKGROUND,
            self.DARK_BACKGROUND,
        )

    def _panel_background(self) -> str:

        return self._pick(
            self.LIGHT_PANEL,
            self.DARK_PANEL,
        )

    def _input_background(self) -> str:

        return self._pick(
            self.LIGHT_INPUT,
            self.DARK_INPUT,
        )

    def _border_color(self) -> str:

        return self._pick(
            self.LIGHT_BORDER,
            self.DARK_BORDER,
        )

    def _demo_background(self) -> str:

        return self._pick(
            self.LIGHT_DEMO_BG,
            self.DARK_DEMO_BG,
        )

    def _demo_border(self) -> str:

        return self._pick(
            self.LIGHT_DEMO_BORDER,
            self.DARK_DEMO_BORDER,
        )

    def _font(
        self,
        size: int,
        bold: bool = False,
    ):

        if bold:

            return (
                self.FONT_FAMILY,
                size,
                "bold",
            )

        return (
            self.FONT_FAMILY,
            size,
        )

    # ============================================================
    # MAIN LAYOUT
    # ============================================================

    def _build_layout(self) -> None:

        # --------------------------------------------------------
        # Full-screen shell
        # --------------------------------------------------------

        self._shell = ctk.CTkFrame(
            self,
            fg_color="transparent",
        )

        self._shell.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        self._shell.grid_rowconfigure(
            0,
            weight=1,
        )

        self._shell.grid_columnconfigure(
            0,
            weight=1,
        )

        # --------------------------------------------------------
        # Main login card
        #
        # IMPORTANT:
        # The card gets an explicit responsive size later.
        # This prevents the contents from forcing the window
        # larger than the available screen.
        # --------------------------------------------------------

        self._panel = ctk.CTkFrame(
            self._shell,
            fg_color=self._panel_background(),
            corner_radius=24,
            border_width=1,
            border_color=self._border_color(),
        )

        self._panel.grid(
            row=0,
            column=0,
            sticky="n",
            padx=16,
            pady=16,
        )

        # Do not allow children to dictate panel size.
        self._panel.grid_propagate(False)

        self._panel.grid_rowconfigure(
            1,
            weight=1,
        )

        self._panel.grid_columnconfigure(
            0,
            weight=1,
        )

        # --------------------------------------------------------
        # Green brand bar
        # --------------------------------------------------------

        self._brand_bar = ctk.CTkFrame(
            self._panel,
            height=5,
            fg_color=self.PRIMARY_GREEN,
            corner_radius=3,
        )

        self._brand_bar.grid(
            row=0,
            column=0,
            padx=2,
            pady=(2, 0),
            sticky="ew",
        )

        # --------------------------------------------------------
        # Scrollable content
        # --------------------------------------------------------

        self._scroll_frame = ctk.CTkScrollableFrame(
            self._panel,
            fg_color="transparent",
            scrollbar_button_color=self.PRIMARY_GREEN,
            scrollbar_button_hover_color=self.HOVER_GREEN,
            scrollbar_fg_color="transparent",
        )

        self._scroll_frame.grid(
            row=1,
            column=0,
            padx=2,
            pady=2,
            sticky="nsew",
        )

        self._scroll_frame.grid_columnconfigure(
            0,
            weight=1,
        )

        # --------------------------------------------------------
        # Sections
        # --------------------------------------------------------

        self._build_branding()
        self._build_welcome_section()
        self._build_username_field()
        self._build_password_field()
        self._build_error_section()
        self._build_login_button()
        self._build_loading_section()
        self._build_demo_card()
        self._build_footer()

    # ============================================================
    # BRANDING
    # ============================================================

    def _build_branding(self) -> None:

        self._branding_frame = ctk.CTkFrame(
            self._scroll_frame,
            fg_color="transparent",
        )

        self._branding_frame.grid(
            row=0,
            column=0,
            padx=36,
            pady=(22, 4),
            sticky="ew",
        )

        self._branding_frame.grid_columnconfigure(
            0,
            weight=1,
        )

        loaded = self._load_logo_ctk(
            self._branding_frame
        )

        if not loaded:

            self._logo_label = ctk.CTkLabel(
                self._branding_frame,
                text="UNTANGLED",
                text_color=self.PRIMARY_GREEN,
                font=self._font(
                    26,
                    True,
                ),
            )

            self._logo_label.grid(
                row=0,
                column=0,
                pady=(4, 2),
            )

        self._brand_title = ctk.CTkLabel(
            self._branding_frame,
            text=Theme.COMPANY_NAME,
            text_color=self._pick(
                "#16201A",
                "#F1F5F0",
            ),
            font=self._font(
                21,
                True,
            ),
        )

        self._brand_title.grid(
            row=1,
            column=0,
            pady=(8, 0),
        )

        self._brand_subtitle = ctk.CTkLabel(
            self._branding_frame,
            text=Theme.SUBTITLE,
            text_color=self._pick(
                "#6B776C",
                "#94A395",
            ),
            font=self._font(11),
        )

        self._brand_subtitle.grid(
            row=2,
            column=0,
            pady=(2, 0),
        )

    # ============================================================
    # LOGO
    # ============================================================

    def _get_logo_path(self):

        logo_names = [
            "logo.png",
            "logo.webp",
            "icon.png",
            "Untangled_Logo.png",
            "Untangled-Logo.png",
        ]

        try:

            if hasattr(
                Theme,
                "logo_for_current_mode",
            ):

                path = Theme.logo_for_current_mode()

                if path:

                    path = Path(path)

                    if path.exists():
                        return path

        except Exception:
            pass

        project_root = (
            Path(__file__)
            .resolve()
            .parent
            .parent
            .parent
        )

        locations = [
            project_root / "assets" / "logo",
            project_root / "assets" / "brand",
            project_root / "assets" / "images",
            project_root / "assets",
            project_root / "images",
            Path("./assets/logo"),
            Path("./assets/images"),
            Path("./assets"),
            Path("."),
        ]

        for location in locations:

            try:

                if not location.exists():
                    continue

            except Exception:

                continue

            for name in logo_names:

                candidate = location / name

                if candidate.exists():
                    return candidate

        return None

    def _load_logo_ctk(
        self,
        parent,
    ) -> bool:

        if Image is None:
            return False

        logo_path = self._get_logo_path()

        if logo_path is None:
            return False

        try:

            source = Image.open(
                logo_path
            ).convert("RGBA")

            self._logo_image = ctk.CTkImage(
                light_image=source,
                dark_image=source,
                size=(190, 65),
            )

            self._logo_label = ctk.CTkLabel(
                parent,
                image=self._logo_image,
                text="",
            )

            self._logo_label.grid(
                row=0,
                column=0,
                pady=(4, 2),
            )

            # Prevent image garbage collection.
            self._logo_label._image_reference = (
                self._logo_image
            )

            return True

        except Exception as error:

            print(
                f"Could not load logo: {error}"
            )

            self._logo_image = None

            return False

    # ============================================================
    # WELCOME
    # ============================================================

    def _build_welcome_section(self) -> None:

        self._welcome_frame = ctk.CTkFrame(
            self._scroll_frame,
            fg_color="transparent",
        )

        self._welcome_frame.grid(
            row=1,
            column=0,
            padx=36,
            pady=(18, 5),
            sticky="ew",
        )

        self._welcome_frame.grid_columnconfigure(
            0,
            weight=1,
        )

        self._welcome_label = ctk.CTkLabel(
            self._welcome_frame,
            text="Welcome Back",
            text_color=self._pick(
                "#16201A",
                "#F1F5F0",
            ),
            font=self._font(
                22,
                True,
            ),
            anchor="w",
        )

        self._welcome_label.grid(
            row=0,
            column=0,
            sticky="w",
        )

        self._subtitle_label = ctk.CTkLabel(
            self._welcome_frame,
            text="Sign in to continue",
            text_color=self._pick(
                "#6B776C",
                "#94A395",
            ),
            font=self._font(13),
            anchor="w",
        )

        self._subtitle_label.grid(
            row=1,
            column=0,
            sticky="w",
            pady=(3, 0),
        )

    # ============================================================
    # USERNAME
    # ============================================================

    def _build_username_field(self) -> None:

        self._username_container = ctk.CTkFrame(
            self._scroll_frame,
            fg_color="transparent",
        )

        self._username_container.grid(
            row=2,
            column=0,
            padx=36,
            pady=(12, 6),
            sticky="ew",
        )

        self._username_container.grid_columnconfigure(
            0,
            weight=1,
        )

        self.username_entry = ctk.CTkEntry(
            self._username_container,
            height=48,
            placeholder_text="Username or email",
            border_color=self._border_color(),
            fg_color=self._input_background(),
            text_color=self._pick(
                "#16201A",
                "#F1F5F0",
            ),
            border_width=1,
            corner_radius=12,
            font=self._font(14),
            placeholder_text_color=self._pick(
                "#7D897F",
                "#7D897F",
            ),
        )

        self.username_entry.grid(
            row=0,
            column=0,
            sticky="ew",
        )

        self.username_entry.bind(
            "<FocusIn>",
            lambda event:
            self._on_entry_focus(
                self.username_entry,
                True,
            ),
        )

        self.username_entry.bind(
            "<FocusOut>",
            lambda event:
            self._on_entry_focus(
                self.username_entry,
                False,
            ),
        )

    # ============================================================
    # PASSWORD
    # ============================================================

    def _build_password_field(self) -> None:

        self._password_container = ctk.CTkFrame(
            self._scroll_frame,
            fg_color="transparent",
        )

        self._password_container.grid(
            row=3,
            column=0,
            padx=36,
            pady=(4, 4),
            sticky="ew",
        )

        self._password_container.grid_columnconfigure(
            0,
            weight=1,
        )

        self.password_entry = ctk.CTkEntry(
            self._password_container,
            height=48,
            placeholder_text="Password",
            show="●",
            border_color=self._border_color(),
            fg_color=self._input_background(),
            text_color=self._pick(
                "#16201A",
                "#F1F5F0",
            ),
            border_width=1,
            corner_radius=12,
            font=self._font(14),
            placeholder_text_color=self._pick(
                "#7D897F",
                "#7D897F",
            ),
        )

        self.password_entry.grid(
            row=0,
            column=0,
            sticky="ew",
        )

        self.password_entry.bind(
            "<FocusIn>",
            lambda event:
            self._on_entry_focus(
                self.password_entry,
                True,
            ),
        )

        self.password_entry.bind(
            "<FocusOut>",
            lambda event:
            self._on_entry_focus(
                self.password_entry,
                False,
            ),
        )

        self._show_pass_btn = ctk.CTkButton(
            self._password_container,
            text="👁",
            width=44,
            height=48,
            fg_color=self._input_background(),
            hover_color=self._pick(
                "#EDF5E5",
                "#263529",
            ),
            text_color=self._pick(
                "#6B776C",
                "#94A395",
            ),
            border_width=1,
            border_color=self._border_color(),
            command=self._toggle_password_visibility,
            corner_radius=12,
            font=self._font(13),
        )

        self._show_pass_btn.grid(
            row=0,
            column=1,
            padx=(8, 0),
            sticky="ns",
        )

    # ============================================================
    # ERROR
    # ============================================================

    def _build_error_section(self) -> None:

        self.error_label = ctk.CTkLabel(
            self._scroll_frame,
            text="",
            text_color=self.ERROR_RED,
            font=self._font(11),
            justify="left",
            anchor="w",
            wraplength=420,
        )

        self.error_label.grid(
            row=4,
            column=0,
            padx=36,
            pady=(7, 0),
            sticky="ew",
        )

    # ============================================================
    # LOGIN BUTTON
    # ============================================================

    def _build_login_button(self) -> None:

        self.login_button = ctk.CTkButton(
            self._scroll_frame,
            text="Sign In",
            height=50,
            fg_color=self.PRIMARY_GREEN,
            hover_color=self.HOVER_GREEN,
            text_color="#FFFFFF",
            corner_radius=12,
            font=self._font(
                15,
                True,
            ),
            command=self._submit,
        )

        self.login_button.grid(
            row=5,
            column=0,
            padx=36,
            pady=(15, 0),
            sticky="ew",
        )

    # ============================================================
    # LOADING
    # ============================================================

    def _build_loading_section(self) -> None:

        self._loading_label = ctk.CTkLabel(
            self._scroll_frame,
            text="",
            font=self._font(11),
            text_color=self._pick(
                "#6B776C",
                "#94A395",
            ),
            height=18,
        )

        self._loading_label.grid(
            row=6,
            column=0,
            padx=36,
            pady=(4, 0),
            sticky="ew",
        )

    # ============================================================
    # DEMO CARD
    # ============================================================

    def _build_demo_card(self) -> None:

        self._demo_frame = ctk.CTkFrame(
            self._scroll_frame,
            fg_color=self._demo_background(),
            corner_radius=14,
            border_width=1,
            border_color=self._demo_border(),
        )

        self._demo_frame.grid(
            row=7,
            column=0,
            padx=36,
            pady=(15, 5),
            sticky="ew",
        )

        self._demo_frame.grid_columnconfigure(
            0,
            weight=1,
        )

        self._demo_title = ctk.CTkLabel(
            self._demo_frame,
            text="Demo Access",
            font=self._font(
                11,
                True,
            ),
            text_color=self._pick(
                self.DARK_GREEN,
                self.BRIGHT_GREEN,
            ),
            anchor="w",
        )

        self._demo_title.grid(
            row=0,
            column=0,
            padx=14,
            pady=(9, 3),
            sticky="w",
        )

        self._fill_button = ctk.CTkButton(
            self._demo_frame,
            text="Fill",
            width=58,
            height=27,
            fg_color=self._pick(
                self.LIGHT_GREEN,
                "#22331F",
            ),
            hover_color=self._pick(
                "#D7EBC9",
                "#2C4328",
            ),
            text_color=self._pick(
                self.DARK_GREEN,
                self.BRIGHT_GREEN,
            ),
            corner_radius=8,
            font=self._font(
                10,
                True,
            ),
            command=self._auto_fill_demo,
        )

        self._fill_button.grid(
            row=0,
            column=1,
            padx=12,
            pady=(7, 3),
            sticky="e",
        )

        ctk.CTkLabel(
            self._demo_frame,
            text="siyandan@untangled.co.za",
            font=self._font(10),
            text_color=self._pick(
                "#6B776C",
                "#94A395",
            ),
            anchor="w",
        ).grid(
            row=1,
            column=0,
            columnspan=2,
            padx=14,
            pady=(1, 0),
            sticky="w",
        )

        ctk.CTkLabel(
            self._demo_frame,
            text="••••••••••••••••",
            font=self._font(10),
            text_color=self._pick(
                "#6B776C",
                "#94A395",
            ),
            anchor="w",
        ).grid(
            row=2,
            column=0,
            columnspan=2,
            padx=14,
            pady=(1, 9),
            sticky="w",
        )

    # ============================================================
    # FOOTER
    # ============================================================

    def _build_footer(self) -> None:

        self._footer_frame = ctk.CTkFrame(
            self._scroll_frame,
            fg_color="transparent",
        )

        self._footer_frame.grid(
            row=8,
            column=0,
            padx=36,
            pady=(8, 16),
            sticky="ew",
        )

        self._footer_frame.grid_columnconfigure(
            0,
            weight=1,
        )

        ctk.CTkLabel(
            self._footer_frame,
            text=f"v{Theme.VERSION}",
            font=self._font(9),
            text_color=self._pick(
                "#6B776C",
                "#94A395",
            ),
            anchor="w",
        ).grid(
            row=0,
            column=0,
            sticky="w",
        )

        self._status_frame = ctk.CTkFrame(
            self._footer_frame,
            fg_color="transparent",
        )

        self._status_frame.grid(
            row=0,
            column=1,
            sticky="e",
        )

        ctk.CTkLabel(
            self._status_frame,
            text="●",
            text_color=self.PRIMARY_GREEN,
            font=self._font(9),
        ).pack(
            side="left"
        )

        ctk.CTkLabel(
            self._status_frame,
            text=" All systems ready",
            text_color=self._pick(
                "#6B776C",
                "#94A395",
            ),
            font=self._font(9),
        ).pack(
            side="left"
        )

    # ============================================================
    # RESPONSIVE SIZING
    # ============================================================

    def _on_window_resize(
        self,
        event=None,
    ) -> None:

        if self._is_destroyed:
            return

        if event is not None:

            # Only react to the actual window.
            if event.widget is not self:
                return

        if self._resize_job is not None:

            try:
                self.after_cancel(
                    self._resize_job
                )
            except Exception:
                pass

        self._resize_job = self.after(
            50,
            self._apply_responsive_layout,
        )

    def _apply_responsive_layout(self) -> None:

        self._resize_job = None

        if self._is_destroyed:
            return

        try:

            window_width = self.winfo_width()
            window_height = self.winfo_height()

            if window_width <= 1:
                return

            if window_height <= 1:
                return

            # ====================================================
            # MOBILE
            # ====================================================

            if window_width <= self.MOBILE_WIDTH:

                layout = "mobile"

                outer_margin = 8

                panel_width = max(
                    self.MIN_WIDTH - 10,
                    window_width - (
                        outer_margin * 2
                    ),
                )

                panel_height = max(
                    430,
                    window_height - (
                        outer_margin * 2
                    ),
                )

                panel_radius = 16

                content_padding = 18

                logo_width = 150
                logo_height = 52

                welcome_size = 18

                input_height = 43
                button_height = 45

            # ====================================================
            # TABLET
            # ====================================================

            elif window_width <= self.TABLET_WIDTH:

                layout = "tablet"

                outer_margin = 14

                panel_width = min(
                    540,
                    window_width - (
                        outer_margin * 2
                    ),
                )

                panel_height = min(
                    680,
                    window_height - (
                        outer_margin * 2
                    ),
                )

                panel_height = max(
                    500,
                    panel_height,
                )

                panel_radius = 20

                content_padding = 28

                logo_width = 175
                logo_height = 60

                welcome_size = 20

                input_height = 46
                button_height = 48

            # ====================================================
            # DESKTOP
            # ====================================================

            else:

                layout = "desktop"

                outer_margin = 20

                panel_width = 520

                panel_height = min(
                    680,
                    window_height - (
                        outer_margin * 2
                    ),
                )

                panel_height = max(
                    560,
                    panel_height,
                )

                panel_radius = 24

                content_padding = 36

                logo_width = 190
                logo_height = 65

                welcome_size = 22

                input_height = 48
                button_height = 50

            # ====================================================
            # FINAL SAFETY LIMITS
            # ====================================================

            # Never let the panel become larger than the window.
            panel_width = min(
                panel_width,
                window_width - (
                    outer_margin * 2
                ),
            )

            panel_height = min(
                panel_height,
                window_height - (
                    outer_margin * 2
                ),
            )

            panel_width = max(
                300,
                panel_width,
            )

            panel_height = max(
                400,
                panel_height,
            )

            # ====================================================
            # APPLY PANEL SIZE
            # ====================================================

            self._panel.configure(
                width=panel_width,
                height=panel_height,
                corner_radius=panel_radius,
            )

            self._panel.grid_configure(
                padx=outer_margin,
                pady=outer_margin,
            )

            # ====================================================
            # CONTENT PADDING
            # ====================================================

            content_widgets = [
                self._branding_frame,
                self._welcome_frame,
                self._username_container,
                self._password_container,
                self.error_label,
                self.login_button,
                self._loading_label,
                self._demo_frame,
                self._footer_frame,
            ]

            for widget in content_widgets:

                try:

                    widget.grid_configure(
                        padx=content_padding
                    )

                except Exception:
                    pass

            # ====================================================
            # LOGO
            # ====================================================

            if self._logo_image is not None:

                try:

                    self._logo_image.configure(
                        size=(
                            logo_width,
                            logo_height,
                        )
                    )

                except Exception:
                    pass

            # ====================================================
            # WELCOME
            # ====================================================

            self._welcome_label.configure(
                font=self._font(
                    welcome_size,
                    True,
                )
            )

            # ====================================================
            # INPUTS
            # ====================================================

            self.username_entry.configure(
                height=input_height,
                font=self._font(
                    13
                    if layout != "desktop"
                    else 14
                ),
            )

            self.password_entry.configure(
                height=input_height,
                font=self._font(
                    13
                    if layout != "desktop"
                    else 14
                ),
            )

            self._show_pass_btn.configure(
                height=input_height,
                width=42,
            )

            # ====================================================
            # LOGIN BUTTON
            # ====================================================

            self.login_button.configure(
                height=button_height,
                font=self._font(
                    14
                    if layout != "desktop"
                    else 15,
                    True,
                ),
            )

            # ====================================================
            # ERROR WRAPPING
            # ====================================================

            self.error_label.configure(
                wraplength=max(
                    180,
                    panel_width - (
                        content_padding * 2
                    ) - 10,
                )
            )

            # ====================================================
            # MOBILE SPACING
            # ====================================================

            if layout == "mobile":

                self._branding_frame.grid_configure(
                    pady=(14, 2)
                )

                self._welcome_frame.grid_configure(
                    pady=(13, 4)
                )

                self._username_container.grid_configure(
                    pady=(8, 5)
                )

                self._password_container.grid_configure(
                    pady=(3, 3)
                )

                self.error_label.grid_configure(
                    pady=(5, 0)
                )

                self.login_button.grid_configure(
                    pady=(11, 0)
                )

                self._loading_label.grid_configure(
                    pady=(3, 0)
                )

                self._demo_frame.grid_configure(
                    pady=(12, 4)
                )

                self._footer_frame.grid_configure(
                    pady=(6, 12)
                )

            # ====================================================
            # TABLET SPACING
            # ====================================================

            elif layout == "tablet":

                self._branding_frame.grid_configure(
                    pady=(18, 3)
                )

                self._welcome_frame.grid_configure(
                    pady=(16, 5)
                )

                self._username_container.grid_configure(
                    pady=(10, 6)
                )

                self._password_container.grid_configure(
                    pady=(4, 4)
                )

                self.error_label.grid_configure(
                    pady=(6, 0)
                )

                self.login_button.grid_configure(
                    pady=(13, 0)
                )

                self._loading_label.grid_configure(
                    pady=(4, 0)
                )

                self._demo_frame.grid_configure(
                    pady=(14, 5)
                )

                self._footer_frame.grid_configure(
                    pady=(7, 14)
                )

            # ====================================================
            # DESKTOP SPACING
            # ====================================================

            else:

                self._branding_frame.grid_configure(
                    pady=(22, 4)
                )

                self._welcome_frame.grid_configure(
                    pady=(18, 5)
                )

                self._username_container.grid_configure(
                    pady=(12, 6)
                )

                self._password_container.grid_configure(
                    pady=(4, 4)
                )

                self.error_label.grid_configure(
                    pady=(7, 0)
                )

                self.login_button.grid_configure(
                    pady=(15, 0)
                )

                self._loading_label.grid_configure(
                    pady=(4, 0)
                )

                self._demo_frame.grid_configure(
                    pady=(15, 5)
                )

                self._footer_frame.grid_configure(
                    pady=(8, 16)
                )

            # ====================================================
            # SHORT WINDOW
            # ====================================================

            if window_height < 560:

                self._branding_frame.grid_configure(
                    pady=(8, 2)
                )

                self._welcome_frame.grid_configure(
                    pady=(8, 3)
                )

                self._username_container.grid_configure(
                    pady=(5, 4)
                )

                self._password_container.grid_configure(
                    pady=(3, 3)
                )

                self.login_button.grid_configure(
                    pady=(8, 0)
                )

                self._demo_frame.grid_configure(
                    pady=(8, 3)
                )

                self._footer_frame.grid_configure(
                    pady=(5, 8)
                )

            self.update_idletasks()

        except Exception as error:

            print(
                f"Login responsive layout error: {error}"
            )

    # ============================================================
    # FOCUS
    # ============================================================

    def _focus_username(self) -> None:

        if self._is_destroyed:
            return

        try:

            if self.username_entry.winfo_exists():

                self.username_entry.focus_set()

        except Exception:
            pass

    # ============================================================
    # ENTRY FOCUS
    # ============================================================

    def _on_entry_focus(
        self,
        entry,
        focused: bool,
    ) -> None:

        if self._is_destroyed:
            return

        try:

            if focused:

                entry.configure(
                    border_color=self.PRIMARY_GREEN,
                    border_width=2,
                )

            else:

                entry.configure(
                    border_color=self._border_color(),
                    border_width=1,
                )

        except Exception:
            pass

    # ============================================================
    # PASSWORD VISIBILITY
    # ============================================================

    def _toggle_password_visibility(self) -> None:

        if self._is_destroyed:
            return

        self._password_visible = (
            not self._password_visible
        )

        try:

            self.password_entry.configure(
                show=(
                    ""
                    if self._password_visible
                    else "●"
                )
            )

            self._show_pass_btn.configure(
                text=(
                    "🙈"
                    if self._password_visible
                    else "👁"
                ),
                text_color=(
                    self.PRIMARY_GREEN
                    if self._password_visible
                    else self._pick(
                        "#6B776C",
                        "#94A395",
                    )
                ),
            )

        except Exception:
            pass

    # ============================================================
    # DEMO FILL
    # ============================================================

    def _auto_fill_demo(self) -> None:

        if self._is_destroyed:
            return

        try:

            self.username_entry.delete(
                0,
                "end",
            )

            self.username_entry.insert(
                0,
                "siyandan@untangled.co.za",
            )

            self.password_entry.delete(
                0,
                "end",
            )

            self.password_entry.insert(
                0,
                "Password@untangled123",
            )

            self.error_label.configure(
                text=""
            )

            self.username_entry.configure(
                border_color=self.PRIMARY_GREEN
            )

            self.password_entry.configure(
                border_color=self.PRIMARY_GREEN
            )

            if self._reset_border_job is not None:

                try:

                    self.after_cancel(
                        self._reset_border_job
                    )

                except Exception:
                    pass

            self._reset_border_job = self.after(
                1500,
                self._reset_border_colors,
            )

        except Exception:
            pass

    def _reset_border_colors(self) -> None:

        self._reset_border_job = None

        if self._is_destroyed:
            return

        try:

            self.username_entry.configure(
                border_color=self._border_color()
            )

            self.password_entry.configure(
                border_color=self._border_color()
            )

        except Exception:
            pass

    # ============================================================
    # LOGIN
    # ============================================================

    def _submit(self) -> None:

        if self._is_destroyed:
            return

        if self._login_success:
            return

        username = (
            self.username_entry
            .get()
            .strip()
        )

        password = (
            self.password_entry
            .get()
        )

        # --------------------------------------------------------
        # Validation
        # --------------------------------------------------------

        if not username or not password:

            self.error_label.configure(
                text=(
                    "Please enter your username "
                    "and password."
                ),
                text_color=self.ERROR_RED,
            )

            return

        # --------------------------------------------------------
        # Loading
        # --------------------------------------------------------

        self.login_button.configure(
            state="disabled",
            text="Authenticating...",
            fg_color=self.DISABLED_GREY,
            hover_color=self.DISABLED_GREY,
        )

        self._loading_label.configure(
            text="Authenticating...",
            text_color=self._pick(
                "#6B776C",
                "#94A395",
            ),
        )

        self.error_label.configure(
            text=""
        )

        self.update_idletasks()

        # --------------------------------------------------------
        # Controller
        # --------------------------------------------------------

        try:

            success, message = (
                self._controller.login(
                    username,
                    password,
                )
            )

            if self._is_destroyed:
                return

            if success:

                self._login_success = True

                self.error_label.configure(
                    text=""
                )

                self._loading_label.configure(
                    text="✓ Authentication successful",
                    text_color=self.PRIMARY_GREEN,
                )

                self.login_button.configure(
                    text="Welcome!",
                    fg_color=self.SUCCESS_GREEN,
                    hover_color=self.SUCCESS_GREEN,
                    state="normal",
                )

                self.after(
                    500,
                    self.withdraw,
                )

            else:

                self._reset_login_button()

                self._loading_label.configure(
                    text=""
                )

                self.error_label.configure(
                    text=message,
                    text_color=self.ERROR_RED,
                )

                self.username_entry.focus_set()

        except Exception as error:

            self._reset_login_button()

            self._loading_label.configure(
                text=""
            )

            self.error_label.configure(
                text=f"Login error: {error}",
                text_color=self.ERROR_RED,
            )

            import traceback

            traceback.print_exc()

    # ============================================================
    # RESET BUTTON
    # ============================================================

    def _reset_login_button(self) -> None:

        try:

            self.login_button.configure(
                state="normal",
                text="Sign In",
                fg_color=self.PRIMARY_GREEN,
                hover_color=self.HOVER_GREEN,
                text_color="#FFFFFF",
            )

        except Exception:
            pass

    # ============================================================
    # SHOW
    # ============================================================

    def show(self) -> None:

        if self._is_destroyed:
            return

        self._login_success = False
        self._password_visible = False

        try:

            self.deiconify()
            self.lift()
            self.focus_force()

            self.username_entry.delete(
                0,
                "end",
            )

            self.password_entry.delete(
                0,
                "end",
            )

            self.password_entry.configure(
                show="●"
            )

            self._show_pass_btn.configure(
                text="👁",
                text_color=self._pick(
                    "#6B776C",
                    "#94A395",
                ),
            )

            self.error_label.configure(
                text=""
            )

            self._loading_label.configure(
                text=""
            )

            self._reset_login_button()

            self.after(
                100,
                self._focus_username,
            )

            self.after(
                120,
                self._apply_responsive_layout,
            )

        except Exception:
            pass

    # ============================================================
    # DESTROY
    # ============================================================

    def destroy(self) -> None:

        if self._is_destroyed:
            return

        self._is_destroyed = True

        if self._resize_job is not None:

            try:

                self.after_cancel(
                    self._resize_job
                )

            except Exception:
                pass

            self._resize_job = None

        if self._reset_border_job is not None:

            try:

                self.after_cancel(
                    self._reset_border_job
                )

            except Exception:
                pass

            self._reset_border_job = None

        self._logo_image = None

        try:

            super().destroy()

        except Exception:
            pass
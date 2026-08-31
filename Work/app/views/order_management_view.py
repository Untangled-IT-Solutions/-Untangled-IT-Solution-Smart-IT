# app/views/order_management_view.py
"""
Order Management View

Matches the existing Quote Management workspace style.

MongoDB collection:
    orders

Expected order structure:

{
    "_id": ...,
    "reference": "ORD-MT5RV30Z-5ZAY",
    "customerName": "Siyanda Nkosi",
    "company": "Siyanda Nkosi",
    "email": "siyanda.nkosi.developer@gmail.com",
    "phone": "0781021593",
    "address": "1241 Camphor Tree Street",
    "notes": "",
    "items": [...],
    "total": 15950,
    "status": "pending",
    "createdAt": datetime(...),
    "updatedAt": datetime(...)
}
"""

from datetime import datetime
from typing import Optional, Dict, Any, List

import customtkinter as ctk

from app.services.mongodb_service import MongoDBService
from app.services.backend_api_client import BackendAPIClient
from app.utils.theme import Theme


class OrderManagementView(ctk.CTkFrame):
    """Order Management workspace."""

    # ------------------------------------------------------------------
    # STATUS
    # ------------------------------------------------------------------

    STATUS_OPTIONS = [
        "Pending",
        "Confirmed",
        "Processing",
        "Assigned",
        "In Progress",
        "Ready",
        "Awaiting Payment",
        "Paid",
        "Completed",
        "Cancelled",
    ]

    STATUS_COLORS = {
        "Pending": "#FFC107",
        "Confirmed": "#2196F3",
        "Processing": "#9C27B0",
        "Assigned": "#3F51B5",
        "In Progress": "#FF9800",
        "Ready": "#00BCD4",
        "Awaiting Payment": "#E91E63",
        "Paid": "#4CAF50",
        "Completed": "#388E3C",
        "Cancelled": "#F44336",
    }

    STATUS_ICONS = {
        "Pending": "⏳",
        "Confirmed": "✅",
        "Processing": "⚙️",
        "Assigned": "📋",
        "In Progress": "🔧",
        "Ready": "📦",
        "Awaiting Payment": "💰",
        "Paid": "💳",
        "Completed": "🏁",
        "Cancelled": "❌",
    }

    DISPLAY_TO_MONGO = {
        "Pending": "pending",
        "Confirmed": "confirmed",
        "Processing": "processing",
        "Assigned": "assigned",
        "In Progress": "in_progress",
        "Ready": "ready",
        "Awaiting Payment": "awaiting_payment",
        "Paid": "paid",
        "Completed": "completed",
        "Cancelled": "cancelled",
    }

    MONGO_TO_DISPLAY = {
        "pending": "Pending",
        "confirmed": "Confirmed",
        "processing": "Processing",
        "assigned": "Assigned",
        "in_progress": "In Progress",
        "in progress": "In Progress",
        "ready": "Ready",
        "awaiting_payment": "Awaiting Payment",
        "paid": "Paid",
        "completed": "Completed",
        "cancelled": "Cancelled",
    }

    MANAGER_ROLES = [
        "Director",
        "Branch Manager",
        "Business Lead",
        "Operations Manager",
        "Manager",
        "Admin",
        "Administrator",
        "Super Admin",
    ]

    STAFF_ROLES = [
        "Staff",
        "Intern",
    ]

    # ------------------------------------------------------------------
    # INIT
    # ------------------------------------------------------------------

    def __init__(
        self,
        master,
        mongodb_service: MongoDBService,
        people_controller=None,
        notification_controller=None,
        auth_service=None,
        navigation_controller=None,
        backend_api: BackendAPIClient = None,
    ):
        super().__init__(
            master,
            fg_color=Theme.BG,
            corner_radius=0,
        )

        self._mongodb = mongodb_service
        self._people_controller = people_controller
        self._notification_controller = notification_controller
        self._auth_service = auth_service
        self._navigation_controller = navigation_controller
        self._backend_api = backend_api or BackendAPIClient()

        self._orders: List[Dict[str, Any]] = []

        self._selected_order: Optional[Dict[str, Any]] = None
        self._selected_order_id: Optional[str] = None

        self._current_role = "Staff"
        self._current_user_name = ""
        self._current_username = ""

        self._is_staff = False
        self._is_manager = False
        self._is_destroyed = False

        self._search_job = None
        self._active_status_filter = "All"

        self._filter_buttons = {}
        self._order_cards = {}

        self._status_dropdown = None
        self._assign_menu = None

        self._employee_names: List[str] = []
        self._employee_cache: Dict[str, Dict[str, Any]] = {}

        if not self._check_authorization():
            return

        self._setup_ui()

        self.after(
            100,
            self._load_orders,
        )

        self._load_employees()

    # ==================================================================
    # AUTHORIZATION
    # ==================================================================

    def _check_authorization(self) -> bool:
        """Determine current user and role."""

        session = (
            getattr(
                self._auth_service,
                "current_session",
                None,
            )
            if self._auth_service
            else None
        )

        if session:
            self._current_role = getattr(
                session,
                "role",
                "Staff",
            )

            self._current_user_name = (
                getattr(session, "full_name", None)
                or getattr(session, "name", None)
                or getattr(session, "username", None)
                or getattr(session, "email", None)
                or ""
            )

            self._current_username = (
                getattr(session, "username", None)
                or getattr(session, "email", None)
                or ""
            )

            if (
                not self._current_user_name
                and hasattr(session, "account")
            ):
                self._current_user_name = getattr(
                    session.account,
                    "full_name",
                    "",
                )

                self._current_username = getattr(
                    session.account,
                    "username",
                    "",
                )

        elif self._navigation_controller:
            self._current_role = getattr(
                self._navigation_controller,
                "_current_role",
                "Staff",
            )

            self._current_username = getattr(
                self._navigation_controller,
                "_current_username",
                "",
            )

            self._current_user_name = getattr(
                self._navigation_controller,
                "_current_full_name",
                "",
            )

        role = str(
            self._current_role or "Staff"
        ).strip()

        print(
            f"👤 Order Management user: "
            f"{self._current_user_name} | "
            f"Username: {self._current_username} | "
            f"Role: {role}"
        )

        if role in self.MANAGER_ROLES:
            self._is_manager = True
            self._is_staff = False

        elif role in self.STAFF_ROLES:
            self._is_manager = False
            self._is_staff = True

        else:
            # Keep access compatible with the existing
            # Quote Management behaviour.
            self._is_manager = False
            self._is_staff = False

        return True

    # ==================================================================
    # UI
    # ==================================================================

    def _setup_ui(self):
        """
        Same basic proportions as Quote Management:
        30% list / 70% details.
        """

        self.grid_columnconfigure(
            0,
            weight=30,
            minsize=320,
        )

        self.grid_columnconfigure(
            1,
            weight=70,
            minsize=500,
        )

        self.grid_rowconfigure(
            0,
            weight=1,
        )

        self.grid_rowconfigure(
            1,
            weight=0,
        )

        self._setup_list_panel()
        self._setup_details_panel()

        self._status_bar = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=12),
            anchor="w",
            text_color=Theme.MUTED_TEXT,
            height=24,
        )

        self._status_bar.grid(
            row=1,
            column=0,
            columnspan=2,
            sticky="ew",
            padx=15,
            pady=(2, 8),
        )

        try:
            self.winfo_toplevel().bind(
                "<F5>",
                lambda event: self._load_orders(),
            )
        except Exception:
            pass

    # ------------------------------------------------------------------
    # LEFT PANEL
    # ------------------------------------------------------------------

    def _setup_list_panel(self):
        self._list_panel = ctk.CTkFrame(
            self,
            corner_radius=12,
            fg_color=Theme.PANEL,
        )

        self._list_panel.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=(0, 6),
            pady=(0, 2),
        )

        self._list_panel.grid_columnconfigure(
            0,
            weight=1,
        )

        self._list_panel.grid_rowconfigure(
            4,
            weight=1,
        )

        # Header
        header = ctk.CTkFrame(
            self._list_panel,
            fg_color="transparent",
        )

        header.grid(
            row=0,
            column=0,
            padx=15,
            pady=(14, 6),
            sticky="ew",
        )

        header.grid_columnconfigure(
            0,
            weight=1,
        )

        title_box = ctk.CTkFrame(
            header,
            fg_color="transparent",
        )

        title_box.grid(
            row=0,
            column=0,
            sticky="w",
        )

        ctk.CTkLabel(
            title_box,
            text=(
                "All Orders"
                if self._is_manager
                else "My Orders"
            ),
            font=ctk.CTkFont(
                size=18,
                weight="bold",
            ),
            text_color=Theme.TEXT,
        ).pack(
            anchor="w",
        )

        self._stats_label = ctk.CTkLabel(
            title_box,
            text="Loading orders…",
            font=ctk.CTkFont(size=11),
            text_color=Theme.MUTED_TEXT,
        )

        self._stats_label.pack(
            anchor="w",
        )

        self._refresh_btn = ctk.CTkButton(
            header,
            text="🔄",
            width=36,
            height=32,
            command=self._load_orders,
            fg_color="#2196F3",
            hover_color="#1976D2",
            font=ctk.CTkFont(size=14),
        )

        self._refresh_btn.grid(
            row=0,
            column=1,
            sticky="e",
        )

        # Search
        tools = ctk.CTkFrame(
            self._list_panel,
            fg_color="transparent",
        )

        tools.grid(
            row=1,
            column=0,
            padx=15,
            pady=(4, 6),
            sticky="ew",
        )

        tools.grid_columnconfigure(
            0,
            weight=1,
        )

        self._search_entry = ctk.CTkEntry(
            tools,
            placeholder_text="🔍 Search orders...",
            height=32,
        )

        self._search_entry.grid(
            row=0,
            column=0,
            sticky="ew",
        )

        self._search_entry.bind(
            "<KeyRelease>",
            self._on_search_key,
        )

        # Filter bar
        self._filter_bar = ctk.CTkFrame(
            self._list_panel,
            fg_color="transparent",
        )

        self._filter_bar.grid(
            row=2,
            column=0,
            padx=12,
            pady=(0, 4),
            sticky="ew",
        )

        self._build_filter_chips()

        # Result hint
        self._result_hint = ctk.CTkLabel(
            self._list_panel,
            text="",
            font=ctk.CTkFont(size=10),
            text_color=Theme.MUTED_TEXT,
        )

        self._result_hint.grid(
            row=3,
            column=0,
            padx=16,
            pady=(0, 2),
            sticky="w",
        )

        # Order list
        self._order_list = ctk.CTkScrollableFrame(
            self._list_panel,
            fg_color="transparent",
            corner_radius=0,
        )

        self._order_list.grid(
            row=4,
            column=0,
            sticky="nsew",
            padx=10,
            pady=(0, 6),
        )

        self._order_list.grid_columnconfigure(
            0,
            weight=1,
        )

    # ------------------------------------------------------------------
    # FILTERS
    # ------------------------------------------------------------------

    def _build_filter_chips(self):
        for child in self._filter_bar.winfo_children():
            child.destroy()

        statuses = [
            "All"
        ] + self.STATUS_OPTIONS

        self._filter_buttons = {}

        chip_frame = ctk.CTkFrame(
            self._filter_bar,
            fg_color="transparent",
        )

        chip_frame.pack(
            fill="x",
        )

        for name in statuses:
            button_width = max(
                62,
                min(
                    118,
                    len(name) * 8 + 25,
                ),
            )

            btn = ctk.CTkButton(
                chip_frame,
                text=name,
                height=24,
                width=button_width,
                corner_radius=12,
                font=ctk.CTkFont(size=10),
                fg_color=(
                    Theme.ACCENT
                    if name == "All"
                    else Theme.PANEL_ALT
                ),
                hover_color=Theme.PANEL_ALT,
                text_color=(
                    "#1a1a1a"
                    if name == "All"
                    else Theme.TEXT
                ),
                command=lambda n=name:
                    self._set_status_filter(n),
            )

            btn.pack(
                side="left",
                padx=2,
                pady=2,
            )

            self._filter_buttons[name] = btn

        self._active_status_filter = "All"

    # ------------------------------------------------------------------
    # RIGHT PANEL
    # ------------------------------------------------------------------

    def _setup_details_panel(self):
        self._details_panel = ctk.CTkFrame(
            self,
            corner_radius=12,
            fg_color=Theme.PANEL,
        )

        self._details_panel.grid(
            row=0,
            column=1,
            sticky="nsew",
            padx=(6, 0),
            pady=(0, 2),
        )

        self._details_panel.grid_columnconfigure(
            0,
            weight=1,
        )

        self._details_panel.grid_rowconfigure(
            0,
            weight=1,
        )

        # Empty state
        self._empty_state = ctk.CTkFrame(
            self._details_panel,
            fg_color="transparent",
        )

        self._empty_state.grid(
            row=0,
            column=0,
            sticky="nsew",
        )

        self._empty_state.grid_columnconfigure(
            0,
            weight=1,
        )

        self._empty_state.grid_rowconfigure(
            0,
            weight=1,
        )

        inner = ctk.CTkFrame(
            self._empty_state,
            fg_color="transparent",
        )

        inner.grid(
            row=0,
            column=0,
        )

        ctk.CTkLabel(
            inner,
            text="👈 Select an order",
            font=ctk.CTkFont(
                size=18,
                weight="bold",
            ),
            text_color=Theme.TEXT,
        ).pack(
            pady=(0, 8),
        )

        ctk.CTkLabel(
            inner,
            text=(
                "Choose an order from the list "
                "to view details and manage it."
            ),
            font=ctk.CTkFont(size=13),
            text_color=Theme.MUTED_TEXT,
        ).pack()

        # Details frame
        self._details_frame = ctk.CTkScrollableFrame(
            self._details_panel,
            fg_color="transparent",
        )

        self._details_frame.grid(
            row=0,
            column=0,
            sticky="nsew",
            padx=16,
            pady=12,
        )

        self._details_frame.grid_columnconfigure(
            0,
            weight=1,
        )

        self._details_frame.grid_columnconfigure(
            1,
            weight=0,
        )

        self._details_frame.grid_remove()

    # ==================================================================
    # EMPLOYEES
    # ==================================================================

    def _load_employees(self):
        """Load active employees through the authenticated backend API only."""
        try:
            response = self._backend_api.request("GET", "/api/employees")
            employees = response.get("employees", []) if response else []
            self._employee_names = []
            self._employee_cache = {}
            for employee in employees:
                name = str(employee.get("full_name") or employee.get("username") or employee.get("email") or "").strip()
                if not name:
                    continue
                self._employee_names.append(name)
                self._employee_cache[name] = dict(employee)
            self._employee_names = sorted(set(self._employee_names))
            print("✅ Order assignment employees loaded:", len(self._employee_names))
        except Exception as exc:
            print(f"⚠️ Could not load order employees from backend: {exc}")
            self._employee_names = []
            self._employee_cache = {}

    # ==================================================================
    # ORDERS
    # ==================================================================

    def _get_orders_from_api(self):
        """Get orders from the backend API (same path as quotes)."""
        if not self._backend_api:
            return None
        try:
            response = self._backend_api.request("GET", "/api/orders")
            if response and response.get("success"):
                return response.get("orders", [])
            if isinstance(response, dict) and "orders" in response:
                return response.get("orders") or []
        except Exception as e:
            print(f"⚠️ Could not fetch orders from API: {e}")
        return None

    def _normalize_orders(self, raw_orders):
        normalized_orders = []
        for order in raw_orders or []:
            if not isinstance(order, dict):
                continue
            if "_id" in order:
                order["_id"] = str(order["_id"])
            mongo_status = str(
                order.get("status", "pending")
            ).strip().lower()
            order["status"] = self._map_mongo_to_display(mongo_status)
            if not isinstance(order.get("items"), list):
                order["items"] = []
            normalized_orders.append(order)
        return normalized_orders

    def _load_orders(self):
        """Load orders via Backend API first (like quotes), MongoDB only as fallback."""

        if self._is_destroyed:
            return

        try:
            self._refresh_btn.configure(
                state="disabled",
                text="⏳",
            )

            self._status_bar.configure(
                text="Loading orders...",
            )

            self.update_idletasks()

            # ---- Primary: Backend API (same as Quote Management) ----
            api_orders = self._get_orders_from_api()
            if api_orders is not None:
                self._orders = self._normalize_orders(api_orders)
                print(
                    f"✅ Order Management loaded "
                    f"{len(self._orders)} order(s) from API"
                )
                for order in self._orders[:5]:
                    print(
                        "   📦",
                        order.get("reference"),
                        "|",
                        order.get("customerName"),
                        "|",
                        order.get("status"),
                    )
                self._filter_orders()
                self._update_stats()
                if self._orders:
                    self._select_order(self._orders[0])
                else:
                    self._selected_order = None
                    self._show_empty_details()
                    self._status_bar.configure(text="No orders found.")
                return

            # ---- Fallback: direct MongoDB (legacy / offline) ----
            if (
                not self._mongodb
                or not self._mongodb.is_connected
            ):
                self._show_list_message(
                    "⚠️ Could not load orders from API",
                    "Check API_BASE_URL / backend is running. MongoDB is not connected either.",
                )
                return

            self._orders = self._normalize_orders(
                self._mongodb.get_orders(limit=500)
            )

            print(
                f"✅ Order Management loaded "
                f"{len(self._orders)} order(s) from MongoDB"
            )

            for order in self._orders[:5]:
                print(
                    "   📦",
                    order.get("reference"),
                    "|",
                    order.get("customerName"),
                    "|",
                    order.get("status"),
                )

            self._filter_orders()
            self._update_stats()

            if self._orders:
                self._select_order(
                    self._orders[0]
                )
            else:
                self._selected_order = None
                self._show_empty_details()

                self._status_bar.configure(
                    text="No orders found.",
                )

        except Exception as exc:
            print(
                f"❌ Error loading orders: {exc}"
            )

            import traceback

            traceback.print_exc()

            self._show_list_message(
                f"❌ Error: {exc}",
                "Press Refresh to try again.",
            )

            self._status_bar.configure(
                text="Failed to load orders.",
            )

        finally:
            try:
                self._refresh_btn.configure(
                    state="normal",
                    text="🔄",
                )
            except Exception:
                pass

    # ==================================================================
    # SEARCH / FILTER
    # ==================================================================

    def _on_search_key(self, event=None):
        if self._search_job:
            try:
                self.after_cancel(
                    self._search_job
                )
            except Exception:
                pass

        self._search_job = self.after(
            180,
            self._filter_orders,
        )

    def _set_status_filter(
        self,
        name: str,
    ):
        self._active_status_filter = name

        for btn_name, btn in self._filter_buttons.items():
            if btn_name == name:
                btn.configure(
                    fg_color=Theme.ACCENT,
                    text_color="#1a1a1a",
                )
            else:
                btn.configure(
                    fg_color=Theme.PANEL_ALT,
                    text_color=Theme.TEXT,
                )

        self._filter_orders()

    def _filter_orders(self):
        if self._is_destroyed:
            return

        if self._search_job:
            try:
                self.after_cancel(
                    self._search_job
                )
            except Exception:
                pass

            self._search_job = None

        search_text = ""

        try:
            search_text = (
                self._search_entry.get()
                .strip()
                .lower()
            )
        except Exception:
            pass

        orders = list(
            self._orders
        )

        # Status
        if self._active_status_filter != "All":
            orders = [
                order
                for order in orders
                if order.get("status")
                == self._active_status_filter
            ]

        # Search
        if search_text:
            filtered = []

            for order in orders:
                searchable = " ".join(
                    [
                        str(
                            order.get(
                                "reference",
                                "",
                            )
                        ),
                        str(
                            order.get(
                                "customerName",
                                "",
                            )
                        ),
                        str(
                            order.get(
                                "company",
                                "",
                            )
                        ),
                        str(
                            order.get(
                                "email",
                                "",
                            )
                        ),
                        str(
                            order.get(
                                "phone",
                                "",
                            )
                        ),
                    ]
                ).lower()

                if search_text in searchable:
                    filtered.append(order)

            orders = filtered

        # Staff assignment
        if self._is_staff and self._current_username:
            username = self._current_username.lower()

            orders = [
                order
                for order in orders
                if self._is_assigned_to_user(
                    order,
                    username,
                )
                or not (
                    order.get("assignedTo")
                    or order.get("assigned_to")
                )
            ]

        self._render_order_list(
            orders
        )

        self._result_hint.configure(
            text=(
                f"Showing {len(orders)} "
                f"of {len(self._orders)} orders"
            )
        )

    def _is_assigned_to_user(
        self,
        order: Dict[str, Any],
        username: str,
    ) -> bool:
        assigned = (
            order.get("assignedTo")
            or order.get("assigned_to")
        )

        if not assigned:
            return False

        username = str(
            username
        ).lower()

        if isinstance(assigned, dict):
            possible_values = [
                assigned.get("username"),
                assigned.get("name"),
                assigned.get("display_name"),
                assigned.get("email"),
            ]

            return any(
                str(value or "").lower()
                == username
                for value in possible_values
            )

        return (
            str(assigned).lower()
            == username
        )

    # ==================================================================
    # LIST
    # ==================================================================

    def _clear_order_list(self):
        for widget in self._order_list.winfo_children():
            widget.destroy()

        self._order_cards = {}

    def _show_list_message(
        self,
        title: str,
        subtitle: str = "",
    ):
        self._clear_order_list()

        ctk.CTkLabel(
            self._order_list,
            text=title,
            font=ctk.CTkFont(
                size=15,
                weight="bold",
            ),
            text_color=Theme.TEXT,
        ).pack(
            pady=(30, 6),
        )

        if subtitle:
            ctk.CTkLabel(
                self._order_list,
                text=subtitle,
                font=ctk.CTkFont(size=12),
                text_color=Theme.MUTED_TEXT,
            ).pack()

    def _render_order_list(
        self,
        orders: List[Dict[str, Any]],
    ):
        self._clear_order_list()

        if not orders:
            ctk.CTkLabel(
                self._order_list,
                text="No orders found",
                font=ctk.CTkFont(size=13),
                text_color=Theme.MUTED_TEXT,
            ).pack(
                pady=30,
            )

            return

        for order in orders:
            self._create_order_item(
                order
            )

    def _create_order_item(
        self,
        order: Dict[str, Any],
    ):
        frame = ctk.CTkFrame(
            self._order_list,
            corner_radius=8,
            fg_color=(
                "gray95",
                "gray12",
            ),
        )

        frame.pack(
            fill="x",
            pady=3,
            padx=2,
        )

        status = order.get(
            "status",
            "Pending",
        )

        status_color = self.STATUS_COLORS.get(
            status,
            "#9E9E9E",
        )

        status_icon = self.STATUS_ICONS.get(
            status,
            "📋",
        )

        # Status / reference
        top_row = ctk.CTkFrame(
            frame,
            fg_color="transparent",
        )

        top_row.pack(
            fill="x",
            padx=12,
            pady=(6, 0),
        )

        ctk.CTkLabel(
            top_row,
            text=f"{status_icon} {status}",
            font=ctk.CTkFont(
                size=11,
                weight="bold",
            ),
            text_color=status_color,
        ).pack(
            side="left",
        )

        ctk.CTkLabel(
            top_row,
            text=order.get(
                "reference",
                "No ref",
            ),
            font=ctk.CTkFont(
                size=12,
                weight="bold",
            ),
            text_color=Theme.TEXT,
        ).pack(
            side="right",
        )

        # Customer
        ctk.CTkLabel(
            frame,
            text=(
                f"👤 "
                f"{order.get('customerName', 'Unknown customer')}"
            ),
            font=ctk.CTkFont(size=12),
            anchor="w",
            text_color=Theme.TEXT,
        ).pack(
            fill="x",
            padx=12,
            pady=(2, 0),
        )

        company = str(
            order.get(
                "company",
                "",
            )
            or ""
        ).strip()

        if company:
            ctk.CTkLabel(
                frame,
                text=f"🏢 {company}",
                font=ctk.CTkFont(size=10),
                text_color=Theme.MUTED_TEXT,
                anchor="w",
            ).pack(
                fill="x",
                padx=12,
            )

        items = order.get(
            "items",
            [],
        )

        date_str = self._format_date(
            order.get("createdAt")
        )

        total = self._format_currency(
            order.get("total", 0)
        )

        ctk.CTkLabel(
            frame,
            text=(
                f"📦 {len(items)} items"
                f"  •  "
                f"📅 {date_str or 'N/A'}"
            ),
            font=ctk.CTkFont(size=10),
            text_color=Theme.MUTED_TEXT,
            anchor="w",
        ).pack(
            fill="x",
            padx=12,
            pady=(1, 0),
        )

        ctk.CTkLabel(
            frame,
            text=total,
            font=ctk.CTkFont(
                size=12,
                weight="bold",
            ),
            text_color=Theme.ACCENT,
            anchor="w",
        ).pack(
            fill="x",
            padx=12,
            pady=(2, 6),
        )

        # Click
        def select(
            _event=None,
            current_order=order,
        ):
            self._select_order(
                current_order
            )

        frame.bind(
            "<Button-1>",
            select,
        )

        for child in frame.winfo_children():
            try:
                child.bind(
                    "<Button-1>",
                    select,
                )

                child.configure(
                    cursor="hand2",
                )

            except Exception:
                pass

        frame.configure(
            cursor="hand2"
        )

        self._order_cards[
            order.get(
                "reference",
                "",
            )
        ] = frame

    # ==================================================================
    # DETAILS
    # ==================================================================

    def _select_order(
        self,
        order: Dict[str, Any],
    ):
        if self._is_destroyed:
            return

        self._selected_order = order

        self._selected_order_id = order.get(
            "reference"
        )

        self._show_order_details(
            order
        )

    def _show_empty_details(self):
        try:
            self._details_frame.grid_remove()
            self._empty_state.grid()
        except Exception:
            pass

    def _show_order_details(
        self,
        order: Dict[str, Any],
    ):
        if self._is_destroyed:
            return

        self._empty_state.grid_remove()
        self._details_frame.grid()

        for widget in self._details_frame.winfo_children():
            widget.destroy()

        row = 0

        status = order.get(
            "status",
            "Pending",
        )

        status_color = self.STATUS_COLORS.get(
            status,
            "#9E9E9E",
        )

        status_icon = self.STATUS_ICONS.get(
            status,
            "📋",
        )

        # --------------------------------------------------------------
        # HEADER
        # --------------------------------------------------------------

        header = ctk.CTkFrame(
            self._details_frame,
            fg_color="transparent",
        )

        header.grid(
            row=row,
            column=0,
            sticky="ew",
            pady=(0, 8),
        )

        header.grid_columnconfigure(
            0,
            weight=1,
        )

        row += 1

        title_box = ctk.CTkFrame(
            header,
            fg_color="transparent",
        )

        title_box.grid(
            row=0,
            column=0,
            sticky="w",
        )

        ctk.CTkLabel(
            title_box,
            text=order.get(
                "reference",
                "No reference",
            ),
            font=ctk.CTkFont(
                size=18,
                weight="bold",
            ),
            text_color=Theme.TEXT,
        ).pack(
            anchor="w",
        )

        ctk.CTkLabel(
            title_box,
            text=(
                f"👤 "
                f"{order.get('customerName', 'Unknown customer')}"
            ),
            font=ctk.CTkFont(size=13),
            text_color=Theme.MUTED_TEXT,
        ).pack(
            anchor="w",
        )

        # Status badge
        status_badge = ctk.CTkFrame(
            header,
            fg_color=status_color,
            corner_radius=12,
            height=28,
        )

        status_badge.grid(
            row=0,
            column=1,
            sticky="e",
            padx=(10, 0),
        )

        status_badge.grid_propagate(
            False
        )

        ctk.CTkLabel(
            status_badge,
            text=(
                f"  {status_icon} "
                f"{status}  "
            ),
            font=ctk.CTkFont(
                size=12,
                weight="bold",
            ),
            text_color="#1a1a1a",
        ).pack(
            pady=4,
        )

        # --------------------------------------------------------------
        # STATUS
        # --------------------------------------------------------------

        row = self._add_section_title(
            "Update Status",
            row,
        )

        status_frame = ctk.CTkFrame(
            self._details_frame,
            fg_color="transparent",
        )

        status_frame.grid(
            row=row,
            column=0,
            sticky="ew",
            pady=(0, 8),
        )

        row += 1

        status_var = ctk.StringVar(
            value=status
        )

        self._status_dropdown = ctk.CTkOptionMenu(
            status_frame,
            values=self.STATUS_OPTIONS,
            variable=status_var,
            width=200,
            height=30,
            fg_color=status_color,
            button_color=status_color,
            button_hover_color=self._darken_color(
                status_color
            ),
            text_color="#1a1a1a",
            font=ctk.CTkFont(size=12),
        )

        self._status_dropdown.grid(
            row=0,
            column=0,
            sticky="w",
        )

        ctk.CTkButton(
            status_frame,
            text="Update Status",
            width=120,
            height=30,
            fg_color=Theme.ACCENT,
            hover_color=Theme.ACCENT_HOVER,
            font=ctk.CTkFont(
                size=11,
                weight="bold",
            ),
            command=lambda:
                self._update_status_from_dropdown(
                    order,
                    status_var.get(),
                ),
        ).grid(
            row=0,
            column=1,
            padx=(10, 0),
            sticky="w",
        )

        row = self._add_divider(
            row
        )

        # --------------------------------------------------------------
        # CUSTOMER
        # --------------------------------------------------------------

        row = self._add_section_title(
            "Customer Information",
            row,
        )

        row = self._add_detail(
            "Customer",
            order.get(
                "customerName"
            ),
            row,
        )

        row = self._add_detail(
            "Company",
            order.get(
                "company"
            ),
            row,
        )

        row = self._add_detail(
            "Email",
            order.get(
                "email"
            ),
            row,
        )

        row = self._add_detail(
            "Phone",
            order.get(
                "phone"
            ),
            row,
        )

        row = self._add_detail(
            "Address",
            order.get(
                "address"
            ),
            row,
        )

        row = self._add_divider(
            row
        )

        # --------------------------------------------------------------
        # ORDER INFORMATION
        # --------------------------------------------------------------

        row = self._add_section_title(
            "Order Information",
            row,
        )

        row = self._add_detail(
            "Created",
            self._format_date(
                order.get(
                    "createdAt"
                )
            ),
            row,
        )

        row = self._add_detail(
            "Updated",
            self._format_date(
                order.get(
                    "updatedAt"
                )
            ),
            row,
        )

        # --------------------------------------------------------------
        # ITEMS
        # --------------------------------------------------------------

        row = self._add_divider(
            row
        )

        row = self._add_section_title(
            "Order Items",
            row,
        )

        items = order.get(
            "items",
            [],
        )

        if not isinstance(
            items,
            list,
        ):
            items = []

        if items:
            for index, item in enumerate(
                items,
                start=1,
            ):
                row = self._add_item_card(
                    index,
                    item,
                    row,
                )
        else:
            ctk.CTkLabel(
                self._details_frame,
                text="No items recorded.",
                font=ctk.CTkFont(size=12),
                text_color=Theme.MUTED_TEXT,
                anchor="w",
            ).grid(
                row=row,
                column=0,
                sticky="ew",
                pady=(0, 8),
            )

            row += 1

        # --------------------------------------------------------------
        # TOTAL
        # --------------------------------------------------------------

        total_frame = ctk.CTkFrame(
            self._details_frame,
            fg_color=Theme.PANEL_ALT,
            corner_radius=8,
        )

        total_frame.grid(
            row=row,
            column=0,
            sticky="ew",
            pady=(10, 10),
        )

        total_frame.grid_columnconfigure(
            0,
            weight=1,
        )

        ctk.CTkLabel(
            total_frame,
            text="Order Total",
            font=ctk.CTkFont(
                size=14,
                weight="bold",
            ),
            text_color=Theme.TEXT,
        ).grid(
            row=0,
            column=0,
            sticky="w",
            padx=14,
            pady=12,
        )

        ctk.CTkLabel(
            total_frame,
            text=self._format_currency(
                order.get(
                    "total",
                    0,
                )
            ),
            font=ctk.CTkFont(
                size=18,
                weight="bold",
            ),
            text_color=Theme.ACCENT,
        ).grid(
            row=0,
            column=1,
            sticky="e",
            padx=14,
            pady=12,
        )

        row += 1

        # --------------------------------------------------------------
        # NOTES
        # --------------------------------------------------------------

        row = self._add_divider(
            row
        )

        row = self._add_section_title(
            "Notes",
            row,
        )

        notes = str(
            order.get(
                "notes",
                "",
            )
            or ""
        ).strip()

        ctk.CTkLabel(
            self._details_frame,
            text=(
                notes
                if notes
                else "No notes."
            ),
            font=ctk.CTkFont(size=12),
            text_color=Theme.MUTED_TEXT,
            justify="left",
            anchor="w",
            wraplength=650,
        ).grid(
            row=row,
            column=0,
            sticky="ew",
            pady=(0, 12),
        )

        row += 1

        # --------------------------------------------------------------
        # ASSIGN
        # --------------------------------------------------------------

        row = self._add_divider(
            row
        )

        row = self._add_section_title(
            "Assign Order",
            row,
        )

        assign_frame = ctk.CTkFrame(
            self._details_frame,
            fg_color="transparent",
        )

        assign_frame.grid(
            row=row,
            column=0,
            sticky="ew",
            pady=(0, 10),
        )

        assign_frame.grid_columnconfigure(
            1,
            weight=1,
        )

        row += 1

        assigned = (
            order.get("assignedTo")
            or order.get("assigned_to")
        )

        current_name = self._get_assignment_name(
            assigned
        )

        ctk.CTkLabel(
            assign_frame,
            text=f"Currently: {current_name}",
            font=ctk.CTkFont(size=12),
            text_color=Theme.TEXT,
            anchor="w",
        ).grid(
            row=0,
            column=0,
            padx=(0, 10),
            sticky="w",
        )

        employee_options = [
            "Nobody (unassign)"
        ] + self._employee_names

        if not employee_options:
            employee_options = [
                "Nobody (unassign)"
            ]

        self._assign_menu = ctk.CTkOptionMenu(
            assign_frame,
            values=employee_options,
            width=210,
            height=30,
            fg_color=Theme.PANEL_ALT,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER,
            font=ctk.CTkFont(size=12),
        )

        self._assign_menu.grid(
            row=0,
            column=1,
            sticky="ew",
        )

        if (
            current_name != "Nobody"
            and current_name in employee_options
        ):
            self._assign_menu.set(
                current_name
            )
        else:
            self._assign_menu.set(
                "Nobody (unassign)"
            )

        ctk.CTkButton(
            assign_frame,
            text="Assign",
            width=80,
            height=30,
            fg_color="#2196F3",
            hover_color="#1976D2",
            font=ctk.CTkFont(
                size=11,
                weight="bold",
            ),
            command=self._assign_order,
        ).grid(
            row=0,
            column=2,
            padx=(10, 0),
            sticky="e",
        )

        # --------------------------------------------------------------
        # ACTIONS
        # --------------------------------------------------------------

        row = self._add_divider(
            row
        )

        row = self._add_section_title(
            "Quick Actions",
            row,
        )

        action_frame = ctk.CTkFrame(
            self._details_frame,
            fg_color="transparent",
        )

        action_frame.grid(
            row=row,
            column=0,
            sticky="ew",
            pady=(0, 20),
        )

        ctk.CTkButton(
            action_frame,
            text="🏁 Mark Completed",
            height=34,
            width=150,
            fg_color=Theme.SUCCESS,
            hover_color="#2E7D32",
            font=ctk.CTkFont(
                size=11,
                weight="bold",
            ),
            command=lambda:
                self._quick_status(
                    order,
                    "Completed",
                ),
        ).pack(
            side="left",
            padx=(0, 8),
        )

        ctk.CTkButton(
            action_frame,
            text="❌ Cancel Order",
            height=34,
            width=130,
            fg_color=Theme.DANGER,
            hover_color=Theme.DANGER_HOVER,
            font=ctk.CTkFont(
                size=11,
                weight="bold",
            ),
            command=lambda:
                self._quick_status(
                    order,
                    "Cancelled",
                ),
        ).pack(
            side="left",
        )

    # ==================================================================
    # DETAILS HELPERS
    # ==================================================================

    def _add_section_title(
        self,
        title: str,
        row: int,
    ) -> int:
        ctk.CTkLabel(
            self._details_frame,
            text=title,
            font=ctk.CTkFont(
                size=14,
                weight="bold",
            ),
            text_color=Theme.TEXT,
            anchor="w",
        ).grid(
            row=row,
            column=0,
            sticky="ew",
            pady=(6, 6),
        )

        return row + 1

    def _add_divider(
        self,
        row: int,
    ) -> int:
        divider = ctk.CTkFrame(
            self._details_frame,
            height=1,
            fg_color=Theme.BORDER,
        )

        divider.grid(
            row=row,
            column=0,
            sticky="ew",
            pady=8,
        )

        return row + 1

    def _add_detail(
        self,
        label: str,
        value: Any,
        row: int,
    ) -> int:
        value_text = (
            "-"
            if value is None
            or str(value).strip() == ""
            else str(value)
        )

        frame = ctk.CTkFrame(
            self._details_frame,
            fg_color="transparent",
        )

        frame.grid(
            row=row,
            column=0,
            sticky="ew",
            pady=2,
        )

        frame.grid_columnconfigure(
            1,
            weight=1,
        )

        ctk.CTkLabel(
            frame,
            text=f"{label}:",
            font=ctk.CTkFont(
                size=11,
                weight="bold",
            ),
            text_color=Theme.MUTED_TEXT,
            anchor="w",
        ).grid(
            row=0,
            column=0,
            sticky="nw",
            padx=(0, 12),
        )

        ctk.CTkLabel(
            frame,
            text=value_text,
            font=ctk.CTkFont(size=11),
            text_color=Theme.TEXT,
            anchor="w",
            justify="left",
            wraplength=650,
        ).grid(
            row=0,
            column=1,
            sticky="ew",
        )

        return row + 1

    def _add_item_card(
        self,
        index: int,
        item: Any,
        row: int,
    ) -> int:
        frame = ctk.CTkFrame(
            self._details_frame,
            fg_color=Theme.PANEL_ALT,
            corner_radius=8,
        )

        frame.grid(
            row=row,
            column=0,
            sticky="ew",
            pady=4,
        )

        frame.grid_columnconfigure(
            0,
            weight=1,
        )

        ctk.CTkLabel(
            frame,
            text=f"Item {index}",
            font=ctk.CTkFont(
                size=12,
                weight="bold",
            ),
            text_color=Theme.TEXT,
            anchor="w",
        ).grid(
            row=0,
            column=0,
            sticky="ew",
            padx=12,
            pady=(8, 5),
        )

        if isinstance(item, dict):
            item_row = 1

            for key, value in item.items():
                display_key = (
                    str(key)
                    .replace(
                        "_",
                        " ",
                    )
                    .title()
                )

                if isinstance(
                    value,
                    dict,
                ):
                    value_text = ", ".join(
                        f"{k}: {v}"
                        for k, v in value.items()
                    )
                elif isinstance(
                    value,
                    list,
                ):
                    value_text = ", ".join(
                        str(v)
                        for v in value
                    )
                else:
                    value_text = str(
                        value
                    )

                ctk.CTkLabel(
                    frame,
                    text=f"{display_key}:",
                    font=ctk.CTkFont(
                        size=10,
                        weight="bold",
                    ),
                    text_color=Theme.MUTED_TEXT,
                    anchor="w",
                ).grid(
                    row=item_row,
                    column=0,
                    sticky="ew",
                    padx=12,
                    pady=1,
                )

                ctk.CTkLabel(
                    frame,
                    text=value_text,
                    font=ctk.CTkFont(size=10),
                    text_color=Theme.TEXT,
                    anchor="w",
                    justify="left",
                    wraplength=650,
                ).grid(
                    row=item_row + 1,
                    column=0,
                    sticky="ew",
                    padx=12,
                    pady=(0, 3),
                )

                item_row += 2

            bottom_pad = item_row

        else:
            ctk.CTkLabel(
                frame,
                text=str(item),
                font=ctk.CTkFont(size=11),
                text_color=Theme.TEXT,
                anchor="w",
                wraplength=650,
            ).grid(
                row=1,
                column=0,
                sticky="ew",
                padx=12,
                pady=(0, 10),
            )

            bottom_pad = 2

        return row + 1

    # ==================================================================
    # STATUS ACTIONS
    # ==================================================================

    def _quick_status(
        self,
        order: Dict[str, Any],
        display_status: str,
    ):
        self._update_order_status(
            order,
            display_status,
        )

    def _update_status_from_dropdown(
        self,
        order: Dict[str, Any],
        display_status: str,
    ):
        self._update_order_status(
            order,
            display_status,
        )

    def _update_order_status(
        self,
        order: Dict[str, Any],
        display_status: str,
    ):
        reference = order.get(
            "reference"
        )

        if not reference:
            return

        mongo_status = self.DISPLAY_TO_MONGO.get(
            display_status,
            display_status.lower().replace(
                " ",
                "_",
            ),
        )

        try:
            # Prefer Backend API (desktop should not require direct Mongo)
            api_ok = False
            if self._backend_api:
                try:
                    response = self._backend_api.request(
                        "PATCH",
                        "/api/orders/status",
                        {
                            "reference": reference,
                            "status": mongo_status,
                        },
                    )
                    api_ok = bool(response and response.get("success", True))
                except Exception as api_exc:
                    print(f"⚠️ Order status API update failed: {api_exc}")

            if not api_ok:
                if not self._mongodb or not self._mongodb.is_connected:
                    self._status_bar.configure(
                        text=f"❌ Failed to update {reference} (API + Mongo unavailable)"
                    )
                    return
                success = self._mongodb.update_order_status(
                    reference,
                    mongo_status,
                )
                if not success:
                    print(f"❌ Failed to update order {reference}")
                    self._status_bar.configure(
                        text=f"❌ Failed to update {reference}"
                    )
                    return

            print(
                f"✅ Order {reference} "
                f"updated to {mongo_status}"
            )

            self._status_bar.configure(
                text=(
                    f"✅ {reference} "
                    f"updated to {display_status}"
                )
            )

            self._load_orders()

        except Exception as exc:
            print(
                f"❌ Order status update error: {exc}"
            )

            self._status_bar.configure(
                text=f"❌ {exc}",
            )

    # ==================================================================
    # ASSIGNMENT
    # ==================================================================

    def _get_assignment_name(
        self,
        assigned: Any,
    ) -> str:
        if not assigned:
            return "Nobody"

        if isinstance(
            assigned,
            dict,
        ):
            return str(
                assigned.get(
                    "display_name"
                )
                or assigned.get(
                    "name"
                )
                or assigned.get(
                    "username"
                )
                or assigned.get(
                    "email"
                )
                or "Nobody"
            )

        return str(
            assigned
        )

    def _assign_order(self):
        """Assign the current order through the authenticated backend API."""
        if not self._selected_order or not self._assign_menu:
            return
        selected = self._assign_menu.get()
        reference = str(self._selected_order.get("reference") or "").strip()
        if not reference:
            return
        employee = None if selected == "Nobody (unassign)" else self._employee_cache.get(selected)
        if selected != "Nobody (unassign)" and not employee:
            self._status_bar.configure(text=f"❌ Employee not found: {selected}")
            return
        try:
            # Prefer stable employee_id; also send _id / id so backend can resolve ObjectIds
            emp_payload = None
            if employee:
                emp_payload = (
                    employee.get("employee_id")
                    or employee.get("id")
                    or employee.get("_id")
                )
            response = self._backend_api.request(
                "PUT",
                f"/api/admin/orders/{reference}/assignment",
                {
                    "employee_id": emp_payload,
                    "employeeId": emp_payload,
                    "assigned_to": emp_payload,
                },
            )
            if not response.get("success"):
                raise RuntimeError(response.get("error") or "Assignment failed")
            order_data = response.get("order") or {}
            self._selected_order["assigned_to"] = order_data.get("assigned_to")
            if order_data.get("status"):
                self._selected_order["status"] = self._map_mongo_to_display(str(order_data["status"]))
            self._status_bar.configure(text=f"✅ {reference} assignment updated")
            self._load_orders()
        except Exception as exc:
            print(f"❌ Order assignment error: {exc}")
            self._status_bar.configure(text=f"❌ Assignment failed: {exc}")

    def _map_mongo_to_display(
        self,
        status: str,
    ) -> str:
        status = str(
            status or "pending"
        ).strip().lower()

        return self.MONGO_TO_DISPLAY.get(
            status,
            status.replace(
                "_",
                " ",
            ).title(),
        )

    # ==================================================================
    # STATS
    # ==================================================================

    def _update_stats(self):
        total = len(
            self._orders
        )

        pending = sum(
            1
            for order in self._orders
            if order.get("status")
            == "Pending"
        )

        processing = sum(
            1
            for order in self._orders
            if order.get("status")
            in {
                "Processing",
                "Assigned",
                "In Progress",
            }
        )

        completed = sum(
            1
            for order in self._orders
            if order.get("status")
            == "Completed"
        )

        self._stats_label.configure(
            text=(
                f"{total} orders"
                f"  •  "
                f"{pending} pending"
                f"  •  "
                f"{processing} active"
                f"  •  "
                f"{completed} completed"
            )
        )

    # ==================================================================
    # HELPERS
    # ==================================================================

    @staticmethod
    def _format_currency(
        value: Any,
    ) -> str:
        try:
            amount = float(
                value or 0
            )

            return f"R {amount:,.2f}"

        except (
            TypeError,
            ValueError,
        ):
            return "R 0.00"

    @staticmethod
    def _format_date(
        value: Any,
    ) -> str:
        if not value:
            return ""

        try:
            if isinstance(
                value,
                datetime,
            ):
                return value.strftime(
                    "%d %b %Y, %H:%M"
                )

            return str(value)

        except Exception:
            return str(value)

    @staticmethod
    def _darken_color(
        color: str,
    ) -> str:
        """
        Small helper for status button hover colours.

        If the supplied colour cannot be parsed,
        return the original colour.
        """

        try:
            color = color.lstrip("#")

            if len(color) != 6:
                return f"#{color}"

            r = int(
                color[0:2],
                16,
            )

            g = int(
                color[2:4],
                16,
            )

            b = int(
                color[4:6],
                16,
            )

            r = max(
                0,
                int(r * 0.75),
            )

            g = max(
                0,
                int(g * 0.75),
            )

            b = max(
                0,
                int(b * 0.75),
            )

            return (
                f"#{r:02X}"
                f"{g:02X}"
                f"{b:02X}"
            )

        except Exception:
            return color

    # ==================================================================
    # DESTROY
    # ==================================================================

    def destroy(self):
        self._is_destroyed = True

        if self._search_job:
            try:
                self.after_cancel(
                    self._search_job
                )
            except Exception:
                pass

            self._search_job = None

        try:
            super().destroy()
        except Exception:
            pass
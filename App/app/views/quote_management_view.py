
# app/views/quote_management_view.py
"""Quote Management View - Complete employee workspace with all statuses."""

import customtkinter as ctk
from tkinter import messagebox, filedialog
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import base64
import os

# Production: Backend API only — no direct MongoDB from the desktop client.
from app.services.backend_api_client import BackendAPIClient
from app.utils.theme import Theme
from app.utils.async_tasks import run_in_background
from app.utils.ui_tasks import ui_task, ui_steps, RemoteCall, ui_callback


class QuoteManagementView(ctk.CTkFrame):
    """Complete employee workspace with full status workflow."""

    # Professional workflow statuses
    # Assign → Collect Details → Quote → Client Approves → Payment → Delivery → Complete
    STATUS_OPTIONS = [
        "Pending",
        "Assigned",
        "Awaiting Details",
        "Quoted",
        "Awaiting Client Approval",
        "Awaiting Payment",
        "Paid",
        "In Progress",
        "Out for Delivery",
        "Completed",
        "Returned",
        # Legacy (still supported for existing jobs)
        "In Review",
        "Accepted",
        "Awaiting Client",
    ]

    STATUS_COLORS = {
        "Pending": "#FFC107",
        "Assigned": "#2196F3",
        "Awaiting Details": "#FF9800",
        "Quoted": "#4CAF50",
        "Awaiting Client Approval": "#9C27B0",
        "Awaiting Payment": "#E91E63",
        "Paid": "#00BCD4",
        "In Progress": "#FF9800",
        "Out for Delivery": "#3F51B5",
        "Completed": "#9E9E9E",
        "Returned": "#F44336",
        "In Review": "#FF9800",
        "Accepted": "#4CAF50",
        "Awaiting Client": "#9C27B0",
    }

    STATUS_ICONS = {
        "Pending": "⏳",
        "Assigned": "📋",
        "Awaiting Details": "📝",
        "Quoted": "💰",
        "Awaiting Client Approval": "🤝",
        "Awaiting Payment": "💳",
        "Paid": "✅",
        "In Progress": "🔧",
        "Out for Delivery": "🚚",
        "Completed": "🏁",
        "Returned": "↩️",
        "In Review": "📝",
        "Accepted": "✅",
        "Awaiting Client": "⏳",
    }

    STATUS_HELP = {
        "Pending": "Client submitted a request. Review and assign if needed.",
        "Assigned": "Job assigned. Contact the client and collect any missing details.",
        "Awaiting Details": "Missing address, measurements, or other info. Collect from client.",
        "Quoted": "Quotation prepared with pricing. Send to the client.",
        "Awaiting Client Approval": "Client is reviewing the quote. Wait for accept/reject.",
        "Awaiting Payment": "Client accepted the quote. Waiting for payment.",
        "Paid": "Payment received. Schedule work or delivery.",
        "In Progress": "Manufacturing or service is underway. Update progress.",
        "Out for Delivery": "Item is being delivered. Track until delivered.",
        "Completed": "Delivered successfully. Job closed.",
        "Returned": "Returned to manager for reassignment.",
        "In Review": "Legacy: pricing and details being worked out.",
        "Accepted": "Legacy: job accepted by employee.",
        "Awaiting Client": "Legacy: waiting for client response.",
    }

    # Next-step guidance for the primary action button
    WORKFLOW_NEXT = {
        "Pending": {"label": "📋 Assign / Start", "action": "assign_start", "color": "#2196F3"},
        "Assigned": {"label": "📝 Request Details", "action": "request_details", "color": "#FF9800"},
        "Awaiting Details": {"label": "💰 Generate Quote", "action": "generate_quote", "color": "#4CAF50"},
        "Quoted": {"label": "📤 Send for Approval", "action": "send_approval", "color": "#9C27B0"},
        "Awaiting Client Approval": {"label": "💳 Mark Awaiting Payment", "action": "await_payment", "color": "#E91E63"},
        "Awaiting Payment": {"label": "✅ Mark Paid", "action": "mark_paid", "color": "#00BCD4"},
        "Paid": {"label": "🔧 Start Work", "action": "start_work", "color": "#FF9800"},
        "In Progress": {"label": "🚚 Out for Delivery", "action": "out_for_delivery", "color": "#3F51B5"},
        "Out for Delivery": {"label": "🏁 Mark Completed", "action": "complete", "color": "#9E9E9E"},
        "Accepted": {"label": "🔧 Start Work", "action": "start_work", "color": "#FF9800"},
        "In Review": {"label": "💰 Generate Quote", "action": "generate_quote", "color": "#4CAF50"},
        "Awaiting Client": {"label": "💳 Mark Awaiting Payment", "action": "await_payment", "color": "#E91E63"},
    }

    MANAGER_ROLES = ["Director", "Business Lead", "Operations Manager"]
    STAFF_ROLES = ["Staff", "Intern"]

    # Map display status to MongoDB / API status
    DISPLAY_TO_MONGO = {
        "Pending": "received",
        "Assigned": "assigned",
        "Awaiting Details": "awaiting_details",
        "Quoted": "quoted",
        "Awaiting Client Approval": "awaiting_client_approval",
        "Awaiting Payment": "awaiting_payment",
        "Paid": "paid",
        "In Progress": "in_progress",
        "Out for Delivery": "out_for_delivery",
        "Completed": "completed",
        "Returned": "returned",
        "In Review": "in_review",
        "Accepted": "accepted",
        "Awaiting Client": "awaiting_client",
    }

    MONGO_TO_DISPLAY = {
        "received": "Pending",
        "pending": "Pending",
        "assigned": "Assigned",
        "awaiting_details": "Awaiting Details",
        "quoted": "Quoted",
        "awaiting_client_approval": "Awaiting Client Approval",
        "awaiting_client": "Awaiting Client Approval",  # map legacy to new name
        "awaiting_payment": "Awaiting Payment",
        "paid": "Paid",
        "in_progress": "In Progress",
        "in progress": "In Progress",
        "out_for_delivery": "Out for Delivery",
        "completed": "Completed",
        "returned": "Returned",
        "in_review": "In Review",
        "accepted": "Accepted",
        "awaiting_director": "In Review",
        "awaiting director": "In Review",
    }

    def __init__(
        self,
        master,
        people_controller=None,
        notification_controller=None,
        auth_service=None,
        navigation_controller=None,
        backend_api: Optional[BackendAPIClient] = None,
    ):
        super().__init__(master, fg_color=Theme.BG, corner_radius=0)
        self._backend_api = backend_api or BackendAPIClient()
        self._people_controller = people_controller
        self._notification_controller = notification_controller
        self._auth_service = auth_service
        self._navigation_controller = navigation_controller

        self._quotes: List[Dict[str, Any]] = []
        self._selected_quote: Optional[Dict[str, Any]] = None
        self._selected_quote_id: Optional[str] = None
        self._current_role = "Staff"
        self._current_user_name = ""
        self._current_username = ""
        self._is_staff = False
        self._is_manager = False
        self._is_destroyed = False

        self._status_dropdown = None
        self._reply_text = None
        self._assign_menu = None
        self._filter_buttons = {}
        self._quote_cards = {}
        self._search_job = None
        self._status_job = None
        self._active_status_filter = "All"
        self._loaded_reply = ""
        self._employee_names: List[str] = []
        self._employee_cache: Dict[str, Dict[str, Any]] = {}

        if not self._check_authorization():
            return

        self._setup_ui()
        # Defer network loads until the frame is mapped into the workspace.
        # Starting workers during __init__ raced with show_workspace_view and
        # the apply() callback was dropped before the list could render.
        self.after(50, self._load_quotes)
        self.after(80, self._load_employees)

    # ------------------------------------------------------------------ auth

    def _check_authorization(self) -> bool:
        """Check user role and set appropriate permissions."""
        session = getattr(self._auth_service, "current_session", None) if self._auth_service else None
        if session:
            self._current_role = getattr(session, "role", "Staff")
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
            
            if not self._current_user_name and hasattr(session, "account"):
                self._current_user_name = getattr(session.account, "full_name", "")
                self._current_username = getattr(session.account, "username", "")
            
            print(f"👤 User: {self._current_user_name} | Username: {self._current_username} | Role: {self._current_role}")
            
            if self._current_role in self.MANAGER_ROLES:
                self._is_staff = False
                self._is_manager = True
                return True
            if self._current_role in self.STAFF_ROLES:
                self._is_staff = True
                self._is_manager = False
                return True
            
            self._show_unauthorized_message()
            return False
        
        if self._navigation_controller:
            self._current_role = getattr(self._navigation_controller, '_current_role', 'Staff')
            self._current_username = getattr(self._navigation_controller, '_current_username', '')
            self._current_user_name = getattr(self._navigation_controller, '_current_full_name', '')
            
            if self._current_role in self.MANAGER_ROLES:
                self._is_staff = False
                self._is_manager = True
                return True
            if self._current_role in self.STAFF_ROLES:
                self._is_staff = True
                self._is_manager = False
                return True
        
        return True

    def _show_unauthorized_message(self):
        for widget in self.winfo_children():
            widget.destroy()
        frame = ctk.CTkFrame(self, fg_color="transparent")
        frame.pack(expand=True, fill="both")
        ctk.CTkLabel(
            frame,
            text="You don't have access to Quotes",
            font=ctk.CTkFont(size=26, weight="bold"),
            text_color=Theme.TEXT,
        ).pack(pady=(60, 8))
        ctk.CTkLabel(
            frame,
            text="Quote Management is available to all employees.\nStaff can see and work on their assigned quotes.",
            font=ctk.CTkFont(size=14),
            justify="center",
            text_color=Theme.MUTED_TEXT,
        ).pack(pady=6)

    # -------------------------------------------------------------------- ui

    def _setup_ui(self):
        # Desktop-friendly proportions - 30% list, 70% details
        self.grid_columnconfigure(0, weight=30, minsize=320)
        self.grid_columnconfigure(1, weight=70, minsize=500)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)

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
        self._status_bar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=15, pady=(2, 8))

        master = self.winfo_toplevel()
        master.bind("<F5>", lambda e: self._load_quotes())

    def _setup_list_panel(self):
        self._list_panel = ctk.CTkFrame(self, corner_radius=12, fg_color=Theme.PANEL)
        self._list_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=(0, 2))
        self._list_panel.grid_columnconfigure(0, weight=1)
        # Weight must be on the list row (4). Row 5 was empty, so the list
        # collapsed to ~0 height and cards never became visible.
        self._list_panel.grid_rowconfigure(4, weight=1)

        # Header
        header = ctk.CTkFrame(self._list_panel, fg_color="transparent")
        header.grid(row=0, column=0, padx=15, pady=(14, 6), sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            title_box,
            text="All Quotes" if self._is_manager else "My Jobs",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=Theme.TEXT,
        ).pack(anchor="w")

        self._stats_label = ctk.CTkLabel(
            title_box,
            text="Loading your jobs…",
            font=ctk.CTkFont(size=11),
            text_color=Theme.MUTED_TEXT,
        )
        self._stats_label.pack(anchor="w")

        self._refresh_btn = ctk.CTkButton(
            header,
            text="🔄",
            width=36,
            height=32,
            command=self._load_quotes,
            fg_color="#2196F3",
            hover_color="#1976D2",
            font=ctk.CTkFont(size=14),
        )
        self._refresh_btn.grid(row=0, column=1, sticky="e", padx=(0, 0))

        # Search
        tools = ctk.CTkFrame(self._list_panel, fg_color="transparent")
        tools.grid(row=1, column=0, padx=15, pady=(4, 6), sticky="ew")
        tools.grid_columnconfigure(0, weight=1)

        self._search_entry = ctk.CTkEntry(
            tools,
            placeholder_text="🔍 Search jobs...",
            height=32,
        )
        self._search_entry.grid(row=0, column=0, sticky="ew")
        self._search_entry.bind("<KeyRelease>", self._on_search_key)

        # Filter chips - scrollable horizontal
        self._filter_bar = ctk.CTkFrame(self._list_panel, fg_color="transparent")
        self._filter_bar.grid(row=2, column=0, padx=12, pady=(0, 4), sticky="ew")
        self._build_filter_chips()

        self._result_hint = ctk.CTkLabel(
            self._list_panel,
            text="",
            font=ctk.CTkFont(size=10),
            text_color=Theme.MUTED_TEXT,
        )
        self._result_hint.grid(row=3, column=0, padx=16, pady=(0, 2), sticky="w")

        # Quote list — must expand (row weight 4) or cards are clipped/invisible
        self._quote_list = ctk.CTkScrollableFrame(
            self._list_panel,
            fg_color="transparent",
            corner_radius=0,
            height=420,
        )
        self._quote_list.grid(row=4, column=0, sticky="nsew", padx=10, pady=(0, 6))
        self._quote_list.grid_columnconfigure(0, weight=1)

    def _build_filter_chips(self):
        for child in self._filter_bar.winfo_children():
            child.destroy()

        statuses = ["All"] + self.STATUS_OPTIONS
        self._filter_buttons = {}

        # Use a scrollable frame for chips
        chip_frame = ctk.CTkFrame(self._filter_bar, fg_color="transparent")
        chip_frame.pack(fill="x")

        for i, name in enumerate(statuses):
            btn = ctk.CTkButton(
                chip_frame,
                text=name,
                height=24,
                width=0,
                corner_radius=12,
                font=ctk.CTkFont(size=10),
                fg_color=Theme.PANEL_ALT if name != "All" else Theme.ACCENT,
                hover_color=Theme.PANEL_ALT,
                text_color=Theme.TEXT if name != "All" else "#1a1a1a",
                command=lambda n=name: self._set_status_filter(n),
            )
            btn.pack(side="left", padx=2, pady=2)
            self._filter_buttons[name] = btn

        self._active_status_filter = "All"

    def _setup_details_panel(self):
        self._details_panel = ctk.CTkFrame(self, corner_radius=12, fg_color=Theme.PANEL)
        self._details_panel.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=(0, 2))
        self._details_panel.grid_columnconfigure(0, weight=1)
        self._details_panel.grid_rowconfigure(0, weight=1)

        # Empty state
        self._empty_state = ctk.CTkFrame(self._details_panel, fg_color="transparent")
        self._empty_state.grid(row=0, column=0, sticky="nsew")
        self._empty_state.grid_columnconfigure(0, weight=1)
        self._empty_state.grid_rowconfigure(0, weight=1)

        inner = ctk.CTkFrame(self._empty_state, fg_color="transparent")
        inner.grid(row=0, column=0)

        ctk.CTkLabel(
            inner,
            text="👈 Select a job to work on",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=Theme.TEXT,
        ).pack(pady=(0, 8))

        ctk.CTkLabel(
            inner,
            text="Choose a job from the list to view details and update progress.",
            font=ctk.CTkFont(size=13),
            text_color=Theme.MUTED_TEXT,
        ).pack()

        # Details frame (hidden initially)
        self._details_frame = ctk.CTkScrollableFrame(self._details_panel, fg_color="transparent")
        self._details_frame.grid(row=0, column=0, sticky="nsew", padx=16, pady=12)
        self._details_frame.grid_columnconfigure(0, weight=1)
        self._details_frame.grid_columnconfigure(1, weight=0)
        self._details_frame.grid_remove()

    # ------------------------------------------------------------------ data

    def _get_quotes_from_api(self):
        """Get quotes from the backend API."""
        if not self._backend_api:
            return None

        try:
            response = self._backend_api.request("GET", "/api/quotes")
            if not response:
                return None
            if isinstance(response, list):
                return response
            if response.get("success") is False:
                return None
            return (
                response.get("quotes")
                or response.get("items")
                or response.get("data")
                or []
            )
        except Exception as e:
            print(f"⚠️ Could not fetch quotes from API: {e}")
        return None

    def _load_employees(self):
        """Load employees without blocking the Tk event loop."""
        if self._is_destroyed or not self._backend_api:
            return

        def fetch():
            response = self._backend_api.request("GET", "/api/employees")
            return response.get("employees", []) if response else []

        def apply(employees):
            if self._is_destroyed:
                return
            self._employee_names = []
            self._employee_cache = {}
            for employee in employees or []:
                full_name = str(
                    employee.get("full_name")
                    or employee.get("username")
                    or employee.get("email")
                    or ""
                ).strip()
                if not full_name:
                    continue
                self._employee_names.append(full_name)
                self._employee_cache[full_name] = dict(employee)
            self._employee_names = sorted(set(self._employee_names))
            print(f"✅ Total {len(self._employee_names)} employees loaded for assignment")

        def failed(exc):
            if self._is_destroyed:
                return
            print(f"⚠️ API error loading employees: {exc}")
            self._toast("Could not load employees from the backend.", "error")

        run_in_background(self, fetch, apply, failed, name="quote-employees")

    def _load_quotes(self):
        """Load quotes off the UI thread and render them on Tk's thread."""
        if self._is_destroyed:
            print("⚠️ _load_quotes skipped: view already destroyed")
            return

        try:
            if not self.winfo_exists():
                print("⚠️ _load_quotes skipped: widget does not exist")
                return
        except Exception:
            return

        try:
            self._refresh_btn.configure(state="disabled", text="⏳")
            self._show_list_message(
                "Loading quotes…",
                "Your workspace will appear as soon as the data arrives.",
            )
        except Exception as exc:
            print(f"⚠️ Could not show loading state: {exc}")

        def fetch():
            api_error = None
            if self._backend_api:
                try:
                    response = self._backend_api.request("GET", "/api/quotes")
                    if not isinstance(response, dict):
                        raise RuntimeError(f"Unexpected quotes response type: {type(response)}")
                    quotes = (
                        response.get("quotes")
                        or response.get("data")
                        or response.get("items")
                        or []
                    )
                    if isinstance(quotes, dict):
                        quotes = quotes.get("quotes") or quotes.get("items") or []
                    if not isinstance(quotes, list):
                        quotes = []
                    print(
                        f"📋 API quotes response: success={response.get('success')} "
                        f"count={response.get('count', len(quotes))} keys={list(response.keys())}"
                    )
                    return quotes
                except Exception as exc:
                    api_error = exc
                    print(f"⚠️ Quotes API fetch failed: {exc}")

            raise RuntimeError(
                f"Could not load quotes from the backend"
                f"{': ' + str(api_error) if api_error else ''}"
            )

        def apply(quotes):
            print(f"📋 apply() entered with {type(quotes).__name__}")
            try:
                if self._is_destroyed:
                    print("⚠️ apply() aborted: _is_destroyed=True")
                    return
                try:
                    if not self.winfo_exists():
                        print("⚠️ apply() aborted: winfo_exists=False")
                        return
                except Exception as exc:
                    print(f"⚠️ apply() aborted: widget check failed: {exc}")
                    return

                if not isinstance(quotes, list):
                    print(f"⚠️ apply() expected list, got {type(quotes)}")
                    quotes = []

                normalized = []
                for quote in quotes:
                    if not isinstance(quote, dict):
                        continue
                    quote = dict(quote)
                    if "_id" in quote:
                        quote["_id"] = str(quote["_id"])
                    raw_status = quote.get("status", "received")
                    quote["status"] = self._map_mongo_to_display(raw_status)
                    if not quote.get("customerName"):
                        quote["customerName"] = (
                            quote.get("customer_name")
                            or quote.get("clientName")
                            or quote.get("client_name")
                            or quote.get("company")
                            or "Unknown customer"
                        )
                    if not quote.get("reference"):
                        quote["reference"] = (
                            quote.get("ref")
                            or quote.get("quote_number")
                            or quote.get("quoteNumber")
                            or quote.get("_id")
                            or "No ref"
                        )
                    if not quote.get("items"):
                        quote["items"] = quote.get("line_items") or []
                    if not quote.get("photos"):
                        quote["photos"] = []
                    if not quote.get("createdAt"):
                        quote["createdAt"] = quote.get("created_at") or quote.get("created")
                    # Normalize director review for Director availability UI
                    review = quote.get("director_review") or quote.get("directorReview")
                    if isinstance(review, dict):
                        # Treat legacy backend status "requested" as pending
                        st = str(review.get("status") or "").lower()
                        if st in ("requested", "awaiting", "awaiting_director"):
                            review = {**review, "status": "pending"}
                        quote["director_review"] = review
                    elif str(raw_status).lower() in ("awaiting_director", "awaiting director"):
                        # Stuck status with no review object — synthesize pending shell
                        items = quote.get("items") or []
                        quote["director_review"] = {
                            "status": "pending",
                            "requested_at": quote.get("updatedAt") or quote.get("createdAt"),
                            "requested_by": {"full_name": "Employee"},
                            "items": [
                                {
                                    "item_id": str(it.get("id") or it.get("_id") or ""),
                                    "item_name": it.get("name") or "Item",
                                    "qty_requested": it.get("qty", 1),
                                    "availability": "",
                                    "comment": "",
                                }
                                for it in items
                            ],
                        }
                    normalized.append(quote)

                total_from_api = len(normalized)
                if self._is_staff and self._current_username:
                    username = self._current_username.lower()
                    normalized = [
                        q for q in normalized if self._is_assigned_to_user(q, username)
                    ]
                    print(
                        f"📋 Quotes loaded: {total_from_api} total, "
                        f"{len(normalized)} assigned to {self._current_username}"
                    )
                else:
                    print(
                        f"📋 Quotes loaded: {total_from_api} (manager view, showing all)"
                    )

                self._quotes = normalized
                self._render_quote_list()
                try:
                    self._update_stats()
                except Exception as exc:
                    print(f"⚠️ _update_stats failed: {exc}")

                if self._quotes:
                    try:
                        self._select_quote(self._quotes[0])
                    except Exception as exc:
                        print(f"⚠️ _select_quote failed: {exc}")
                        import traceback
                        traceback.print_exc()
                else:
                    if self._is_staff:
                        self._show_list_message(
                            "No jobs assigned to you",
                            f"Backend has {total_from_api} quote(s), but none are assigned to "
                            f"{self._current_username or 'your account'}. Ask a manager to assign work.",
                        )
                    else:
                        self._show_list_message(
                            "No jobs found",
                            "New client work will appear here when it is received.",
                        )

                try:
                    self._refresh_btn.configure(state="normal", text="🔄")
                except Exception:
                    pass
                print(f"✅ Quote list render finished ({len(self._quotes)} cards)")
            except Exception as exc:
                print(f"❌ apply() crashed: {exc}")
                import traceback
                traceback.print_exc()
                try:
                    self._refresh_btn.configure(state="normal", text="🔄")
                except Exception:
                    pass

        def failed(exc):
            print(f"⚠️ Error loading quotes: {exc}")
            if self._is_destroyed:
                return
            try:
                self._show_list_message(
                    "We couldn't load the jobs",
                    "Check your connection and press Refresh to try again.",
                )
                self._refresh_btn.configure(state="normal", text="🔄")
            except Exception:
                pass

        print("📋 quote-loader worker starting…")
        run_in_background(self, fetch, apply, failed, name="quote-loader")

    def _is_assigned_to_user(self, quote: Dict[str, Any], username: str) -> bool:
        """Match staff identity against assigned_to (email, username, name, ids)."""
        if not username:
            return False
        username = str(username).strip().lower()
        assigned_to = (
            quote.get("assigned_to")
            or quote.get("assignedTo")
            or quote.get("assignee")
            or quote.get("employee")
        )
        if not assigned_to:
            return False

        def _matches(value: Any) -> bool:
            if value is None:
                return False
            text = str(value).strip().lower()
            if not text:
                return False
            if text == username:
                return True
            # Allow email local-part match (s.nkosi@... vs s.nkosi)
            if "@" in text and text.split("@", 1)[0] == username.split("@", 1)[0]:
                return True
            if "@" in username and username.split("@", 1)[0] == text:
                return True
            return False

        if isinstance(assigned_to, dict):
            candidates = [
                assigned_to.get("username"),
                assigned_to.get("email"),
                assigned_to.get("email_address"),
                assigned_to.get("name"),
                assigned_to.get("full_name"),
                assigned_to.get("display_name"),
                assigned_to.get("employee_id"),
                assigned_to.get("id"),
            ]
            return any(_matches(value) for value in candidates)
        return _matches(assigned_to)

    # ------------------------------------------------------------- list view

    def _show_list_message(self, title: str, subtitle: str = ""):
        for widget in self._quote_list.winfo_children():
            widget.destroy()
        ctk.CTkLabel(
            self._quote_list,
            text=title,
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color=Theme.TEXT,
        ).pack(pady=(30, 6))
        if subtitle:
            ctk.CTkLabel(
                self._quote_list,
                text=subtitle,
                font=ctk.CTkFont(size=12),
                text_color=Theme.MUTED_TEXT,
            ).pack()

    def _on_search_key(self, event=None):
        if self._search_job:
            self.after_cancel(self._search_job)
        self._search_job = self.after(180, self._filter_quotes)

    def _filter_quotes(self, event=None):
        """Filter and render quotes based on search and status."""
        if self._search_job:
            self.after_cancel(self._search_job)
            self._search_job = None
            
        filter_text = self._search_entry.get().strip().lower() if hasattr(self, '_search_entry') else ""
        
        for widget in self._quote_list.winfo_children():
            widget.destroy()

        quotes = self._quotes
        if self._active_status_filter != "All":
            quotes = [q for q in quotes if q.get("status") == self._active_status_filter]
        if filter_text:
            quotes = [
                q for q in quotes
                if filter_text in str(q.get("reference", "")).lower()
                or filter_text in str(q.get("customerName", "")).lower()
            ]

        if not quotes:
            ctk.CTkLabel(
                self._quote_list,
                text="No jobs found",
                font=ctk.CTkFont(size=13),
                text_color=Theme.MUTED_TEXT,
            ).pack(pady=30)
            if hasattr(self, '_result_hint'):
                self._result_hint.configure(text="")
            return

        for quote in quotes:
            self._create_quote_item(quote)
            
        if hasattr(self, '_result_hint'):
            self._result_hint.configure(
                text=f"Showing {len(quotes)} of {len(self._quotes)} jobs"
            )

    def _create_quote_item(self, quote: Dict[str, Any]):
        """Create a clean job card for the employee."""
        frame = ctk.CTkFrame(self._quote_list, corner_radius=8, fg_color=("gray95", "gray12"))
        frame.pack(fill="x", pady=3, padx=2)

        status = quote.get("status", "Pending")
        status_color = self.STATUS_COLORS.get(status, "#9E9E9E")
        status_icon = self.STATUS_ICONS.get(status, "📋")

        # Status and reference row
        top_row = ctk.CTkFrame(frame, fg_color="transparent")
        top_row.pack(fill="x", padx=12, pady=(6, 0))

        ctk.CTkLabel(
            top_row,
            text=f"{status_icon} {status}",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=status_color,
        ).pack(side="left")

        ctk.CTkLabel(
            top_row,
            text=quote.get("reference", "No ref"),
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=Theme.TEXT,
        ).pack(side="right")

        # Customer name
        ctk.CTkLabel(
            frame,
            text=f"👤 {quote.get('customerName', 'Unknown customer')}",
            font=ctk.CTkFont(size=12),
            anchor="w",
            text_color=Theme.TEXT,
        ).pack(fill="x", padx=12, pady=(2, 0))

        # Item count and date
        items = quote.get("items", [])
        date_str = self._format_date(quote.get("createdAt"))
        ctk.CTkLabel(
            frame,
            text=f"📦 {len(items)} items  •  📅 {date_str or 'N/A'}",
            font=ctk.CTkFont(size=10),
            text_color=Theme.MUTED_TEXT,
            anchor="w",
        ).pack(fill="x", padx=12, pady=(1, 4))

        # Action row - show for both staff and managers
        action_row = ctk.CTkFrame(frame, fg_color="transparent")
        action_row.pack(fill="x", padx=12, pady=(0, 6))

        current_status = quote.get("status", "Pending")
        action = self._get_next_action(current_status)

        if action:
            ctk.CTkButton(
                action_row,
                text=action["label"],
                height=28,
                width=100,
                fg_color=action["color"],
                hover_color=self._darken_color(action["color"]),
                font=ctk.CTkFont(size=10, weight="bold"),
                command=lambda q=quote: self._execute_action(q, action["action"]),
            ).pack(side="left", padx=(0, 6))

        # Return button for active statuses - show for both staff and managers
        if current_status not in ["Completed", "Returned"]:
            ctk.CTkButton(
                action_row,
                text="↩️",
                width=30,
                height=28,
                fg_color=Theme.DANGER,
                hover_color=Theme.DANGER_HOVER,
                font=ctk.CTkFont(size=11),
                command=lambda q=quote: self._return_quote(q),
            ).pack(side="right")

        # Click to select
        def select(_event=None, q=quote):
            self._select_quote(q)

        frame.bind("<Button-1>", select)
        for child in frame.winfo_children():
            child.bind("<Button-1>", select)
            child.configure(cursor="hand2")
        frame.configure(cursor="hand2")

        self._quote_cards[quote.get("reference", "")] = frame

    def _get_next_action(self, status: str) -> Optional[Dict[str, Any]]:
        """Next primary action for the professional workflow."""
        return self.WORKFLOW_NEXT.get(status)

    @ui_task
    def _execute_action(self, quote: Dict[str, Any], action: str):
        """Execute workflow action and advance status when appropriate."""
        if action in ("assign_start", "review", "check", "update"):
            self._select_quote(quote)
        elif action == "accept":
            (yield from ui_steps(self._quick_accept, quote))
        elif action == "start" or action == "start_work":
            (yield from ui_steps(self._apply_status_change, quote, "In Progress"))
        elif action == "request_details":
            (yield from ui_steps(self._request_client_details, quote))
        elif action == "generate_quote":
            (yield from ui_steps(self._generate_quotation, quote))
        elif action == "send_approval":
            (yield from ui_steps(self._apply_status_change, quote, "Awaiting Client Approval"))
        elif action == "await_payment":
            (yield from ui_steps(self._apply_status_change, quote, "Awaiting Payment"))
        elif action == "mark_paid":
            (yield from ui_steps(self._apply_status_change, quote, "Paid"))
        elif action == "out_for_delivery":
            (yield from ui_steps(self._apply_status_change, quote, "Out for Delivery"))
        elif action == "complete":
            (yield from ui_steps(self._mark_complete, quote))
        else:
            self._select_quote(quote)

    def _set_status_filter(self, name: str):
        self._active_status_filter = name
        for btn_name, btn in self._filter_buttons.items():
            if btn_name == name:
                btn.configure(fg_color=Theme.ACCENT, text_color="#1a1a1a")
            else:
                btn.configure(fg_color=Theme.PANEL_ALT, text_color=Theme.TEXT)
        self._filter_quotes()

    def _select_quote(self, quote: Dict[str, Any]):
        if self._is_destroyed:
            return
        self._selected_quote = quote
        self._selected_quote_id = quote.get("reference")
        self._show_quote_details(quote)

    # ---------------------------------------------------------- details view

    def _show_quote_details(self, quote: Dict[str, Any]):
        if self._is_destroyed:
            return
            
        self._empty_state.grid_remove()
        self._details_frame.grid()

        for widget in self._details_frame.winfo_children():
            widget.destroy()

        row = 0
        status = quote.get("status", "Pending")
        status_color = self.STATUS_COLORS.get(status, "#9E9E9E")
        status_icon = self.STATUS_ICONS.get(status, "📋")

        # === HEADER ===
        header = ctk.CTkFrame(self._details_frame, fg_color="transparent")
        header.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        header.grid_columnconfigure(0, weight=1)
        row += 1

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            title_box,
            text=quote.get("reference", "No reference"),
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=Theme.TEXT,
        ).pack(anchor="w")

        ctk.CTkLabel(
            title_box,
            text=f"👤 {quote.get('customerName', 'Unknown customer')}",
            font=ctk.CTkFont(size=13),
            text_color=Theme.MUTED_TEXT,
        ).pack(anchor="w")

        # Status badge
        status_badge = ctk.CTkFrame(
            header,
            fg_color=status_color,
            corner_radius=12,
            height=28,
        )
        status_badge.grid(row=0, column=1, sticky="e", padx=(10, 0))
        status_badge.grid_propagate(False)

        ctk.CTkLabel(
            status_badge,
            text=f"  {status_icon} {status}  ",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color="#1a1a1a",
        ).pack(pady=4)

        # Status help
        help_text = self.STATUS_HELP.get(status, "")
        if help_text:
            ctk.CTkLabel(
                self._details_frame,
                text=f"💡 {help_text}",
                font=ctk.CTkFont(size=11),
                text_color=Theme.MUTED_TEXT,
                anchor="w",
            ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 8))
            row += 1

        # === STATUS DROPDOWN - Show for BOTH staff AND managers ===
        if status not in ["Completed", "Returned"]:
            row = self._add_section_title("Update Status", row)
            status_frame = ctk.CTkFrame(self._details_frame, fg_color="transparent")
            status_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 8))
            status_frame.grid_columnconfigure(0, weight=0)
            status_frame.grid_columnconfigure(1, weight=0)
            row += 1

            status_var = ctk.StringVar(value=status)
            self._status_dropdown = ctk.CTkOptionMenu(
                status_frame,
                values=self.STATUS_OPTIONS,
                variable=status_var,
                command=self._on_status_change,
                width=200,
                height=30,
                fg_color=status_color,
                button_color=status_color,
                button_hover_color=self._darken_color(status_color),
                text_color="#1a1a1a",
                font=ctk.CTkFont(size=12),
            )
            self._status_dropdown.grid(row=0, column=0, sticky="w")

            ctk.CTkButton(
                status_frame,
                text="Update Status",
                width=120,
                height=30,
                fg_color=Theme.ACCENT,
                hover_color=Theme.ACCENT_HOVER,
                font=ctk.CTkFont(size=11, weight="bold"),
                command=lambda: self._update_status_from_dropdown(quote, status_var.get()),
            ).grid(row=0, column=1, padx=(10, 0), sticky="w")

            row = self._add_divider(row)

        # === QUICK ACTION - Show for BOTH staff AND managers ===
        action = self._get_next_action(status)
        if action and status not in ["Completed", "Returned"]:
            action_frame = ctk.CTkFrame(self._details_frame, fg_color="transparent")
            action_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 8))
            action_frame.grid_columnconfigure(0, weight=0)
            action_frame.grid_columnconfigure(1, weight=1)
            row += 1

            ctk.CTkButton(
                action_frame,
                text=action["label"],
                height=34,
                width=160,
                fg_color=action["color"],
                hover_color=self._darken_color(action["color"]),
                font=ctk.CTkFont(size=12, weight="bold"),
                command=lambda: self._execute_action(quote, action["action"]),
            ).grid(row=0, column=0, sticky="w")

            if status not in ["Completed", "Returned"]:
                ctk.CTkButton(
                    action_frame,
                    text="↩️ Return",
                    height=34,
                    width=100,
                    fg_color=Theme.DANGER,
                    hover_color=Theme.DANGER_HOVER,
                    font=ctk.CTkFont(size=11),
                    command=lambda: self._return_quote(quote),
                ).grid(row=0, column=1, sticky="e")

        # === ASSIGN SECTION - Show for BOTH staff AND managers ===
        if status not in ["Completed", "Returned"]:
            row = self._add_divider(row)
            row = self._add_section_title("Assign Job", row)
            assign_frame = ctk.CTkFrame(self._details_frame, fg_color="transparent")
            assign_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 10))
            assign_frame.grid_columnconfigure(0, weight=0)
            assign_frame.grid_columnconfigure(1, weight=1)
            assign_frame.grid_columnconfigure(2, weight=0)
            assign_frame.grid_columnconfigure(3, weight=0)
            row += 1

            # Current assignment display
            current_assigned = quote.get("assigned_to")
            if current_assigned:
                if isinstance(current_assigned, dict):
                    current_name = current_assigned.get("display_name") or current_assigned.get("name") or current_assigned.get("username", "Nobody")
                else:
                    current_name = str(current_assigned)
            else:
                current_name = "Nobody"

            ctk.CTkLabel(
                assign_frame,
                text=f"Currently: {current_name}",
                font=ctk.CTkFont(size=12),
                text_color=Theme.TEXT,
                anchor="w",
            ).grid(row=0, column=0, padx=(0, 10), sticky="w")

            # Employee dropdown
            employee_options = ["Nobody (unassign)"] + self._employee_names
            self._assign_menu = ctk.CTkOptionMenu(
                assign_frame,
                values=employee_options,
                width=200,
                height=30,
                fg_color=Theme.PANEL_ALT,
                button_color=Theme.ACCENT,
                button_hover_color=Theme.ACCENT_HOVER,
                font=ctk.CTkFont(size=12),
            )
            self._assign_menu.grid(row=0, column=1, sticky="ew")
            
            # Try to find the current assignment in the dropdown options
            if current_name != "Nobody" and current_name in employee_options:
                self._assign_menu.set(current_name)
            else:
                # Try to find by username
                found = False
                if current_assigned and isinstance(current_assigned, dict):
                    username = current_assigned.get("username")
                    if username:
                        for option in employee_options:
                            if option == username:
                                self._assign_menu.set(option)
                                found = True
                                break
                if not found:
                    self._assign_menu.set("Nobody (unassign)")

            # Show count of available employees
            ctk.CTkLabel(
                assign_frame,
                text=f"{len(self._employee_names)} available",
                font=ctk.CTkFont(size=10),
                text_color=Theme.MUTED_TEXT,
                anchor="w",
            ).grid(row=1, column=0, padx=(0, 10), sticky="w")

            ctk.CTkButton(
                assign_frame,
                text="Assign",
                width=80,
                height=30,
                fg_color="#2196F3",
                hover_color="#1976D2",
                font=ctk.CTkFont(size=11, weight="bold"),
                command=self._assign_quote,
            ).grid(row=0, column=2, padx=(10, 0), sticky="e")

            ctk.CTkButton(
                assign_frame,
                text="🔄",
                width=30,
                height=30,
                fg_color=Theme.PANEL_ALT,
                hover_color=Theme.BORDER,
                font=ctk.CTkFont(size=12),
                command=self._load_employees,
            ).grid(row=0, column=3, padx=(5, 0), sticky="e")

            if not self._employee_names:
                ctk.CTkLabel(
                    assign_frame,
                    text="No team members available. Click refresh to load.",
                    font=ctk.CTkFont(size=10),
                    text_color=Theme.MUTED_TEXT,
                    anchor="w",
                ).grid(row=2, column=0, columnspan=4, sticky="w", pady=(4, 0))

        # === CUSTOMER DETAILS + MISSING INFO ===
        row = self._add_divider(row)
        row = self._render_customer_and_missing_section(quote, row)

        # === QUOTATION ===
        row = self._render_quotation_section(quote, row)

        # === DELIVERY (after payment) ===
        row = self._render_delivery_section(quote, row)

        # === ITEMS ===
        row = self._add_divider(row)
        items = quote.get("items", [])
        row = self._add_section_title(f"Items ({len(items)})", row)
        items_frame = ctk.CTkFrame(self._details_frame, fg_color="transparent")
        items_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        items_frame.grid_columnconfigure(0, weight=2)
        items_frame.grid_columnconfigure(1, weight=0)
        items_frame.grid_columnconfigure(2, weight=3)
        row += 1

        if items:
            for i, item in enumerate(items, start=1):
                stripe = ("gray96", "gray14") if i % 2 else "transparent"
                ctk.CTkLabel(
                    items_frame,
                    text=item.get("name", "Unnamed item"),
                    anchor="w",
                    font=ctk.CTkFont(size=12),
                    text_color=Theme.TEXT,
                    fg_color=stripe,
                    corner_radius=4,
                    wraplength=180,
                ).grid(row=i, column=0, sticky="ew", pady=1, padx=(0, 6))
                ctk.CTkLabel(
                    items_frame,
                    text=f"× {item.get('qty', 1)}",
                    anchor="w",
                    font=ctk.CTkFont(size=12),
                    text_color=Theme.TEXT,
                    fg_color=stripe,
                ).grid(row=i, column=1, sticky="ew", pady=1, padx=(0, 6))
                price = item.get("price") or item.get("unit_price")
                if price is not None:
                    try:
                        specs_text = f"R {float(price):,.2f}"
                    except Exception:
                        specs_text = str(price)
                else:
                    specs = item.get("specs")
                    if isinstance(specs, list) and specs:
                        specs_text = " · ".join(str(s) for s in specs[:2])
                    elif specs:
                        specs_text = str(specs)
                    else:
                        specs_text = "No price set"
                ctk.CTkLabel(
                    items_frame,
                    text=specs_text,
                    anchor="w",
                    font=ctk.CTkFont(size=10),
                    text_color=Theme.MUTED_TEXT,
                    fg_color=stripe,
                    wraplength=180,
                ).grid(row=i, column=2, sticky="ew", pady=1)

        # === DIRECTOR AVAILABILITY REVIEW ===
        row = self._render_director_review_section(quote, row)

        # === HISTORY ===
        history = quote.get("history", [])
        if history:
            row = self._add_divider(row)
            row = self._add_section_title("Activity Log", row, hint=f"{len(history)} events")
            history_frame = ctk.CTkFrame(
                self._details_frame, fg_color=("gray95", "gray15"), corner_radius=8
            )
            history_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 10))
            history_frame.grid_columnconfigure(0, weight=1)
            history_frame.grid_rowconfigure(0, weight=1)
            row += 1

            history_textbox = ctk.CTkTextbox(
                history_frame, 
                height=100, 
                wrap="word", 
                corner_radius=6,
                font=ctk.CTkFont(size=11),
                text_color=Theme.TEXT,
                fg_color="transparent",
                border_width=0
            )
            history_textbox.grid(row=0, column=0, padx=12, pady=10, sticky="nsew")

            sorted_history = sorted(
                history[-12:], 
                key=lambda x: x.get("time", ""), 
                reverse=True
            )
            
            for h in sorted_history:
                action = h.get("action", "update")
                by = h.get("by") or h.get("username") or "System"
                time_str = h.get("time", "")
                note = h.get("note", "")
                progress = h.get("progress")
                
                emoji = self._get_action_emoji(action)
                action_text = self._format_action_text(action, progress)
                
                time_display = ""
                if time_str:
                    try:
                        if isinstance(time_str, str):
                            dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
                            time_display = dt.strftime("%d %b %H:%M")
                        else:
                            time_display = str(time_str)
                    except:
                        time_display = str(time_str)
                
                line = f"{emoji} {action_text}"
                if by and by != "System" and by != "None":
                    line += f" by {by}"
                if time_display:
                    line += f" ({time_display})"
                if note and "progress" not in action.lower() and "status" not in action.lower():
                    if len(note) > 50:
                        note = note[:50] + "..."
                    line += f"\n   └ {note}"
                
                history_textbox.insert("end", line + "\n")
            
            history_textbox.configure(state="disabled")

        # === CUSTOMER COMMUNICATION ===
        row = self._add_divider(row)
        row = self._add_section_title("Customer Communication", row)

        # Show existing reply
        existing_reply = quote.get("replyMessage", "") or ""
        if existing_reply:
            reply_box = ctk.CTkFrame(
                self._details_frame, fg_color=("gray95", "gray15"), corner_radius=8
            )
            reply_box.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 6))
            reply_box.grid_columnconfigure(0, weight=1)
            row += 1
            ctk.CTkLabel(
                reply_box,
                text="Previous reply:",
                font=ctk.CTkFont(size=10, weight="bold"),
                text_color=Theme.MUTED_TEXT,
                anchor="w",
            ).grid(row=0, column=0, padx=12, pady=(6, 0), sticky="w")
            ctk.CTkLabel(
                reply_box,
                text=existing_reply,
                anchor="w",
                wraplength=450,
                justify="left",
                font=ctk.CTkFont(size=12),
                text_color=Theme.TEXT,
            ).grid(row=1, column=0, padx=12, pady=(2, 10), sticky="w")

        # Reply input - for employees assigned to this quote OR managers
        current_status = quote.get("status", "Pending")
        is_assigned_to_me = self._is_assigned_to_user(
            quote, (self._current_username or "").lower()
        )

        # Allow reply if:
        # 1. User is a Manager, OR
        # 2. Employee is assigned to this quote
        # 3. Status is not Completed or Returned
        can_reply = (self._is_manager or is_assigned_to_me) and current_status not in ["Completed", "Returned"]
        
        if can_reply:
            # Reply input
            reply_label = ctk.CTkLabel(
                self._details_frame,
                text="Send a reply to the customer:",
                font=ctk.CTkFont(size=11, weight="bold"),
                text_color=Theme.TEXT,
                anchor="w",
            )
            reply_label.grid(row=row, column=0, columnspan=2, sticky="w", pady=(8, 4))
            row += 1

            self._reply_text = ctk.CTkTextbox(
                self._details_frame, 
                height=70, 
                wrap="word", 
                corner_radius=8
            )
            self._reply_text.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 6))
            
            # Pre-fill with a helpful message
            if not existing_reply:
                self._reply_text.insert("1.0", f"Hi {quote.get('customerName', 'Customer')},\n\nThank you for your inquiry. ")

            reply_row = ctk.CTkFrame(self._details_frame, fg_color="transparent")
            reply_row.grid(row=row + 1, column=0, columnspan=2, sticky="ew", pady=(0, 10))
            reply_row.grid_columnconfigure(0, weight=1)
            
            self._reply_hint = ctk.CTkLabel(
                reply_row,
                text="Your reply will be saved to this quote.",
                font=ctk.CTkFont(size=10),
                text_color=Theme.MUTED_TEXT,
                anchor="w",
            )
            self._reply_hint.grid(row=0, column=0, sticky="w")

            self._save_reply_btn = ctk.CTkButton(
                reply_row,
                text="✉️ Send Reply",
                command=lambda q=quote: self._send_reply(q),
                fg_color="#4CAF50",
                hover_color="#388E3C",
                height=32,
                width=130,
                font=ctk.CTkFont(size=11, weight="bold"),
            )
            self._save_reply_btn.grid(row=0, column=1, sticky="e")
            row += 2
            
        elif current_status in ["Completed", "Returned"]:
            ctk.CTkLabel(
                self._details_frame,
                text="This job is completed/returned. No further replies can be sent.",
                font=ctk.CTkFont(size=11),
                text_color=Theme.MUTED_TEXT,
                anchor="w",
            ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 10))
            row += 1
        else:
            ctk.CTkLabel(
                self._details_frame,
                text="You cannot reply to this quote - it's assigned to another team member.",
                font=ctk.CTkFont(size=11),
                text_color=Theme.MUTED_TEXT,
                anchor="w",
            ).grid(row=row, column=0, columnspan=2, sticky="w", pady=(0, 10))
            row += 1

    def _get_action_emoji(self, action: str) -> str:
        """Get emoji for action type."""
        action_lower = action.lower()
        if "assigned" in action_lower:
            return "📋"
        elif "accepted" in action_lower:
            return "✅"
        elif "progress" in action_lower:
            return "📈"
        elif "started" in action_lower:
            return "▶️"
        elif "completed" in action_lower:
            return "🏁"
        elif "returned" in action_lower:
            return "↩️"
        elif "replied" in action_lower or "reply" in action_lower:
            return "✉️"
        elif "note" in action_lower:
            return "📝"
        elif "status" in action_lower:
            return "🔄"
        else:
            return "•"

    def _format_action_text(self, action: str, progress: Optional[int] = None) -> str:
        """Format action text for display."""
        action_lower = action.lower()
        
        if "progress_updated" in action_lower:
            if progress is not None:
                return f"Progress updated to {progress}%"
            return "Progress updated"
        elif "status_changed" in action_lower:
            return "Status changed"
        elif "status_changed_to" in action_lower:
            parts = action.split("_to_")
            if len(parts) > 1:
                status_name = parts[1].replace("_", " ").title()
                return f"Status → {status_name}"
            return "Status changed"
        elif "assigned" in action_lower:
            return "Job assigned"
        elif "accepted" in action_lower:
            return "Job accepted"
        elif "started" in action_lower:
            return "Started working"
        elif "completed" in action_lower:
            return "Job completed"
        elif "returned" in action_lower:
            return "Job returned"
        elif "replied" in action_lower or "reply" in action_lower:
            return "Reply sent to customer"
        elif "note" in action_lower:
            return "Note added"
        else:
            return action.replace("_", " ").title()

    # ------------------------------------------------------------- actions

    @ui_task
    def _on_status_change(self, new_status: str):
        """Handle status change from dropdown."""
        if self._selected_quote:
            (yield from ui_steps(self._update_status_from_dropdown, self._selected_quote, new_status))

    @ui_task
    def _update_status_from_dropdown(self, quote: Dict[str, Any], new_status: str):
        """Update status from dropdown."""
        if not quote:
            return
            
        current_status = quote.get("status", "Pending")
        if current_status == new_status:
            self._toast("Status is already set to this.", "info")
            return
            
        reference = quote.get("reference", "")
        if not reference:
            self._toast("No reference found.", "error")
            return

        try:
            api_status = self.DISPLAY_TO_MONGO.get(
                new_status, str(new_status).lower().replace(" ", "_")
            )
            if not (yield from ui_steps(self._api_set_quote_status, reference, api_status)):
                raise RuntimeError("The backend did not accept the status update.")
            quote["status"] = new_status
            for q in self._quotes:
                if q.get("reference") == reference:
                    q["status"] = new_status
                    break

            self._toast(f"Status updated to {new_status}", "success")
            self._filter_quotes()
            
            colour = self.STATUS_COLORS.get(new_status, Theme.ACCENT)
            if self._status_dropdown:
                self._status_dropdown.configure(
                    fg_color=colour,
                    button_color=colour,
                    button_hover_color=self._darken_color(colour)
                )

        except Exception as e:
            self._toast(f"Backend status update failed: {e}", "error")
            import traceback
            traceback.print_exc()

    @ui_task
    def _assign_quote(self):
        """Assign the current quote through the authenticated backend API."""
        if self._is_destroyed or not self._selected_quote or not self._assign_menu:
            return
        reference = str(self._selected_quote.get("reference") or "").strip()
        if not reference:
            self._toast("This quote has no reference.", "error")
            return
        selected = self._assign_menu.get()
        employee = None if selected == "Nobody (unassign)" else self._employee_cache.get(selected)
        if selected != "Nobody (unassign)" and not employee:
            self._toast(f"Could not find employee: {selected}", "error")
            return
        payload = {"employee_id": employee.get("employee_id") if employee else None}
        try:
            response = (yield RemoteCall(self._backend_api.request, "PUT", f"/api/admin/quotes/{reference}/assignment", payload))
            if not response.get("success"):
                raise RuntimeError(response.get("error") or "Assignment failed")
            assigned = (response.get("quote") or {}).get("assigned_to")
            self._selected_quote["assigned_to"] = assigned
            if response.get("quote", {}).get("status"):
                self._selected_quote["status"] = response["quote"]["status"]
            for quote in self._quotes:
                if quote.get("reference") == reference:
                    quote["assigned_to"] = assigned
                    quote["status"] = self._selected_quote.get("status", quote.get("status"))
                    break
            self._toast(f"{reference} assignment updated.", "success")
            if assigned:
                try:
                    (yield from ui_steps(self._notify_quote_assigned, reference, assigned, self._selected_quote))
                except Exception as notify_exc:
                    print(f"⚠️ Assignment notification failed: {notify_exc}")
            self._filter_quotes()
            self._show_quote_details(self._selected_quote)
        except Exception as exc:
            print(f"⚠️ Quote assignment failed: {exc}")
            self._toast(f"Assignment failed: {exc}", "error")

    def _resolve_assignee_identity(self, assigned_to) -> str:
        """Best identity string for existing notify_user lookup."""
        if not assigned_to:
            return ""
        if isinstance(assigned_to, dict):
            return (
                assigned_to.get("full_name")
                or assigned_to.get("display_name")
                or assigned_to.get("name")
                or assigned_to.get("email")
                or assigned_to.get("username")
                or assigned_to.get("employee_id")
                or ""
            )
        return str(assigned_to)

    @ui_task
    def _notify_quote_assigned(self, reference: str, assigned_to, quote: Dict[str, Any] = None):
        """Notify employee when a quote is assigned."""
        identity = self._resolve_assignee_identity(assigned_to)
        if not identity:
            return
        customer = (quote or {}).get("customerName") or "customer"
        (yield from ui_steps(self._send_notification, 
            identity,
            f"Quote {reference} ({customer}) was assigned to you.",
            "Quote Assigned",
            reference,
            category="Quote Assignment",
        ))

    @ui_task
    def _notify_director_review_requested(self, reference: str, quote: Dict[str, Any] = None):
        """Notify Director when staff requests availability check (or resubmits)."""
        customer = (quote or {}).get("customerName") or "customer"
        by = self._current_user_name or self._current_username or "Staff"
        # Detect resubmit from prior reviewed state before overwrite when possible
        review = (quote or {}).get("director_review") or {}
        history = (quote or {}).get("director_review_history") or []
        is_resubmit = bool(history) or (
            isinstance(review, dict) and review.get("status") in ("reviewed", "pending")
            and review.get("reviewed_at")
        )
        title = "Quote Resubmitted" if is_resubmit else "Quote Availability Check"
        action = (
            "resubmitted"
            if is_resubmit
            else "requested Director availability review for"
        )
        try:
            if self._notification_controller and hasattr(
                self._notification_controller, "notify_executive"
            ):
                (yield RemoteCall(self._notification_controller.notify_executive, 
                    title=title,
                    message=f"{by} {action} {reference} ({customer}).",
                    category="Quote Director Review",
                    reference_type="quote",
                    reference_id=reference,
                ))
        except Exception as e:
            print(f"⚠️ Director review request notification failed: {e}")

    @ui_task
    def _notify_director_review_completed(self, reference: str, quote: Dict[str, Any] = None):
        """Notify assigned employee when Director submits availability reply."""
        identity = self._resolve_assignee_identity((quote or {}).get("assigned_to"))
        if not identity:
            return
        customer = (quote or {}).get("customerName") or "customer"
        (yield from ui_steps(self._send_notification, 
            identity,
            f"Director replied on availability for {reference} ({customer}). Open Quote Management to review.",
            "Director Availability Response",
            reference,
            category="Quote Director Review",
        ))

    @ui_task
    def _send_notification(
        self,
        recipient: str,
        message: str,
        title: str,
        reference: str = "",
        category: str = "Quote Assignment",
    ):
        """Route through the existing notification controller only."""
        if not recipient:
            return
        try:
            if self._notification_controller and hasattr(
                self._notification_controller, "notify_user"
            ):
                (yield RemoteCall(self._notification_controller.notify_user, 
                    recipient,
                    message,
                    category=category,
                    title=title,
                    reference_type="quote" if reference else "",
                    reference_id=reference or "",
                ))
        except Exception as e:
            print(f"⚠️ Could not send notification via controller: {e}")

    @ui_task
    def _send_reply(self, quote: Dict[str, Any]):
        """Send a reply to the customer."""
        if self._is_destroyed:
            return
            
        if not self._reply_text:
            self._toast("Reply input not available.", "error")
            return
            
        reply = self._reply_text.get("1.0", "end-1c").strip()
        if not reply:
            self._toast("Type a message before sending.", "error")
            self._reply_text.focus_set()
            return

        reference = quote.get("reference", "")
        if not reference:
            self._toast("No reference found.", "error")
            return

        if not messagebox.askyesno(
            "Send Reply",
            f"Send your reply for {reference} to {quote.get('customerName') or 'the customer'}?",
        ):
            return

        try:
            response = (yield RemoteCall(
                self._backend_api.request,
                "PUT",
                f"/api/admin/quotes/{reference}",
                {"replyMessage": reply},
            ))
            if not response or not response.get("success"):
                raise RuntimeError((response or {}).get("error") or "The backend rejected the reply.")

            quote["replyMessage"] = reply
            quote["repliedAt"] = datetime.now(timezone.utc)
            quote["replied_by"] = self._current_user_name
            for existing in self._quotes:
                if existing.get("reference") == reference:
                    existing["replyMessage"] = reply
                    existing["replied_by"] = self._current_user_name
                    break
            self._loaded_reply = reply
            self._toast(f"Reply sent for {reference}!", "success")
            self._show_quote_details(quote)
        except Exception as e:
            self._toast(f"Backend reply failed: {e}", "error")
            import traceback
            traceback.print_exc()

    def _return_quote(self, quote: Dict[str, Any]):
        """Return a quote to the manager for reassignment."""
        reference = quote.get("reference", "")
        if not reference:
            self._toast("No reference found.", "error")
            return
        
        dialog = ctk.CTkToplevel(self)
        dialog.title("Return Quote")
        dialog.geometry("480x300")
        dialog.configure(fg_color=Theme.BG)
        dialog.transient(self)
        dialog.grab_set()
        
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - 240
        y = (dialog.winfo_screenheight() // 2) - 150
        dialog.geometry(f"480x300+{x}+{y}")
        
        main = ctk.CTkFrame(dialog, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=20, pady=16)
        
        ctk.CTkLabel(
            main,
            text="↩️ Return Quote to Manager",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=Theme.TEXT,
        ).pack(pady=(0, 4))
        
        ctk.CTkLabel(
            main,
            text=f"Return {reference} to manager for reassignment.",
            font=ctk.CTkFont(size=12),
            text_color=Theme.MUTED_TEXT,
        ).pack(pady=(0, 12))
        
        # Return to
        ctk.CTkLabel(
            main,
            text="Return to:",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=Theme.TEXT,
            anchor="w",
        ).pack(fill="x")
        
        return_to_options = ["Director", "Business Lead", "Operations Manager"]
        return_var = ctk.StringVar(value="Director")
        return_menu = ctk.CTkOptionMenu(
            main,
            values=return_to_options,
            variable=return_var,
            width=280,
            height=30,
            font=ctk.CTkFont(size=12),
        )
        return_menu.pack(pady=(2, 8))
        
        # Reason
        ctk.CTkLabel(
            main,
            text="Reason:",
            font=ctk.CTkFont(size=11, weight="bold"),
            text_color=Theme.TEXT,
            anchor="w",
        ).pack(fill="x")
        
        reason_text = ctk.CTkTextbox(main, height=50, wrap="word")
        reason_text.pack(fill="x", pady=(2, 10))
        reason_text.insert("1.0", "Client not responding / needs reassignment")
        
        btn_frame = ctk.CTkFrame(main, fg_color="transparent")
        btn_frame.pack(fill="x")
        
        @ui_callback(self)
        def on_return():
            reason = reason_text.get("1.0", "end-1c").strip()
            if not reason:
                self._toast("Please provide a reason.", "error")
                return
            dialog.destroy()
            (yield from ui_steps(self._execute_return, quote, reason, return_var.get()))
        
        def on_cancel():
            dialog.destroy()
        
        ctk.CTkButton(
            btn_frame,
            text="Cancel",
            width=80,
            height=32,
            fg_color=Theme.PANEL_ALT,
            hover_color=Theme.BORDER,
            font=ctk.CTkFont(size=11),
            command=on_cancel,
        ).pack(side="left", padx=4)
        
        ctk.CTkButton(
            btn_frame,
            text="↩️ Return",
            width=120,
            height=32,
            fg_color=Theme.DANGER,
            hover_color=Theme.DANGER_HOVER,
            font=ctk.CTkFont(size=11, weight="bold"),
            command=on_return,
        ).pack(side="right", padx=4)

    @ui_task
    def _execute_return(self, quote: Dict[str, Any], reason: str, return_to: str):
        """Execute the return action."""
        reference = quote.get("reference", "")
        if not reference:
            return
        
        try:
            if not (yield from ui_steps(self._api_set_quote_status, reference, "returned")):
                raise RuntimeError("The backend did not accept the return.")
            quote["status"] = "Returned"
            quote["return_reason"] = reason
            quote["returned_to"] = return_to
            
            self._toast(f"Returned to {return_to}!", "success")
            self._filter_quotes()
            
        except Exception as e:
            self._toast(f"Backend return failed: {e}", "error")
            import traceback
            traceback.print_exc()

    @ui_task
    def _mark_complete(self, quote: Dict[str, Any]):
        """Mark a quote as complete."""
        reference = quote.get("reference", "")
        if not reference:
            self._toast("No reference found.", "error")
            return

        if not messagebox.askyesno(
            "Mark Complete",
            f"Mark {reference} as complete?\n\nThis will notify your manager.",
        ):
            return

        try:
            if not (yield from ui_steps(self._api_set_quote_status, reference, "completed")):
                raise RuntimeError("The backend did not accept completion.")
            quote["status"] = "Completed"
            quote["progress"] = 100
            self._toast(f"{reference} complete! 🎉", "success")
            self._filter_quotes()
            (yield from ui_steps(self._notify_managers, reference, f"Completed by {self._current_user_name}"))

        except Exception as e:
            self._toast(f"Backend completion failed: {e}", "error")
            import traceback
            traceback.print_exc()

    @ui_task
    def _api_set_quote_status(self, reference: str, mongo_status: str) -> bool:
        """Update quote status via the backend. Tries known route shapes."""
        if not self._backend_api or not reference:
            return False
        payload = {
            "status": mongo_status,
            "by": self._current_user_name or self._current_username,
            "username": self._current_username,
        }
        # Backend documents: PUT/POST /api/admin/quotes/:reference/status
        # Older clients incorrectly called PUT /api/admin/quotes/:reference (404).
        # Prefer POST (canonical on fixed backend); keep aliases for older deploys.
        candidates = [
            ("POST", f"/api/admin/quotes/{reference}/status"),
            ("PUT", f"/api/admin/quotes/{reference}/status"),
            ("PATCH", f"/api/admin/quotes/{reference}/status"),
            ("POST", f"/api/quotes/{reference}/status"),
            ("PUT", f"/api/quotes/{reference}/status"),
        ]
        last_error = None
        for method, path in candidates:
            try:
                response = (yield RemoteCall(self._backend_api.request, method, path, payload))
                if response and response.get("success") is not False:
                    print(f"✅ Status updated via {method} {path} -> {mongo_status}")
                    return True
            except Exception as exc:
                last_error = exc
                print(f"⚠️ {method} {path} failed: {exc}")
        if last_error:
            print(f"⚠️ All status endpoints failed for {reference}: {last_error}")
        return False

    @ui_task
    def _quick_accept(self, quote: Dict[str, Any]):
        """Quick accept a quote."""
        reference = quote.get("reference", "")
        if not reference:
            return
        
        try:
            if not (yield from ui_steps(self._api_set_quote_status, reference, "accepted")):
                raise RuntimeError("The backend did not accept the assignment.")
            quote["status"] = "Accepted"
            for q in self._quotes:
                if q.get("reference") == reference:
                    q["status"] = "Accepted"
                    break
            
            self._toast("Accepted!", "success")
            self._filter_quotes()
            (yield from ui_steps(self._notify_managers, reference, f"Accepted by {self._current_user_name}"))
            
        except Exception as e:
            self._toast(f"Backend acceptance failed: {e}", "error")

    @ui_task
    def _quick_start_work(self, quote: Dict[str, Any]):
        """Quick start work on a quote."""
        reference = quote.get("reference", "")
        if not reference:
            return
        
        try:
            if not (yield from ui_steps(self._api_set_quote_status, reference, "in_progress")):
                raise RuntimeError("The backend did not start the work item.")
            quote["status"] = "In Progress"
            for q in self._quotes:
                if q.get("reference") == reference:
                    q["status"] = "In Progress"
                    break
            
            self._toast("Started work!", "success")
            self._filter_quotes()
            
        except Exception as e:
            self._toast(f"Backend start failed: {e}", "error")

    @ui_task
    def _notify_managers(self, reference: str, message: str, title: str = "Quote Update"):
        """Notify managers about quote updates."""
        if self._notification_controller:
            try:
                if hasattr(self._notification_controller, 'notify_operational'):
                    (yield RemoteCall(self._notification_controller.notify_operational, 
                        self.MANAGER_ROLES,
                        f"{title}: {reference}",
                        message,
                        "Quote",
                        "Quote",
                        reference
                    ))
                elif hasattr(self._notification_controller, 'record_activity'):
                    (yield RemoteCall(self._notification_controller.record_activity, 
                        title,
                        message,
                        "Quote",
                        reference
                    ))
            except Exception as e:
                print(f"⚠️ Could not send notification: {e}")

    # -------------------------------------------------------------- helpers

    def _add_divider(self, row: int) -> int:
        ctk.CTkFrame(self._details_frame, height=1, fg_color=("gray80", "gray28")).grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=8
        )
        return row + 1

    def _add_section_title(self, text: str, row: int, hint: str = "") -> int:
        box = ctk.CTkFrame(self._details_frame, fg_color="transparent")
        box.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 4))
        box.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            box,
            text=text,
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color=Theme.TEXT,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        if hint:
            ctk.CTkLabel(
                box,
                text=hint,
                font=ctk.CTkFont(size=10),
                text_color=Theme.MUTED_TEXT,
            ).grid(row=0, column=1, sticky="e")
        return row + 1

    @staticmethod
    def _darken_color(hex_color: str, amount: int = 40) -> str:
        """Darken a hex color by the given amount."""
        hex_color = hex_color.lstrip('#')
        r = max(0, int(hex_color[0:2], 16) - amount)
        g = max(0, int(hex_color[2:4], 16) - amount)
        b = max(0, int(hex_color[4:6], 16) - amount)
        return f"#{r:02x}{g:02x}{b:02x}"

    @staticmethod
    def _format_date(value: Any, long: bool = False) -> str:
        if not value:
            return ""
        try:
            if isinstance(value, datetime):
                return value.strftime("%d %b %Y, %H:%M" if long else "%d %b %Y")
            text = str(value)
            parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
            return parsed.strftime("%d %b %Y, %H:%M" if long else "%d %b %Y")
        except Exception:
            return str(value)[:10]

    def _update_stats(self):
        if not self._quotes:
            self._stats_label.configure(text="No jobs yet")
            return

        active = sum(
            1 for q in self._quotes 
            if q.get("status") in ("Pending", "Assigned", "Awaiting Details", "Quoted", "Awaiting Client Approval", "Awaiting Payment", "Paid", "In Progress", "Out for Delivery", "Accepted", "In Review", "Awaiting Client")
        )
        self._stats_label.configure(
            text=f"{len(self._quotes)} jobs · {active} active"
        )

    # ------------------------------------------------------------- Director review

    AVAILABILITY_OPTIONS = [
        "Available",
        "Partially Available",
        "Unavailable",
        "Alternative Required",
    ]

    def _is_director(self) -> bool:
        role = str(self._current_role or "").strip().lower()
        # Accept common variants used in auth / sidebar
        return role in {
            "director",
            "demo admin",
            "admin",
            "business lead",
            "operations manager",
        } or "director" in role

    def _get_director_review(self, quote: Dict[str, Any]) -> Dict[str, Any]:
        """Return a normalized director_review dict from either API field name."""
        review = quote.get("director_review") or quote.get("directorReview") or {}
        if not isinstance(review, dict):
            return {}
        st = str(review.get("status") or "").lower()
        # Backend historically used "requested" — treat as pending for the form
        if st in ("requested", "awaiting", "awaiting_director"):
            review = {**review, "status": "pending"}
        return review


    # ------------------------------------------------------------------ workflow UI

    def _format_rand(self, value) -> str:
        try:
            return f"R {float(value):,.2f}"
        except Exception:
            return "R 0.00"

    def _quotation_lines(self, quote: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build quotation lines from quote.items / quote.quotation."""
        stored = quote.get("quotation") or quote.get("quote_lines") or []
        if isinstance(stored, list) and stored:
            lines = []
            for line in stored:
                if not isinstance(line, dict):
                    continue
                lines.append({
                    "name": line.get("name") or line.get("description") or "Item",
                    "amount": float(line.get("amount") or line.get("price") or 0),
                })
            return lines

        lines = []
        for item in quote.get("items") or []:
            name = item.get("name") or "Item"
            qty = float(item.get("qty") or 1)
            unit = item.get("price") or item.get("unit_price")
            if unit is None:
                # no price yet — still list the line at 0 for Generate Quote UX
                amount = 0.0
            else:
                try:
                    amount = float(unit) * qty
                except Exception:
                    amount = 0.0
            lines.append({"name": name if qty == 1 else f"{name} ×{int(qty) if qty == int(qty) else qty}", "amount": amount})

        delivery_fee = quote.get("delivery_fee") or quote.get("deliveryFee")
        if delivery_fee:
            try:
                lines.append({
                    "name": f"Delivery ({quote.get('delivery_area') or quote.get('city') or 'client address'})",
                    "amount": float(delivery_fee),
                })
            except Exception:
                pass
        return lines

    def _quotation_total(self, quote: Dict[str, Any]) -> float:
        total = quote.get("quotation_total") or quote.get("total") or quote.get("paymentAmount")
        if total is not None:
            try:
                return float(total)
            except Exception:
                pass
        return sum(line["amount"] for line in self._quotation_lines(quote))

    def _missing_client_fields(self, quote: Dict[str, Any]) -> List[str]:
        missing = []
        if not (quote.get("address") or quote.get("delivery_address")):
            missing.append("Delivery address")
        if not (quote.get("phone") or quote.get("mobile")):
            missing.append("Phone number")
        if not (quote.get("delivery_date") or quote.get("preferred_delivery_date")):
            missing.append("Preferred delivery date")
        return missing

    def _render_customer_and_missing_section(self, quote: Dict[str, Any], row: int) -> int:
        row = self._add_section_title("Customer Details", row)
        card = ctk.CTkFrame(self._details_frame, fg_color=("gray95", "gray15"), corner_radius=8)
        card.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 8))
        card.grid_columnconfigure(0, weight=0)
        card.grid_columnconfigure(1, weight=1)
        row += 1

        address = quote.get("address") or quote.get("delivery_address") or ""
        delivery_date = quote.get("delivery_date") or quote.get("preferred_delivery_date") or ""
        site_notes = quote.get("site_notes") or quote.get("notes") or ""

        details = [
            ("Name", quote.get("customerName") or "—"),
            ("Email", quote.get("email") or "—"),
            ("Phone", quote.get("phone") or quote.get("mobile") or "—"),
            ("Address", address or "—"),
            ("Delivery Date", delivery_date or "—"),
        ]
        if quote.get("company"):
            details.insert(1, ("Company", quote["company"]))
        if site_notes:
            details.append(("Site Notes", site_notes))

        for i, (label, value) in enumerate(details):
            is_missing = value in ("—", "", None)
            ctk.CTkLabel(
                card,
                text=label,
                font=ctk.CTkFont(size=11, weight="bold"),
                anchor="w",
                width=100,
                text_color=Theme.MUTED_TEXT,
            ).grid(row=i, column=0, sticky="w", padx=(12, 6), pady=3)
            ctk.CTkLabel(
                card,
                text=("Missing — request from client" if is_missing else str(value)),
                anchor="w",
                font=ctk.CTkFont(size=12),
                text_color=("#C62828" if is_missing else Theme.TEXT),
                wraplength=340,
                justify="left",
            ).grid(row=i, column=1, sticky="w", padx=(0, 12), pady=3)

        missing = self._missing_client_fields(quote)
        if missing:
            miss_box = ctk.CTkFrame(self._details_frame, fg_color=("#FFF3E0", "#3E2723"), corner_radius=8)
            miss_box.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 10))
            miss_box.grid_columnconfigure(0, weight=1)
            row += 1
            ctk.CTkLabel(
                miss_box,
                text="⚠️  Missing Information",
                font=ctk.CTkFont(size=12, weight="bold"),
                text_color="#E65100",
                anchor="w",
            ).pack(fill="x", padx=12, pady=(10, 2))
            ctk.CTkLabel(
                miss_box,
                text="•  " + "\n•  ".join(missing),
                font=ctk.CTkFont(size=11),
                text_color=Theme.TEXT,
                anchor="w",
                justify="left",
            ).pack(fill="x", padx=12, pady=(0, 6))
            ctk.CTkButton(
                miss_box,
                text="Request Details from Client",
                height=30,
                width=200,
                fg_color="#FF9800",
                hover_color="#F57C00",
                font=ctk.CTkFont(size=11, weight="bold"),
                command=lambda: self._request_client_details(quote),
            ).pack(anchor="w", padx=12, pady=(0, 12))
        return row

    def _render_quotation_section(self, quote: Dict[str, Any], row: int) -> int:
        row = self._add_divider(row)
        row = self._add_section_title("Quotation", row)

        box = ctk.CTkFrame(self._details_frame, fg_color=("gray95", "gray15"), corner_radius=8)
        box.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        box.grid_columnconfigure(0, weight=1)
        box.grid_columnconfigure(1, weight=0)
        row += 1

        lines = self._quotation_lines(quote)
        total = self._quotation_total(quote)
        validity = quote.get("quote_valid_until") or quote.get("valid_until") or "14 days"
        includes = quote.get("quote_includes") or "Includes delivery to the client's address"

        if not lines:
            ctk.CTkLabel(
                box,
                text="No priced lines yet. Use Generate Quote after collecting details.",
                font=ctk.CTkFont(size=11),
                text_color=Theme.MUTED_TEXT,
                anchor="w",
            ).grid(row=0, column=0, columnspan=2, sticky="w", padx=14, pady=12)
        else:
            for i, line in enumerate(lines):
                ctk.CTkLabel(
                    box,
                    text=line["name"],
                    font=ctk.CTkFont(size=12),
                    text_color=Theme.TEXT,
                    anchor="w",
                ).grid(row=i, column=0, sticky="w", padx=14, pady=3)
                ctk.CTkLabel(
                    box,
                    text=self._format_rand(line["amount"]),
                    font=ctk.CTkFont(size=12),
                    text_color=Theme.TEXT,
                    anchor="e",
                ).grid(row=i, column=1, sticky="e", padx=14, pady=3)

            # separator
            sep = ctk.CTkFrame(box, fg_color=("gray80", "gray30"), height=1)
            sep.grid(row=len(lines), column=0, columnspan=2, sticky="ew", padx=14, pady=(6, 4))

            ctk.CTkLabel(
                box,
                text="Total",
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color=Theme.TEXT,
                anchor="w",
            ).grid(row=len(lines) + 1, column=0, sticky="w", padx=14, pady=(2, 2))
            ctk.CTkLabel(
                box,
                text=self._format_rand(total),
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color="#2E7D32",
                anchor="e",
            ).grid(row=len(lines) + 1, column=1, sticky="e", padx=14, pady=(2, 2))

            ctk.CTkLabel(
                box,
                text=f"Validity: {validity}  •  {includes}",
                font=ctk.CTkFont(size=10),
                text_color=Theme.MUTED_TEXT,
                anchor="w",
            ).grid(row=len(lines) + 2, column=0, columnspan=2, sticky="w", padx=14, pady=(2, 10))

        btn_row = ctk.CTkFrame(box, fg_color="transparent")
        btn_row.grid(row=50, column=0, columnspan=2, sticky="ew", padx=14, pady=(0, 12))
        ctk.CTkButton(
            btn_row,
            text="Generate / Refresh Quote",
            height=30,
            width=180,
            fg_color="#4CAF50",
            hover_color="#388E3C",
            font=ctk.CTkFont(size=11, weight="bold"),
            command=lambda: self._generate_quotation(quote),
        ).pack(side="left")
        if total > 0 and quote.get("status") in (
            "Quoted", "Awaiting Details", "Assigned", "In Review", "Pending"
        ):
            ctk.CTkButton(
                btn_row,
                text="Send for Client Approval",
                height=30,
                width=180,
                fg_color="#9C27B0",
                hover_color="#7B1FA2",
                font=ctk.CTkFont(size=11, weight="bold"),
                command=lambda: self._apply_status_change(quote, "Awaiting Client Approval"),
            ).pack(side="left", padx=(8, 0))
        return row

    def _render_delivery_section(self, quote: Dict[str, Any], row: int) -> int:
        status = quote.get("status", "")
        if status not in ("Paid", "In Progress", "Out for Delivery", "Completed"):
            return row

        row = self._add_divider(row)
        row = self._add_section_title("Delivery Details", row)
        box = ctk.CTkFrame(self._details_frame, fg_color=("gray95", "gray15"), corner_radius=8)
        box.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        box.grid_columnconfigure(0, weight=0)
        box.grid_columnconfigure(1, weight=1)
        row += 1

        delivery = quote.get("delivery") if isinstance(quote.get("delivery"), dict) else {}
        address = (
            delivery.get("address")
            or quote.get("delivery_address")
            or quote.get("address")
            or "—"
        )
        date = delivery.get("date") or quote.get("delivery_date") or "—"
        driver = delivery.get("driver") or quote.get("driver") or "—"
        d_status = delivery.get("status") or (
            "Delivered" if status == "Completed"
            else "Out for delivery" if status == "Out for Delivery"
            else "Scheduled" if status in ("Paid", "In Progress")
            else "—"
        )

        for i, (label, value) in enumerate([
            ("Address", address),
            ("Date", date),
            ("Driver", driver),
            ("Status", d_status),
        ]):
            ctk.CTkLabel(
                box, text=label, font=ctk.CTkFont(size=11, weight="bold"),
                text_color=Theme.MUTED_TEXT, anchor="w", width=80,
            ).grid(row=i, column=0, sticky="w", padx=(14, 6), pady=3)
            ctk.CTkLabel(
                box, text=str(value), font=ctk.CTkFont(size=12),
                text_color=Theme.TEXT, anchor="w", wraplength=340, justify="left",
            ).grid(row=i, column=1, sticky="w", padx=(0, 14), pady=3)

        actions = ctk.CTkFrame(box, fg_color="transparent")
        actions.grid(row=10, column=0, columnspan=2, sticky="ew", padx=14, pady=(6, 12))
        if status in ("Paid", "In Progress"):
            ctk.CTkButton(
                actions,
                text="Mark Out for Delivery",
                height=30,
                width=180,
                fg_color="#3F51B5",
                hover_color="#303F9F",
                font=ctk.CTkFont(size=11, weight="bold"),
                command=lambda: self._apply_status_change(quote, "Out for Delivery"),
            ).pack(side="left")
        if status == "Out for Delivery":
            ctk.CTkButton(
                actions,
                text="Mark Delivered / Complete",
                height=30,
                width=200,
                fg_color="#9E9E9E",
                hover_color="#757575",
                font=ctk.CTkFont(size=11, weight="bold"),
                command=lambda: self._mark_complete(quote),
            ).pack(side="left")
        return row

    @ui_task
    def _request_client_details(self, quote: Dict[str, Any]):
        """Draft a client message and move status to Awaiting Details."""
        name = (quote.get("customerName") or "there").split()[0]
        missing = self._missing_client_fields(quote)
        if not missing:
            missing = ["delivery address", "preferred delivery date"]
        needs = " and ".join(missing).lower()
        msg = (
            f"Hi {name}, before we can finalize your quotation, please send your "
            f"{needs}. Thank you!"
        )
        # Prefill communication box if present
        try:
            if getattr(self, "_reply_text", None):
                self._reply_text.delete("1.0", "end")
                self._reply_text.insert("1.0", msg)
        except Exception:
            pass
        (yield from ui_steps(self._apply_status_change, quote, "Awaiting Details"))
        self._toast("Status → Awaiting Details. Message drafted for the client.", "info")
        print(f"📨 Request details draft for {quote.get('reference')}: {msg}")

    @ui_task
    def _generate_quotation(self, quote: Dict[str, Any]):
        """Build / refresh quotation totals from items and optional delivery fee."""
        lines = self._quotation_lines(quote)
        total = sum(line["amount"] for line in lines)
        quote["quotation"] = lines
        quote["quotation_total"] = total
        if total > 0:
            quote["paymentAmount"] = total
            quote["paymentRequired"] = True
        # Advance to Quoted if we were collecting details / assigned
        status = quote.get("status", "")
        if status in ("Awaiting Details", "Assigned", "Pending", "In Review", "Accepted"):
            (yield from ui_steps(self._apply_status_change, quote, "Quoted"))
        else:
            # just refresh UI
            self._show_quote_details(quote)
        self._toast(f"Quotation total {self._format_rand(total)}", "success")

    @ui_task
    def _apply_status_change(self, quote: Dict[str, Any], new_status: str):
        """Shared status update used by workflow actions."""
        # Gate: don't jump to payment without a quote total
        if new_status == "Awaiting Payment":
            total = self._quotation_total(quote)
            if total <= 0:
                self._toast("Generate a quotation with pricing before Awaiting Payment.", "error")
                return
        if new_status == "Completed" and quote.get("status") not in (
            "Out for Delivery", "Paid", "In Progress", "Completed"
        ):
            # soft warning only
            print(f"ℹ️ Completing from {quote.get('status')} — preferred path is Out for Delivery first")
        (yield from ui_steps(self._update_status_from_dropdown, quote, new_status))

    def _render_director_review_section(self, quote: Dict[str, Any], row: int) -> int:
        """Clean Director availability UI — stacked layout, no overlaps."""
        status = quote.get("status", "Pending")
        if status in ("Completed", "Returned"):
            return row

        review = quote.get("director_review") or quote.get("directorReview") or {}
        if not isinstance(review, dict):
            review = {}
        review_status = str(review.get("status") or "").lower()
        if review_status in ("requested", "awaiting", "awaiting_director"):
            review_status = "pending"
            review = {**review, "status": "pending"}
            quote["director_review"] = review

        is_assigned_to_me = self._is_assigned_to_user(
            quote, (self._current_username or "").lower()
        )
        is_director = self._is_director()

        if not (
            is_director
            or is_assigned_to_me
            or getattr(self, "_is_manager", False)
            or review_status in ("pending", "reviewed", "completed")
        ):
            return row

        row = self._add_divider(row)
        row = self._add_section_title("Director Availability Check", row)

        box = ctk.CTkFrame(self._details_frame, fg_color=("gray95", "gray15"), corner_radius=8)
        box.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        box.grid_columnconfigure(0, weight=1)
        row += 1

        r = 0
        self._director_item_widgets = []
        self._director_general_reply = None

        can_send = (
            (is_assigned_to_me or getattr(self, "_is_manager", False))
            and not is_director
            and review_status != "pending"
            and status not in ("Completed", "Returned")
        )
        if can_send:
            ctk.CTkLabel(
                box,
                text="Ask the Director to confirm whether client items are available.",
                font=ctk.CTkFont(size=11),
                text_color=Theme.MUTED_TEXT,
                anchor="w",
            ).grid(row=r, column=0, sticky="ew", padx=14, pady=(12, 4))
            r += 1
            ctk.CTkButton(
                box,
                text="Send to Director",
                height=32,
                width=170,
                fg_color="#673AB7",
                hover_color="#5E35B1",
                font=ctk.CTkFont(size=12, weight="bold"),
                command=lambda: self._send_to_director(quote),
            ).grid(row=r, column=0, sticky="w", padx=14, pady=(0, 12))
            r += 1

        if review_status == "pending":
            req_by = review.get("requested_by") or review.get("requestedBy") or {}
            who = req_by if isinstance(req_by, str) else (
                req_by.get("full_name") or req_by.get("username") or "employee"
            )
            ctk.CTkLabel(
                box,
                text="⏳  Awaiting Director availability review",
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color="#E65100",
                anchor="w",
            ).grid(row=r, column=0, sticky="ew", padx=14, pady=(12, 2))
            r += 1
            ctk.CTkLabel(
                box,
                text=f"Requested by {who}",
                font=ctk.CTkFont(size=11),
                text_color=Theme.MUTED_TEXT,
                anchor="w",
            ).grid(row=r, column=0, sticky="ew", padx=14, pady=(0, 10))
            r += 1

            if is_director:
                items = quote.get("items") or []
                review_items = review.get("items") or []
                form = ctk.CTkFrame(box, fg_color="transparent")
                form.grid(row=r, column=0, sticky="ew", padx=14, pady=(0, 6))
                form.grid_columnconfigure(0, weight=2)
                form.grid_columnconfigure(1, weight=0)
                form.grid_columnconfigure(2, weight=2)
                r += 1

                ctk.CTkLabel(
                    form, text="Item", font=ctk.CTkFont(size=11, weight="bold"),
                    text_color=Theme.MUTED_TEXT, anchor="w",
                ).grid(row=0, column=0, sticky="w", pady=(0, 4))
                ctk.CTkLabel(
                    form, text="Availability", font=ctk.CTkFont(size=11, weight="bold"),
                    text_color=Theme.MUTED_TEXT, anchor="w",
                ).grid(row=0, column=1, sticky="w", padx=(8, 0), pady=(0, 4))
                ctk.CTkLabel(
                    form, text="Comment", font=ctk.CTkFont(size=11, weight="bold"),
                    text_color=Theme.MUTED_TEXT, anchor="w",
                ).grid(row=0, column=2, sticky="w", padx=(8, 0), pady=(0, 4))

                for idx, item in enumerate(items):
                    item_id = str(item.get("id") or item.get("_id") or "")
                    name = item.get("name") or "Item"
                    qty = item.get("qty", 1)
                    prior = next(
                        (
                            ri for ri in review_items
                            if str(ri.get("item_id") or "") == item_id
                            or str(ri.get("item_name") or "").lower() == name.lower()
                        ),
                        {},
                    )
                    ctk.CTkLabel(
                        form,
                        text=f"{name}  ×{qty}",
                        font=ctk.CTkFont(size=12),
                        text_color=Theme.TEXT,
                        anchor="w",
                        wraplength=180,
                    ).grid(row=idx + 1, column=0, sticky="w", pady=3)

                    avail_menu = ctk.CTkOptionMenu(
                        form,
                        values=self.AVAILABILITY_OPTIONS,
                        width=150,
                        height=28,
                        font=ctk.CTkFont(size=11),
                    )
                    avail_menu.set(prior.get("availability") or "Available")
                    avail_menu.grid(row=idx + 1, column=1, sticky="w", padx=(8, 0), pady=3)

                    comment_entry = ctk.CTkEntry(
                        form, placeholder_text="Optional note", height=28, font=ctk.CTkFont(size=11)
                    )
                    if prior.get("comment"):
                        comment_entry.insert(0, str(prior.get("comment")))
                    comment_entry.grid(row=idx + 1, column=2, sticky="ew", padx=(8, 0), pady=3)

                    self._director_item_widgets.append({
                        "item_id": item_id,
                        "item_name": name,
                        "qty_requested": qty,
                        "availability_menu": avail_menu,
                        "comment_entry": comment_entry,
                    })

                ctk.CTkLabel(
                    box,
                    text="Your reply to the employee",
                    font=ctk.CTkFont(size=11, weight="bold"),
                    text_color=Theme.TEXT,
                    anchor="w",
                ).grid(row=r, column=0, sticky="ew", padx=14, pady=(8, 2))
                r += 1
                self._director_general_reply = ctk.CTkTextbox(
                    box, height=80, wrap="word", corner_radius=6, font=ctk.CTkFont(size=12)
                )
                self._director_general_reply.grid(row=r, column=0, sticky="ew", padx=14, pady=(0, 6))
                r += 1
                self._director_general_reply.insert("1.0", "Items checked. ")

                ctk.CTkButton(
                    box,
                    text="Send Reply to Employee",
                    height=34,
                    width=200,
                    fg_color="#2196F3",
                    hover_color="#1976D2",
                    font=ctk.CTkFont(size=12, weight="bold"),
                    command=lambda: self._submit_director_review(quote),
                ).grid(row=r, column=0, sticky="w", padx=14, pady=(0, 14))
                r += 1
            else:
                ctk.CTkLabel(
                    box,
                    text="The Director has not replied yet. You will be notified when they do.",
                    font=ctk.CTkFont(size=11),
                    text_color=Theme.MUTED_TEXT,
                    anchor="w",
                ).grid(row=r, column=0, sticky="ew", padx=14, pady=(0, 12))
                r += 1

        elif review_status in ("reviewed", "completed"):
            director = review.get("director") or {}
            who = director.get("full_name") or director.get("username") or "Director"
            when = self._format_review_time(
                review.get("reviewed_at") or review.get("reviewedAt") or ""
            )

            header = ctk.CTkFrame(box, fg_color=("gray90", "gray20"), corner_radius=6)
            header.grid(row=r, column=0, sticky="ew", padx=14, pady=(12, 8))
            r += 1
            ctk.CTkLabel(
                header,
                text=f"✅  Director response from {who}",
                font=ctk.CTkFont(size=13, weight="bold"),
                text_color="#2E7D32",
                anchor="w",
            ).pack(fill="x", padx=10, pady=(8, 0 if when else 8))
            if when:
                ctk.CTkLabel(
                    header,
                    text=when,
                    font=ctk.CTkFont(size=11),
                    text_color=Theme.MUTED_TEXT,
                    anchor="w",
                ).pack(fill="x", padx=10, pady=(2, 8))

            general = review.get("general_reply") or review.get("reply") or ""
            if general:
                reply_box = ctk.CTkFrame(box, fg_color=("gray92", "gray18"), corner_radius=6)
                reply_box.grid(row=r, column=0, sticky="ew", padx=14, pady=(0, 8))
                r += 1
                ctk.CTkLabel(
                    reply_box,
                    text="Reply",
                    font=ctk.CTkFont(size=10, weight="bold"),
                    text_color=Theme.MUTED_TEXT,
                    anchor="w",
                ).pack(fill="x", padx=10, pady=(8, 2))
                ctk.CTkLabel(
                    reply_box,
                    text=general,
                    font=ctk.CTkFont(size=12),
                    text_color=Theme.TEXT,
                    anchor="w",
                    justify="left",
                    wraplength=420,
                ).pack(fill="x", padx=10, pady=(0, 8))

            items_resp = review.get("items") or []
            if items_resp:
                items_box = ctk.CTkFrame(box, fg_color="transparent")
                items_box.grid(row=r, column=0, sticky="ew", padx=14, pady=(0, 8))
                r += 1
                ctk.CTkLabel(
                    items_box,
                    text="Item availability",
                    font=ctk.CTkFont(size=10, weight="bold"),
                    text_color=Theme.MUTED_TEXT,
                    anchor="w",
                ).pack(fill="x", pady=(0, 4))
                for it in items_resp:
                    avail = it.get("availability") or "—"
                    name = it.get("item_name") or "Item"
                    comment = it.get("comment") or ""
                    line = f"•  {name}:  {avail}"
                    if comment:
                        line += f"  —  {comment}"
                    ctk.CTkLabel(
                        items_box,
                        text=line,
                        font=ctk.CTkFont(size=12),
                        text_color=Theme.TEXT,
                        anchor="w",
                        justify="left",
                        wraplength=420,
                    ).pack(fill="x", pady=1)

            if (is_assigned_to_me or getattr(self, "_is_staff", False)) and not is_director:
                ctk.CTkButton(
                    box,
                    text="Update / Resubmit to Director",
                    height=32,
                    width=220,
                    fg_color="#673AB7",
                    hover_color="#5E35B1",
                    font=ctk.CTkFont(size=12, weight="bold"),
                    command=lambda: self._send_to_director(quote),
                ).grid(row=r, column=0, sticky="w", padx=14, pady=(4, 14))
                r += 1

        elif is_director:
            ctk.CTkLabel(
                box,
                text="No availability request on this quote yet.\n"
                     "When an employee sends it for review, the reply form will appear here.",
                font=ctk.CTkFont(size=11),
                text_color=Theme.MUTED_TEXT,
                anchor="w",
                justify="left",
            ).grid(row=r, column=0, sticky="ew", padx=14, pady=14)

        return row

    def _format_review_time(self, value) -> str:
        """Format ISO timestamps into a short readable form."""
        if not value:
            return ""
        try:
            text = str(value).replace("Z", "+00:00")
            dt = datetime.fromisoformat(text)
            return dt.strftime("%d %b %Y, %H:%M")
        except Exception:
            return str(value)[:16]

    @ui_task
    def _send_to_director(self, quote: Dict[str, Any]):
        """Employee (or manager) sends quote to Director for availability check."""
        if self._is_destroyed or not quote:
            return
        reference = str(quote.get("reference") or "").strip()
        if not reference:
            self._toast("No reference found.", "error")
            return
        if not messagebox.askyesno(
            "Send to Director",
            f"Send {reference} to the Director for item availability checking?",
        ):
            return
        payload = {
            "username": self._current_username,
            "full_name": self._current_user_name,
            "by": self._current_user_name,
        }
        try:
            if self._backend_api:
                response = (yield RemoteCall(self._backend_api.request, 
                    "POST",
                    f"/api/admin/quotes/{reference}/director-review/request",
                    payload,
                ))
                if response and response.get("success"):
                    q = response.get("quote") or {}
                    quote["status"] = self._map_mongo_to_display(q.get("status") or "in_review")
                    quote["director_review"] = q.get("director_review")
                    for existing in self._quotes:
                        if existing.get("reference") == reference:
                            existing["status"] = quote["status"]
                            existing["director_review"] = quote.get("director_review")
                            break
                    try:
                        (yield from ui_steps(self._notify_director_review_requested, reference, quote))
                    except Exception as notify_exc:
                        print(f"⚠️ Send-to-Director notification failed: {notify_exc}")
                    self._toast("Sent to Director for availability review.", "success")
                    self._filter_quotes()
                    self._show_quote_details(quote)
                    return
                raise RuntimeError((response or {}).get("error") or "Request failed")
            raise RuntimeError("The backend is required for director review requests.")
        except Exception as exc:
            print(f"⚠️ Send to Director failed: {exc}")
            self._toast(f"Send to Director failed: {exc}", "error")

    @ui_task
    def _submit_director_review(self, quote: Dict[str, Any]):
        """Director submits per-item availability + general reply back to employee."""
        if self._is_destroyed or not quote:
            return
        if not self._is_director():
            self._toast("Only Directors can submit availability reviews.", "error")
            return
        reference = str(quote.get("reference") or "").strip()
        if not reference:
            self._toast("No reference found.", "error")
            return

        items_payload = []
        for w in getattr(self, "_director_item_widgets", []) or []:
            items_payload.append({
                "item_id": w.get("item_id"),
                "item_name": w.get("item_name"),
                "qty_requested": w.get("qty_requested", 1),
                "availability": w["availability_menu"].get() if w.get("availability_menu") else "Unavailable",
                "comment": (w["comment_entry"].get().strip() if w.get("comment_entry") else ""),
            })
        general = ""
        if self._director_general_reply:
            general = self._director_general_reply.get("1.0", "end-1c").strip()

        if not messagebox.askyesno(
            "Send Director Reply",
            f"Send availability response for {reference} back to the assigned employee?",
        ):
            return

        payload = {
            "general_reply": general,
            "items": items_payload,
            "username": self._current_username,
            "full_name": self._current_user_name,
            "by": self._current_user_name,
        }
        try:
            if self._backend_api:
                response = (yield RemoteCall(self._backend_api.request, 
                    "PUT",
                    f"/api/admin/quotes/{reference}/director-review",
                    payload,
                ))
                if response and response.get("success"):
                    q = response.get("quote") or {}
                    quote["status"] = self._map_mongo_to_display(q.get("status") or "assigned")
                    quote["director_review"] = q.get("director_review")
                    quote["director_review_history"] = q.get("director_review_history") or quote.get(
                        "director_review_history"
                    ) or []
                    for existing in self._quotes:
                        if existing.get("reference") == reference:
                            existing["status"] = quote["status"]
                            existing["director_review"] = quote.get("director_review")
                            existing["director_review_history"] = quote.get("director_review_history")
                            break
                    try:
                        (yield from ui_steps(self._notify_director_review_completed, reference, quote))
                    except Exception as notify_exc:
                        print(f"⚠️ Director-reply notification failed: {notify_exc}")
                    self._toast("Director reply sent to employee.", "success")
                    self._filter_quotes()
                    self._show_quote_details(quote)
                    return
                raise RuntimeError((response or {}).get("error") or "Submit failed")

            raise RuntimeError("The backend is required for director review responses.")
        except Exception as exc:
            print(f"⚠️ Director review submit failed: {exc}")
            self._toast(f"Director review failed: {exc}", "error")

    def _toast(self, message: str, kind: str = "info"):
        if self._is_destroyed:
            return
            
        colors = {
            "success": "#4CAF50",
            "error": Theme.DANGER,
            "info": Theme.MUTED_TEXT,
        }
        self._status_bar.configure(text=message, text_color=colors.get(kind, Theme.MUTED_TEXT))
        self.after(5000, lambda: self._status_bar.configure(text=""))

    @staticmethod
    def _map_mongo_to_display(mongo_status: Any) -> str:
        if not mongo_status:
            return "Pending"
        return QuoteManagementView.MONGO_TO_DISPLAY.get(str(mongo_status).lower(), "Pending")

    def _render_quote_list(self, filter_text: str = ""):
        self._filter_quotes()

    def destroy(self):
        self._is_destroyed = True
        
        if self._search_job:
            try:
                self.after_cancel(self._search_job)
            except:
                pass
            self._search_job = None
        
        if self._status_job:
            try:
                self.after_cancel(self._status_job)
            except:
                pass
            self._status_job = None
        
        self._quotes = []
        self._selected_quote = None
        self._quote_cards = {}
        self._filter_buttons = {}
        
        super().destroy()

    def refresh(self):
        """Refresh data without reconstructing the entire workspace."""
        if self._is_destroyed:
            return
        if self._check_authorization():
            self._load_quotes()
            self._load_employees()

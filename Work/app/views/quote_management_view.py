# app/views/quote_management_view.py
"""Quote Management View - Complete employee workspace with all statuses."""

import customtkinter as ctk
from tkinter import messagebox, filedialog
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List
import base64
import os

from app.services.mongodb_service import MongoDBService
from app.services.backend_api_client import BackendAPIClient
from app.utils.theme import Theme


class QuoteManagementView(ctk.CTkFrame):
    """Complete employee workspace with full status workflow."""

    # Complete status list for employees
    STATUS_OPTIONS = [
        "Pending", "In Review", "Quoted", "Assigned", "Accepted", 
        "In Progress", "Awaiting Client", "Awaiting Payment", "Paid", "Completed", "Returned"
    ]
    
    STATUS_COLORS = {
        "Pending": "#FFC107",
        "In Review": "#FF9800",
        "Quoted": "#4CAF50",
        "Assigned": "#2196F3",
        "Accepted": "#4CAF50",
        "In Progress": "#FF9800",
        "Awaiting Client": "#9C27B0",
        "Awaiting Payment": "#E91E63",
        "Paid": "#00BCD4",
        "Completed": "#9E9E9E",
        "Returned": "#F44336",
    }

    STATUS_ICONS = {
        "Pending": "⏳",
        "In Review": "📝",
        "Quoted": "💰",
        "Assigned": "📋",
        "Accepted": "✅",
        "In Progress": "🔧",
        "Awaiting Client": "⏳",
        "Awaiting Payment": "💰",
        "Paid": "✅",
        "Completed": "🏁",
        "Returned": "↩️",
    }

    STATUS_HELP = {
        "Pending": "New request awaiting review.",
        "In Review": "Pricing and details being worked out.",
        "Quoted": "Price sent to customer.",
        "Assigned": "Assigned to you. Click Accept to start.",
        "Accepted": "You've accepted the job. Click Start Work to begin.",
        "In Progress": "Work in progress. Update below.",
        "Awaiting Client": "Waiting for client response.",
        "Awaiting Payment": "Waiting for payment.",
        "Paid": "Payment received. Complete the job.",
        "Completed": "Job complete! 🎉",
        "Returned": "Returned to manager for reassignment.",
    }

    MANAGER_ROLES = ["Director", "Branch Manager", "Business Lead", "Operations Manager"]
    STAFF_ROLES = ["Staff", "Intern"]

    # Map display status to MongoDB status
    DISPLAY_TO_MONGO = {
        "Pending": "received",
        "In Review": "in_review",
        "Quoted": "quoted",
        "Assigned": "assigned",
        "Accepted": "accepted",
        "In Progress": "in_progress",
        "Awaiting Client": "awaiting_client",
        "Awaiting Payment": "awaiting_payment",
        "Paid": "paid",
        "Completed": "completed",
        "Returned": "returned",
    }

    MONGO_TO_DISPLAY = {
        "received": "Pending",
        "in_review": "In Review",
        "quoted": "Quoted",
        "assigned": "Assigned",
        "accepted": "Accepted",
        "in_progress": "In Progress",
        "in progress": "In Progress",
        "awaiting_client": "Awaiting Client",
        "awaiting_payment": "Awaiting Payment",
        "paid": "Paid",
        "completed": "Completed",
        "returned": "Returned",
    }

    def __init__(
        self,
        master,
        mongodb_service: MongoDBService = None,
        people_controller=None,
        notification_controller=None,
        auth_service=None,
        navigation_controller=None,
        backend_api: BackendAPIClient = None,
    ):
        super().__init__(master, fg_color=Theme.BG, corner_radius=0)
        self._mongodb = mongodb_service
        self._backend_api = backend_api or BackendAPIClient()  # Initialize if not provided
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
        self._load_quotes()
        self._load_employees()

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
        self._list_panel.grid_rowconfigure(5, weight=1)

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

        # Quote list
        self._quote_list = ctk.CTkScrollableFrame(
            self._list_panel, fg_color="transparent", corner_radius=0
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
            if response and response.get('success'):
                return response.get('quotes', [])
        except Exception as e:
            print(f"⚠️ Could not fetch quotes from API: {e}")
        return None

    def _get_collection(self):
        """Get MongoDB collection - fallback if API fails."""
        if not self._mongodb:
            return None
        try:
            collection = self._mongodb.get_collection("quotes")
            if collection.find_one():
                return collection
        except Exception:
            pass
        try:
            test_db = self._mongodb._client["test"]
            collection = test_db["quotes"]
            return collection
        except Exception:
            pass
        return None

    def _load_employees(self):
        """Load active employees through the authenticated backend API only."""
        self._employee_names = []
        self._employee_cache = {}
        try:
            response = self._backend_api.request("GET", "/api/employees")
            employees = response.get("employees", []) if response else []
            for employee in employees:
                full_name = str(employee.get("full_name") or employee.get("username") or employee.get("email") or "").strip()
                if not full_name:
                    continue
                display_name = full_name
                self._employee_names.append(display_name)
                self._employee_cache[display_name] = dict(employee)
            self._employee_names = sorted(set(self._employee_names))
            print(f"✅ Total {len(self._employee_names)} employees loaded for assignment")
        except Exception as exc:
            print(f"⚠️ API error loading employees: {exc}")
            self._toast("Could not load employees from the backend.", "error")

    def _load_employees_from_mongodb(self):
        """Fallback: Load employees from MongoDB directly."""
        if not self._mongodb:
            return
        
        try:
            users_collection = self._mongodb.get_collection("users")
            employees_collection = self._mongodb.get_collection("employees")
            
            # Get ALL users from users collection
            users = list(users_collection.find({}))
            print(f"📊 Found {len(users)} users in MongoDB")
            
            for user in users:
                full_name = user.get("full_name") or user.get("name") or user.get("username") or user.get("email")
                if full_name:
                    if "@" in full_name:
                        display_name = full_name.split("@")[0]
                    else:
                        display_name = full_name
                    
                    self._employee_names.append(display_name)
                    self._employee_cache[display_name] = {
                        "username": user.get("username") or user.get("email") or display_name,
                        "employee_id": user.get("employee_id"),
                        "role": user.get("role", "Staff"),
                        "email": user.get("email"),
                        "full_name": full_name,
                        "display_name": display_name
                    }
                    print(f"✅ Added user: {display_name} (role: {user.get('role', 'Unknown')})")
            
            # Also get employees from employees collection
            employees = list(employees_collection.find({}))
            print(f"📊 Found {len(employees)} employees in MongoDB")
            
            for emp in employees:
                full_name = emp.get("full_name") or emp.get("name") or emp.get("first_name") + " " + emp.get("surname")
                if full_name:
                    display_name = full_name.strip()
                    if display_name not in self._employee_cache:
                        self._employee_names.append(display_name)
                        self._employee_cache[display_name] = {
                            "username": emp.get("email") or emp.get("username") or display_name.lower().replace(" ", "."),
                            "employee_id": emp.get("employee_id"),
                            "role": emp.get("role", "Staff"),
                            "email": emp.get("email"),
                            "full_name": display_name,
                            "display_name": display_name
                        }
                        print(f"✅ Added employee: {display_name}")
        except Exception as e:
            print(f"⚠️ MongoDB fallback error: {e}")

    def _load_quotes(self):
        if self._is_destroyed:
            return
        
        self._refresh_btn.configure(state="disabled", text="⏳")
        self.update_idletasks()

        try:
            # Try to get quotes from Backend API first
            if self._backend_api:
                try:
                    response = self._backend_api.request("GET", "/api/quotes")
                    if response and response.get('success'):
                        self._quotes = response.get('quotes', [])
                        
                        # Process quotes
                        for quote in self._quotes:
                            if "_id" in quote:
                                quote["_id"] = str(quote["_id"])
                            quote["status"] = self._map_mongo_to_display(quote.get("status", "received"))
                            if not quote.get("items"):
                                quote["items"] = []
                            if not quote.get("photos"):
                                quote["photos"] = []
                        
                        # Staff only see their assigned quotes, Managers see all
                        if self._is_staff and self._current_username:
                            username = self._current_username.lower()
                            self._quotes = [
                                q for q in self._quotes
                                if self._is_assigned_to_user(q, username)
                            ]
                            print(f"👤 Staff {username} sees {len(self._quotes)} assigned jobs")
                        else:
                            print(f"👤 Manager {self._current_user_name} sees all {len(self._quotes)} quotes")
                        
                        self._render_quote_list()
                        self._update_stats()
                        
                        if self._quotes:
                            self._select_quote(self._quotes[0])
                        
                        self._refresh_btn.configure(state="normal", text="🔄")
                        return
                except Exception as e:
                    print(f"⚠️ API error loading quotes: {e}")
                    # Fall through to MongoDB
            
            # Fallback to MongoDB
            if not self._mongodb or not self._mongodb.is_connected:
                self._show_list_message("⚠️ Not connected to MongoDB", "Please check your connection.")
                self._refresh_btn.configure(state="normal", text="🔄")
                return
            
            collection = self._get_collection()
            if collection is None:
                self._show_list_message("No quotes database found", "Please check your MongoDB connection.")
                self._refresh_btn.configure(state="normal", text="🔄")
                return

            self._quotes = list(collection.find().sort("createdAt", -1).limit(200))

            for quote in self._quotes:
                if "_id" in quote:
                    quote["_id"] = str(quote["_id"])
                quote["status"] = self._map_mongo_to_display(quote.get("status", "received"))
                if not quote.get("items"):
                    quote["items"] = []
                if not quote.get("photos"):
                    quote["photos"] = []

            # Staff only see their assigned quotes, Managers see all
            if self._is_staff and self._current_username:
                username = self._current_username.lower()
                self._quotes = [
                    q for q in self._quotes
                    if self._is_assigned_to_user(q, username)
                ]
                print(f"👤 Staff {username} sees {len(self._quotes)} assigned jobs")
            else:
                print(f"👤 Manager {self._current_user_name} sees all {len(self._quotes)} quotes")

            self._render_quote_list()
            self._update_stats()

            if self._quotes:
                self._select_quote(self._quotes[0])

        except Exception as e:
            self._show_list_message(f"❌ Error: {str(e)}", "Press Refresh to try again.")
            import traceback
            traceback.print_exc()
        finally:
            self._refresh_btn.configure(state="normal", text="🔄")

    def _is_assigned_to_user(self, quote: Dict[str, Any], username: str) -> bool:
        assigned_to = quote.get("assigned_to")
        if not assigned_to:
            return False
        if isinstance(assigned_to, dict):
            assigned_username = str(assigned_to.get("username", "")).lower()
            assigned_name = str(assigned_to.get("name", "")).lower()
            assigned_display = str(assigned_to.get("display_name", "")).lower()
            return assigned_username == username or assigned_name == username or assigned_display == username
        return str(assigned_to).lower() == username

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
        """Get the next action for a status."""
        actions = {
            "Pending": {"label": "📝 Review", "action": "review", "color": "#FFC107"},
            "In Review": {"label": "📝 Review", "action": "review", "color": "#FF9800"},
            "Quoted": {"label": "💰 Check", "action": "check", "color": "#4CAF50"},
            "Assigned": {"label": "✅ Accept", "action": "accept", "color": "#4CAF50"},
            "Accepted": {"label": "▶ Start", "action": "start", "color": "#FF9800"},
            "In Progress": {"label": "📝 Update", "action": "update", "color": "#2196F3"},
            "Awaiting Client": {"label": "⏳ Check", "action": "check", "color": "#9C27B0"},
            "Awaiting Payment": {"label": "💰 Check", "action": "check", "color": "#E91E63"},
            "Paid": {"label": "✅ Complete", "action": "complete", "color": "#00BCD4"},
        }
        return actions.get(status)

    def _execute_action(self, quote: Dict[str, Any], action: str):
        """Execute the action based on current status."""
        if action == "accept":
            self._quick_accept(quote)
        elif action == "start":
            self._quick_start_work(quote)
        elif action == "update":
            self._select_quote(quote)
        elif action == "check":
            self._select_quote(quote)
        elif action == "complete":
            self._mark_complete(quote)
        elif action == "review":
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

        # === CUSTOMER DETAILS ===
        row = self._add_divider(row)
        row = self._add_section_title("Customer Details", row)
        card = ctk.CTkFrame(self._details_frame, fg_color=("gray95", "gray15"), corner_radius=8)
        card.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        card.grid_columnconfigure(0, weight=0)
        card.grid_columnconfigure(1, weight=1)
        row += 1

        details = [
            ("Name", quote.get("customerName") or "Not provided"),
            ("Email", quote.get("email") or "Not provided"),
            ("Phone", quote.get("phone") or "Not provided"),
            ("Address", quote.get("address") or "Not provided"),
        ]
        if quote.get("company"):
            details.append(("Company", quote["company"]))

        for i, (label, value) in enumerate(details):
            ctk.CTkLabel(
                card,
                text=label,
                font=ctk.CTkFont(size=11, weight="bold"),
                anchor="w",
                width=80,
                text_color=Theme.MUTED_TEXT,
            ).grid(row=i, column=0, sticky="w", padx=(12, 6), pady=3)
            ctk.CTkLabel(
                card,
                text=value,
                anchor="w",
                font=ctk.CTkFont(size=12),
                text_color=Theme.TEXT,
                wraplength=350,
                justify="left",
            ).grid(row=i, column=1, sticky="w", padx=(0, 12), pady=3)

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
                specs = item.get("specs")
                if isinstance(specs, list) and specs:
                    specs_text = " · ".join(str(s) for s in specs[:2])
                elif specs:
                    specs_text = str(specs)
                else:
                    specs_text = "No specs"
                ctk.CTkLabel(
                    items_frame,
                    text=specs_text,
                    anchor="w",
                    font=ctk.CTkFont(size=10),
                    text_color=Theme.MUTED_TEXT,
                    fg_color=stripe,
                    wraplength=180,
                ).grid(row=i, column=2, sticky="ew", pady=1)

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
        assigned_to = quote.get("assigned_to")
        is_assigned_to_me = False
        
        # Check if assigned to current user
        if assigned_to:
            if isinstance(assigned_to, dict):
                assigned_username = assigned_to.get("username", "").lower()
                assigned_display = assigned_to.get("display_name", "").lower()
                assigned_name = assigned_to.get("name", "").lower()
                is_assigned_to_me = (
                    assigned_username == self._current_username.lower() or
                    assigned_display == self._current_username.lower() or
                    assigned_name == self._current_username.lower()
                )
            else:
                is_assigned_to_me = str(assigned_to).lower() == self._current_username.lower()
        
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

    def _on_status_change(self, new_status: str):
        """Handle status change from dropdown."""
        if self._selected_quote:
            self._update_status_from_dropdown(self._selected_quote, new_status)

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
            # Try using API first
            if self._backend_api:
                try:
                    response = self._backend_api.request(
                        "PUT", 
                        f"/api/admin/quotes/{reference}",
                        {"status": new_status}
                    )
                    if response and response.get('success'):
                        quote["status"] = new_status
                        for q in self._quotes:
                            if q.get("reference") == reference:
                                q["status"] = new_status
                                break
                        self._toast(f"Status updated to {new_status}", "success")
                        self._filter_quotes()
                        return
                except Exception as e:
                    print(f"⚠️ API status update failed: {e}")
                    # Fall through to MongoDB

            # Fallback to MongoDB
            collection = self._get_collection()
            if collection is None:
                self._toast("Could not find quotes collection.", "error")
                return

            mongo_status = self.DISPLAY_TO_MONGO.get(new_status, "received")
            
            history_entry = {
                "action": f"status_changed_to_{new_status.lower().replace(' ', '_')}",
                "by": self._current_user_name,
                "username": self._current_username,
                "time": datetime.now(timezone.utc).isoformat(),
                "from": current_status,
                "to": new_status,
                "note": f"Status changed from {current_status} to {new_status}"
            }

            collection.update_one(
                {"reference": reference},
                {
                    "$set": {
                        "status": mongo_status,
                        "updated_at": datetime.now(timezone.utc)
                    },
                    "$push": {"history": history_entry}
                }
            )

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
            self._toast(f"Error updating status: {e}", "error")
            import traceback
            traceback.print_exc()

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
            response = self._backend_api.request("PUT", f"/api/admin/quotes/{reference}/assignment", payload)
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
            self._filter_quotes()
            self._show_quote_details(self._selected_quote)
        except Exception as exc:
            print(f"⚠️ Quote assignment failed: {exc}")
            self._toast(f"Assignment failed: {exc}", "error")

    def _send_notification(self, recipient: str, message: str, title: str, reference: str = ""):
        """Send a notification to a user."""
        if not recipient:
            return
            
        try:
            if self._notification_controller:
                if hasattr(self._notification_controller, 'notify_user'):
                    self._notification_controller.notify_user(recipient, message, title)
                    return
        except Exception:
            pass
        
        try:
            notifications = self._mongodb.get_collection("notifications")
            notification = {
                "recipient": recipient,
                "recipient_role": "Staff",
                "title": title,
                "message": message,
                "category": "Quote Assignment",
                "reference": reference,
                "is_read": False,
                "created_at": datetime.now(timezone.utc)
            }
            notifications.insert_one(notification)
        except Exception as e:
            print(f"⚠️ Could not save notification: {e}")

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
            # Try using API first
            if self._backend_api:
                try:
                    response = self._backend_api.request(
                        "PUT",
                        f"/api/admin/quotes/{reference}",
                        {"replyMessage": reply}
                    )
                    if response and response.get('success'):
                        quote["replyMessage"] = reply
                        quote["repliedAt"] = datetime.now(timezone.utc)
                        quote["replied_by"] = self._current_user_name
                        for q in self._quotes:
                            if q.get("reference") == reference:
                                q["replyMessage"] = reply
                                q["replied_by"] = self._current_user_name
                                break
                        self._loaded_reply = reply
                        self._toast(f"Reply sent for {reference}!", "success")
                        self._show_quote_details(quote)
                        return
                except Exception as e:
                    print(f"⚠️ API reply failed: {e}")
                    # Fall through to MongoDB

            # Fallback to MongoDB
            collection = self._get_collection()
            if collection is None:
                self._toast("Could not find quotes collection.", "error")
                return

            # Update the quote with the reply
            result = collection.update_one(
                {"reference": reference},
                {
                    "$set": {
                        "replyMessage": reply,
                        "repliedAt": datetime.now(timezone.utc),
                        "replied_by": self._current_user_name,
                        "replied_username": self._current_username,
                        "updated_at": datetime.now(timezone.utc)
                    },
                    "$push": {
                        "history": {
                            "action": "reply_sent",
                            "by": self._current_user_name,
                            "username": self._current_username,
                            "time": datetime.now(timezone.utc).isoformat(),
                            "message": reply[:100] + ("..." if len(reply) > 100 else ""),
                            "note": f"Reply sent to customer by {self._current_user_name}"
                        }
                    }
                }
            )

            if result.modified_count > 0 or result.matched_count > 0:
                # Update local quote
                quote["replyMessage"] = reply
                quote["repliedAt"] = datetime.now(timezone.utc)
                quote["replied_by"] = self._current_user_name
                
                for q in self._quotes:
                    if q.get("reference") == reference:
                        q["replyMessage"] = reply
                        q["replied_by"] = self._current_user_name
                        break
                
                self._loaded_reply = reply
                self._toast(f"Reply sent for {reference}!", "success")
                
                # Notify manager that a reply was sent
                self._notify_managers(
                    reference,
                    f"Reply sent to customer by {self._current_user_name}:\n{reply[:100]}{'...' if len(reply) > 100 else ''}",
                    "Reply Sent"
                )
                
                # Refresh the details view to show the reply
                self._show_quote_details(quote)
            else:
                self._toast("Could not send reply. Please try again.", "error")
                
        except Exception as e:
            self._toast(f"Error sending reply: {e}", "error")
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
        
        return_to_options = ["Director", "Branch Manager", "Business Lead", "Operations Manager"]
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
        
        def on_return():
            reason = reason_text.get("1.0", "end-1c").strip()
            if not reason:
                self._toast("Please provide a reason.", "error")
                return
            dialog.destroy()
            self._execute_return(quote, reason, return_var.get())
        
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

    def _execute_return(self, quote: Dict[str, Any], reason: str, return_to: str):
        """Execute the return action."""
        reference = quote.get("reference", "")
        if not reference:
            return
        
        try:
            # Try using API first
            if self._backend_api:
                try:
                    response = self._backend_api.request(
                        "PUT",
                        f"/api/admin/quotes/{reference}",
                        {"status": "returned", "return_reason": reason, "returned_to": return_to}
                    )
                    if response and response.get('success'):
                        quote["status"] = "Returned"
                        quote["return_reason"] = reason
                        quote["returned_to"] = return_to
                        self._toast(f"Returned to {return_to}!", "success")
                        self._filter_quotes()
                        return
                except Exception as e:
                    print(f"⚠️ API return failed: {e}")
                    # Fall through to MongoDB

            # Fallback to MongoDB
            collection = self._get_collection()
            if collection is None:
                self._toast("Could not find quotes collection.", "error")
                return
            
            collection.update_one(
                {"reference": reference},
                {
                    "$set": {
                        "status": "returned",
                        "returned_at": datetime.now(timezone.utc),
                        "returned_by": self._current_user_name,
                        "returned_username": self._current_username,
                        "return_reason": reason,
                        "returned_to": return_to,
                        "updated_at": datetime.now(timezone.utc)
                    },
                    "$push": {
                        "history": {
                            "action": "returned",
                            "by": self._current_user_name,
                            "username": self._current_username,
                            "time": datetime.now(timezone.utc).isoformat(),
                            "reason": reason,
                            "returned_to": return_to,
                            "note": f"Returned to {return_to}. Reason: {reason}"
                        }
                    }
                }
            )
            
            quote["status"] = "Returned"
            quote["return_reason"] = reason
            quote["returned_to"] = return_to
            
            self._toast(f"Returned to {return_to}!", "success")
            self._filter_quotes()
            
            self._notify_managers(
                reference,
                f"Returned by {self._current_user_name} to {return_to}. Reason: {reason}",
                f"Returned Quote - {return_to}"
            )
            
        except Exception as e:
            self._toast(f"Error: {e}", "error")
            import traceback
            traceback.print_exc()

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
            # Try using API first
            if self._backend_api:
                try:
                    response = self._backend_api.request(
                        "PUT",
                        f"/api/admin/quotes/{reference}",
                        {"status": "completed", "progress": 100}
                    )
                    if response and response.get('success'):
                        quote["status"] = "Completed"
                        quote["progress"] = 100
                        self._toast(f"{reference} complete! 🎉", "success")
                        self._filter_quotes()
                        return
                except Exception as e:
                    print(f"⚠️ API complete failed: {e}")
                    # Fall through to MongoDB

            # Fallback to MongoDB
            collection = self._get_collection()
            if collection is None:
                self._toast("Could not find quotes collection.", "error")
                return

            collection.update_one(
                {"reference": reference},
                {
                    "$set": {
                        "status": "completed",
                        "progress": 100,
                        "completed_at": datetime.now(timezone.utc),
                        "completed_by": self._current_user_name,
                        "updated_at": datetime.now(timezone.utc)
                    },
                    "$push": {
                        "history": {
                            "action": "completed",
                            "by": self._current_user_name,
                            "username": self._current_username,
                            "time": datetime.now(timezone.utc).isoformat(),
                            "note": "Quote marked as completed"
                        }
                    }
                }
            )

            quote["status"] = "Completed"
            quote["progress"] = 100
            self._toast(f"{reference} complete! 🎉", "success")
            self._filter_quotes()
            self._notify_managers(reference, f"Completed by {self._current_user_name}")

        except Exception as e:
            self._toast(f"Error: {e}", "error")
            import traceback
            traceback.print_exc()

    def _quick_accept(self, quote: Dict[str, Any]):
        """Quick accept a quote."""
        reference = quote.get("reference", "")
        if not reference:
            return
        
        try:
            # Try using API first
            if self._backend_api:
                try:
                    response = self._backend_api.request(
                        "PUT",
                        f"/api/admin/quotes/{reference}",
                        {"status": "accepted"}
                    )
                    if response and response.get('success'):
                        quote["status"] = "Accepted"
                        for q in self._quotes:
                            if q.get("reference") == reference:
                                q["status"] = "Accepted"
                                break
                        self._toast("Accepted!", "success")
                        self._filter_quotes()
                        return
                except Exception as e:
                    print(f"⚠️ API accept failed: {e}")
                    # Fall through to MongoDB

            # Fallback to MongoDB
            collection = self._get_collection()
            if collection is None:
                return
            
            collection.update_one(
                {"reference": reference},
                {
                    "$set": {
                        "status": "accepted",
                        "accepted_at": datetime.now(timezone.utc),
                        "accepted_by": self._current_user_name,
                        "updated_at": datetime.now(timezone.utc)
                    },
                    "$push": {
                        "history": {
                            "action": "accepted",
                            "by": self._current_user_name,
                            "username": self._current_username,
                            "time": datetime.now(timezone.utc).isoformat(),
                            "note": "Employee accepted the assignment"
                        }
                    }
                }
            )
            
            quote["status"] = "Accepted"
            for q in self._quotes:
                if q.get("reference") == reference:
                    q["status"] = "Accepted"
                    break
            
            self._toast("Accepted!", "success")
            self._filter_quotes()
            self._notify_managers(reference, f"Accepted by {self._current_user_name}")
            
        except Exception as e:
            self._toast(f"Error: {e}", "error")

    def _quick_start_work(self, quote: Dict[str, Any]):
        """Quick start work on a quote."""
        reference = quote.get("reference", "")
        if not reference:
            return
        
        try:
            # Try using API first
            if self._backend_api:
                try:
                    response = self._backend_api.request(
                        "PUT",
                        f"/api/admin/quotes/{reference}",
                        {"status": "in_progress"}
                    )
                    if response and response.get('success'):
                        quote["status"] = "In Progress"
                        for q in self._quotes:
                            if q.get("reference") == reference:
                                q["status"] = "In Progress"
                                break
                        self._toast("Started work!", "success")
                        self._filter_quotes()
                        return
                except Exception as e:
                    print(f"⚠️ API start work failed: {e}")
                    # Fall through to MongoDB

            # Fallback to MongoDB
            collection = self._get_collection()
            if collection is None:
                return
            
            collection.update_one(
                {"reference": reference},
                {
                    "$set": {
                        "status": "in_progress",
                        "started_at": datetime.now(timezone.utc),
                        "updated_at": datetime.now(timezone.utc)
                    },
                    "$push": {
                        "history": {
                            "action": "started_work",
                            "by": self._current_user_name,
                            "username": self._current_username,
                            "time": datetime.now(timezone.utc).isoformat(),
                            "note": "Started working on the quote"
                        }
                    }
                }
            )
            
            quote["status"] = "In Progress"
            for q in self._quotes:
                if q.get("reference") == reference:
                    q["status"] = "In Progress"
                    break
            
            self._toast("Started work!", "success")
            self._filter_quotes()
            
        except Exception as e:
            self._toast(f"Error: {e}", "error")

    def _notify_managers(self, reference: str, message: str, title: str = "Quote Update"):
        """Notify managers about quote updates."""
        if self._notification_controller:
            try:
                if hasattr(self._notification_controller, 'notify_operational'):
                    self._notification_controller.notify_operational(
                        self.MANAGER_ROLES,
                        f"{title}: {reference}",
                        message,
                        "Quote",
                        "Quote",
                        reference
                    )
                elif hasattr(self._notification_controller, 'record_activity'):
                    self._notification_controller.record_activity(
                        title,
                        message,
                        "Quote",
                        reference
                    )
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
            if q.get("status") in ("Assigned", "Accepted", "In Progress", "Pending", "In Review")
        )
        self._stats_label.configure(
            text=f"{len(self._quotes)} jobs · {active} active"
        )

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
        if self._check_authorization():
            self._load_quotes()
            self._load_employees()
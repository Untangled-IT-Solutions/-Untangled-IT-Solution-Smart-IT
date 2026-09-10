# app/views/quote_management_view.py
"""Quote Management View - Directors, Business Leads, and Staff.

Pure MongoDB workflow - no task/quote duplication.
Managers: full control (assign, change status, reply)
Staff: view and work on assigned quotes only
"""

import customtkinter as ctk
from tkinter import messagebox
from datetime import datetime, timezone
from typing import Optional, Dict, Any, List

from app.services.mongodb_service import MongoDBService
from app.utils.theme import Theme


class QuoteManagementView(ctk.CTkFrame):
    """Quote management - Managers get full control, Staff see assigned quotes only."""

    STATUS_OPTIONS = ["Pending", "In Review", "Quoted", "Assigned", "Closed"]
    STATUS_COLORS = {
        "Pending": "#FFC107",
        "In Review": "#FF9800",
        "Quoted": "#4CAF50",
        "Closed": "#9E9E9E",
        "Assigned": "#2196F3",
    }

    STATUS_HELP = {
        "Pending": "New request — nobody has looked at it yet.",
        "In Review": "Someone is working out the pricing.",
        "Quoted": "A price has been sent to the customer.",
        "Assigned": "Handed over to a team member.",
        "Closed": "Finished — won, lost or cancelled.",
    }

    SORT_OPTIONS = ["Newest first", "Oldest first", "Customer A–Z", "Status"]

    DISPLAY_TO_MONGO = {
        "Pending": "received",
        "In Review": "in_review",
        "Quoted": "quoted",
        "Closed": "closed",
        "Assigned": "assigned",
    }

    MONGO_TO_DISPLAY = {
        "received": "Pending",
        "in_review": "In Review",
        "quoted": "Quoted",
        "closed": "Closed",
        "assigned": "Assigned",
    }

    MANAGER_ROLES = ["Director", "Branch Manager", "Business Lead", "Operations Manager"]
    STAFF_ROLES = ["Staff", "Intern"]

    def __init__(
        self,
        master,
        mongodb_service: MongoDBService,
        people_controller=None,
        notification_controller=None,
        auth_service=None,
    ):
        super().__init__(master, fg_color=Theme.BG, corner_radius=0)
        self._mongodb = mongodb_service
        self._people_controller = people_controller
        self._notification_controller = notification_controller
        self._auth_service = auth_service

        self._quotes: List[Dict[str, Any]] = []
        self._visible_quotes: List[Dict[str, Any]] = []
        self._selected_quote: Optional[Dict[str, Any]] = None
        self._selected_quote_id: Optional[str] = None
        self._employee_names: List[str] = []
        self._employee_cache: Dict[str, Dict[str, Any]] = {}
        self._current_role = "Staff"
        self._current_user_name = ""
        self._current_username = ""
        self._is_staff = False
        self._is_destroyed = False

        self._status_dropdown = None
        self._reply_text = None
        self._assign_menu = None
        self._save_reply_btn = None
        self._reply_hint = None
        self._loaded_reply = ""
        self._work_notes = None
        self._work_hint = None
        self._active_status_filter = "All"
        self._sort_mode = "Newest first"
        self._search_job = None
        self._status_job = None
        self._filter_buttons: Dict[str, ctk.CTkButton] = {}
        self._quote_cards: Dict[str, ctk.CTkFrame] = {}

        if not self._check_authorization():
            return

        self._setup_ui()
        self._load_quotes()

    # ------------------------------------------------------------------ auth

    def _check_authorization(self) -> bool:
        """Managers get full control; staff get a read-and-update view of their own quotes."""
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
                return True
            if self._current_role in self.STAFF_ROLES:
                self._is_staff = True
                return True
            self._show_unauthorized_message()
            return False
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
            text=(
                "Quote Management is available to Directors, Branch Managers,\n"
                "Business Leads and Operations Managers."
            ),
            font=ctk.CTkFont(size=14),
            justify="center",
            text_color=Theme.MUTED_TEXT,
        ).pack(pady=6)

        ctk.CTkLabel(
            frame,
            text=f"You're signed in as: {self._current_role}",
            font=ctk.CTkFont(size=12),
            text_color=Theme.MUTED_TEXT,
        ).pack(pady=(6, 2))

        ctk.CTkLabel(
            frame,
            text="Ask your manager if you need this access.",
            font=ctk.CTkFont(size=12),
            text_color=Theme.MUTED_TEXT,
        ).pack()

    # -------------------------------------------------------------------- ui

    def _setup_ui(self):
        self.grid_columnconfigure(0, weight=2, minsize=340)
        self.grid_columnconfigure(1, weight=3)
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
        )
        self._status_bar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=15, pady=(2, 8))

        master = self.winfo_toplevel()
        master.bind("<F5>", lambda e: self._load_quotes())
        master.bind("<Control-f>", self._focus_search)
        master.bind("<Control-r>", lambda e: self._load_quotes())

    def _setup_list_panel(self):
        self._list_panel = ctk.CTkFrame(self, corner_radius=12, fg_color=Theme.PANEL)
        self._list_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 6), pady=(0, 2))
        self._list_panel.grid_columnconfigure(0, weight=1)
        self._list_panel.grid_rowconfigure(4, weight=1)

        header = ctk.CTkFrame(self._list_panel, fg_color="transparent")
        header.grid(row=0, column=0, padx=15, pady=(14, 6), sticky="ew")
        header.grid_columnconfigure(0, weight=1)

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            title_box,
            text="My assigned quotes" if self._is_staff else "Quotes",
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=Theme.TEXT,
        ).pack(anchor="w")

        self._stats_label = ctk.CTkLabel(
            title_box,
            text="Loading your quotes…",
            font=ctk.CTkFont(size=12),
            text_color=Theme.MUTED_TEXT,
        )
        self._stats_label.pack(anchor="w")

        self._refresh_btn = ctk.CTkButton(
            header,
            text="Refresh",
            width=90,
            height=32,
            command=self._load_quotes,
            fg_color="#2196F3",
            hover_color="#1976D2",
        )
        self._refresh_btn.grid(row=0, column=1, sticky="e")
        self._add_tooltip(self._refresh_btn, "Get the latest quotes (F5)")

        tools = ctk.CTkFrame(self._list_panel, fg_color="transparent")
        tools.grid(row=1, column=0, padx=15, pady=(4, 6), sticky="ew")
        tools.grid_columnconfigure(0, weight=1)

        self._search_entry = ctk.CTkEntry(
            tools,
            placeholder_text="Search name, email or reference…",
            height=34,
        )
        self._search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 6))
        self._search_entry.bind("<KeyRelease>", self._on_search_key)
        self._search_entry.bind("<Escape>", self._clear_search)

        self._sort_menu = ctk.CTkOptionMenu(
            tools,
            values=self.SORT_OPTIONS,
            width=140,
            height=34,
            command=self._on_sort_change,
            fg_color=Theme.PANEL_ALT,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER,
        )
        self._sort_menu.set(self._sort_mode)
        self._sort_menu.grid(row=0, column=1)

        self._filter_bar = ctk.CTkFrame(self._list_panel, fg_color="transparent")
        self._filter_bar.grid(row=2, column=0, padx=12, pady=(0, 4), sticky="ew")
        self._build_filter_chips()

        self._result_hint = ctk.CTkLabel(
            self._list_panel,
            text="",
            font=ctk.CTkFont(size=11),
            text_color=Theme.MUTED_TEXT,
        )
        self._result_hint.grid(row=3, column=0, padx=16, pady=(0, 2), sticky="w")

        self._quote_list = ctk.CTkScrollableFrame(
            self._list_panel, fg_color="transparent", corner_radius=0
        )
        self._quote_list.grid(row=4, column=0, sticky="nsew", padx=10, pady=(0, 12))
        self._quote_list.grid_columnconfigure(0, weight=1)

    def _build_filter_chips(self):
        for child in self._filter_bar.winfo_children():
            child.destroy()
        self._filter_buttons = {}

        for i, name in enumerate(["All"] + self.STATUS_OPTIONS):
            btn = ctk.CTkButton(
                self._filter_bar,
                text=name,
                height=26,
                width=0,
                corner_radius=13,
                font=ctk.CTkFont(size=11),
                command=lambda n=name: self._set_status_filter(n),
            )
            btn.grid(row=0, column=i, padx=3, sticky="w")
            self._filter_buttons[name] = btn

        self._paint_filter_chips()

    def _paint_filter_chips(self):
        for name, btn in self._filter_buttons.items():
            count = (
                len(self._quotes)
                if name == "All"
                else sum(1 for q in self._quotes if q.get("status") == name)
            )
            active = name == self._active_status_filter
            accent = self.STATUS_COLORS.get(name, Theme.ACCENT)
            btn.configure(
                text=f"{name} ({count})",
                fg_color=accent if active else Theme.PANEL_ALT,
                hover_color=accent if active else Theme.PANEL_ALT,
                text_color="#1a1a1a" if active else Theme.MUTED_TEXT,
            )

    def _setup_details_panel(self):
        self._details_panel = ctk.CTkFrame(self, corner_radius=12, fg_color=Theme.PANEL)
        self._details_panel.grid(row=0, column=1, sticky="nsew", padx=(6, 0), pady=(0, 2))
        self._details_panel.grid_columnconfigure(0, weight=1)
        self._details_panel.grid_rowconfigure(0, weight=1)

        self._empty_state = ctk.CTkFrame(self._details_panel, fg_color="transparent")
        self._empty_state.grid(row=0, column=0, sticky="nsew")
        self._empty_state.grid_columnconfigure(0, weight=1)
        self._empty_state.grid_rowconfigure(0, weight=1)

        inner = ctk.CTkFrame(self._empty_state, fg_color="transparent")
        inner.grid(row=0, column=0)

        ctk.CTkLabel(
            inner,
            text="Pick a quote to get started",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=Theme.TEXT,
        ).pack(pady=(0, 6))
        ctk.CTkLabel(
            inner,
            text=(
                "Choose one of your assigned quotes on the left to read it,\n"
                "add your update and send it back for review."
                if self._is_staff
                else "Choose a quote on the left to see the customer's\n"
                     "details, update its status, assign it or reply."
            ),
            font=ctk.CTkFont(size=13),
            justify="center",
            text_color=Theme.MUTED_TEXT,
        ).pack()

        self._details_frame = ctk.CTkScrollableFrame(self._details_panel, fg_color="transparent")
        self._details_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=14)
        self._details_frame.grid_columnconfigure(1, weight=1)
        self._details_frame.grid_remove()

    # ------------------------------------------------------------------ data

    def _get_collection(self):
        """Get the quotes collection."""
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

    def _load_quotes(self, event=None):
        if self._is_destroyed:
            return
            
        if not self._mongodb or not self._mongodb.is_connected:
            self._show_list_message(
                "We can't reach the quotes right now",
                "Check your internet connection, then press Refresh.",
                error=True,
            )
            self._toast("Not connected — quotes couldn't be loaded.", "error")
            return

        self._refresh_btn.configure(state="disabled", text="Loading…")
        self._show_list_message("Loading quotes…", "This only takes a moment.")
        self.update_idletasks()

        try:
            collection = self._get_collection()
            if collection is None:
                self._show_list_message(
                    "No quotes database found",
                    "Please check your MongoDB connection.",
                    error=True,
                )
                self._toast("Couldn't find quotes collection.", "error")
                self._refresh_btn.configure(state="normal", text="Refresh")
                return

            self._quotes = list(collection.find().sort("createdAt", -1).limit(100))
            print(f"✅ Loaded {len(self._quotes)} quotes")

            for quote in self._quotes:
                if "_id" in quote:
                    quote["_id"] = str(quote["_id"])
                quote["status"] = self._map_mongo_to_display(quote.get("status"))
                if not quote.get("items"):
                    quote["items"] = []

            if self._is_staff and self._current_username:
                me = self._current_username.lower()
                self._quotes = [
                    q for q in self._quotes
                    if self._is_assigned_to_user(q, me)
                ]
                print(f"👤 Staff {me} sees {len(self._quotes)} assigned quotes")

            self._load_employee_names()

            previous = self._selected_quote_id
            self._render_quote_list()
            self._update_stats()

            if not self._quotes:
                if self._is_staff:
                    self._toast("No quotes assigned to you yet.")
                else:
                    self._toast("No quotes found.")
            else:
                self._toast(f"Showing {len(self._quotes)} quotes.", "success")

            target = None
            if previous:
                target = next(
                    (q for q in self._quotes if q.get("reference") == previous), None
                )
            if target is None and self._visible_quotes:
                target = self._visible_quotes[0]
            if target is not None:
                self._select_quote(target, confirm_unsaved=False)

        except Exception as e:
            self._show_list_message(
                "Something went wrong loading quotes",
                f"{e}\n\nPress Refresh to try again.",
                error=True,
            )
            self._toast("Couldn't load quotes. Please try again.", "error")
            import traceback
            traceback.print_exc()
        finally:
            self._refresh_btn.configure(state="normal", text="Refresh")

    def _is_assigned_to_user(self, quote: Dict[str, Any], username: str) -> bool:
        """Check if a quote is assigned to the given username."""
        assigned_to = quote.get("assigned_to")
        if not assigned_to:
            return False
        
        if isinstance(assigned_to, dict):
            assigned_username = str(assigned_to.get("username", "")).lower()
            assigned_name = str(assigned_to.get("name", "")).lower()
            return assigned_username == username or assigned_name == username
        
        return str(assigned_to).lower() == username

    def _load_employee_names(self):
        """
        Load employee names and cache their data.
        Uses multiple lookup methods to find user accounts.
        """
        if self._is_destroyed:
            return
        
        # Clear cache to force refresh
        self._employee_cache = {}
        self._employee_names = []
            
        try:
            employees_collection = self._mongodb.get_collection("employees")
            employees = employees_collection.find({})
            users_collection = self._mongodb.get_collection("users")
            
            # Get all users for lookup
            all_users = list(users_collection.find({}))
            user_by_full_name = {}
            user_by_employee_id = {}
            user_by_username = {}
            user_by_email = {}
            
            for user in all_users:
                full_name = user.get("full_name")
                if full_name:
                    user_by_full_name[full_name] = user
                    print(f"🔍 User by full_name: {full_name} -> {user.get('username')}")
                
                employee_id = user.get("employee_id")
                if employee_id is not None:
                    user_by_employee_id[str(employee_id)] = user
                    print(f"🔍 User by employee_id: {employee_id} -> {user.get('username')}")
                
                username = user.get("username")
                if username:
                    user_by_username[username] = user
                
                email = user.get("email")
                if email:
                    user_by_email[email] = user
            
            print(f"📊 Found {len(all_users)} users in MongoDB")
            
            for emp in employees:
                full_name = emp.get("full_name")
                if full_name:
                    employee_id = emp.get("employee_id")
                    email = emp.get("email")
                    
                    employee_data = {
                        "employee_id": employee_id,
                        "full_name": full_name,
                        "first_name": emp.get("first_name", ""),
                        "surname": emp.get("surname", ""),
                        "email": email,
                        "has_account": False,
                        "username": None,
                        "role": None
                    }
                    
                    # Try multiple ways to find the user
                    user = None
                    
                    # 1. Try by full_name (most reliable since both collections have it)
                    user = user_by_full_name.get(full_name)
                    if user:
                        print(f"🔍 Found user by full_name for {full_name}")
                    
                    # 2. Try by employee_id
                    if not user and employee_id is not None:
                        user = user_by_employee_id.get(str(employee_id))
                        if user:
                            print(f"🔍 Found user by employee_id for {full_name}")
                    
                    # 3. Try by email
                    if not user and email:
                        user = user_by_email.get(email)
                        if user:
                            print(f"🔍 Found user by email for {full_name}")
                    
                    # 4. Try by username (email)
                    if not user and email:
                        user = user_by_username.get(email)
                        if user:
                            print(f"🔍 Found user by username for {full_name}")
                    
                    if user:
                        actual_username = user.get("username")
                        employee_data["username"] = actual_username
                        employee_data["role"] = user.get("role")
                        employee_data["has_account"] = True
                        print(f"✅ Found user for {full_name}: {actual_username}")
                    else:
                        employee_data["has_account"] = False
                        if email:
                            employee_data["username"] = email
                        else:
                            employee_data["username"] = full_name.lower().replace(" ", ".")
                        print(f"⚠️ No user account for {full_name}, using: {employee_data['username']}")
                    
                    self._employee_cache[full_name] = employee_data
                    
                    if employee_id is not None:
                        self._employee_cache[str(employee_id)] = employee_data
                    
            # Get employee names from the cache keys that are strings (full names)
            self._employee_names = sorted([
                k for k in self._employee_cache.keys() 
                if isinstance(k, str) and not k.isdigit() and not k.startswith('6a') and not k.startswith('6')
            ])
            
            has_account_count = sum(1 for e in self._employee_cache.values() if isinstance(e, dict) and e.get('has_account'))
            print(f"✅ Loaded {len(self._employee_names)} employees, {has_account_count} with user accounts")
            print(f"📋 Employee names: {self._employee_names}")
            
        except Exception as e:
            print(f"Could not load employees: {e}")
            import traceback
            traceback.print_exc()
            self._employee_names = []

    # ------------------------------------------------------------- list view

    def _show_list_message(self, title: str, subtitle: str = "", error: bool = False):
        if self._is_destroyed:
            return
            
        for widget in self._quote_list.winfo_children():
            widget.destroy()
        self._quote_cards = {}

        ctk.CTkLabel(
            self._quote_list,
            text=title,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=Theme.DANGER if error else Theme.TEXT,
            wraplength=280,
            justify="center",
        ).pack(pady=(28, 4))

        if subtitle:
            ctk.CTkLabel(
                self._quote_list,
                text=subtitle,
                font=ctk.CTkFont(size=12),
                text_color=Theme.MUTED_TEXT,
                wraplength=280,
                justify="center",
            ).pack(pady=(0, 20))

    def _sorted(self, quotes: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        mode = self._sort_mode
        if mode == "Customer A–Z":
            return sorted(quotes, key=lambda q: str(q.get("customerName", "")).lower())
        if mode == "Status":
            order = {s: i for i, s in enumerate(self.STATUS_OPTIONS)}
            return sorted(quotes, key=lambda q: order.get(q.get("status", "Pending"), 99))
        reverse = mode == "Newest first"
        return sorted(quotes, key=lambda q: str(q.get("createdAt", "")), reverse=reverse)

    def _render_quote_list(self, filter_text: str = ""):
        if self._is_destroyed:
            return
            
        for widget in self._quote_list.winfo_children():
            widget.destroy()
        self._quote_cards = {}

        quotes = self._quotes
        if self._active_status_filter != "All":
            quotes = [q for q in quotes if q.get("status") == self._active_status_filter]

        text = (filter_text or "").strip().lower()
        if text:
            quotes = [
                q
                for q in quotes
                if text in str(q.get("reference", "")).lower()
                or text in str(q.get("customerName", "")).lower()
                or text in str(q.get("email", "")).lower()
                or text in str(q.get("assigned_to", "")).lower()
            ]

        quotes = self._sorted(quotes)
        self._visible_quotes = quotes
        self._paint_filter_chips()

        if not quotes:
            if text:
                self._show_list_message(
                    f'No quotes match "{filter_text.strip()}"',
                    "Try a different name, email or reference — or clear the search box.",
                )
            elif self._active_status_filter != "All":
                self._show_list_message(
                    f"No {self._active_status_filter.lower()} quotes",
                    "Choose “All” above to see every quote.",
                )
            else:
                if self._is_staff:
                    self._show_list_message(
                        "No quotes assigned to you yet",
                        "When a manager assigns you a quote, it will show up here.",
                    )
                else:
                    self._show_list_message(
                        "No quotes yet",
                        "When a customer sends a request, it will show up here.",
                    )
            self._result_hint.configure(text="")
            return

        self._result_hint.configure(
            text=f"Showing {len(quotes)} of {len(self._quotes)} quotes"
        )

        for quote in quotes:
            self._create_quote_item(quote)

        self._highlight_selected()

    def _create_quote_item(self, quote: Dict[str, Any]):
        frame = ctk.CTkFrame(self._quote_list, corner_radius=10, fg_color=("gray95", "gray12"))
        frame.pack(fill="x", pady=4, padx=2)
        frame.grid_columnconfigure(0, weight=1)

        status = quote.get("status", "Pending")
        status_color = self.STATUS_COLORS.get(status, "#9E9E9E")

        ctk.CTkLabel(
            frame,
            text=quote.get("reference", "No reference"),
            font=ctk.CTkFont(size=13, weight="bold"),
            anchor="w",
            text_color=Theme.TEXT,
        ).grid(row=0, column=0, padx=(14, 5), pady=(8, 0), sticky="w")

        ctk.CTkLabel(
            frame,
            text=f"● {status}",
            text_color=status_color,
            font=ctk.CTkFont(size=11, weight="bold"),
        ).grid(row=0, column=1, padx=(5, 14), pady=(8, 0), sticky="e")

        ctk.CTkLabel(
            frame,
            text=quote.get("customerName") or "Unknown customer",
            font=ctk.CTkFont(size=13),
            anchor="w",
            text_color=Theme.TEXT,
        ).grid(row=1, column=0, columnspan=2, padx=14, pady=(1, 1), sticky="w")

        items = quote.get("items", [])
        bits = [quote.get("email") or "No email", f"{len(items)} item{'s' if len(items) != 1 else ''}"]
        
        assigned_to = quote.get("assigned_to")
        if assigned_to:
            if isinstance(assigned_to, dict):
                assigned_name = assigned_to.get("name") or assigned_to.get("username", "")
            else:
                assigned_name = str(assigned_to)
            if assigned_name:
                bits.append(f"with {assigned_name}")
        
        date_str = self._format_date(quote.get("createdAt"))
        if date_str:
            bits.append(date_str)

        ctk.CTkLabel(
            frame,
            text="  ·  ".join(bits),
            font=ctk.CTkFont(size=11),
            text_color=Theme.MUTED_TEXT,
            anchor="w",
            wraplength=320,
            justify="left",
        ).grid(row=2, column=0, columnspan=2, padx=14, pady=(0, 9), sticky="w")

        def select(_event=None, q=quote):
            self._select_quote(q)

        frame.bind("<Button-1>", select)
        for child in frame.winfo_children():
            child.bind("<Button-1>", select)
            child.configure(cursor="hand2")
        frame.configure(cursor="hand2")

        frame.bind("<Enter>", lambda e, f=frame: self._hover(f, True))
        frame.bind("<Leave>", lambda e, f=frame: self._hover(f, False))

        self._quote_cards[quote.get("reference", "")] = frame

    def _hover(self, frame, entering: bool):
        if getattr(frame, "_is_selected", False):
            return
        frame.configure(fg_color=("gray88", "gray20") if entering else ("gray95", "gray12"))

    def _highlight_selected(self):
        for ref, frame in self._quote_cards.items():
            selected = ref and ref == self._selected_quote_id
            frame._is_selected = selected
            frame.configure(
                fg_color=("gray86", "gray23") if selected else ("gray95", "gray12"),
                border_width=2 if selected else 0,
                border_color=Theme.ACCENT,
            )

    # ------------------------------------------------------------ search/sort

    def _on_search_key(self, event=None):
        """Handle search key press with debouncing."""
        if self._search_job:
            self.after_cancel(self._search_job)
        self._search_job = self.after(180, self._filter_quotes)

    def _filter_quotes(self):
        """Filter quotes based on search text."""
        self._search_job = None
        self._render_quote_list(self._search_entry.get())

    def _clear_search(self, event=None):
        """Clear search and reset view."""
        self._search_entry.delete(0, "end")
        self._render_quote_list()

    def _focus_search(self, event=None):
        """Focus the search entry."""
        try:
            self._search_entry.focus_set()
        except Exception:
            pass

    def _on_sort_change(self, value: str):
        self._sort_mode = value
        self._render_quote_list(self._search_entry.get())

    def _set_status_filter(self, name: str):
        self._active_status_filter = name
        self._render_quote_list(self._search_entry.get())

    # ---------------------------------------------------------- details view

    def _select_quote(self, quote: Dict[str, Any], confirm_unsaved: bool = True):
        if self._is_destroyed:
            return
            
        if confirm_unsaved and self._has_unsaved_reply():
            keep = messagebox.askyesno(
                "Unsaved reply",
                "You've typed a reply that hasn't been sent yet.\n\n"
                "Leave this quote and discard it?",
            )
            if not keep:
                return

        self._selected_quote = quote
        self._selected_quote_id = quote.get("reference")
        self._show_quote_details(quote)
        self._highlight_selected()

    def _has_unsaved_reply(self) -> bool:
        try:
            if self._reply_text is None or not self._reply_text.winfo_exists():
                return False
            return self._reply_text.get("1.0", "end-1c").strip() != self._loaded_reply.strip()
        except Exception:
            return False

    def _show_quote_details(self, quote: Dict[str, Any]):
        if self._is_destroyed:
            return
            
        self._empty_state.grid_remove()
        self._details_frame.grid()

        for widget in self._details_frame.winfo_children():
            widget.destroy()

        row = 0

        header = ctk.CTkFrame(self._details_frame, fg_color="transparent")
        header.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 4))
        header.grid_columnconfigure(0, weight=1)
        row += 1

        title_box = ctk.CTkFrame(header, fg_color="transparent")
        title_box.grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            title_box,
            text=quote.get("reference", "No reference"),
            font=ctk.CTkFont(size=20, weight="bold"),
            text_color=Theme.TEXT,
        ).pack(anchor="w")

        created = self._format_date(quote.get("createdAt"), long=True)
        ctk.CTkLabel(
            title_box,
            text=f"Received {created}" if created else "Request details",
            font=ctk.CTkFont(size=12),
            text_color=Theme.MUTED_TEXT,
        ).pack(anchor="w")

        status_box = ctk.CTkFrame(header, fg_color="transparent")
        status_box.grid(row=0, column=1, sticky="e")

        ctk.CTkLabel(
            status_box,
            text="Status",
            font=ctk.CTkFont(size=11),
            text_color=Theme.MUTED_TEXT,
        ).pack(anchor="e")

        current_status = quote.get("status", "Pending")
        colour = self.STATUS_COLORS.get(current_status, Theme.ACCENT)

        if self._is_staff:
            self._status_dropdown = None
            ctk.CTkLabel(
                status_box,
                text=f"  {current_status}  ",
                font=ctk.CTkFont(size=13, weight="bold"),
                fg_color=colour,
                text_color="#1a1a1a",
                corner_radius=13,
                height=28,
            ).pack(anchor="e", pady=(2, 0))
        else:
            status_var = ctk.StringVar(value=current_status)
            self._status_dropdown = ctk.CTkOptionMenu(
                status_box,
                values=self.STATUS_OPTIONS,
                variable=status_var,
                command=self._on_status_change,
                width=140,
                fg_color=colour,
                button_color=colour,
                button_hover_color=colour,
                text_color="#1a1a1a",
            )
            self._status_dropdown.pack(anchor="e", pady=(2, 0))

        self._status_help_label = ctk.CTkLabel(
            self._details_frame,
            text=self.STATUS_HELP.get(current_status, ""),
            font=ctk.CTkFont(size=11),
            text_color=Theme.MUTED_TEXT,
            anchor="e",
        )
        self._status_help_label.grid(row=row, column=0, columnspan=2, sticky="e", pady=(0, 8))
        row += 1

        row = self._add_divider(row)

        row = self._add_section_title("Customer", row)
        card = ctk.CTkFrame(self._details_frame, fg_color=("gray95", "gray15"), corner_radius=10)
        card.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 12))
        card.grid_columnconfigure(1, weight=1)
        row += 1

        details = [
            ("Name", quote.get("customerName") or "Not provided"),
            ("Email", quote.get("email") or "Not provided"),
            ("Phone", quote.get("phone") or "Not provided"),
        ]
        if quote.get("company"):
            details.append(("Company", quote["company"]))
        
        assigned_to = quote.get("assigned_to")
        if assigned_to:
            if isinstance(assigned_to, dict):
                assigned_display = assigned_to.get("name") or assigned_to.get("username", "Nobody yet")
            else:
                assigned_display = str(assigned_to)
        else:
            assigned_display = "Nobody yet"
        details.append(("Looked after by", assigned_display))

        for i, (label, value) in enumerate(details):
            ctk.CTkLabel(
                card,
                text=label,
                font=ctk.CTkFont(size=12, weight="bold"),
                anchor="w",
                width=130,
                text_color=Theme.MUTED_TEXT,
            ).grid(row=i, column=0, sticky="w", padx=(14, 8), pady=4)
            ctk.CTkLabel(
                card,
                text=value,
                anchor="w",
                font=ctk.CTkFont(size=13),
                text_color=Theme.TEXT,
                wraplength=380,
                justify="left",
            ).grid(row=i, column=1, sticky="w", padx=(0, 14), pady=4)

        notes = quote.get("notes", "")
        if notes:
            row = self._add_section_title("What the customer said", row)
            notes_frame = ctk.CTkFrame(
                self._details_frame, fg_color=("gray95", "gray15"), corner_radius=10
            )
            notes_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 12))
            notes_frame.grid_columnconfigure(0, weight=1)
            row += 1
            ctk.CTkLabel(
                notes_frame,
                text=notes,
                anchor="w",
                wraplength=520,
                justify="left",
                font=ctk.CTkFont(size=13),
                text_color=Theme.TEXT,
            ).grid(row=0, column=0, padx=14, pady=12, sticky="w")

        if self._is_staff:
            row = self._add_section_title(
                "Your work on this quote",
                row,
                hint="Add your pricing / notes, then send it back for review.",
            )

            work_frame = ctk.CTkFrame(self._details_frame, fg_color="transparent")
            work_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 12))
            work_frame.grid_columnconfigure(0, weight=1)
            row += 1

            self._assign_menu = None

            assigned_by = quote.get("assigned_by") or "your manager"
            ctk.CTkLabel(
                work_frame,
                text=f"Assigned to you by {assigned_by}",
                font=ctk.CTkFont(size=12),
                text_color=Theme.MUTED_TEXT,
                anchor="w",
            ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 6))

            self._work_notes = ctk.CTkTextbox(
                work_frame, height=110, wrap="word", corner_radius=10
            )
            self._work_notes.grid(row=1, column=0, columnspan=2, sticky="ew")
            existing_work = quote.get("staff_notes", "") or ""
            if existing_work:
                self._work_notes.insert("1.0", existing_work)

            self._work_hint = ctk.CTkLabel(
                work_frame,
                text=(
                    "Last saved update is shown above."
                    if existing_work
                    else "Nothing written yet — describe the pricing or work you've done."
                ),
                font=ctk.CTkFont(size=11),
                text_color=Theme.MUTED_TEXT,
                anchor="w",
            )
            self._work_hint.grid(row=2, column=0, sticky="w", pady=(6, 0))

            btn_row = ctk.CTkFrame(work_frame, fg_color="transparent")
            btn_row.grid(row=2, column=1, sticky="e", pady=(6, 0))

            save_btn = ctk.CTkButton(
                btn_row,
                text="Save draft",
                width=110,
                height=34,
                fg_color=Theme.PANEL_ALT,
                hover_color=Theme.ACCENT_HOVER,
                command=lambda q=quote: self._save_staff_update(q, submit=False),
            )
            save_btn.pack(side="left", padx=(0, 8))
            self._add_tooltip(save_btn, "Keep your notes without sending them on")

            submit_btn = ctk.CTkButton(
                btn_row,
                text="Send back for review",
                width=180,
                height=34,
                fg_color="#4CAF50",
                hover_color="#388E3C",
                command=lambda q=quote: self._save_staff_update(q, submit=True),
            )
            submit_btn.pack(side="left")
            self._add_tooltip(
                submit_btn, "Marks the quote “In Review” and notifies your manager"
            )
        else:
            row = self._add_section_title("Who should handle this?", row)

            assign_frame = ctk.CTkFrame(self._details_frame, fg_color="transparent")
            assign_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 12))
            assign_frame.grid_columnconfigure(0, weight=1)
            assign_frame.grid_columnconfigure(1, weight=0)
            row += 1

            employee_options = ["Nobody (unassign)"] + self._employee_names
            self._assign_menu = ctk.CTkOptionMenu(
                assign_frame,
                values=employee_options,
                width=240,
                fg_color=Theme.PANEL_ALT,
                button_color=Theme.ACCENT,
                button_hover_color=Theme.ACCENT_HOVER,
            )
            
            assigned_to = quote.get("assigned_to")
            if assigned_to:
                if isinstance(assigned_to, dict):
                    assigned_name = assigned_to.get("name") or assigned_to.get("username", "")
                else:
                    assigned_name = str(assigned_to)
                if assigned_name and assigned_name in employee_options:
                    self._assign_menu.set(assigned_name)
                else:
                    self._assign_menu.set("Nobody (unassign)")
            else:
                self._assign_menu.set("Nobody (unassign)")
            
            self._assign_menu.grid(row=0, column=0, sticky="w")

            def on_assign_click():
                print("🔄 Assign button clicked!")
                self._assign_quote()

            assign_btn = ctk.CTkButton(
                assign_frame,
                text="Save assignment",
                width=140,
                height=34,
                fg_color="#2196F3",
                hover_color="#1976D2",
                command=on_assign_click,
            )
            assign_btn.grid(row=0, column=1, padx=(10, 0), sticky="w")
            self._add_tooltip(assign_btn, "Assign this quote to a team member")

            if not self._employee_names:
                ctk.CTkLabel(
                    assign_frame,
                    text="No team members available to pick from yet.",
                    font=ctk.CTkFont(size=11),
                    text_color=Theme.MUTED_TEXT,
                ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(4, 0))

            if quote.get("staff_notes"):
                row = self._add_section_title(
                    "Update from the team member",
                    row,
                    hint=self._format_date(quote.get("staff_updated_at"), long=True) or "",
                )
                staff_box = ctk.CTkFrame(
                    self._details_frame, fg_color=("gray95", "gray15"), corner_radius=10
                )
                staff_box.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 12))
                staff_box.grid_columnconfigure(0, weight=1)
                row += 1
                ctk.CTkLabel(
                    staff_box,
                    text=quote["staff_notes"],
                    anchor="w",
                    wraplength=520,
                    justify="left",
                    font=ctk.CTkFont(size=13),
                    text_color=Theme.TEXT,
                ).grid(row=0, column=0, padx=14, pady=12, sticky="w")

        row = self._add_divider(row)

        items = quote.get("items", [])
        total_qty = sum(item.get("qty", 1) for item in items)
        row = self._add_section_title(
            f"Items requested ({len(items)})",
            row,
            hint=f"{total_qty} units in total" if items else "",
        )

        items_frame = ctk.CTkFrame(self._details_frame, fg_color="transparent")
        items_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        items_frame.grid_columnconfigure(0, weight=2)
        items_frame.grid_columnconfigure(1, weight=0)
        items_frame.grid_columnconfigure(2, weight=3)
        row += 1

        if items:
            for col, header_text in enumerate(["Item", "Qty", "Details"]):
                ctk.CTkLabel(
                    items_frame,
                    text=header_text,
                    font=ctk.CTkFont(size=11, weight="bold"),
                    text_color=Theme.MUTED_TEXT,
                    anchor="w",
                ).grid(row=0, column=col, sticky="w", pady=(0, 4), padx=(0, 8))

            for i, item in enumerate(items, start=1):
                stripe = ("gray96", "gray14") if i % 2 else "transparent"

                ctk.CTkLabel(
                    items_frame,
                    text=item.get("name", "Unnamed item"),
                    anchor="w",
                    font=ctk.CTkFont(size=13),
                    text_color=Theme.TEXT,
                    fg_color=stripe,
                    corner_radius=4,
                    wraplength=200,
                    justify="left",
                ).grid(row=i, column=0, sticky="ew", pady=2, padx=(0, 8))

                ctk.CTkLabel(
                    items_frame,
                    text=f"× {item.get('qty', 1)}",
                    anchor="w",
                    font=ctk.CTkFont(size=13),
                    text_color=Theme.TEXT,
                    fg_color=stripe,
                    corner_radius=4,
                ).grid(row=i, column=1, sticky="ew", pady=2, padx=(0, 8))

                specs = item.get("specs")
                if isinstance(specs, list) and specs:
                    specs_text = " · ".join(str(s) for s in specs)
                elif specs:
                    specs_text = str(specs)
                else:
                    specs_text = "No extra details"

                ctk.CTkLabel(
                    items_frame,
                    text=specs_text,
                    anchor="w",
                    font=ctk.CTkFont(size=11),
                    text_color=Theme.MUTED_TEXT,
                    fg_color=stripe,
                    corner_radius=4,
                    wraplength=260,
                    justify="left",
                ).grid(row=i, column=2, sticky="ew", pady=2)
        else:
            ctk.CTkLabel(
                items_frame,
                text="The customer didn't list any specific items.",
                text_color=Theme.MUTED_TEXT,
                font=ctk.CTkFont(size=13),
                anchor="w",
            ).grid(row=1, column=0, columnspan=3, sticky="w", pady=6)

        row = self._add_divider(row)

        if self._is_staff:
            self._reply_text = None
            self._save_reply_btn = None
            self._reply_hint = None
            self._loaded_reply = quote.get("replyMessage", "") or ""

            row = self._add_section_title(
                "Reply sent to the customer",
                row,
                hint="Only managers send replies.",
            )
            reply_box = ctk.CTkFrame(
                self._details_frame, fg_color=("gray95", "gray15"), corner_radius=10
            )
            reply_box.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 20))
            reply_box.grid_columnconfigure(0, weight=1)
            row += 1
            ctk.CTkLabel(
                reply_box,
                text=self._loaded_reply or "Nothing has been sent to the customer yet.",
                anchor="w",
                wraplength=520,
                justify="left",
                font=ctk.CTkFont(size=13),
                text_color=Theme.TEXT if self._loaded_reply else Theme.MUTED_TEXT,
            ).grid(row=0, column=0, padx=14, pady=12, sticky="w")
            return

        row = self._add_section_title(
            "Reply to the customer",
            row,
            hint="They'll see this with their quote.",
        )

        self._reply_text = ctk.CTkTextbox(self._details_frame, height=110, wrap="word", corner_radius=10)
        self._reply_text.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        row += 1

        self._loaded_reply = quote.get("replyMessage", "") or ""
        if self._loaded_reply:
            self._reply_text.insert("1.0", self._loaded_reply)
        self._reply_text.bind("<KeyRelease>", self._on_reply_typed)
        self._reply_text.bind("<Control-Return>", lambda e, q=quote: self._send_reply(q))

        footer = ctk.CTkFrame(self._details_frame, fg_color="transparent")
        footer.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 20))
        footer.grid_columnconfigure(0, weight=1)
        row += 1

        self._reply_hint = ctk.CTkLabel(
            footer,
            text="Reply saved." if self._loaded_reply else "Nothing sent yet.",
            font=ctk.CTkFont(size=11),
            text_color=Theme.MUTED_TEXT,
            anchor="w",
        )
        self._reply_hint.grid(row=0, column=0, sticky="w")

        self._save_reply_btn = ctk.CTkButton(
            footer,
            text="Send reply",
            command=lambda: self._send_reply(quote),
            fg_color="#4CAF50",
            hover_color="#388E3C",
            height=36,
            width=150,
            state="disabled",
        )
        self._save_reply_btn.grid(row=0, column=1, sticky="e")
        self._add_tooltip(self._save_reply_btn, "Send reply (Ctrl+Enter)")

    def _on_reply_typed(self, event=None):
        if self._is_destroyed:
            return
            
        if not self._save_reply_btn:
            return
        changed = self._has_unsaved_reply()
        self._save_reply_btn.configure(state="normal" if changed else "disabled")
        if self._reply_hint:
            self._reply_hint.configure(
                text="Unsaved changes." if changed else
                ("Reply saved." if self._loaded_reply else "Nothing sent yet.")
            )

    # ------------------------------------------------------------- actions

    def _save_staff_update(self, quote: Dict[str, Any], submit: bool = False):
        """Staff save their work on an assigned quote, optionally handing it back for review."""
        if self._is_destroyed:
            return
            
        if self._work_notes is None:
            return

        notes = self._work_notes.get("1.0", "end-1c").strip()
        if not notes:
            self._toast("Write your update before saving.", "error")
            self._work_notes.focus_set()
            return

        reference = quote.get("reference", "")
        if not reference:
            self._toast("This quote has no reference, so it can't be updated.", "error")
            return

        assigned_by = quote.get("assigned_by") or ""
        reviewer_name = assigned_by if assigned_by else "your manager"

        if submit and not messagebox.askyesno(
            "Send back for review?",
            f"Send {reference} back to {reviewer_name} for review?\n\n"
            "You won't be able to change it again until it's returned to you.",
        ):
            return

        try:
            collection = self._get_collection()
            if collection is None:
                self._toast("Could not find quotes collection.", "error")
                return

            update: Dict[str, Any] = {
                "staff_notes": notes,
                "staff_updated_at": datetime.now(timezone.utc),
                "staff_updated_by": self._current_user_name,
                "updatedAt": datetime.now(timezone.utc),
            }
            
            if submit:
                update["status"] = self.DISPLAY_TO_MONGO["In Review"]
                update["submitted_for_review_at"] = datetime.now(timezone.utc)
                update["submitted_for_review_by"] = self._current_user_name

            result = collection.update_one({"reference": reference}, {"$set": update})
            if not (result.modified_count or result.matched_count):
                self._toast("We couldn't save your update. Please try again.", "error")
                return

            quote["staff_notes"] = notes
            for q in self._quotes:
                if q.get("reference") == reference:
                    q["staff_notes"] = notes
                    if submit:
                        q["status"] = "In Review"
                    break

            if submit:
                self._toast(f"{reference} sent back for review.", "success")
                self._load_quotes()
            else:
                if self._work_hint is not None and self._work_hint.winfo_exists():
                    self._work_hint.configure(text="Draft saved — nobody notified yet.")
                self._toast("Draft saved.", "success")

        except Exception as e:
            self._toast(f"Couldn't save your update: {e}", "error")
            import traceback
            traceback.print_exc()

    def _get_employee_by_name(self, full_name: str) -> Optional[Dict[str, Any]]:
        """
        Get employee dict by full name.
        Uses multiple lookup methods to find the user account.
        """
        try:
            # FIRST: Try to find user by full_name (most reliable)
            users_collection = self._mongodb.get_collection("users")
            user = users_collection.find_one({"full_name": full_name})
            
            if user:
                actual_username = user.get("username")
                # If username contains @, use the local part
                if actual_username and "@" in actual_username:
                    local_part = actual_username.split("@")[0]
                    user_check = users_collection.find_one({"username": local_part})
                    if user_check:
                        actual_username = local_part
                        print(f"✅ Found user by local part for {full_name}: {actual_username}")
                    else:
                        print(f"✅ Found user by full_name for {full_name}: {actual_username}")
                else:
                    print(f"✅ Found user by full_name for {full_name}: {actual_username}")
                
                return {
                    "username": actual_username,
                    "name": full_name,
                    "employee_id": user.get("employee_id"),
                    "role": user.get("role")
                }
            
            # If not found by full_name, get employee and try other methods
            employees_collection = self._mongodb.get_collection("employees")
            employee = employees_collection.find_one({"full_name": full_name})
            
            if not employee:
                print(f"❌ Could not find employee: {full_name}")
                return None
            
            employee_id = employee.get("employee_id")
            email = employee.get("email")
            
            # 2. Try by employee_id
            if employee_id is not None:
                user = users_collection.find_one({"employee_id": employee_id})
                if user:
                    actual_username = user.get("username")
                    print(f"✅ Found user by employee_id for {full_name}: {actual_username}")
                    return {
                        "username": actual_username,
                        "name": full_name,
                        "employee_id": employee_id,
                        "role": user.get("role")
                    }
            
            # 3. Try by email
            if email:
                user = users_collection.find_one({"email": email})
                if user:
                    actual_username = user.get("username")
                    print(f"✅ Found user by email for {full_name}: {actual_username}")
                    return {
                        "username": actual_username,
                        "name": full_name,
                        "employee_id": employee_id,
                        "role": user.get("role")
                    }
            
            # 4. Try by username (email)
            if email:
                user = users_collection.find_one({"username": email})
                if user:
                    actual_username = user.get("username")
                    print(f"✅ Found user by username for {full_name}: {actual_username}")
                    return {
                        "username": actual_username,
                        "name": full_name,
                        "employee_id": employee_id,
                        "role": user.get("role")
                    }
            
            # 5. Try by generated username
            generated = full_name.lower().replace(" ", ".")
            user = users_collection.find_one({"username": generated})
            if user:
                actual_username = user.get("username")
                print(f"✅ Found user by generated username for {full_name}: {actual_username}")
                return {
                    "username": actual_username,
                    "name": full_name,
                    "employee_id": employee_id,
                    "role": user.get("role")
                }
            
            # Fallback: use email or generated
            fallback_username = email if email else full_name.lower().replace(" ", ".")
            print(f"⚠️ No user account for {full_name}, using: {fallback_username}")
            return {
                "username": fallback_username,
                "name": full_name,
                "employee_id": employee_id
            }
            
        except Exception as e:
            print(f"Error finding employee: {e}")
            import traceback
            traceback.print_exc()
            return None

    def _assign_quote(self):
        """Assign the current quote to a team member."""
        if self._is_destroyed:
            return
            
        if not self._selected_quote:
            self._toast("Pick a quote first.", "error")
            return

        reference = self._selected_quote.get("reference", "")
        if not reference:
            self._toast("This quote has no reference, so it can't be updated.", "error")
            return

        selected_name = self._assign_menu.get()
        print(f"📋 Selected from dropdown: '{selected_name}'")
        
        if selected_name == "Nobody (unassign)":
            assigned_to = None
            print(f"📋 Unassigning quote {reference}")
        else:
            assigned_to_dict = self._get_employee_by_name(selected_name)
            if not assigned_to_dict:
                self._toast(f"Could not find employee: {selected_name}", "error")
                return
            assigned_to = assigned_to_dict
            print(f"✅ Found user: {assigned_to.get('name')} (username: {assigned_to.get('username')})")

        try:
            collection = self._get_collection()
            if collection is None:
                self._toast("Could not find quotes collection.", "error")
                return

            # Build the assigned_to object
            if assigned_to:
                assigned_to_obj = {
                    "name": selected_name,
                    "username": assigned_to.get("username"),
                    "employee_id": assigned_to.get("employee_id")
                }
                status = "assigned"
                print(f"📋 Assigning to: {assigned_to_obj}")
            else:
                assigned_to_obj = None
                status = "received"
                print(f"📋 Unassigning quote")

            # Update the quote with the assigned_to object
            update = {
                "$set": {
                    "assigned_to": assigned_to_obj,
                    "assigned_by": self._current_user_name,
                    "status": status,
                    "updatedAt": datetime.now(timezone.utc)
                }
            }
            
            # Add to history if assigned
            if assigned_to:
                update["$push"] = {
                    "history": {
                        "action": "assigned",
                        "by": self._current_user_name,
                        "employee": selected_name,
                        "username": assigned_to.get("username"),
                        "employee_id": assigned_to.get("employee_id"),
                        "time": datetime.now(timezone.utc).isoformat()
                    }
                }

            result = collection.update_one(
                {"reference": reference},
                update
            )

            print(f"📋 Update result: modified_count={result.modified_count}, matched_count={result.matched_count}")

            if result.modified_count > 0 or result.matched_count > 0:
                # Update local cache
                for q in self._quotes:
                    if q.get("reference") == reference:
                        q["assigned_to"] = assigned_to_obj
                        q["status"] = "Assigned" if assigned_to else "Pending"
                        break
                if self._selected_quote and self._selected_quote.get("reference") == reference:
                    self._selected_quote["assigned_to"] = assigned_to_obj
                    self._selected_quote["status"] = "Assigned" if assigned_to else "Pending"
                
                self._render_quote_list(self._search_entry.get())

                if assigned_to:
                    self._toast(f"{reference} is now with {selected_name}.", "success")
                    username = assigned_to.get("username")
                    if username:
                        self._send_notification(
                            username,
                            f"New quote assigned to you: {reference}",
                            "Quote Assignment",
                            reference
                        )
                        print(f"📧 Notification sent to: {username}")
                    
                    # Also verify the quote was updated by fetching it
                    updated_quote = collection.find_one({"reference": reference})
                    if updated_quote:
                        print(f"📋 Verified quote assignment: {updated_quote.get('assigned_to')}")
                    else:
                        print(f"⚠️ Could not verify quote update")
                else:
                    self._toast(f"{reference} is no longer assigned to anyone.", "success")
            else:
                self._toast("We couldn't save that assignment. Please try again.", "error")

        except Exception as e:
            self._toast(f"Couldn't save the assignment: {e}", "error")
            import traceback
            traceback.print_exc()

    def _send_notification(self, recipient: str, message: str, title: str, reference: str = ""):
        """Send a notification to a user."""
        if not recipient:
            return
            
        try:
            if self._notification_controller:
                if hasattr(self._notification_controller, 'notify_user'):
                    self._notification_controller.notify_user(recipient, message, title)
                elif hasattr(self._notification_controller, 'record_activity'):
                    self._notification_controller.record_activity(
                        title,
                        message,
                        "Quote",
                        reference
                    )
                print(f"✅ Notification sent via controller to {recipient}")
                return
        except Exception as e:
            print(f"⚠️ Notification controller error: {e}")
        
        # Direct MongoDB notification
        try:
            notifications = self._mongodb.get_collection("notifications")
            users_collection = self._mongodb.get_collection("users")
            
            # Try to find the user
            user = None
            user_role = "Staff"
            
            # 1. Try exact username
            user = users_collection.find_one({"username": recipient})
            if user:
                print(f"✅ Found user by exact username: {recipient}")
            else:
                # 2. Try by email
                user = users_collection.find_one({"email": recipient})
                if user:
                    print(f"✅ Found user by email: {recipient}")
                else:
                    # 3. Try by full_name
                    user = users_collection.find_one({"full_name": recipient})
                    if user:
                        print(f"✅ Found user by full_name: {recipient}")
                    else:
                        # 4. Try by local part
                        if "@" in recipient:
                            local_part = recipient.split("@")[0]
                            user = users_collection.find_one({"username": local_part})
                            if user:
                                print(f"✅ Found user by local part: {local_part}")
                        else:
                            # 5. Try to find employee and then user
                            employees_collection = self._mongodb.get_collection("employees")
                            employee = employees_collection.find_one({"full_name": recipient})
                            if employee:
                                employee_id = employee.get("employee_id")
                                if employee_id:
                                    user = users_collection.find_one({"employee_id": employee_id})
                                    if user:
                                        print(f"✅ Found user by employee_id: {employee_id}")
            
            if user:
                user_role = user.get("role", "Staff")
                print(f"✅ Found user '{user.get('username')}' with role {user_role}")
            else:
                print(f"⚠️ Could not find user '{recipient}', using default role Staff")
            
            # Create notification
            notification = {
                "recipient": recipient,
                "recipient_role": user_role,
                "title": title,
                "message": message,
                "category": "Quote Assignment",
                "reference": reference,
                "is_read": False,
                "created_at": datetime.now(timezone.utc)
            }
            result = notifications.insert_one(notification)
            print(f"✅ Notification created for {recipient} with ID: {result.inserted_id}")
            
        except Exception as e:
            print(f"⚠️ Could not save notification: {e}")
            import traceback
            traceback.print_exc()

    def _on_status_change(self, new_display_status: str):
        if self._is_destroyed:
            return
            
        if not self._selected_quote:
            return
        if self._status_job:
            self.after_cancel(self._status_job)
        self._status_job = self.after(
            120, lambda: self._update_status_action(self._selected_quote, new_display_status)
        )

    def _update_status_action(self, quote: Dict[str, Any], new_display_status: str):
        self._status_job = None
        
        if self._is_destroyed:
            return
            
        try:
            reference = quote.get("reference", "")
            if not reference:
                self._toast("This quote has no reference, so it can't be updated.", "error")
                return

            previous = quote.get("status", "Pending")
            if previous == new_display_status:
                return

            mongo_status = self.DISPLAY_TO_MONGO.get(new_display_status, "received")
            
            collection = self._get_collection()
            if collection is None:
                self._toast("Could not find quotes collection.", "error")
                return

            collection.update_one(
                {"reference": reference},
                {
                    "$push": {
                        "history": {
                            "action": "status_change",
                            "from": previous,
                            "to": new_display_status,
                            "by": self._current_user_name,
                            "time": datetime.now(timezone.utc).isoformat()
                        }
                    }
                }
            )

            result = collection.update_one(
                {"reference": reference},
                {"$set": {"status": mongo_status, "updatedAt": datetime.now(timezone.utc)}}
            )

            if result.modified_count > 0 or result.matched_count > 0:
                for q in self._quotes:
                    if q.get("reference") == reference:
                        q["status"] = new_display_status
                        break
                quote["status"] = new_display_status

                self._render_quote_list(self._search_entry.get())
                self._update_stats()

                colour = self.STATUS_COLORS.get(new_display_status, Theme.ACCENT)
                if self._status_dropdown and self._status_dropdown.winfo_exists():
                    self._status_dropdown.set(new_display_status)
                    self._status_dropdown.configure(
                        fg_color=colour, button_color=colour, button_hover_color=colour
                    )
                if getattr(self, "_status_help_label", None) and self._status_help_label.winfo_exists():
                    self._status_help_label.configure(
                        text=self.STATUS_HELP.get(new_display_status, "")
                    )

                self._toast(f"{reference} is now “{new_display_status}”.", "success")
            else:
                self._toast("We couldn't change the status. Please try again.", "error")
                if self._status_dropdown and self._status_dropdown.winfo_exists():
                    self._status_dropdown.set(previous)

        except Exception as e:
            self._toast(f"Couldn't change the status: {e}", "error")
            self._load_quotes()

    def _send_reply(self, quote: Dict[str, Any]):
        if self._is_destroyed:
            return
            
        reply = self._reply_text.get("1.0", "end-1c").strip()
        if not reply:
            self._toast("Type a message before sending.", "error")
            self._reply_text.focus_set()
            return

        reference = quote.get("reference", "")
        if not reference:
            self._toast("This quote has no reference, so it can't be updated.", "error")
            return

        if not messagebox.askyesno(
            "Send this reply?",
            f"Send your reply for {reference} to {quote.get('customerName') or 'the customer'}?",
        ):
            return

        try:
            collection = self._get_collection()
            if collection is None:
                self._toast("Could not find quotes collection.", "error")
                return

            collection.update_one(
                {"reference": reference},
                {
                    "$push": {
                        "history": {
                            "action": "replied",
                            "by": self._current_user_name,
                            "message": reply[:100] + ("..." if len(reply) > 100 else ""),
                            "time": datetime.now(timezone.utc).isoformat()
                        }
                    }
                }
            )

            result = collection.update_one(
                {"reference": reference},
                {
                    "$set": {
                        "replyMessage": reply,
                        "repliedAt": datetime.now(timezone.utc),
                        "status": self.DISPLAY_TO_MONGO["Quoted"],
                        "updatedAt": datetime.now(timezone.utc)
                    }
                }
            )

            if result.modified_count > 0 or result.matched_count > 0:
                for q in self._quotes:
                    if q.get("reference") == reference:
                        q["replyMessage"] = reply
                        q["status"] = "Quoted"
                        break
                quote["replyMessage"] = reply
                quote["status"] = "Quoted"
                self._loaded_reply = reply
                self._on_reply_typed()
                self._render_quote_list(self._search_entry.get())
                self._toast(f"Reply sent for {reference}.", "success")
            else:
                self._toast("We couldn't send that reply. Please try again.", "error")
        except Exception as e:
            self._toast(f"Couldn't send the reply: {e}", "error")
            import traceback
            traceback.print_exc()

    # -------------------------------------------------------------- helpers

    def _add_divider(self, row: int) -> int:
        ctk.CTkFrame(self._details_frame, height=1, fg_color=("gray80", "gray28")).grid(
            row=row, column=0, columnspan=2, sticky="ew", pady=10
        )
        return row + 1

    def _add_section_title(self, text: str, row: int, hint: str = "") -> int:
        box = ctk.CTkFrame(self._details_frame, fg_color="transparent")
        box.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        box.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            box,
            text=text,
            font=ctk.CTkFont(size=14, weight="bold"),
            text_color=Theme.TEXT,
            anchor="w",
        ).grid(row=0, column=0, sticky="w")

        if hint:
            ctk.CTkLabel(
                box,
                text=hint,
                font=ctk.CTkFont(size=11),
                text_color=Theme.MUTED_TEXT,
            ).grid(row=0, column=1, sticky="e")
        return row + 1

    def _add_tooltip(self, widget, text: str):
        tip = {"window": None}

        def show(_event=None):
            if tip["window"] is not None:
                return
            try:
                x = widget.winfo_rootx() + 10
                y = widget.winfo_rooty() + widget.winfo_height() + 6
                win = ctk.CTkToplevel(widget)
                win.overrideredirect(True)
                win.geometry(f"+{x}+{y}")
                win.attributes("-topmost", True)
                ctk.CTkLabel(
                    win,
                    text=text,
                    font=ctk.CTkFont(size=11),
                    fg_color=("gray90", "gray20"),
                    corner_radius=6,
                    padx=8,
                    pady=4,
                ).pack()
                tip["window"] = win
            except Exception:
                tip["window"] = None

        def hide(_event=None):
            if tip["window"] is not None:
                try:
                    tip["window"].destroy()
                except Exception:
                    pass
                tip["window"] = None

        widget.bind("<Enter>", show)
        widget.bind("<Leave>", hide)
        widget.bind("<Button-1>", hide, add="+")

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
        self._paint_filter_chips()
        if not self._quotes:
            self._stats_label.configure(text="No quotes yet")
            return

        needs_action = sum(
            1 for q in self._quotes if q.get("status") in ("Pending", "In Review")
        )
        self._stats_label.configure(
            text=f"{len(self._quotes)} quotes · {needs_action} still need attention"
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
        self.after(6000, lambda: self._status_bar.configure(text=""))

    @staticmethod
    def _map_mongo_to_display(mongo_status: Any) -> str:
        if not mongo_status:
            return "Pending"
        return QuoteManagementView.MONGO_TO_DISPLAY.get(str(mongo_status).lower(), "Pending")

    @staticmethod
    def _map_display_to_mongo(display_status: str) -> str:
        return QuoteManagementView.DISPLAY_TO_MONGO.get(display_status, "received")

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
        self._visible_quotes = []
        self._selected_quote = None
        self._employee_names = []
        self._quote_cards = {}
        self._filter_buttons = {}
        
        super().destroy()

    def refresh(self):
        if self._check_authorization():
            self._load_quotes()
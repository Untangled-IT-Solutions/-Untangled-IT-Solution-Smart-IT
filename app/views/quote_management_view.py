# app/views/quote_management_view.py
"""Quote Management View - Reads directly from MongoDB."""

import customtkinter as ctk
from tkinter import messagebox
from datetime import datetime, timezone
import json
from typing import Optional, Dict, Any, List

from app.services.mongodb_service import MongoDBService
from app.utils.theme import Theme


class QuoteManagementView(ctk.CTkFrame):
    """Quote management that reads directly from MongoDB."""

    STATUS_OPTIONS = ["Pending", "In Review", "Quoted", "Closed"]
    STATUS_COLORS = {
        "Pending": "#FFC107",
        "In Review": "#FF9800", 
        "Quoted": "#4CAF50",
        "Closed": "#9E9E9E"
    }
    
    # Status mapping - both directions
    DISPLAY_TO_MONGO = {
        "Pending": "received",
        "In Review": "in_review",
        "Quoted": "quoted",
        "Closed": "closed"
    }
    
    MONGO_TO_DISPLAY = {
        "received": "Pending",
        "in_review": "In Review",
        "quoted": "Quoted",
        "closed": "Closed"
    }

    def __init__(
        self,
        master,
        mongodb_service: MongoDBService,
        work_controller,
        people_controller,
        notification_controller=None,
    ):
        super().__init__(master, fg_color=Theme.BG, corner_radius=0)
        self._mongodb = mongodb_service
        self._work_controller = work_controller
        self._people_controller = people_controller
        self._notification_controller = notification_controller
        self._quotes: List[Dict[str, Any]] = []
        self._selected_quote: Optional[Dict[str, Any]] = None
        self._selected_quote_id: Optional[str] = None
        self._status_dropdown = None
        self._reply_text = None
        self._setup_ui()
        self._load_quotes()

    def _setup_ui(self):
        """Setup the quote management UI."""
        self.grid_columnconfigure(0, weight=2)
        self.grid_columnconfigure(1, weight=3)
        self.grid_rowconfigure(0, weight=1)
        self.grid_rowconfigure(1, weight=0)

        # Left panel - Quote list
        self._setup_list_panel()
        
        # Right panel - Quote details
        self._setup_details_panel()
        
        # Status bar
        self._status_bar = ctk.CTkLabel(
            self,
            text="",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        self._status_bar.grid(row=1, column=0, columnspan=2, sticky="ew", padx=15, pady=5)

    def _setup_list_panel(self):
        """Setup the left panel with quote list."""
        self._list_panel = ctk.CTkFrame(self, corner_radius=10, fg_color=Theme.PANEL)
        self._list_panel.grid(row=0, column=0, sticky="nsew", padx=(0, 5))
        self._list_panel.grid_columnconfigure(0, weight=1)
        self._list_panel.grid_rowconfigure(4, weight=1)

        # Header with refresh button
        header_frame = ctk.CTkFrame(self._list_panel, fg_color="transparent")
        header_frame.grid(row=0, column=0, padx=15, pady=10, sticky="ew")
        header_frame.grid_columnconfigure(0, weight=1)

        title_label = ctk.CTkLabel(
            header_frame,
            text="📋 Quotes from MongoDB",
            font=ctk.CTkFont(size=16, weight="bold"),
            text_color=Theme.TEXT
        )
        title_label.grid(row=0, column=0, sticky="w")

        # Refresh button
        refresh_btn = ctk.CTkButton(
            header_frame,
            text="🔄 Refresh",
            width=100,
            height=30,
            command=self._load_quotes,
            fg_color="#2196F3",
            hover_color="#1976D2"
        )
        refresh_btn.grid(row=0, column=1)

        # Search
        search_frame = ctk.CTkFrame(self._list_panel, fg_color="transparent")
        search_frame.grid(row=1, column=0, padx=15, pady=5, sticky="ew")
        search_frame.grid_columnconfigure(0, weight=1)

        self._search_entry = ctk.CTkEntry(
            search_frame,
            placeholder_text="🔍 Search by reference, customer, or email...",
            height=32
        )
        self._search_entry.grid(row=0, column=0, sticky="ew", padx=(0, 5))
        self._search_entry.bind("<KeyRelease>", self._filter_quotes)

        # Stats
        self._stats_label = ctk.CTkLabel(
            self._list_panel,
            text="Loading...",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        self._stats_label.grid(row=2, column=0, padx=15, pady=(0, 5), sticky="w")

        # Quote list
        self._quote_list = ctk.CTkScrollableFrame(
            self._list_panel,
            fg_color="transparent",
            corner_radius=0
        )
        self._quote_list.grid(row=3, column=0, sticky="nsew", padx=10, pady=5)
        self._quote_list.grid_columnconfigure(0, weight=1)

    def _setup_details_panel(self):
        """Setup the right panel with quote details."""
        self._details_panel = ctk.CTkFrame(self, corner_radius=10, fg_color=Theme.PANEL)
        self._details_panel.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        self._details_panel.grid_columnconfigure(0, weight=1)
        self._details_panel.grid_rowconfigure(0, weight=1)

        # No selection message
        self._no_selection_label = ctk.CTkLabel(
            self._details_panel,
            text="👈 Select a quote from the list",
            font=ctk.CTkFont(size=14),
            text_color="gray"
        )
        self._no_selection_label.grid(row=0, column=0, padx=20, pady=20)

        # Details frame (hidden initially)
        self._details_frame = ctk.CTkScrollableFrame(
            self._details_panel,
            fg_color="transparent"
        )
        self._details_frame.grid(row=0, column=0, sticky="nsew", padx=20, pady=10)
        self._details_frame.grid_columnconfigure(1, weight=1)
        self._details_frame.grid_remove()

    def _load_quotes(self):
        """Load quotes directly from MongoDB."""
        if not self._mongodb or not self._mongodb.is_connected:
            self._update_status("❌ MongoDB not connected")
            for widget in self._quote_list.winfo_children():
                widget.destroy()
            label = ctk.CTkLabel(
                self._quote_list,
                text="⚠️ MongoDB is not connected.\nPlease check your MongoDB connection.",
                text_color=Theme.DANGER,
                font=ctk.CTkFont(size=14)
            )
            label.pack(pady=20)
            return
            
        try:
            self._update_status("🔄 Loading quotes from MongoDB...")
            self._quotes = self._mongodb.get_quotes(limit=200)
            
            # Clean up quotes for display
            for quote in self._quotes:
                if "_id" in quote:
                    quote["_id"] = str(quote["_id"])
                # Map MongoDB status to display status
                if "status" in quote:
                    quote["status"] = self._map_mongo_to_display(quote["status"])
                else:
                    quote["status"] = "Pending"
                if "items" not in quote or not quote["items"]:
                    quote["items"] = []
            
            selected_ref = self._selected_quote_id
            
            self._render_quote_list()
            self._update_stats()
            
            if self._quotes:
                self._update_status(f"✅ Loaded {len(self._quotes)} quotes from MongoDB")
            else:
                self._update_status("ℹ️ No quotes found in MongoDB.")
            
            # Restore selection
            if selected_ref:
                for quote in self._quotes:
                    if quote.get('reference') == selected_ref:
                        self._select_quote(quote)
                        break
                else:
                    if self._quotes:
                        self._select_quote(self._quotes[0])
            elif self._quotes and not self._selected_quote:
                self._select_quote(self._quotes[0])
                
        except Exception as e:
            self._update_status(f"❌ Error loading quotes: {str(e)}")
            for widget in self._quote_list.winfo_children():
                widget.destroy()
            label = ctk.CTkLabel(
                self._quote_list,
                text=f"❌ Error loading quotes: {str(e)}",
                text_color=Theme.DANGER,
                font=ctk.CTkFont(size=13)
            )
            label.pack(pady=20)

    def _render_quote_list(self, filter_text: str = ""):
        """Render the list of quotes."""
        for widget in self._quote_list.winfo_children():
            widget.destroy()

        filtered_quotes = self._quotes
        if filter_text:
            filter_lower = filter_text.lower()
            filtered_quotes = [
                q for q in self._quotes
                if filter_lower in q.get('reference', '').lower()
                or filter_lower in q.get('customerName', '').lower()
                or filter_lower in q.get('email', '').lower()
            ]

        if not filtered_quotes:
            label = ctk.CTkLabel(
                self._quote_list,
                text="No quotes found",
                text_color="gray",
                font=ctk.CTkFont(size=13)
            )
            label.pack(pady=20)
            return

        for quote in filtered_quotes:
            self._create_quote_item(quote)

    def _create_quote_item(self, quote: Dict[str, Any]):
        """Create a single quote list item."""
        frame = ctk.CTkFrame(
            self._quote_list,
            corner_radius=8,
            fg_color=("gray95", "gray12")
        )
        frame.pack(fill="x", pady=3)
        frame.grid_columnconfigure(0, weight=1)

        ref_label = ctk.CTkLabel(
            frame,
            text=quote.get('reference', 'N/A'),
            font=ctk.CTkFont(weight="bold"),
            anchor="w",
            text_color=Theme.TEXT
        )
        ref_label.grid(row=0, column=0, padx=(12, 5), pady=(5, 0), sticky="w")

        status = quote.get('status', 'Pending')
        status_color = self.STATUS_COLORS.get(status, "#9E9E9E")
        
        status_label = ctk.CTkLabel(
            frame,
            text=f"● {status}",
            text_color=status_color,
            font=ctk.CTkFont(size=11)
        )
        status_label.grid(row=0, column=1, padx=(5, 12), pady=(5, 0), sticky="e")

        customer_label = ctk.CTkLabel(
            frame,
            text=f"👤 {quote.get('customerName', 'Unknown')}",
            font=ctk.CTkFont(size=12),
            anchor="w",
            text_color=Theme.TEXT
        )
        customer_label.grid(row=1, column=0, columnspan=2, padx=12, pady=(0, 2), sticky="w")

        items = quote.get('items', [])
        info_text = f"📧 {quote.get('email', 'N/A')}  |  📦 {len(items)} items"
        
        created_at = quote.get('createdAt', '')
        if created_at:
            try:
                if isinstance(created_at, datetime):
                    date_str = created_at.strftime("%Y-%m-%d")
                else:
                    date_str = str(created_at)[:10] if len(str(created_at)) >= 10 else str(created_at)
                info_text += f"  |  📅 {date_str}"
            except:
                pass

        info_label = ctk.CTkLabel(
            frame,
            text=info_text,
            font=ctk.CTkFont(size=10),
            text_color="gray",
            anchor="w"
        )
        info_label.grid(row=2, column=0, columnspan=2, padx=12, pady=(0, 5), sticky="w")

        frame.bind("<Button-1>", lambda e, q=quote: self._select_quote(q))
        for child in frame.winfo_children():
            child.bind("<Button-1>", lambda e, q=quote: self._select_quote(q))

        def on_enter(e, f=frame):
            f.configure(fg_color=("gray85", "gray20"))
        def on_leave(e, f=frame):
            f.configure(fg_color=("gray95", "gray12"))
        frame.bind("<Enter>", on_enter)
        frame.bind("<Leave>", on_leave)

    def _filter_quotes(self, event=None):
        filter_text = self._search_entry.get()
        self._render_quote_list(filter_text)

    def _select_quote(self, quote: Dict[str, Any]):
        """Select a quote and show its details."""
        self._selected_quote = quote
        self._selected_quote_id = quote.get('reference')
        self._show_quote_details(quote)

    def _show_quote_details(self, quote: Dict[str, Any]):
        """Show detailed view with full interaction capabilities."""
        self._no_selection_label.grid_remove()
        self._details_frame.grid()
        
        for widget in self._details_frame.winfo_children():
            widget.destroy()

        row = 0

        header_frame = ctk.CTkFrame(self._details_frame, fg_color="transparent")
        header_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 15))
        header_frame.grid_columnconfigure(0, weight=1)
        row += 1

        ref_label = ctk.CTkLabel(
            header_frame,
            text=f"📋 {quote.get('reference', 'N/A')}",
            font=ctk.CTkFont(size=18, weight="bold"),
            text_color=Theme.TEXT
        )
        ref_label.grid(row=0, column=0, sticky="w")

        status_frame = ctk.CTkFrame(header_frame, fg_color="transparent")
        status_frame.grid(row=0, column=1, sticky="e")

        current_status = quote.get('status', 'Pending')
        status_var = ctk.StringVar(value=current_status)
        
        # Store reference to the current quote for status updates
        self._current_quote_ref = quote.get('reference')
        
        self._status_dropdown = ctk.CTkOptionMenu(
            status_frame,
            values=self.STATUS_OPTIONS,
            variable=status_var,
            command=self._on_status_change,
            width=130,
            fg_color="#839705",
            button_color="#839705",
            button_hover_color="#98ab06"
        )
        self._status_dropdown.grid(row=0, column=0)

        divider = ctk.CTkFrame(self._details_frame, height=2, fg_color="gray70")
        divider.grid(row=row, column=0, columnspan=2, sticky="ew", pady=5)
        row += 1

        notes = quote.get('notes', '')
        if notes:
            notes_label = ctk.CTkLabel(
                self._details_frame,
                text="💬 Client Message:",
                font=ctk.CTkFont(weight="bold", size=13),
                text_color=Theme.TEXT
            )
            notes_label.grid(row=row, column=0, sticky="w", pady=(5, 0))
            row += 1
            
            notes_frame = ctk.CTkFrame(
                self._details_frame,
                fg_color=("gray95", "gray15"),
                corner_radius=8
            )
            notes_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(2, 10))
            notes_frame.grid_columnconfigure(0, weight=1)
            
            notes_text = ctk.CTkLabel(
                notes_frame,
                text=notes,
                anchor="w",
                wraplength=550,
                justify="left",
                font=ctk.CTkFont(size=12),
                text_color=Theme.TEXT
            )
            notes_text.grid(row=0, column=0, padx=12, pady=10, sticky="w")
            row += 1

        if notes:
            divider2 = ctk.CTkFrame(self._details_frame, height=2, fg_color="gray70")
            divider2.grid(row=row, column=0, columnspan=2, sticky="ew", pady=5)
            row += 1

        self._add_detail_row("👤 Customer", quote.get('customerName', 'N/A'), row)
        row += 1
        self._add_detail_row("📧 Email", quote.get('email', 'N/A'), row)
        row += 1
        self._add_detail_row("📞 Phone", quote.get('phone', 'N/A'), row)
        row += 1
        if quote.get('company'):
            self._add_detail_row("🏢 Company", quote.get('company', ''), row)
            row += 1

        divider3 = ctk.CTkFrame(self._details_frame, height=2, fg_color="gray70")
        divider3.grid(row=row, column=0, columnspan=2, sticky="ew", pady=10)
        row += 1

        items = quote.get('items', [])
        
        items_header_frame = ctk.CTkFrame(self._details_frame, fg_color="transparent")
        items_header_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 5))
        items_header_frame.grid_columnconfigure(0, weight=1)
        row += 1

        items_label = ctk.CTkLabel(
            items_header_frame,
            text=f"📦 Items Requested ({len(items)})",
            font=ctk.CTkFont(weight="bold", size=14),
            text_color=Theme.TEXT
        )
        items_label.grid(row=0, column=0, sticky="w")

        total_qty = sum(item.get('qty', 1) for item in items)
        qty_label = ctk.CTkLabel(
            items_header_frame,
            text=f"Total: {total_qty} units",
            font=ctk.CTkFont(size=11),
            text_color="gray"
        )
        qty_label.grid(row=0, column=1, sticky="e")

        items_frame = ctk.CTkFrame(self._details_frame, fg_color="transparent")
        items_frame.grid(row=row, column=0, columnspan=2, sticky="ew")
        items_frame.grid_columnconfigure(0, weight=2)
        items_frame.grid_columnconfigure(1, weight=1)
        items_frame.grid_columnconfigure(2, weight=3)
        row += 1

        if items:
            headers = ["Item Name", "Qty", "Specifications"]
            for col, header in enumerate(headers):
                header_label = ctk.CTkLabel(
                    items_frame,
                    text=header,
                    font=ctk.CTkFont(weight="bold", size=11),
                    text_color="gray",
                    anchor="w"
                )
                header_label.grid(row=0, column=col, sticky="w", pady=(0, 5))

            for i, item in enumerate(items):
                item_row = i + 1
                
                name = item.get('name', 'Unknown')
                name_label = ctk.CTkLabel(
                    items_frame,
                    text=f"  📄 {name}",
                    anchor="w",
                    font=ctk.CTkFont(size=12),
                    text_color=Theme.TEXT
                )
                name_label.grid(row=item_row, column=0, sticky="w", pady=3)
                
                qty = item.get('qty', 1)
                qty_label = ctk.CTkLabel(
                    items_frame,
                    text=f"× {qty}",
                    anchor="w",
                    font=ctk.CTkFont(size=12),
                    text_color=Theme.TEXT
                )
                qty_label.grid(row=item_row, column=1, sticky="w", pady=3)
                
                specs_text = ""
                if 'specs' in item and item['specs']:
                    specs_list = item['specs']
                    if isinstance(specs_list, list):
                        specs_text = " | ".join(specs_list[:3])
                        if len(specs_list) > 3:
                            specs_text += f" (+{len(specs_list) - 3} more)"
                    else:
                        specs_text = str(specs_list)
                
                if not specs_text:
                    specs_text = "No specifications"
                
                specs_label = ctk.CTkLabel(
                    items_frame,
                    text=specs_text,
                    anchor="w",
                    font=ctk.CTkFont(size=10),
                    text_color="gray",
                    wraplength=200
                )
                specs_label.grid(row=item_row, column=2, sticky="w", pady=3, padx=(5, 0))

            row += len(items) + 1
        else:
            no_items = ctk.CTkLabel(
                items_frame,
                text="  No items listed",
                text_color="gray",
                font=ctk.CTkFont(size=12)
            )
            no_items.grid(row=1, column=0, columnspan=3, sticky="w", pady=5)
            row += 2

        divider4 = ctk.CTkFrame(self._details_frame, height=2, fg_color="gray70")
        divider4.grid(row=row, column=0, columnspan=2, sticky="ew", pady=10)
        row += 1

        reply_label = ctk.CTkLabel(
            self._details_frame,
            text="💬 Reply to Customer",
            font=ctk.CTkFont(weight="bold", size=14),
            text_color=Theme.TEXT
        )
        reply_label.grid(row=row, column=0, sticky="w", pady=(10, 5))
        row += 1

        self._reply_text = ctk.CTkTextbox(
            self._details_frame,
            height=80,
            wrap="word",
            corner_radius=8
        )
        self._reply_text.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        row += 1
        
        existing_reply = quote.get('replyMessage', '')
        if existing_reply:
            self._reply_text.insert("1.0", existing_reply)

        btn_frame = ctk.CTkFrame(self._details_frame, fg_color="transparent")
        btn_frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(0, 10))
        btn_frame.grid_columnconfigure(0, weight=1)
        btn_frame.grid_columnconfigure(1, weight=1)
        row += 1

        reply_btn = ctk.CTkButton(
            btn_frame,
            text="💬 Send Reply to MongoDB",
            command=lambda: self._send_reply(quote),
            fg_color="#4CAF50",
            hover_color="#388E3C",
            height=35
        )
        reply_btn.grid(row=0, column=0, columnspan=2, padx=5, sticky="ew")

    def _add_detail_row(self, label: str, value: str, row: int):
        """Add a detail row to the details panel."""
        label_widget = ctk.CTkLabel(
            self._details_frame,
            text=label,
            font=ctk.CTkFont(weight="bold"),
            anchor="w",
            width=120,
            text_color=Theme.TEXT
        )
        label_widget.grid(row=row, column=0, sticky="w", pady=3)

        value_widget = ctk.CTkLabel(
            self._details_frame,
            text=value,
            anchor="w",
            text_color=Theme.TEXT
        )
        value_widget.grid(row=row, column=1, sticky="w", pady=3, padx=(10, 0))

    def _on_status_change(self, new_display_status: str):
        """Handle status change from dropdown."""
        if not self._selected_quote:
            return
            
        reference = self._selected_quote.get('reference', '')
        if not reference:
            return
            
        # Update the status
        self._update_status_action(self._selected_quote, new_display_status)

    def _update_status_action(self, quote: Dict[str, Any], new_display_status: str):
        """Update the status of a quote in MongoDB and refresh the view."""
        try:
            reference = quote.get('reference', '')
            if not reference:
                messagebox.showerror("Error", "No reference found for this quote")
                return
            
            # Convert display status to MongoDB status
            mongo_status = self.DISPLAY_TO_MONGO.get(new_display_status, "received")
            
            print(f"🔄 Updating status for {reference} from '{quote.get('status')}' to: {new_display_status} (MongoDB: {mongo_status})")
            
            # Update status in MongoDB
            success = self._mongodb.update_quote_status(reference, mongo_status)
            
            if success:
                # Update the quote in the local list immediately
                for q in self._quotes:
                    if q.get('reference') == reference:
                        q['status'] = new_display_status
                        break
                
                # Update the selected quote
                if self._selected_quote and self._selected_quote.get('reference') == reference:
                    self._selected_quote['status'] = new_display_status
                
                # Re-render the list to show updated status
                self._render_quote_list(self._search_entry.get())
                self._update_stats()
                
                # Update the dropdown in the details panel
                if hasattr(self, '_status_dropdown'):
                    self._status_dropdown.set(new_display_status)
                
                self._update_status(f"✅ Status updated to {new_display_status}")
                
                # Show a success message
                messagebox.showinfo("Success", f"Quote {reference} status updated to {new_display_status}")
            else:
                # If update failed, reload quotes to get correct state
                self._load_quotes()
                messagebox.showerror("Error", "Failed to update status in MongoDB")
                
        except Exception as e:
            self._update_status(f"❌ Error updating status: {str(e)}")
            messagebox.showerror("Error", f"Failed to update status: {str(e)}")
            # Reload to ensure consistent state
            self._load_quotes()

    def _send_reply(self, quote: Dict[str, Any]):
        """Send a reply to the customer and save to MongoDB."""
        reply = self._reply_text.get("1.0", "end-1c").strip()
        if not reply:
            messagebox.showwarning("No Reply", "Please enter a reply message.")
            return

        reference = quote.get('reference', '')
        if not reference:
            messagebox.showerror("Error", "No reference found for this quote")
            return

        if not messagebox.askyesno("Send Reply", f"Send this reply for quote {reference} to the customer and save to MongoDB?"):
            return

        try:
            success = self._mongodb.update_quote_reply(reference, reply)
            
            if success:
                for q in self._quotes:
                    if q.get('reference') == reference:
                        q['replyMessage'] = reply
                        break
                
                if self._selected_quote and self._selected_quote.get('reference') == reference:
                    self._selected_quote['replyMessage'] = reply
                
                self._update_status(f"✅ Reply sent for {reference} and saved to MongoDB")
                messagebox.showinfo("Success", f"Reply sent for {reference} and saved to MongoDB!")
            else:
                messagebox.showerror("Error", "Failed to send reply to MongoDB")
                
        except Exception as e:
            self._update_status(f"❌ Error sending reply: {str(e)}")
            messagebox.showerror("Error", f"Failed to send reply: {str(e)}")

    def _update_stats(self):
        """Update the stats label."""
        if not self._quotes:
            self._stats_label.configure(text="No quotes loaded")
            return
            
        total = len(self._quotes)
        pending = sum(1 for q in self._quotes if q.get('status') == 'Pending')
        in_review = sum(1 for q in self._quotes if q.get('status') == 'In Review')
        quoted = sum(1 for q in self._quotes if q.get('status') == 'Quoted')
        closed = sum(1 for q in self._quotes if q.get('status') == 'Closed')
        
        stats_text = f"📊 Total: {total} | Pending: {pending} | In Review: {in_review} | Quoted: {quoted} | Closed: {closed}"
        self._stats_label.configure(text=stats_text)

    def _update_status(self, message: str):
        """Update the status bar."""
        self._status_bar.configure(text=message)
        self.after(5000, lambda: self._status_bar.configure(text=""))

    @staticmethod
    def _map_mongo_to_display(mongo_status: str) -> str:
        """Map MongoDB status to display status."""
        if not mongo_status:
            return "Pending"
        status_map = {
            "received": "Pending",
            "in_review": "In Review",
            "quoted": "Quoted",
            "closed": "Closed"
        }
        return status_map.get(str(mongo_status).lower(), "Pending")

    @staticmethod
    def _map_display_to_mongo(display_status: str) -> str:
        """Map display status to MongoDB status."""
        status_map = {
            "Pending": "received",
            "In Review": "in_review",
            "Quoted": "quoted",
            "Closed": "closed"
        }
        return status_map.get(display_status, "received")

    def refresh(self):
        """Refresh the view."""
        self._load_quotes()
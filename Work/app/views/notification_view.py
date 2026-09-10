# app/views/notification_view.py
from app.controllers.notification_controller import NotificationController
from app.models.notification import Notification
from app.utils.theme import Theme
from app.widgets.notification_card import NotificationCard
import customtkinter as ctk


class NotificationView(ctk.CTkFrame):

    ROLE_OPTIONS = [
        "All",
        "Director",
        "Branch Manager",
        "Business Lead",
        "Operations Manager",
        "Staff",
        "Intern",
    ]

    def __init__(self, master, controller: NotificationController, filters=None):
        super().__init__(master, fg_color=Theme.BG)

        self.controller = controller
        self.filters = filters or {}
        self._master_window = master

        self.role_var = ctk.StringVar(
            value=self.filters.get("role", "All")
        )

        self.unread_var = ctk.BooleanVar(
            value=self.filters.get("unread_only", False)
        )

        self.build_ui()
        self.refresh()

    def build_ui(self):

        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 10))

        ctk.CTkLabel(
            header,
            text="Notifications",
            font=("Segoe UI", 22, "bold"),
            text_color=Theme.TEXT,
        ).pack(anchor="w")

        ctk.CTkLabel(
            header,
            text="Employee & Director notification centre",
            font=("Segoe UI", 12),
            text_color=Theme.MUTED_TEXT,
        ).pack(anchor="w")

        filter_frame = ctk.CTkFrame(self, fg_color="transparent")
        filter_frame.pack(fill="x", padx=20)

        ctk.CTkOptionMenu(
            filter_frame,
            values=self.ROLE_OPTIONS,
            variable=self.role_var,
            command=lambda _=None: self.refresh(),
            width=170,
        ).pack(side="left")

        ctk.CTkCheckBox(
            filter_frame,
            text="Unread only",
            variable=self.unread_var,
            command=self.refresh,
        ).pack(side="left", padx=10)

        self.list_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
        )

        self.list_frame.pack(
            fill="both",
            expand=True,
            padx=20,
            pady=20,
        )

    def _convert(self, item):
        """Convert dict to Notification object or return existing."""
        if isinstance(item, Notification):
            return item

        notification_id = item.get("id") or item.get("_id")
        if notification_id and not isinstance(notification_id, int):
            notification_id = str(notification_id)

        return Notification(
            id=notification_id,
            recipient_role=item.get("recipient_role", ""),
            title=item.get("title", ""),
            message=item.get("message", ""),
            category=item.get("category", "General"),
            reference_type=item.get("reference_type", ""),
            reference_id=item.get("reference_id"),
            is_executive=item.get("is_executive", False),
            is_read=item.get("is_read", False),
            created_at=item.get("created_at"),
        )

    def refresh(self):

        for child in self.list_frame.winfo_children():
            child.destroy()

        notifications = self.controller.get_notifications(
            role=self.role_var.get(),
            unread_only=self.unread_var.get(),
        )

        if not notifications:
            ctk.CTkLabel(
                self.list_frame,
                text="No notifications found",
                font=("Segoe UI", 13),
                text_color=Theme.MUTED_TEXT,
            ).pack(pady=40)
            return

        for item in notifications:
            notification = self._convert(item)
            card = NotificationCard(
                self.list_frame,
                notification,
                self.mark_as_read,
            )
            card.pack(fill="x", pady=6)

    def mark_as_read(self, notification_id):
        """Mark notification as read and handle Quote Assignment actions."""
        if not notification_id:
            return

        try:
            notification_id_str = str(notification_id)
            print(f"📋 Marking notification as read: {notification_id_str}")
            
            # Find the notification
            notification_found = None
            notifications = self.controller.get_notifications(role="All", unread_only=False)
            for n in notifications:
                n_id = None
                if isinstance(n, Notification):
                    n_id = str(n.id) if n.id else None
                elif isinstance(n, dict):
                    n_id = str(n.get("id") or n.get("_id") or "")
                
                if n_id == notification_id_str:
                    notification_found = n
                    break
            
            # Mark as read in controller
            self.controller.mark_read(notification_id_str)
            print(f"✅ Notification {notification_id_str} marked as read")
            
            # Handle Quote Assignment notifications
            if notification_found:
                category = None
                reference = None
                
                if isinstance(notification_found, Notification):
                    category = notification_found.category
                    reference = notification_found.reference_id
                elif isinstance(notification_found, dict):
                    category = notification_found.get("category", "")
                    reference = notification_found.get("reference_id") or notification_found.get("reference")
                
                if category == "Quote Assignment":
                    print(f"📋 Quote assignment notification - reference: {reference}")
                    self._handle_quote_assignment(notification_found, reference)
            
            self.refresh()

        except Exception as e:
            print(f"Mark read failed: {e}")
            import traceback
            traceback.print_exc()

    def _handle_quote_assignment(self, notification, reference):
        """Handle accepting a quote assignment."""
        if not reference:
            print("⚠️ No reference found in notification")
            return
        
        # Show accept dialog
        dialog = ctk.CTkToplevel(self)
        dialog.title("Accept Assignment")
        dialog.geometry("450x250")
        dialog.configure(fg_color=Theme.BG)
        dialog.transient(self)
        dialog.grab_set()
        
        # Center the dialog
        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - 225
        y = (dialog.winfo_screenheight() // 2) - 125
        dialog.geometry(f"450x250+{x}+{y}")
        
        # Content
        main = ctk.CTkFrame(dialog, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=20, pady=20)
        
        ctk.CTkLabel(
            main,
            text="📋 New Quote Assignment",
            font=("Segoe UI", 20, "bold"),
            text_color=Theme.TEXT,
        ).pack(pady=(0, 10))
        
        message_text = notification.message if hasattr(notification, 'message') else "You have been assigned a new quote."
        ctk.CTkLabel(
            main,
            text=message_text,
            font=("Segoe UI", 13),
            text_color=Theme.MUTED_TEXT,
            wraplength=380,
            justify="center",
        ).pack(pady=(0, 10))
        
        ctk.CTkLabel(
            main,
            text=f"Quote: {reference}",
            font=("Segoe UI", 12, "bold"),
            text_color=Theme.TEXT,
        ).pack(pady=(0, 15))
        
        # Buttons
        btn_frame = ctk.CTkFrame(main, fg_color="transparent")
        btn_frame.pack(fill="x")
        
        def on_accept():
            dialog.destroy()
            self._accept_quote(reference)
        
        def on_decline():
            dialog.destroy()
        
        ctk.CTkButton(
            btn_frame,
            text="✅ Accept Job",
            width=120,
            height=40,
            fg_color=Theme.SUCCESS,
            hover_color=Theme.SUCCESS_HOVER,
            font=("Segoe UI", 13, "bold"),
            command=on_accept,
        ).pack(side="left", padx=5)
        
        ctk.CTkButton(
            btn_frame,
            text="❌ Decline",
            width=120,
            height=40,
            fg_color=Theme.DANGER,
            hover_color=Theme.DANGER_HOVER,
            command=on_decline,
        ).pack(side="right", padx=5)

    def _accept_quote(self, reference):
        """Accept the quote assignment."""
        try:
            # Find the main window to access navigation controller
            main_window = self._find_main_window()
            if not main_window:
                print("⚠️ Could not find main window")
                return
            
            # Get navigation controller
            nav_controller = getattr(main_window, '_navigation_controller', None)
            if not nav_controller:
                print("⚠️ Navigation controller not found")
                return
            
            # Get MongoDB service
            mongodb = getattr(main_window, '_mongodb', None)
            if not mongodb:
                mongodb = getattr(nav_controller, '_mongodb', None)
            if not mongodb:
                print("⚠️ MongoDB service not found")
                return
            
            # Update quote status to Accepted
            collection = mongodb.get_collection("quotes")
            result = collection.update_one(
                {"reference": reference},
                {
                    "$set": {
                        "status": "accepted",
                        "accepted_at": datetime.now(timezone.utc),
                        "accepted_by": nav_controller._current_username,
                        "updated_at": datetime.now(timezone.utc)
                    },
                    "$push": {
                        "history": {
                            "action": "accepted",
                            "by": nav_controller._current_full_name,
                            "username": nav_controller._current_username,
                            "time": datetime.now(timezone.utc).isoformat(),
                            "note": "Employee accepted the assignment"
                        }
                    }
                }
            )
            
            if result.modified_count > 0:
                print(f"✅ Quote {reference} accepted by {nav_controller._current_username}")
                
                # Notify manager
                if nav_controller._notification_service:
                    try:
                        nav_controller._notification_service.notify_operational(
                            ["Director", "Branch Manager", "Business Lead", "Operations Manager"],
                            f"Quote Accepted: {reference}",
                            f"{nav_controller._current_full_name} has accepted quote {reference}.",
                            "Quote Assignment",
                            "Quote",
                            reference
                        )
                    except Exception as e:
                        print(f"⚠️ Could not send notification: {e}")
                
                # Refresh the notification view
                self.refresh()
                
                # Navigate to Quote Management
                nav_controller.navigate("Quote Management")
                
                # Show success message
                self._show_toast(f"✅ Quote {reference} accepted successfully!", "success")
            else:
                print(f"⚠️ Could not accept quote {reference}")
                self._show_toast(f"Could not accept quote {reference}", "error")
                
        except Exception as e:
            print(f"❌ Error accepting quote: {e}")
            import traceback
            traceback.print_exc()
            self._show_toast(f"Error accepting quote: {e}", "error")

    def _show_toast(self, message, kind="info"):
        """Show a toast message."""
        try:
            # Try to find status bar in main window
            main_window = self._find_main_window()
            if main_window:
                # Use status bar if available
                if hasattr(main_window, '_status_bar'):
                    colors = {
                        "success": "#4CAF50",
                        "error": Theme.DANGER,
                        "info": Theme.MUTED_TEXT,
                    }
                    main_window._status_bar.configure(
                        text=message,
                        text_color=colors.get(kind, Theme.MUTED_TEXT)
                    )
                    main_window.after(6000, lambda: main_window._status_bar.configure(text=""))
        except Exception:
            print(f"Toast: {message}")

    def _find_main_window(self):
        """Find the main window in the widget hierarchy."""
        widget = self.master
        while widget is not None:
            try:
                if hasattr(widget, '_navigation_controller') and hasattr(widget, '_nav_buttons'):
                    return widget
                if widget.__class__.__name__ == "MainWindow":
                    return widget
            except:
                pass
            
            try:
                widget = widget.master
            except:
                break
        return None
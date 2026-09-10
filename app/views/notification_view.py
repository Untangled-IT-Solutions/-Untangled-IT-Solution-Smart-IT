# app/views/notification_view.py
"""Notification view with sound support and Mark all as read.

Sound behaviour:
- Plays immediately when new unread notifications appear.
- Keeps a gentle repeating reminder sound (every ~18 s) while any
  unread notifications remain for the current view.
- Stops automatically as soon as the employee marks them as read
  (single or Mark all as read) or turns the Sound toggle off.
"""

from app.controllers.notification_controller import NotificationController
from app.models.notification import Notification
from app.utils.theme import Theme
from app.widgets.notification_card import NotificationCard
from app.utils.sound import SoundManager
import customtkinter as ctk
from tkinter import messagebox
from collections import OrderedDict


class NotificationView(ctk.CTkFrame):

    CATEGORY_OPTIONS = ["All", "Tasks", "Calendar", "Approvals", "Sales", "Operations", "System"]
    CATEGORY_COLORS = {
        "Tasks": "#F97316",
        "Calendar": "#DB2777",
        "Approvals": "#059669",
        "Sales": "#7C3AED",
        "Operations": "#0284C7",
        "System": "#64748B",
    }

    ROLE_OPTIONS = [
        "All",
        "Director",
        "Super User",
        "Administrator",
        "Super Admin",
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

        self._previous_notification_ids = set()
        self._destroyed = False

        self.role_var = ctk.StringVar(
            value=self.filters.get("role", "All")
        )

        self.unread_var = ctk.BooleanVar(
            value=self.filters.get("unread_only", False)
        )
        self.search_var = ctk.StringVar(value=str(self.filters.get("search") or ""))
        self.category_var = ctk.StringVar(
            value=str(self.filters.get("category") or "All")
        )
        if self.category_var.get() not in self.CATEGORY_OPTIONS:
            self.category_var.set("All")
        self._refresh_job = None

        self.build_ui()
        self.refresh()
        self._schedule_auto_refresh()

    def build_ui(self):
        """Build the notification UI with sound toggle and Mark all as read."""
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=20, pady=(20, 12))
        header.grid_columnconfigure(0, weight=1)

        ctk.CTkLabel(
            header,
            text="Notifications",
            font=("Segoe UI", 22, "bold"),
            text_color=Theme.TEXT,
        ).grid(row=0, column=0, sticky="w")

        ctk.CTkLabel(
            header,
            text="Search, review and action important Nexus updates",
            font=("Segoe UI", 12),
            text_color=Theme.MUTED_TEXT,
        ).grid(row=1, column=0, pady=(3, 0), sticky="w")

        self.mark_all_btn = ctk.CTkButton(
            header,
            text="✓  Mark all as read",
            width=190,
            height=40,
            corner_radius=Theme.RADIUS,
            fg_color=Theme.SUCCESS,
            hover_color=Theme.SUCCESS_HOVER,
            text_color="#FFFFFF",
            font=Theme.FONT_BUTTON,
            command=self.mark_all_as_read,
        )
        self.mark_all_btn.grid(row=0, column=1, rowspan=2, padx=(12, 0), sticky="e")

        self.summary_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.summary_frame.pack(fill="x", padx=20, pady=(0, 12))
        for column in range(5):
            self.summary_frame.grid_columnconfigure(column, weight=1, uniform="notice_summary")
        self.summary_labels = {}
        summary_items = (
            ("Total", Theme.INFO),
            ("Unread", Theme.DANGER),
            ("Tasks", self.CATEGORY_COLORS["Tasks"]),
            ("Calendar", self.CATEGORY_COLORS["Calendar"]),
            ("Approvals", self.CATEGORY_COLORS["Approvals"]),
        )
        for column, (label, color) in enumerate(summary_items):
            card = ctk.CTkFrame(
                self.summary_frame,
                fg_color=Theme.PANEL,
                border_color=color,
                border_width=2,
                corner_radius=Theme.RADIUS,
            )
            card.grid(
                row=0, column=column,
                padx=(0 if column == 0 else 5, 0), sticky="ew",
            )
            value_label = ctk.CTkLabel(
                card, text="0", text_color=color,
                font=("Segoe UI", 22, "bold"),
            )
            value_label.pack(anchor="w", padx=12, pady=(9, 0))
            ctk.CTkLabel(
                card, text=label, text_color=Theme.MUTED_TEXT,
                font=("Segoe UI", 11, "bold"),
            ).pack(anchor="w", padx=12, pady=(0, 9))
            self.summary_labels[label] = value_label

        filter_frame = ctk.CTkFrame(self, fg_color="transparent")
        filter_frame.pack(fill="x", padx=20, pady=(0, 10))
        filter_frame.grid_columnconfigure(0, weight=1)

        self.search_entry = ctk.CTkEntry(
            filter_frame,
            textvariable=self.search_var,
            placeholder_text="Search title, message, category or reference...",
            height=40,
            fg_color=Theme.PANEL,
            border_color=Theme.BORDER,
            text_color=Theme.TEXT,
        )
        self.search_entry.grid(row=0, column=0, padx=(0, 8), sticky="ew")
        self.search_entry.bind("<KeyRelease>", self._schedule_refresh)
        self.search_entry.bind("<Return>", lambda _event: self.refresh())

        ctk.CTkOptionMenu(
            filter_frame,
            values=self.ROLE_OPTIONS,
            variable=self.role_var,
            command=lambda _=None: self.refresh(),
            width=170,
            height=40,
            fg_color=Theme.PANEL_ALT,
            button_color=Theme.ACCENT,
            button_hover_color=Theme.ACCENT_HOVER,
            text_color=Theme.TEXT,
        ).grid(row=0, column=1, padx=(0, 8))

        ctk.CTkCheckBox(
            filter_frame,
            text="Unread only",
            variable=self.unread_var,
            command=self.refresh,
            fg_color=Theme.ACCENT,
            hover_color=Theme.ACCENT_HOVER,
            border_color=Theme.BORDER,
            text_color=Theme.TEXT,
        ).grid(row=0, column=2, padx=(0, 10))

        self.sound_toggle = ctk.CTkSwitch(
            filter_frame,
            text="🔊 Sound",
            command=self.toggle_sound,
            onvalue=True,
            offvalue=False,
            progress_color=Theme.ACCENT,
            text_color=Theme.TEXT,
        )
        self.sound_toggle.select()
        self.sound_toggle.grid(row=0, column=3, padx=(0, 10))

        ctk.CTkButton(
            filter_frame,
            text="Clear filters",
            width=105,
            height=40,
            fg_color=Theme.PANEL_ALT,
            hover_color=Theme.BORDER,
            text_color=Theme.TEXT,
            command=self._clear_filters,
        ).grid(row=0, column=4)

        self.category_tabs = ctk.CTkSegmentedButton(
            self,
            values=self.CATEGORY_OPTIONS,
            variable=self.category_var,
            command=lambda _value: self.refresh(),
            selected_color=Theme.ACCENT,
            selected_hover_color=Theme.ACCENT_HOVER,
            unselected_color=Theme.PANEL_ALT,
            unselected_hover_color=Theme.BORDER,
            text_color=Theme.TEXT,
        )
        self.category_tabs.pack(fill="x", padx=20, pady=(0, 8))
        self.category_tabs.set(self.category_var.get())

        self.result_label = ctk.CTkLabel(
            self, text="", text_color=Theme.MUTED_TEXT, font=Theme.FONT_SMALL,
        )
        self.result_label.pack(fill="x", padx=22, pady=(0, 2), anchor="w")

        self.list_frame = ctk.CTkScrollableFrame(
            self,
            fg_color="transparent",
        )
        self.list_frame.pack(
            fill="both",
            expand=True,
            padx=20,
            pady=(8, 20),
        )

    def toggle_sound(self):
        enabled = bool(self.sound_toggle.get())
        SoundManager.set_enabled(enabled)

        try:
            if hasattr(self.controller, "_notification_service"):
                self.controller._notification_service.set_sound_enabled(enabled)
        except Exception:
            pass

        if not enabled:
            SoundManager.stop_reminder()
        else:
            self.refresh()

    def _schedule_refresh(self, _event=None):
        if self._refresh_job is not None:
            try:
                self.after_cancel(self._refresh_job)
            except Exception:
                pass
        self._refresh_job = self.after(250, self.refresh)

    def _clear_filters(self):
        self.search_var.set("")
        self.category_var.set("All")
        self.category_tabs.set("All")
        self.unread_var.set(False)
        self.refresh()

    @classmethod
    def _notification_group(cls, item) -> str:
        """Collapse many source labels into a small, predictable set of groups."""
        if isinstance(item, Notification):
            values = (
                item.category, item.reference_type, item.title, item.message,
            )
        else:
            values = (
                item.get("category", ""), item.get("reference_type", ""),
                item.get("title", ""), item.get("message", ""),
            )
        text = " ".join(str(value or "") for value in values).casefold()
        if any(word in text for word in ("quote", "rfq", "tender", "order", "sale", "product")):
            return "Sales"
        if any(word in text for word in ("task", "sprint", "work item", "assignment")):
            return "Tasks"
        if any(word in text for word in ("calendar", "meeting", "event", "invite")):
            return "Calendar"
        if any(word in text for word in ("approval", "approved", "rejected", "authorisation")):
            return "Approvals"
        if any(word in text for word in (
            "attendance", "clock", "leave", "office", "inventory", "stock",
            "project", "operations", "technical", "support",
        )):
            return "Operations"
        return "System"

    def _matches_search(self, item) -> bool:
        query = self.search_var.get().strip().casefold()
        if not query:
            return True
        if isinstance(item, Notification):
            values = (
                item.title, item.message, item.category, item.reference_type,
                item.reference_id, item.recipient_role,
            )
        else:
            values = (
                item.get("title", ""), item.get("message", ""),
                item.get("category", ""), item.get("reference_type", ""),
                item.get("reference_id", ""), item.get("recipient_role", ""),
                item.get("recipient_name", ""),
            )
        return query in " ".join(str(value or "") for value in values).casefold()

    @staticmethod
    def _is_unread(item) -> bool:
        if isinstance(item, Notification):
            return not item.is_read
        return not bool(item.get("is_read", False))

    def _update_summary(self, items) -> None:
        totals = {
            "Total": len(items),
            "Unread": sum(1 for item in items if self._is_unread(item)),
            "Tasks": sum(1 for item in items if self._notification_group(item) == "Tasks"),
            "Calendar": sum(1 for item in items if self._notification_group(item) == "Calendar"),
            "Approvals": sum(1 for item in items if self._notification_group(item) == "Approvals"),
        }
        for label, value in totals.items():
            self.summary_labels[label].configure(text=str(value))

    def _convert(self, item):
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

    def _extract_id(self, item) -> str:
        if isinstance(item, dict):
            return str(item.get("id") or item.get("_id") or "")
        if isinstance(item, Notification):
            return str(item.id) if item.id else ""
        return ""

    def mark_all_as_read(self):
        """Mark the unread notifications visible under the current filters as read."""
        try:
            role = self.role_var.get() or "All"
            unread = self.controller.get_notifications(role=role, unread_only=True) or []
            selected_category = self.category_var.get() or "All"
            visible_unread = [
                item for item in unread
                if (
                    selected_category == "All"
                    or self._notification_group(item) == selected_category
                )
                and self._matches_search(item)
            ]
            count = len(visible_unread)
            if count == 0:
                messagebox.showinfo(
                    "Notifications", "There are no unread notifications in this view."
                )
                return

            ok = messagebox.askyesno(
                "Mark visible notifications as read",
                f"Mark {count} visible unread notification(s) as read?",
            )
            if not ok:
                return

            updated = 0
            for item in visible_unread:
                nid = self._extract_id(item)
                if nid:
                    self.controller.mark_read(nid)
                    updated += 1

            SoundManager.stop_reminder()
            self._previous_notification_ids = set()
            print(f"✅ Marked {updated} notification(s) as read")
            self.refresh()
            messagebox.showinfo("Notifications", f"Marked {updated} notification(s) as read.")
        except Exception as e:
            print(f"⚠️ Mark all as read failed: {e}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("Error", f"Could not mark all as read:\n{e}")

    def refresh(self):
        if self._destroyed:
            return

        if self._refresh_job is not None:
            self._refresh_job = None

        for child in self.list_frame.winfo_children():
            child.destroy()

        try:
            all_notifications = self.controller.get_notifications(
                role=self.role_var.get(), unread_only=False,
            ) or []
        except Exception as exc:
            self.result_label.configure(text="Notifications could not be loaded")
            ctk.CTkLabel(
                self.list_frame,
                text=f"Could not load notifications.\n{exc}",
                text_color=Theme.DANGER,
                font=Theme.FONT_BODY,
                justify="left",
            ).pack(anchor="w", pady=24)
            return

        self._update_summary(all_notifications)
        unread_check = [item for item in all_notifications if self._is_unread(item)]
        selected_category = self.category_var.get() or "All"
        display_notifications = [
            item for item in all_notifications
            if (not self.unread_var.get() or self._is_unread(item))
            and (
                selected_category == "All"
                or self._notification_group(item) == selected_category
            )
            and self._matches_search(item)
        ]

        current_ids = set()
        for item in unread_check or []:
            nid = self._extract_id(item)
            if nid:
                current_ids.add(nid)

        new_notifications = current_ids - self._previous_notification_ids

        if SoundManager.is_enabled():
            if new_notifications:
                print(f"🔔 Playing sound for {len(new_notifications)} new notification(s)")
                SoundManager.play_notification_sound()

            if current_ids:
                SoundManager.start_reminder(interval_seconds=18)
            else:
                SoundManager.stop_reminder()
        else:
            SoundManager.stop_reminder()

        self._previous_notification_ids = current_ids

        visible_unread_count = sum(
            1 for item in display_notifications if self._is_unread(item)
        )
        # Enable or disable the bulk action for the notifications currently shown.
        try:
            if visible_unread_count:
                self.mark_all_btn.configure(
                    state="normal",
                    text=f"✓  Mark visible read ({visible_unread_count})",
                )
            else:
                self.mark_all_btn.configure(state="disabled", text="✓  Visible items read")
        except Exception:
            pass

        noun = "notification" if len(display_notifications) == 1 else "notifications"
        filter_note = ""
        if selected_category != "All":
            filter_note = f" in {selected_category}"
        self.result_label.configure(
            text=f"Showing {len(display_notifications)} {noun}{filter_note}"
        )

        if not display_notifications:
            ctk.CTkLabel(
                self.list_frame,
                text="No notifications match these filters.",
                font=("Segoe UI", 13),
                text_color=Theme.MUTED_TEXT,
            ).pack(pady=40)
            return

        grouped = OrderedDict()
        for group_name in self.CATEGORY_OPTIONS[1:]:
            group_items = [
                item for item in display_notifications
                if self._notification_group(item) == group_name
            ]
            if group_items:
                grouped[group_name] = group_items

        for group_name, group_items in grouped.items():
            group_header = ctk.CTkFrame(self.list_frame, fg_color="transparent")
            group_header.pack(fill="x", pady=(12, 4))
            ctk.CTkFrame(
                group_header,
                width=6,
                height=24,
                corner_radius=3,
                fg_color=self.CATEGORY_COLORS[group_name],
            ).pack(side="left", padx=(2, 9))
            ctk.CTkLabel(
                group_header,
                text=f"{group_name}  ·  {len(group_items)}",
                font=("Segoe UI", 14, "bold"),
                text_color=Theme.TEXT,
            ).pack(side="left")

            for item in group_items:
                notification = self._convert(item)
                card = NotificationCard(
                    self.list_frame,
                    notification,
                    self.mark_as_read,
                    accent_color=self.CATEGORY_COLORS[group_name],
                    group_label=group_name,
                )
                card.pack(fill="x", pady=5)

    def mark_as_read(self, notification_id):
        if not notification_id:
            return

        try:
            notification_id_str = str(notification_id)
            print(f"📋 Marking notification as read: {notification_id_str}")

            notification_found = None
            notifications = self.controller.get_notifications(role="All", unread_only=False)
            for n in notifications:
                if self._extract_id(n) == notification_id_str:
                    notification_found = n
                    break

            self.controller.mark_read(notification_id_str)
            print(f"✅ Notification {notification_id_str} marked as read")

            if notification_found:
                category = None
                reference = None
                if isinstance(notification_found, Notification):
                    category = notification_found.category
                    reference = notification_found.reference_id
                elif isinstance(notification_found, dict):
                    category = notification_found.get("category", "")
                    reference = (
                        notification_found.get("reference_id")
                        or notification_found.get("reference")
                    )

                if category in ("Quote Assignment", "Quote Assigned"):
                    print(f"📋 Quote assignment notification – reference: {reference}")
                    self._handle_quote_assignment(notification_found, reference)

            self.refresh()

        except Exception as e:
            print(f"Mark read failed: {e}")
            import traceback
            traceback.print_exc()

    def _handle_quote_assignment(self, notification, reference):
        if not reference:
            return

        dialog = ctk.CTkToplevel(self)
        dialog.title("Accept Assignment")
        dialog.geometry("450x250")
        dialog.configure(fg_color=Theme.BG)
        dialog.transient(self)
        dialog.grab_set()

        dialog.update_idletasks()
        x = (dialog.winfo_screenwidth() // 2) - 225
        y = (dialog.winfo_screenheight() // 2) - 125
        dialog.geometry(f"450x250+{x}+{y}")

        main = ctk.CTkFrame(dialog, fg_color="transparent")
        main.pack(fill="both", expand=True, padx=20, pady=20)

        ctk.CTkLabel(
            main,
            text="📋 New Quote Assignment",
            font=("Segoe UI", 20, "bold"),
            text_color=Theme.TEXT,
        ).pack(pady=(0, 10))

        message_text = (
            notification.message
            if hasattr(notification, "message")
            else "You have been assigned a new quote."
        )
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

        btn_row = ctk.CTkFrame(main, fg_color="transparent")
        btn_row.pack()

        ctk.CTkButton(
            btn_row,
            text="Open Quote Management",
            width=180,
            command=dialog.destroy,
        ).pack(side="left", padx=6)

        ctk.CTkButton(
            btn_row,
            text="Close",
            width=100,
            fg_color=Theme.PANEL_ALT,
            command=dialog.destroy,
        ).pack(side="left", padx=6)

    def _schedule_auto_refresh(self):
        if self._destroyed:
            return
        try:
            self.refresh()
        except Exception:
            pass
        self.after(25000, self._schedule_auto_refresh)

    def destroy(self):
        self._destroyed = True
        SoundManager.stop_reminder()
        try:
            super().destroy()
        except Exception:
            pass

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
from app.utils.async_tasks import run_in_background, bump_generation
import customtkinter as ctk
from tkinter import messagebox


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

        self._previous_notification_ids = set()
        self._destroyed = False

        self.role_var = ctk.StringVar(
            value=self.filters.get("role", "All")
        )

        self.unread_var = ctk.BooleanVar(
            value=self.filters.get("unread_only", False)
        )

        self.build_ui()
        self.refresh()
        self._schedule_auto_refresh()

    def build_ui(self):
        """Build the notification UI with sound toggle and Mark all as read."""
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

        self.sound_toggle = ctk.CTkSwitch(
            filter_frame,
            text="🔊 Sound",
            command=self.toggle_sound,
            onvalue=True,
            offvalue=False,
        )
        self.sound_toggle.select()
        self.sound_toggle.pack(side="left", padx=10)

        # Mark all as read button
        self.mark_all_btn = ctk.CTkButton(
            filter_frame,
            text="✓ Mark all as read",
            width=150,
            height=28,
            fg_color="#2E7D32",
            hover_color="#1B5E20",
            command=self.mark_all_as_read,
        )
        self.mark_all_btn.pack(side="right", padx=(10, 0))

        # Unread / missed summary banner
        self.summary_bar = ctk.CTkFrame(self, fg_color="transparent", height=36)
        self.summary_bar.pack(fill="x", padx=20, pady=(8, 0))
        self.summary_label = ctk.CTkLabel(
            self.summary_bar,
            text="",
            font=("Segoe UI", 13, "bold"),
            text_color=Theme.TEXT,
            anchor="w",
        )
        self.summary_label.pack(side="left")
        self.unread_chip = ctk.CTkLabel(
            self.summary_bar,
            text="",
            font=("Segoe UI", 11, "bold"),
            text_color="#FFFFFF",
            fg_color="#DC2626",
            corner_radius=10,
            width=0,
            height=24,
        )
        # packed only when count > 0

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

    def _convert(self, item):
        if isinstance(item, Notification):
            return item

        notification_id = item.get("id") or item.get("_id")
        if notification_id and not isinstance(notification_id, int):
            notification_id = str(notification_id)

        # Prefer service parser when available
        is_read = False
        try:
            from app.services.notification_service import NotificationService
            is_read = NotificationService._parse_is_read(item)
        except Exception:
            is_read = bool(item.get("is_read") or item.get("read") or item.get("isRead"))

        return Notification(
            id=notification_id,
            recipient_role=item.get("recipient_role", ""),
            title=item.get("title", ""),
            message=item.get("message", ""),
            category=item.get("category", "General"),
            reference_type=item.get("reference_type", ""),
            reference_id=item.get("reference_id"),
            is_executive=item.get("is_executive", False),
            is_read=is_read,
            created_at=item.get("created_at") or item.get("createdAt"),
        )

    def _extract_id(self, item) -> str:
        if isinstance(item, dict):
            return str(item.get("id") or item.get("_id") or "")
        if isinstance(item, Notification):
            return str(item.id) if item.id else ""
        return ""

    def mark_all_as_read(self):
        """Mark every unread notification as read (non-blocking) and stop sound."""
        role = self.role_var.get() or "All"
        ok = messagebox.askyesno(
            "Mark all as read",
            "Mark all unread notifications as read?",
        )
        if not ok:
            return

        def do_mark():
            if hasattr(self.controller, "mark_all_read"):
                return int(self.controller.mark_all_read(role) or 0)
            items = self.controller.get_notifications(role=role, unread_only=True) or []
            count = 0
            for item in items:
                nid = self._extract_id(item)
                if nid:
                    self.controller.mark_read(nid)
                    count += 1
            return count

        def on_ok(updated):
            if self._destroyed:
                return
            SoundManager.stop_reminder()
            self._previous_notification_ids = set()
            print(f"✅ Marked {updated} notification(s) as read")
            # Force sidebar badge to 0 immediately (don't wait for poll / stale API)
            try:
                top = self.winfo_toplevel()
                btn = getattr(top, "_nav_buttons", {}).get("Notifications")
                if btn is not None and hasattr(btn, "set_badge"):
                    btn.set_badge(0)
                if hasattr(top, "_last_unread"):
                    top._last_unread = 0
                if hasattr(top, "_poll_notification_badge"):
                    top.after(500, top._poll_notification_badge)
            except Exception:
                pass
            self.refresh()
            messagebox.showinfo(
                "Notifications",
                f"Marked {updated} notification(s) as read." if updated else "No unread notifications.",
            )

        def on_err(exc):
            print(f"⚠️ Mark all as read failed: {exc}")
            import traceback
            traceback.print_exc()
            messagebox.showerror("Error", f"Could not mark all as read:\n{exc}")

        run_in_background(self, do_mark, on_ok, on_err, name="notif-mark-all")

    def refresh(self):
        if self._destroyed:
            return

        role = self.role_var.get()
        unread_only = self.unread_var.get()

        def fetch():
            display = self.controller.get_notifications(role=role, unread_only=unread_only)
            unread = self.controller.get_notifications(role=role, unread_only=True)
            return display, unread

        def apply(result):
            if self._destroyed:
                return
            display_notifications, unread_check = result
            for child in self.list_frame.winfo_children():
                child.destroy()

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

            try:
                if current_ids:
                    self.mark_all_btn.configure(state="normal")
                else:
                    self.mark_all_btn.configure(state="disabled")
            except Exception:
                pass

            # Unread / missed banner (shows exact count e.g. 9)
            unread_count = len(current_ids)
            try:
                if unread_count > 0:
                    label = "missed notification" if unread_count == 1 else "missed notifications"
                    self.summary_label.configure(
                        text=f"You have {unread_count} {label}",
                        text_color="#DC2626",
                    )
                    self.unread_chip.configure(text=f"  {unread_count}  ")
                    if not self.unread_chip.winfo_ismapped():
                        self.unread_chip.pack(side="left", padx=(10, 0))
                else:
                    self.summary_label.configure(
                        text="All caught up — no unread notifications",
                        text_color=Theme.MUTED_TEXT,
                    )
                    try:
                        self.unread_chip.pack_forget()
                    except Exception:
                        pass
            except Exception as exc:
                print(f"⚠️ summary banner update failed: {exc}")

            if not display_notifications:
                ctk.CTkLabel(
                    self.list_frame,
                    text="No notifications found",
                    font=("Segoe UI", 13),
                    text_color=Theme.MUTED_TEXT,
                ).pack(pady=40)
                return

            for item in display_notifications:
                notification = self._convert(item)
                card = NotificationCard(
                    self.list_frame,
                    notification,
                    self.mark_as_read,
                )
                card.pack(fill="x", pady=6)

        def failed(exc):
            print(f"⚠️ notifications refresh failed: {exc}")
            if self._destroyed:
                return
            for child in self.list_frame.winfo_children():
                child.destroy()
            ctk.CTkLabel(
                self.list_frame,
                text="Could not load notifications",
                font=("Segoe UI", 13),
                text_color=Theme.MUTED_TEXT,
            ).pack(pady=40)

        gen = bump_generation(self)
        run_in_background(self, fetch, apply, failed, name="notifications-loader", generation=gen)

    def mark_as_read(self, notification_id):
        if not notification_id:
            return

        notification_id_str = str(notification_id)
        print(f"📋 Marking notification as read: {notification_id_str}")

        def do_mark():
            return self.controller.mark_read(notification_id_str)

        def on_ok(_result):
            if self._destroyed:
                return
            print(f"✅ Notification {notification_id_str} marked as read")
            SoundManager.stop_reminder()
            self.refresh()
            # Refresh sidebar badge
            try:
                top = self.winfo_toplevel()
                if hasattr(top, "_poll_notification_badge"):
                    top.after(200, top._poll_notification_badge)
            except Exception:
                pass

        def on_err(exc):
            print(f"Mark read failed: {exc}")
            import traceback
            traceback.print_exc()

        run_in_background(self, do_mark, on_ok, on_err, name="notif-mark-read")

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
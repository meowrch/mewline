import contextlib
import os
from typing import TYPE_CHECKING

from fabric.notifications.service import Notification
from fabric.notifications.service import NotificationAction
from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.button import Button as FabricButton
from fabric.widgets.centerbox import CenterBox as FabricCenterBox
from fabric.widgets.image import Image
from fabric.widgets.image import Image as FabricImage
from fabric.widgets.label import Label
from fabric.widgets.stack import Stack as FabricStack
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import GLib
from gi.repository import Gtk
from loguru import logger

from mewline import constants as cnst
from mewline.services import cache_notification_service
from mewline.services import notification_service
from mewline.shared.rounded_image import CustomImage
from mewline.utils.misc import check_icon_exists
from mewline.widgets.dynamic_island.base import BaseDiWidget

if TYPE_CHECKING:
    from mewline.widgets.dynamic_island import DynamicIsland


class ActionButton(Button):
    def __init__(
        self, action: NotificationAction, _index: int, _total: int, notification_box
    ):
        super().__init__(
            name="action-button",
            h_expand=True,
            on_clicked=self.on_clicked,
            child=Label(name="button-label", label=action.label),
        )
        self.action = action
        self.notification_box = notification_box
        self.add_style_class("action")
        # Pause dismissal when hovering action buttons so user has time to click
        self.connect(
            "enter-notify-event", lambda *_: notification_box.hover_button(self)
        )
        self.connect(
            "leave-notify-event", lambda *_: notification_box.unhover_button(self)
        )

    def on_clicked(self, *_):
        # Mark that at least one action was invoked for this notification
        with contextlib.suppress(Exception):
            self.notification_box._any_action_invoked = True

        # Invoke the action and then close the notification as dismissed-by-user
        try:
            parent = getattr(self.action, "parent", None)
            action_id = None
            for attr in ("id", "key", "action_id", "identifier", "name"):
                if hasattr(self.action, attr):
                    action_id = getattr(self.action, attr)
                    if action_id:
                        break
            if (
                parent is not None
                and hasattr(parent, "invoke_action")
                and action_id is not None
            ):
                parent.invoke_action(action_id)
            else:
                self.action.invoke()
        except Exception as e:
            logger.error(f"Action invoke failed: {e}")
        # Attempt to close via the underlying notification
        try:
            if hasattr(self.action, "parent") and self.action.parent is not None:
                self.action.parent.close("dismissed-by-user")
            elif hasattr(self.notification_box, "notification"):
                self.notification_box.notification.close("dismissed-by-user")
        except Exception as e:
            logger.warning(f"Failed to close notification after action: {e}")


class NotificationBox(Box):
    def __init__(self, notification: Notification, timeout_ms=5000, **kwargs):
        urgency_class = {
            0: ("low-urgency", False),
            1: ("normal-urgency", False),
            2: ("critical-urgency", True),
        }

        super().__init__(
            name="notification-box",
            orientation="v",
            h_expand=True,
            v_expand=True,
            h_align="fill",
            spacing=10,
            pass_through=False,
            children=[
                self.create_content(notification),
                Box(
                    spacing=10,
                    orientation="vertical",
                    children=[
                        self.create_action_buttons(notification),
                        Box(
                            name="notification-urgency-line",
                            visible=urgency_class.get(
                                notification.urgency, urgency_class[0]
                            )[1],
                            h_expand=True,
                            h_align="fill",
                            style_classes=urgency_class.get(
                                notification.urgency, urgency_class[0]
                            )[0],
                        ),
                    ],
                ),
            ],
        )
        self.notification = notification
        self._any_action_invoked = False
        # If there are actions: we still use timeout to hide the card,
        # but we will NOT mark as EXPIRED
        # Critical urgency: keep until user closes
        if getattr(notification, "urgency", 1) == 2:
            self.timeout_ms = 0
        else:
            self.timeout_ms = timeout_ms
        self._timeout_id = None
        # Island-level hover detection will handle pausing, keep simple setup
        self.start_timeout()

    def create_content(self, notification):
        return Box(
            name="notification-content",
            spacing=8,
            v_align="start",
            h_expand=True,
            h_align="fill",
            children=[
                Box(
                    name="notification-image",
                    v_align="start",
                    children=CustomImage(
                        pixbuf=notification.image_pixbuf.scale_simple(
                            48, 48, GdkPixbuf.InterpType.BILINEAR
                        )
                        if notification.image_pixbuf
                        else self.get_pixbuf(notification.app_icon, 48, 48)
                    ),
                ),
                Box(
                    name="notification-text",
                    orientation="v",
                    v_align="start",
                    h_expand=True,
                    h_align="fill",
                    children=[
                        Box(
                            name="notification-summary-box",
                            orientation="h",
                            h_expand=True,
                            children=[
                                Label(
                                    name="notification-title",
                                    markup=GLib.markup_escape_text(
                                        notification.summary.replace("\n", " ")
                                    ),
                                    h_align="start",
                                    ellipsization="end",
                                    xalign=0,
                                ),
                                Label(
                                    name="notification-app-name",
                                    markup=" | "
                                    + GLib.markup_escape_text(notification.app_name),
                                    h_align="start",
                                    ellipsization="end",
                                    xalign=0,
                                ),
                            ],
                        ),
                        Label(
                            name="notification-text",
                            markup=GLib.markup_escape_text(
                                notification.body.replace("\n", " ")
                            ),
                            h_align="start",
                            ellipsization="end",
                        )
                        if notification.body
                        else Box(),
                    ],
                ),
                Box(
                    orientation="v",
                    v_align="start",
                    children=[
                        self.create_close_button(),
                        Box(v_expand=True),
                    ],
                ),
            ],
        )

    def get_pixbuf(self, icon_path, width, height):
        if icon_path.startswith("file://"):
            icon_path = icon_path[7:]

        if not os.path.exists(icon_path):
            logger.warning(f"Icon path does not exist: {icon_path}")
            return None

        try:
            pixbuf = GdkPixbuf.Pixbuf.new_from_file(icon_path)
            return pixbuf.scale_simple(width, height, GdkPixbuf.InterpType.BILINEAR)
        except Exception as e:
            logger.error(f"Failed to load or scale icon: {e}")
            return None

    def create_action_buttons(self, notification):
        return Box(
            name="notification-action-buttons",
            spacing=8,
            h_expand=True,
            children=[
                ActionButton(action, i, len(notification.actions), self)
                for i, action in enumerate(notification.actions)
            ],
        )

    def create_close_button(self):
        close_button = Button(
            name="notify-close-button",
            visible=True,
            h_align="end",
            v_align="start",
            image=Image(
                style_classes="close-icon",
                icon_name=check_icon_exists(
                    "close-symbolic",
                    cnst.icons["ui"]["close"],
                ),
                icon_size=16,
            ),
            on_clicked=lambda _: self.close_notification(),
        )
        close_button.connect(
            "enter-notify-event", lambda *_: self.hover_button(close_button)
        )
        close_button.connect(
            "leave-notify-event", lambda *_: self.unhover_button(close_button)
        )
        return close_button

    def start_timeout(self):
        self.stop_timeout()
        if not self.timeout_ms or self.timeout_ms == 0:
            return
        self._timeout_id = GLib.timeout_add(self.timeout_ms, self.close_notification)

    def stop_timeout(self):
        if self._timeout_id is not None:
            GLib.source_remove(self._timeout_id)
            self._timeout_id = None

    def close_notification(self):
        # If this notification has actions and no action has been invoked yet,
        # hide it from the view without marking it as EXPIRED.
        try:
            has_actions = bool(getattr(self.notification, "actions", []))
        except Exception:
            has_actions = False
        if has_actions and not getattr(self, "_any_action_invoked", False):
            # Ask container to remove from view without closing upstream
            try:
                if hasattr(self, "_container") and self._container is not None:
                    self._container.remove_box_without_close(self)
            except Exception:
                # Fallback: just hide
                with contextlib.suppress(Exception):
                    self.set_visible(False)
            self.stop_timeout()
            return False
        # Normal close flow (no actions or user has already clicked action)
        with contextlib.suppress(Exception):
            self.notification.close("expired")
        self.stop_timeout()
        return False

    def pause_timeout(self):
        self.stop_timeout()

    def resume_timeout(self):
        self.start_timeout()

    def destroy(self):
        self.stop_timeout()
        super().destroy()

    @staticmethod
    def set_pointer_cursor(widget, cursor_name):
        """Cambia el cursor sobre un widget."""
        window = widget.get_window()
        if window:
            cursor = Gdk.Cursor.new_from_name(widget.get_display(), cursor_name)
            window.set_cursor(cursor)

    def hover_button(self, button):
        self.pause_timeout()
        self.set_pointer_cursor(button, "hand2")

    def unhover_button(self, button):
        self.resume_timeout()
        self.set_pointer_cursor(button, "arrow")


class NotificationContainer(BaseDiWidget, Box):
    """Widget for notification."""

    __slots__ = "dynamic_island"
    focuse_kb: bool = False

    def __init__(self, di: "DynamicIsland"):
        Box.__init__(
            self,
            name="notification",
            orientation="v",
            spacing=4,
            v_expand=True,
            h_expand=True,
        )
        self.dynamic_island = di
        self._boxes_by_id: dict[int, NotificationBox] = {}
        notification_service.connect("notification-added", self.on_new_notification)

        # Dedicated view carousel (stack + dots + prev/next)
        self.view_stack = FabricStack(
            name="di-notification-stack",
            transition_type="slide-left-right",
            transition_duration=200,
            v_expand=True,
            h_expand=True,
        )
        self.view_prev_btn = FabricButton(
            name="inline-nav-button",
            v_align="center",
            h_align="center",
            v_expand=False,
            h_expand=False,
            child=FabricImage(icon_name="go-previous-symbolic", icon_size=12),
            on_clicked=lambda *_: self._view_prev(),
        )
        self.view_prev_btn.add_style_class("nav-left")

        # Close button for dedicated view (top-right)
        self.view_close_btn = FabricButton(
            name="inline-close-button",
            v_align="start",
            h_align="end",
            child=FabricImage(icon_name="window-close-symbolic", icon_size=16),
            on_clicked=lambda *_: self._view_close_current(),
        )

        self.view_next_btn = FabricButton(
            name="inline-nav-button",
            v_align="center",
            h_align="center",
            v_expand=False,
            h_expand=False,
            child=FabricImage(icon_name="go-next-symbolic", icon_size=12),
            on_clicked=lambda *_: self._view_next(),
        )
        self.view_next_btn.add_style_class("nav-right")
        self.view_next_btn.set_valign(Gtk.Align.CENTER)
        self.view_next_btn.set_halign(Gtk.Align.CENTER)

        self.view_dots = Box(
            name="inline-dots", orientation="h", spacing=6, h_align="center"
        )
        # Center column: stack expands, dots at bottom
        self.view_center = Box(
            orientation="v",
            v_expand=True,
            h_expand=True,
            children=[
                Box(v_expand=True, h_expand=True, children=[self.view_stack]),
                self.view_dots,
            ],
        )

        # Right column: copy exact structure from inline capsule (which works perfectly)
        self.view_next_btn.set_halign(Gtk.Align.CENTER)
        self.view_next_btn.set_valign(Gtk.Align.CENTER)

        self.view_right = FabricCenterBox(
            orientation="v",
            start_children=self.view_close_btn,
            center_children=self.view_next_btn,
            end_children=Box(v_expand=True),
            v_expand=True,
            h_expand=False,
        )

        self.view_box = FabricCenterBox(
            name="di-notification-carousel",
            start_children=self.view_prev_btn,
            center_children=self.view_center,
            end_children=self.view_right,
            v_expand=True,
            h_expand=True,
        )

        # Simple single-notification container (no CenterBox)
        self.simple_container = Box(
            name="di-single-notification",
            orientation="v",
            v_expand=True,
            h_expand=True,
        )
        # Add both to this container; we toggle visibility
        self.add(self.simple_container)
        self.add(self.view_box)
        # Initially hide both (no items yet)
        with contextlib.suppress(Exception):
            self.simple_container.set_visible(False)
            self.view_box.set_visible(False)

        self._view_items: list[NotificationBox] = []
        self._view_index: int = 0
        self._nav_attached: bool = True
        # Ensure nav containers are attached initially so center content can fill width
        self._attach_nav()
        self._update_view_nav()

    def _view_prev(self, *args):
        if self._view_index > 0:
            self._view_index -= 1
            self.view_stack.set_visible_child(self._view_items[self._view_index])
            self._update_view_nav()

    def _view_next(self, *args):
        if self._view_index < len(self._view_items) - 1:
            self._view_index += 1
            self.view_stack.set_visible_child(self._view_items[self._view_index])
            self._update_view_nav()

    def _view_go_to(self, idx: int):
        if 0 <= idx < len(self._view_items):
            self._view_index = idx
            self.view_stack.set_visible_child(self._view_items[self._view_index])
            self._update_view_nav()

    def _attach_nav(self):
        try:
            # Add back to containers if missing
            try:
                if self.view_prev_btn.get_parent() is None:
                    self.view_box.start_container.add(self.view_prev_btn)
            except Exception:
                ...
            try:
                if self.view_right.get_parent() is None:
                    self.view_box.end_container.add(self.view_right)
            except Exception:
                ...
        except Exception:
            ...
        self._nav_attached = True

    def _detach_nav(self):
        try:
            # Remove from containers so no space is reserved
            try:
                if self.view_prev_btn.get_parent() is not None:
                    self.view_box.start_container.remove(self.view_prev_btn)
            except Exception:
                ...
            try:
                if self.view_right.get_parent() is not None:
                    self.view_box.end_container.remove(self.view_right)
            except Exception:
                ...
        except Exception:
            ...
        self._nav_attached = False

    def _show_single_notification(self, box: Box):
        # Place a single notification box inside the simple container and show it
        try:
            for child in list(self.simple_container.get_children()):
                self.simple_container.remove(child)
        except Exception:
            ...
        with contextlib.suppress(Exception):
            self.simple_container.add(box)
            self.simple_container.set_visible(True)
            self.view_box.set_visible(False)

    def _show_multi_notification_view(self):
        # Show the carousel view and hide single-container
        with contextlib.suppress(Exception):
            self.simple_container.set_visible(False)
            self.view_box.set_visible(True)

    def _update_view_nav(self):
        # If in single-notification mode, no nav visuals needed
        try:
            if self.simple_container.get_visible():
                # Ensure nav hidden
                with contextlib.suppress(Exception):
                    self.view_prev_btn.set_visible(False)
                    self.view_next_btn.set_visible(False)
                    self.view_dots.set_visible(False)
                    if hasattr(self, "view_close_btn"):
                        self.view_right.set_visible(False)
                        self.view_close_btn.set_visible(False)
                return
        except Exception:
            ...

        # Dots
        try:
            for child in list(self.view_dots.get_children()):
                self.view_dots.remove(child)
                child.destroy()
        except Exception:
            ...

        for i in range(len(self._view_items)):
            dot_shape = Box(name="inline-dot-shape")
            dot = FabricButton(
                name="inline-dot",
                on_clicked=(lambda _w, idx=i: self._view_go_to(idx)),
                child=dot_shape,
            )
            if i == self._view_index:
                dot.add_style_class("active")
            self.view_dots.add(dot)

        show_nav = len(self._view_items) > 1

        # Keep navigation containers attached at all times so the center content can
        # take the full available width of the island. We only toggle visibility.
        # This prevents the CenterBox from collapsing to the natural width of the
        # center child (which caused the "centered narrow" appearance).
        try:
            if not getattr(self, "_nav_attached", False):
                self._attach_nav()
        except Exception:
            ...

        self.view_prev_btn.set_visible(show_nav)
        self.view_next_btn.set_visible(show_nav)
        self.view_dots.set_visible(show_nav)
        # Show external close only when multiple notifications;
        # otherwise rely on internal close
        if hasattr(self, "view_close_btn"):
            self.view_right.set_visible(show_nav)
            self.view_close_btn.set_visible(show_nav)
        # Ensure current item's internal close visibility matches
        if self._view_items:
            current = self._view_items[self._view_index]
            self._set_internal_close_visibility(current, not show_nav)

    def on_new_notification(self, fabric_notif, id):
        notification: Notification = fabric_notif.get_notification_from_id(id)
        cache_notification_service.cache_notification(notification)

        if cache_notification_service.dont_disturb:
            return

        new_box = NotificationBox(notification)
        # Link back so the box can request removal without closing upstream
        with contextlib.suppress(Exception):
            new_box._container = self

        # Track the box by notification id for later cleanup
        with contextlib.suppress(Exception):
            self._boxes_by_id[notification.id] = new_box

        # Connect close handler
        notification.connect("closed", self.on_notification_closed)

        # If DI is already open to some widget (and it's not the notification view),
        # show the notification inline below without interrupting the current view.
        di_open_to_other = (
            self.dynamic_island.current_widget is not None
            and self.dynamic_island.current_widget != "notification"
        )
        if di_open_to_other:
            new_box._inline = True
            self.dynamic_island.show_inline_notification(new_box)
            return

        # Dedicated notification view logic
        pre_count = len(self._view_items)
        new_box._inline = False

        if pre_count == 0:
            # Single mode: show only the box in a simple container (no CenterBox)
            self._view_items.append(new_box)
            self._view_index = 0
            self._set_internal_close_visibility(new_box, True)
            self._show_single_notification(new_box)
        elif pre_count >= 1:
            # If we were in single mode, migrate the existing box into the stack
            if self.simple_container.get_visible():
                try:
                    existing_children = list(self.simple_container.get_children())
                except Exception:
                    existing_children = []
                if existing_children:
                    first_box = existing_children[0]
                    with contextlib.suppress(Exception):
                        self.simple_container.remove(first_box)
                    with contextlib.suppress(Exception):
                        self.view_stack.add_named(
                            first_box, f"n-{getattr(first_box.notification, 'id', 'x')}"
                        )
                self._show_multi_notification_view()

            # Add the new box to the carousel
            self.view_stack.add_named(new_box, f"n-{notification.id}")
            self._view_items.append(new_box)
            self._view_index = len(self._view_items) - 1
            self.view_stack.set_visible_child(new_box)
            # Multiple notifications => use external close, hide internal
            self._set_internal_close_visibility(new_box, False)
            self._update_view_nav()

        # Ensure DI is open to notification view
        self.dynamic_island.open("notification")

    def _hide_internal_close_button(self, container: Box):
        try:

            def hide_in(widget):
                try:
                    if (
                        hasattr(widget, "get_name")
                        and widget.get_name() == "notify-close-button"
                    ):
                        widget.set_visible(False)
                        return True
                except Exception:
                    ...

                try:
                    for child in widget.get_children():
                        if hide_in(child):
                            return True
                except Exception:
                    ...

                return False

            hide_in(container)
        except Exception:
            ...

    def _set_internal_close_visibility(self, container: Box, visible: bool):
        try:

            def set_vis(widget):
                try:
                    if (
                        hasattr(widget, "get_name")
                        and widget.get_name() == "notify-close-button"
                    ):
                        widget.set_visible(visible)
                        return True
                except Exception:
                    ...

                try:
                    for child in widget.get_children():
                        if set_vis(child):
                            return True
                except Exception:
                    ...

                return False

            set_vis(container)
        except Exception:
            ...

    def _view_close_current(self):
        if not self._view_items:
            return
        current = self._view_items[self._view_index]
        try:
            current.notification.close("dismissed-by-user")
        except Exception:
            # Fallback
            with contextlib.suppress(Exception):
                self.view_stack.remove(current)

    def remove_box_without_close(self, notif_box: Box):
        # Remove notification box from dedicated carousel (or inline area)
        # without closing upstream notification
        if getattr(notif_box, "_inline", False):
            # Inline area removal
            self.dynamic_island.remove_inline_notification(notif_box)
            with contextlib.suppress(Exception):
                notif_box.destroy()
            return
        # Dedicated view removal
        if notif_box in self._view_items:
            idx = self._view_items.index(notif_box)
            try:
                if notif_box.get_parent() == self.view_stack:
                    self.view_stack.remove(notif_box)
                elif (
                    self.simple_container.get_visible()
                    and notif_box.get_parent() == self.simple_container
                ):
                    self.simple_container.remove(notif_box)
            except Exception:
                ...
            self._view_items.pop(idx)
            # Decide whether to switch modes based on remaining count
            if len(self._view_items) == 0:
                self._view_index = 0
                with contextlib.suppress(Exception):
                    self.simple_container.set_visible(False)
                    self.view_box.set_visible(False)
                # Close DI if we're in notification view and no items left
                try:
                    if self.dynamic_island.current_widget == "notification":
                        self.dynamic_island.close()
                except Exception:
                    ...
            elif len(self._view_items) == 1:
                # Switch to single mode
                remaining = self._view_items[0]
                with contextlib.suppress(Exception):
                    if remaining.get_parent() == self.view_stack:
                        self.view_stack.remove(remaining)
                self._set_internal_close_visibility(remaining, True)
                self._show_single_notification(remaining)
            else:
                # Stay in multi mode
                self._view_index = min(idx, len(self._view_items) - 1)
                self.view_stack.set_visible_child(self._view_items[self._view_index])
                self._update_view_nav()
        with contextlib.suppress(Exception):
            notif_box.destroy()

    def on_notification_closed(self, notification, reason):
        logger.info(f"Notification {notification.id} closed with reason: {reason}")
        notif_box = self._boxes_by_id.pop(notification.id, None)
        if notif_box is not None and getattr(notif_box, "_inline", False):
            # Remove from inline area only
            self.dynamic_island.remove_inline_notification(notif_box)
            with contextlib.suppress(Exception):
                notif_box.destroy()

            return

        # Remove from dedicated carousel or single container
        if notif_box in self._view_items:
            idx = self._view_items.index(notif_box)
            try:
                if notif_box.get_parent() == self.view_stack:
                    self.view_stack.remove(notif_box)
                elif (
                    self.simple_container.get_visible()
                    and notif_box.get_parent() == self.simple_container
                ):
                    self.simple_container.remove(notif_box)
            except Exception:
                ...

            self._view_items.pop(idx)
            if len(self._view_items) == 0:
                # No notifications left in dedicated view: close DI
                self._view_index = 0
                with contextlib.suppress(Exception):
                    self.simple_container.set_visible(False)
                    self.view_box.set_visible(False)
                try:
                    if self.dynamic_island.current_widget == "notification":
                        self.dynamic_island.close()
                except Exception:
                    ...
            elif len(self._view_items) == 1:
                # Switch to single mode with the remaining box
                remaining = self._view_items[0]
                with contextlib.suppress(Exception):
                    if remaining.get_parent() == self.view_stack:
                        self.view_stack.remove(remaining)
                self._set_internal_close_visibility(remaining, True)
                self._show_single_notification(remaining)
            else:
                # Stay in multi mode
                self._view_index = min(idx, len(self._view_items) - 1)
                self.view_stack.set_visible_child(self._view_items[self._view_index])
                self._update_view_nav()

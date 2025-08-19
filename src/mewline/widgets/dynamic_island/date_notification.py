import contextlib
import time

import gi
from fabric.notifications import Notification
from fabric.utils import invoke_repeater
from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.image import Image
from fabric.widgets.label import Label
from fabric.widgets.revealer import Revealer
from fabric.widgets.scrolledwindow import ScrolledWindow
from gi.repository import GdkPixbuf
from gi.repository import GLib
from gi.repository import Gtk
from loguru import logger

import mewline.constants as cnst
from mewline.services import cache_notification_service
from mewline.services import notification_service
from mewline.shared.rounded_image import CustomImage
from mewline.utils.misc import check_icon_exists
from mewline.utils.misc import parse_markup
from mewline.utils.misc import uptime
from mewline.utils.widget_utils import get_icon
from mewline.utils.widget_utils import setup_cursor_hover
from mewline.widgets.dynamic_island.base import BaseDiWidget

gi.require_version("Gtk", "3.0")


class NotificationHistoryEl(Box):
    def __init__(
        self,
        id: int,
        notification: Notification,
        actions_clicked: bool = False,
        on_removed=None,
    ):
        urgency_class = {0: "low-urgency", 1: "normal-urgency", 2: "critical-urgency"}
        self._any_action_invoked = False
        self._id = id
        self._actions_clicked_initial = actions_clicked
        self._on_removed = on_removed

        Box.__init__(
            self,
            name="notification-history-el",
            orientation="h",
            spacing=16,
            v_expand=True,
            h_expand=True,
            pass_through=True,
            style_classes=urgency_class.get(notification.urgency, "low-urgency"),
        )

        self._notification = notification

        self.close_button = Button(
            style_classes="close-button",
            visible=True,
            h_align="end",
            image=Image(
                style_classes="close-icon",
                icon_name=check_icon_exists(
                    "close-symbolic",
                    cnst.icons["ui"]["close"],
                ),
                icon_size=16,
            ),
            on_clicked=lambda _: self.clear_notification(id),
        )

        self.image: CustomImage = None
        try:
            if image_pixbuf := self._notification.image_pixbuf:
                self.image = CustomImage(
                    pixbuf=image_pixbuf.scale_simple(
                        64,
                        64,
                        GdkPixbuf.InterpType.BILINEAR,
                    ),
                    style_classes="image",
                )
        except GLib.GError:
            logger.warning("[Notification] Image not available.")

        self.notification_icon = get_icon(notification.app_icon)
        self.summary_label = Label(
            markup=GLib.markup_escape_text(notification.summary),
            h_align="start",
            h_expand=True,
            ellipsization="end",
            line_wrap="word-char",
            style_classes="summary",
        )
        self.header_box = Box(orientation="h", spacing=8)
        if not self.image:
            self.header_box.add(self.notification_icon)

        self.header_box.add(self.summary_label)
        self.header_box.add(self.close_button)

        # Build action buttons (if any) under the body text
        self.actions_box = None
        try:
            actions = list(getattr(self._notification, "actions", []) or [])
        except Exception:
            actions = []
        if actions and not self._actions_clicked_initial:

            def make_action_btn(act):
                btn = Button(
                    name="history-action-button",
                    h_expand=False,
                    child=Label(name="button-label", label=getattr(act, "label", "")),
                )
                setup_cursor_hover(btn)

                def on_click(_w):
                    # Mark that at least one action was invoked and hide actions row
                    if not self._any_action_invoked:
                        self._any_action_invoked = True
                        try:
                            if self.actions_box is not None:
                                self.actions_box.set_visible(False)
                                parent = self.actions_box.get_parent()
                                if parent is not None:
                                    parent.remove(self.actions_box)
                        except Exception:
                            ...
                        # Persist that an action was clicked for this history item
                        with contextlib.suppress(Exception):
                            cache_notification_service.mark_action_clicked(self._id)
                    try:
                        parent = getattr(act, "parent", None)
                        action_id = None
                        for attr in ("id", "key", "action_id", "identifier", "name"):
                            if hasattr(act, attr):
                                action_id = getattr(act, attr)
                                if action_id:
                                    break
                        if (
                            parent is not None
                            and hasattr(parent, "invoke_action")
                            and action_id is not None
                        ):
                            parent.invoke_action(action_id)
                        else:
                            act.invoke()
                    except Exception as e:
                        logger.warning(f"History action invoke failed: {e}")

                btn.connect("clicked", on_click)
                return btn

            self.actions_box = Box(
                name="notification-history-actions",
                orientation="h",
                spacing=6,
                children=[make_action_btn(a) for a in actions],
            )

        self.main_container = Box(
            orientation="v",
            spacing=4,
            h_expand=True,
            children=[
                self.header_box,
                Label(
                    markup=GLib.markup_escape_text(
                        parse_markup(self._notification.body)
                    ),
                    line_wrap="word-char",
                    ellipsization="end",
                    v_align="start",
                    h_expand=True,
                    h_align="start",
                    style_classes="text",
                ),
                *([self.actions_box] if self.actions_box is not None else []),
            ],
        )

        if self.image:
            self.children = [self.image, self.main_container]
        else:
            self.children = [self.main_container]

    def clear_notification(self, id):
        cache_notification_service.remove_notification(id)
        if callable(self._on_removed):
            with contextlib.suppress(Exception):
                self._on_removed(id)
        GLib.timeout_add(400, self.destroy)


class NotificationGroup(Box):
    def __init__(self, app_name: str, app_icon_widget: Image | Box, on_empty=None, on_single_left=None):
        super().__init__(
            name="notification-group",
            orientation="v",
            spacing=6,
            h_expand=True,
        )
        self.app_name = app_name
        self.on_empty = on_empty
        self.on_single_left = on_single_left
        self.items: list[NotificationHistoryEl] = []
        self.expanded = False

        # Header with app icon, app name, count, toggles expand/collapse
        self.count_label = Label(name="group-count", label="0")
        # Collapse/expand icon button (always visible, toggles state)
        self.collapse_icon_btn = Button(
            name="group-collapse-icon",
            on_clicked=lambda *_: self.toggle(),
            child=Label(name="group-collapse-icon-label", label="󰡍"),
            visible=True,
        )
        # Close (clear group) icon button
        self.group_close_btn = Button(
            name="group-close-icon",
            on_clicked=lambda *_: self.clear_group(),
            image=Image(
                style_classes="close-icon",
                icon_name=check_icon_exists(
                    "close-symbolic",
                    cnst.icons["ui"]["close"],
                ),
                icon_size=14,
            ),
            visible=True,
        )
        # Header pill (not a button anymore; icon handles toggling)
        # Make app name clickable (acts like toggle)
        self.app_name_btn = Button(
            name="group-app-btn",
            on_clicked=lambda *_: self.toggle(),
            child=Label(name="group-app-name", label=app_name or "Unknown app"),
        )
        self.header_btn = Box(
            name="group-header",
            h_align="fill",
            h_expand=True,
            orientation="h",
            spacing=8,
            children=(
                app_icon_widget,
                self.app_name_btn,
                Box(h_expand=True),
                self.count_label,
                self.collapse_icon_btn,
                self.group_close_btn,
            ),
        )

        # Collapsed stacked preview container via Gtk.Overlay
        self.collapsed_base = Box(name="group-collapsed-base", orientation="v")
        self.collapsed_overlay = Gtk.Overlay()
        self.collapsed_overlay.add(self.collapsed_base)
        # Ensure collapsed overlay is visible by default
        with contextlib.suppress(Exception):
            self.collapsed_overlay.set_visible(True)

        # Expanded container (list of full items)
        self.expanded_box = Box(name="group-body", orientation="v", spacing=8)
        self.revealer = Revealer(reveal_child=False, child=self.expanded_box)

        self.children = (self.header_btn, self.collapsed_overlay, self.revealer)
        self.update_count()

    def update_count(self):
        self.count_label.set_text(str(len(self.items)))

    def add_item(self, item: NotificationHistoryEl):
        def _on_removed(_id):
            if item in self.items:
                self.items.remove(item)
                self.update_count()
                # If only one item remains, promote it out of the group
                if len(self.items) == 1 and callable(self.on_single_left):
                    try:
                        self.on_single_left(self, self.items[0])
                        return
                    except Exception:
                        ...
                # Refresh stack immediately and again on idle to ensure sizes update
                try:
                    self.refresh_view()
                    GLib.idle_add(lambda: (self.refresh_view(), False))
                except Exception:
                    ...
                if not self.items and callable(self.on_empty):
                    self.on_empty(self)
        # inject removal callback
        item._on_removed = _on_removed
        self.items.insert(0, item)  # newest on top
        self.update_count()
        self.refresh_view()

    def refresh_view(self):
        # Update collapsed preview using Gtk.Overlay: up to 3 most recent items
        # Clear existing overlay children except the base
        try:
            for child in list(self.collapsed_overlay.get_children()):
                if child is not self.collapsed_base:
                    self.collapsed_overlay.remove(child)
        except Exception:
            # If removal fails, recreate overlay
            try:
                parent = self.collapsed_overlay.get_parent()
                if parent is not None:
                    parent.remove(self.collapsed_overlay)
            except Exception:
                ...
            self.collapsed_overlay = Gtk.Overlay()
            self.collapsed_base = Box(name="group-collapsed-base", orientation="v")
            self.collapsed_overlay.add(self.collapsed_base)
            # Reinsert into layout
            # Replace second child in self.children tuple
            with contextlib.suppress(Exception):
                self.children = (self.header_btn, self.collapsed_overlay, self.revealer)

        max_preview = 4
        slice_items = self.items[:max_preview]
        # Ensure overlay has enough height to show stacked cards
        step_top = 14  # vertical offset per layer (fixed)
        side_step = 14  # horizontal side margins per layer (for centered narrowing)
        card_height = 100  # fixed compact card height for uniform protrusion
        total_layers = len(slice_items)
        buffer_bottom = 24  # extra space to avoid clipping into next group
        base_height = card_height + step_top * max(0, total_layers - 1) + buffer_bottom
        try:
            # Reserve height on the overlay itself to avoid being clipped by parent
            self.collapsed_overlay.set_size_request(-1, base_height)
            self.collapsed_base.set_size_request(-1, base_height)
        except Exception:
            ...

        # Add older first so newest is on top.
        # Compute margins so newest has zero margins.
        for depth, it in enumerate(reversed(slice_items)):
            inv = max(0, (total_layers - 1) - depth)
            try:
                notif = getattr(it, "_notification", None)
                header_children = []
                if notif and getattr(notif, "app_icon", None):
                    header_children.append(get_icon(notif.app_icon))
                header_children.append(
                    Label(
                        markup=GLib.markup_escape_text(getattr(notif, "summary", "")),
                        ellipsization="end",
                        h_align="start",
                        h_expand=True,
                        style_classes="summary",
                    )
                )
                # Compact preview without body for consistent height
                preview_card_children = [
                    Box(orientation="h", spacing=8, children=tuple(header_children)),
                ]
                preview_card = Box(
                    name="notification-history-el",
                    orientation="v",
                    spacing=4,
                    children=tuple(preview_card_children),
                )
                with contextlib.suppress(Exception):
                    preview_card.set_size_request(-1, card_height)
                    preview_card.set_vexpand(False)
            except Exception:
                preview_card = Box(name="notification-history-el")
                with contextlib.suppress(Exception):
                    preview_card.set_size_request(-1, card_height)
                    preview_card.set_vexpand(False)
            # Add as overlay child and offset it to create ladder
            self.collapsed_overlay.add_overlay(preview_card)
            try:
                preview_card.set_halign(Gtk.Align.FILL)
                preview_card.set_valign(Gtk.Align.START)
                preview_card.set_margin_top(inv * step_top)
                # Centered narrowing: equal side margins
                preview_card.set_margin_start(inv * side_step)
                preview_card.set_margin_end(inv * side_step)
            except Exception:
                ...

        # Update expanded list
        self.expanded_box.children = tuple(self.items)

    def set_expanded(self, value: bool):
        self.expanded = value
        self.revealer.set_reveal_child(value)
        self.collapsed_overlay.set_visible(not value)

    def toggle(self):
        self.set_expanded(not self.expanded)

    def clear_group(self):
        try:
            # Make a copy to avoid modification during iteration
            for it in list(self.items):
                with contextlib.suppress(Exception):
                    it.clear_notification(it._id)
        except Exception:
            ...


class DateNotificationMenu(BaseDiWidget, Box):
    """A menu to display the weather information."""

    focuse_kb: bool = True

    def __init__(self) -> None:
        Box.__init__(
            self,
            name="date-notification",
            orientation="h",
            h_expand=True,
        )

        self.clock_label = Label(
            label=time.strftime("%H:%M"),
            style_classes="clock",
        )

        self.notifications: list[Notification] = (
            cache_notification_service.get_deserialized()
        )

        # Get the raw data for IDs
        raw_notifications = cache_notification_service.do_read_notifications()

        # Build groups by app_name
        items: list[tuple[Notification, dict]] = list(zip(self.notifications, raw_notifications, strict=False))
        items.reverse()  # Oldest first; we'll insert newest into groups so final order newest-first groups
        self.groups_by_app: dict[str, NotificationGroup] = {}
        self.group_container = Box(
            orientation="v",
            h_align="fill",
            spacing=8,
            h_expand=True,
            style_classes="notification-list",
            visible=len(items) > 0,
        )

        def on_group_empty(group: NotificationGroup):
            # Remove empty group from container and mapping
            with contextlib.suppress(Exception):
                self.group_container.remove(group)

            for k, v in list(self.groups_by_app.items()):
                if v is group:
                    self.groups_by_app.pop(k, None)
            if not self.groups_by_app:
                self.group_container.set_visible(False)
                self.placeholder.set_visible(True)

        def on_single_left(group: 'NotificationGroup', sole_item: NotificationHistoryEl):
            # Replace the group with its sole item in the container
            try:
                parent = self.group_container
                # Detach sole item from any parent
                # it may currently have (expanded state)
                try:
                    p = sole_item.get_parent()
                    if p is not None:
                        p.remove(sole_item)
                except Exception:
                    ...
                # Find index of group
                idx = list(parent.children).index(group)
                # Remove group and insert item at same position
                parent.remove(group)
                children = list(parent.children)
                children.insert(idx, sole_item)
                parent.children = tuple(children)
                # Remove group from mapping
                for k, v in list(self.groups_by_app.items()):
                    if v is group:
                        self.groups_by_app.pop(k, None)
                        break
                # If after promotion there are no groups and no other items,
                # show placeholder
                if len(parent.children) == 0:
                    parent.set_visible(False)
                    self.placeholder.set_visible(True)
            except Exception:
                ...

        for notification, raw_data in items:
            app_name = getattr(notification, "app_name", None) or "Unknown app"
            icon_widget = get_icon(notification.app_icon)
            group = self.groups_by_app.get(app_name)
            if group is None:
                group = NotificationGroup(app_name, icon_widget, on_empty=on_group_empty, on_single_left=on_single_left)
                # Newest groups should stay on top; append then will reorder below
                self.group_container.children = (*self.group_container.children, group)
                self.groups_by_app[app_name] = group
            el = NotificationHistoryEl(
                notification=notification,
                id=raw_data["id"],
                actions_clicked=raw_data.get("actions_clicked", False),
            )
            group.add_item(el)

        # Now reorder groups so the one with latest item appears first
        def group_key(g):
            # Support both NotificationGroup
            # and lone NotificationHistoryEl after promotion
            try:
                if hasattr(g, "items"):
                    if not g.items:
                        return -1
                    return max(int(getattr(it, "_id", 0)) for it in g.items)
                # Fallback for single NotificationHistoryEl
                return int(getattr(g, "_id", 0))
            except Exception:
                return 0
        # Promote any single-item groups after initial build
        try:
            for ch in list(self.group_container.children):
                if isinstance(ch, NotificationGroup) and len(ch.items) == 1:
                    on_single_left(ch, ch.items[0])
        except Exception:
            ...
        groups_sorted = sorted(self.group_container.children, key=group_key, reverse=True)
        self.group_container.children = tuple(groups_sorted)

        self.notification_list_box = self.group_container

        # After layout is assembled, schedule a refresh for all groups to ensure
        # overlays compute size after realization.
        with contextlib.suppress(Exception):
            GLib.idle_add(self._refresh_all_groups_once)

        self.uptime = Label(style_classes="uptime", label=f"uptime: {uptime()}")
        self.uptime.set_tooltip_text("System uptime")

        # Placeholder for when there are no notifications
        self.placeholder = Box(
            style_classes="placeholder",
            orientation="v",
            h_align="center",
            v_align="center",
            v_expand=True,
            h_expand=True,
            visible=len(self.notifications) == 0,  # visible if no notifications
            children=(
                Image(
                    icon_name=cnst.icons["notifications"]["silent"],
                    icon_size=64,
                ),
                Label(label="Your inbox is empty"),
            ),
        )

        # Header for the notification column
        self.dnd_switch = Gtk.Switch(
            name="notification-switch",
            active=False,
            valign=Gtk.Align.CENTER,
            visible=True,
        )
        self.dnd_switch.connect("notify::active", self.on_dnd_switch)

        notif_header = Box(
            style_classes="header",
            orientation="h",
            children=(Label(label="Do Not Disturb", name="dnd-text"), self.dnd_switch),
        )

        clear_button = Button(
            name="clear-button",
            v_align="center",
            child=Box(
                children=(
                    Label(label="Clear"),
                    Image(
                        icon_name=cnst.icons["trash"]["empty"]
                        if len(self.notifications) == 0
                        else cnst.icons["trash"]["full"],
                        icon_size=13,
                        name="clear-icon",
                    ),
                )
            ),
        )

        clear_button.connect(
            "clicked", lambda _: cache_notification_service.clear_all_notifications()
        )

        setup_cursor_hover(clear_button)

        notif_header.pack_end(
            clear_button,
            False,
            False,
            0,
        )

        # Notification body column
        notification_column = Box(
            name="notification-column",
            orientation="v",
            visible=False,
            children=(
                notif_header,
                ScrolledWindow(
                    v_expand=True,
                    style_classes="notification-scrollable",
                    v_scrollbar_policy="automatic",
                    h_scrollbar_policy="never",
                    child=Box(
                        orientation="v",
                        children=(self.notification_list_box, self.placeholder),
                    ),
                ),
            ),
        )

        # Date and time column
        date_column = Box(
            style_classes="date-column",
            orientation="v",
            visible=False,
            children=(
                Box(
                    style_classes="clock-box",
                    orientation="v",
                    children=(self.clock_label, self.uptime),
                ),
                Box(
                    style_classes="calendar",
                    children=(
                        Gtk.Calendar(
                            visible=True,
                            hexpand=True,
                            halign=Gtk.Align.CENTER,
                        )
                    ),
                ),
            ),
        )

        self.children = (
            notification_column,
            date_column,
        )

        notification_column.set_visible(True)
        date_column.set_visible(True)

        invoke_repeater(1000, self.update_labels, initial_call=True)
        notification_service.connect("notification-added", self.on_new_notification)
        cache_notification_service.connect("clear_all", self.on_clear_all_notifications)

    def on_clear_all_notifications(self, *_):
        self.notification_list_box.children = []
        self.notifications = []
        # Reset groups mapping
        try:
            self.groups_by_app.clear()
        except Exception:
            self.groups_by_app = {}
        self.notification_list_box.set_visible(False)
        self.placeholder.set_visible(True)

    def on_new_notification(self, fabric_notif, id):
        if cache_notification_service.dont_disturb:
            return

        notification: Notification = fabric_notif.get_notification_from_id(id)

        try:
            raw_cache = cache_notification_service.do_read_notifications()
            new_cache_id = raw_cache[-1]["id"] if raw_cache else 1
        except Exception:
            new_cache_id = 1

        app_name = getattr(notification, "app_name", None) or "Unknown app"
        icon_widget = get_icon(notification.app_icon)
        group = self.groups_by_app.get(app_name)
        if group is None:
            def on_group_empty(g):
                with contextlib.suppress(Exception):
                    self.group_container.remove(g)

                for k, v in list(self.groups_by_app.items()):
                    if v is g:
                        self.groups_by_app.pop(k, None)
                if not self.groups_by_app and len(self.group_container.children) == 0:
                    self.group_container.set_visible(False)
                    self.placeholder.set_visible(True)
            def on_single_left(g, sole_item):
                try:
                    parent = self.group_container
                    # Detach sole item from any current parent (expanded state)
                    try:
                        p = sole_item.get_parent()
                        if p is not None:
                            p.remove(sole_item)
                    except Exception:
                        ...
                    idx = list(parent.children).index(g)
                    parent.remove(g)
                    children = list(parent.children)
                    children.insert(idx, sole_item)
                    parent.children = tuple(children)
                    for k, v in list(self.groups_by_app.items()):
                        if v is g:
                            self.groups_by_app.pop(k, None)
                            break
                    if len(parent.children) == 0:
                        parent.set_visible(False)
                        self.placeholder.set_visible(True)
                except Exception:
                    ...
            group = NotificationGroup(app_name, icon_widget, on_empty=on_group_empty, on_single_left=on_single_left)
            # If there is a lone item for the same app already in the container,
            # merge it into the new group
            try:
                lone_item = None
                for _idx, ch in enumerate(list(self.group_container.children)):
                    if isinstance(ch, NotificationHistoryEl):
                        notif = getattr(ch, "_notification", None)
                        if getattr(notif, "app_name", None) == app_name:
                            lone_item = ch
                            break
                if lone_item is not None:
                    self.group_container.remove(lone_item)
                    group.add_item(lone_item)
            except Exception:
                ...
            # New groups appear on top
            self.group_container.children = (group, *self.group_container.children)
            self.groups_by_app[app_name] = group

        el = NotificationHistoryEl(notification=notification, id=new_cache_id, actions_clicked=False)
        group.add_item(el)
        # Force a refresh soon after to account for new heights
        with contextlib.suppress(Exception):
            GLib.idle_add(lambda: (group.refresh_view(), False))

        # Reorder groups so the most recent stays on top
        def group_key(g):
            try:
                if hasattr(g, "items"):
                    if not g.items:
                        return -1
                    return max(int(getattr(it, "_id", 0)) for it in g.items)
                return int(getattr(g, "_id", 0))
            except Exception:
                return 0
        groups_sorted = sorted(self.group_container.children, key=group_key, reverse=True)
        self.group_container.children = tuple(groups_sorted)

        self.placeholder.set_visible(False)
        self.notification_list_box.set_visible(True)

    def update_labels(self):
        self.clock_label.set_text(time.strftime("%H:%M"))
        self.uptime.set_text(uptime())
        return True

    def _refresh_all_groups_once(self):
        try:
            for group in getattr(self, "groups_by_app", {}).values():
                # Make sure collapsed overlay is visible when not expanded
                with contextlib.suppress(Exception):
                    group.collapsed_overlay.set_visible(not group.expanded)
                group.refresh_view()
        except Exception:
            ...
        return False

    def on_dnd_switch(self, switch, _):
        if switch.get_active():
            cache_notification_service.dont_disturb = True

        else:
            cache_notification_service.dont_disturb = False

import contextlib
import time

import gi
from fabric.notifications import Notification
from fabric.utils import invoke_repeater
from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.image import Image
from fabric.widgets.label import Label
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
        self, id: int, notification: Notification, actions_clicked: bool = False
    ):
        urgency_class = {0: "low-urgency", 1: "normal-urgency", 2: "critical-urgency"}
        self._any_action_invoked = False
        self._id = id
        self._actions_clicked_initial = actions_clicked

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
        GLib.timeout_add(400, self.destroy)


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

        self.notifications_list = [
            NotificationHistoryEl(
                notification=notification,
                id=raw_data["id"],
                actions_clicked=raw_data.get("actions_clicked", False),
            )
            for notification, raw_data in zip(
                self.notifications, raw_notifications, strict=False
            )
        ]
        self.notifications_list.reverse()

        self.notification_list_box = Box(
            orientation="v",
            h_align="fill",
            spacing=8,
            h_expand=True,
            style_classes="notification-list",
            visible=len(self.notifications) > 0,
            children=self.notifications_list,
        )

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
        self.notification_list_box.set_visible(False)
        self.placeholder.set_visible(True)

    def on_new_notification(self, fabric_notif, id):
        if cache_notification_service.dont_disturb:
            return

        notification: Notification = fabric_notif.get_notification_from_id(id)

        # Determine the correct persisted cache ID for this new notification entry.
        # The cache service assigns sequential IDs and persists them; relying on the
        # visible count here can desync with the cache and break actions/removal.
        try:
            raw_cache = cache_notification_service.do_read_notifications()
            new_cache_id = raw_cache[-1]["id"] if raw_cache else 1
        except Exception:
            # Fallback to a best-effort ID if reading cache fails
            new_cache_id = 1 + len(self.notification_list_box.children)

        self.notification_list_box.children = [
            NotificationHistoryEl(
                notification=notification,
                id=new_cache_id,
                actions_clicked=False,
            ),
            *self.notification_list_box.children,
        ]
        self.placeholder.set_visible(False)
        self.notification_list_box.set_visible(True)

    def update_labels(self):
        self.clock_label.set_text(time.strftime("%H:%M"))
        self.uptime.set_text(uptime())
        return True

    def on_dnd_switch(self, switch, _):
        if switch.get_active():
            cache_notification_service.dont_disturb = True

        else:
            cache_notification_service.dont_disturb = False

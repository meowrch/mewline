import os
from typing import TYPE_CHECKING

from fabric.notifications.service import Notification
from fabric.notifications.service import NotificationAction
from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.image import Image
from fabric.widgets.label import Label
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import GLib
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
        self, action: NotificationAction, index: int, total: int, notification_box
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
        self.connect(
            "enter-notify-event", lambda *_: notification_box.hover_button(self)
        )
        self.connect(
            "leave-notify-event", lambda *_: notification_box.unhover_button(self)
        )

    def on_clicked(self, *_):
        self.action.invoke()
        self.action.parent.close("dismissed-by-user")


class NotificationBox(Box):
    def __init__(self, notification: Notification, timeout_ms=5000, **kwargs):
        urgency_class = {0: ("low-urgency", False), 1: ("normal-urgency", False), 2: ("critical-urgency", True)}

        super().__init__(
            name="notification-box",
            orientation="v",
            spacing=10,
            children=[
                self.create_content(notification),
                Box(
                    spacing=10,
                    orientation="vertical",
                    children=[
                        self.create_action_buttons(notification),
                        Box(
                            name="notification-urgency-line",
                            visible=urgency_class.get(notification.urgency, urgency_class[0])[1],
                            h_expand=True,
                            h_align="fill",
                            style_classes=urgency_class.get(notification.urgency, urgency_class[0])[0],
                        ),
                    ],
                ),
            ],
        )
        self.notification = notification
        self.timeout_ms = timeout_ms
        self._timeout_id = None
        self.start_timeout()

    def create_content(self, notification):
        return Box(
            name="notification-content",
            spacing=8,
            children=[
                Box(
                    name="notification-image",
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
                    v_align="center",
                    children=[
                        Box(
                            name="notification-summary-box",
                            orientation="h",
                            children=[
                                Label(
                                    name="notification-title",
                                    markup=notification.summary.replace("\n", " "),
                                    h_align="start",
                                    ellipsization="end",
                                ),
                                Label(
                                    name="notification-app-name",
                                    markup=" | " + notification.app_name,
                                    h_align="start",
                                    ellipsization="end",
                                ),
                            ],
                        ),
                        Label(
                            name="notification-text",
                            markup=notification.body.replace("\n", " "),
                            h_align="start",
                            ellipsization="end",
                        )
                        if notification.body
                        else Box(),
                    ],
                ),
                Box(h_expand=True),
                Box(
                    orientation="v",
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
        self._timeout_id = GLib.timeout_add(self.timeout_ms, self.close_notification)

    def stop_timeout(self):
        if self._timeout_id is not None:
            GLib.source_remove(self._timeout_id)
            self._timeout_id = None

    def close_notification(self):
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
        notification_service.connect("notification-added", self.on_new_notification)

    def on_new_notification(self, fabric_notif, id):
        for child in self.get_children():
            child.destroy()

        notification: Notification = fabric_notif.get_notification_from_id(id)
        cache_notification_service.cache_notification(notification)

        if not cache_notification_service.dont_disturb:
            notification.connect("closed", self.on_notification_closed)
            new_box = NotificationBox(notification)
            self.add(new_box)
            self.dynamic_island.open("notification")

    def on_notification_closed(self, notification, reason):
        self.dynamic_island.close()
        logger.info(f"Notification {notification.id} closed with reason: {reason}")
        for child in self.get_children():
            child.destroy()

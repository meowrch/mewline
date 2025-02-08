from typing import TYPE_CHECKING

from fabric.widgets.box import Box
from fabric.widgets.button import Button
from gi.repository import GLib

from mewline.config import cfg
from mewline.utils.widget_utils import setup_cursor_hover
from mewline.utils.widget_utils import text_icon

if TYPE_CHECKING:
    from mewline.widgets.dynamic_island import DynamicIsland


class PowerMenu(Box):
    """A power menu widget for the dynamic island."""

    def __init__(self, di: "DynamicIsland", **kwargs):
        super().__init__(
            name="power-menu",
            orientation="h",
            spacing=4,
            v_align="center",
            h_align="center",
            v_expand=True,
            h_expand=True,
            visible=True,
            **kwargs,
        )
        self.config = cfg.modules.dynamic_island.power_menu
        self.dynamic_island: DynamicIsland = di

        self.btn_lock = Button(
            name="power-menu-button",
            child=text_icon(
                icon=self.config.lock_icon,
                size=self.config.lock_icon_size,
                props={"name": "button-label"},
            ),
            on_clicked=self.lock,
        )

        self.btn_suspend = Button(
            name="power-menu-button",
            child=text_icon(
                icon=self.config.suspend_icon,
                size=self.config.suspend_icon_size,
                props={"name": "button-label"},
            ),
            on_clicked=self.suspend,
        )

        self.btn_logout = Button(
            name="power-menu-button",
            child=text_icon(
                icon=self.config.logout_icon,
                size=self.config.logout_icon_size,
                props={"name": "button-label"},
            ),
            on_clicked=self.logout,
        )

        self.btn_reboot = Button(
            name="power-menu-button",
            child=text_icon(
                icon=self.config.reboot_icon,
                size=self.config.reboot_icon_size,
                props={"name": "button-label"},
            ),
            on_clicked=self.reboot,
        )

        self.btn_shutdown = Button(
            name="power-menu-button",
            child=text_icon(
                icon=self.config.shutdown_icon,
                size=self.config.shutdown_icon_size,
                props={"name": "button-label"},
            ),
            on_clicked=self.poweroff,
        )

        self.buttons = [
            self.btn_lock,
            self.btn_suspend,
            self.btn_logout,
            self.btn_reboot,
            self.btn_shutdown,
        ]

        for button in self.buttons:
            self.add(button)
            setup_cursor_hover(button, "pointer")

        self.show_all()

    def close_menu(self):
        self.dynamic_island.close()

    def lock(self, *args):
        print("Locking screen...")
        GLib.spawn_command_line_async("swaylock")
        self.close_menu()

    def suspend(self, *args):
        print("Suspending system...")
        GLib.spawn_command_line_async("systemctl suspend")
        self.close_menu()

    def logout(self, *args):
        print("Logging out...")
        GLib.spawn_command_line_async("hyprctl dispatch exit")
        self.close_menu()

    def reboot(self, *args):
        print("Rebooting system...")
        GLib.spawn_command_line_async("systemctl reboot")
        self.close_menu()

    def poweroff(self, *args):
        print("Powering off...")
        GLib.spawn_command_line_async("systemctl poweroff")
        self.close_menu()

import os
import shlex
import subprocess
from typing import TYPE_CHECKING

from fabric.widgets.box import Box
from fabric.widgets.button import Button
from loguru import logger

from mewline.config import cfg
from mewline.utils.config_structure import PowerMenuCommands
from mewline.utils.widget_utils import setup_cursor_hover
from mewline.utils.widget_utils import text_icon
from mewline.widgets.dynamic_island.base import BaseDiWidget

if TYPE_CHECKING:
    from mewline.widgets.dynamic_island import DynamicIsland


class PowerMenu(BaseDiWidget, Box):
    """A power menu widget for the dynamic island."""

    focuse_kb: bool = True

    def __init__(self, di: "DynamicIsland", **kwargs):
        Box.__init__(
            self,
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
                name="button-label",
            ),
            on_clicked=self.lock,
        )

        self.btn_suspend = Button(
            name="power-menu-button",
            child=text_icon(
                icon=self.config.suspend_icon,
                size=self.config.suspend_icon_size,
                name="button-label",
            ),
            on_clicked=self.suspend,
        )

        self.btn_logout = Button(
            name="power-menu-button",
            child=text_icon(
                icon=self.config.logout_icon,
                size=self.config.logout_icon_size,
                name="button-label",
            ),
            on_clicked=self.logout,
        )

        self.btn_reboot = Button(
            name="power-menu-button",
            child=text_icon(
                icon=self.config.reboot_icon,
                size=self.config.reboot_icon_size,
                name="button-label",
            ),
            on_clicked=self.reboot,
        )

        self.btn_shutdown = Button(
            name="power-menu-button",
            child=text_icon(
                icon=self.config.shutdown_icon,
                size=self.config.shutdown_icon_size,
                name="button-label",
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

    def _get_commands(self) -> PowerMenuCommands:
        """Return commands for the current desktop environment.

        Looks up ``XDG_CURRENT_DESKTOP`` in ``config.commands``
        (case-insensitive).  Falls back to the first entry in the dict, or
        to built-in defaults when the dict is empty.
        """
        desktop = os.environ.get("XDG_CURRENT_DESKTOP", "").lower()
        commands_map = self.config.commands

        for key, cmds in commands_map.items():
            if key.lower() == desktop:
                return cmds

        if commands_map:
            first_key = next(iter(commands_map))
            logger.warning(
                f"[PowerMenu] No commands configured for desktop {desktop!r}, "
                f"falling back to {first_key!r} commands."
            )
            return commands_map[first_key]

        logger.warning(
            f"[PowerMenu] No commands configured for desktop {desktop!r} and "
            "no fallback available - using built-in defaults."
        )
        return PowerMenuCommands()

    @staticmethod
    def _run_command(command: str) -> None:
        """Execute *command* safely without a shell.

        ``$VAR`` / ``${VAR}`` references are expanded via
        :func:`os.path.expandvars` before the string is split with
        :func:`shlex.split`.  The resulting argument list is handed directly
        to :class:`subprocess.Popen` (``shell=False``), so no shell injection
        is possible regardless of the command string's content.
        """
        expanded = os.path.expandvars(command)
        try:
            args = shlex.split(expanded)
        except ValueError as exc:
            logger.error(f"[PowerMenu] Failed to parse command {command!r}: {exc}")
            return

        if not args:
            logger.warning(f"[PowerMenu] Empty command after parsing: {command!r}")
            return

        try:
            subprocess.Popen(args)
        except FileNotFoundError:
            logger.error(f"[PowerMenu] Command not found: {args[0]!r}")
        except OSError as exc:
            logger.error(f"[PowerMenu] Failed to start {args!r}: {exc}")

    def lock(self, *args):
        logger.info("[PowerMenu] Locking screen...")
        self._run_command(self._get_commands().lock)
        self.close_menu()

    def suspend(self, *args):
        logger.info("[PowerMenu] Suspending system...")
        self._run_command(self._get_commands().suspend)
        self.close_menu()

    def logout(self, *args):
        logger.info("[PowerMenu] Logging out...")
        self._run_command(self._get_commands().logout)
        self.close_menu()

    def reboot(self, *args):
        logger.info("[PowerMenu] Rebooting system...")
        self._run_command(self._get_commands().reboot)
        self.close_menu()

    def poweroff(self, *args):
        logger.info("[PowerMenu] Powering off system...")
        self._run_command(self._get_commands().shutdown)
        self.close_menu()

from fabric.utils import exec_shell_command_async
from gi.repository import GLib

import mewline.constants as cnst
from mewline.config import cfg
from mewline.shared.widget_container import ButtonWidget
from mewline.utils.misc import uptime
from mewline.utils.widget_utils import text_icon


class PowerButton(ButtonWidget):
    """A widget to power off the system."""

    def __init__(self, **kwargs):
        super().__init__(name="power", **kwargs)
        self.config = cfg.modules.power

        self.children = text_icon(
            self.config.icon,
            self.config.icon_size,
            style_classes="panel-text-icon"
        )

        if self.config.tooltip:
            self._update_tooltip()
            GLib.timeout_add_seconds(60, self._update_tooltip)

        self.connect(
            "clicked",
            lambda *_: exec_shell_command_async(
                cnst.kb_di_open.format(module="power-menu")
            ),
        )

    def _update_tooltip(self):
        """Updates the tooltip with the current system uptime."""
        self.set_tooltip_text(f"Uptime: {uptime()}")
        return True

from fabric.utils import exec_shell_command_async

import mewline.constants as cnst
from mewline.config import cfg
from mewline.shared.widget_container import ButtonWidget
from mewline.utils.widget_utils import text_icon


class PowerButton(ButtonWidget):
    """A widget to power off the system."""

    def __init__(self, **kwargs):
        super().__init__(name="power", **kwargs)
        self.config = cfg.modules.power

        self.children = text_icon(
            self.config.icon,
            self.config.icon_size,
            props={"style_classes": "panel-text-icon"},
        )

        if self.config.tooltip:
            self.set_tooltip_text("Power")

        self.connect(
            "clicked",
            lambda *_: exec_shell_command_async(
                f"{cnst.ACTION_COMMAND} dynamic-island-open 'power'"
            ),
        )

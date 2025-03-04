from fabric.utils import exec_shell_command_async
from fabric.widgets.box import Box
from fabric.widgets.datetime import DateTime

import mewline.constants as cnst
from mewline.config import cfg
from mewline.shared.widget_container import ButtonWidget


class DateTimeWidget(ButtonWidget):
    """A widget to power off the system."""

    def __init__(self, **kwargs):
        super().__init__(name="date-time-button", **kwargs)
        self.config = cfg.modules.datetime
        self.children = Box(
            spacing=10,
            v_align="center",
            children=(DateTime(self.config.format, name="date-time"),),
        )
        self.connect(
            "clicked",
            lambda *_: exec_shell_command_async(
                cnst.kb_di_open.format(module="date_notification")
            ),
        )

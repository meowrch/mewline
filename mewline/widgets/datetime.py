from config import cfg
from fabric.widgets.box import Box
from fabric.widgets.datetime import DateTime
from shared.widget_container import ButtonWidget


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

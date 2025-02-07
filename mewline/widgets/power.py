from config import cfg
from shared.widget_container import ButtonWidget
from utils.widget_utils import text_icon
from widgets.dynamic_island import DynamicIsland


class PowerButton(ButtonWidget):
    """A widget to power off the system."""

    def __init__(self, di: DynamicIsland, **kwargs):
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
            lambda *_: di.open("power"),
        )

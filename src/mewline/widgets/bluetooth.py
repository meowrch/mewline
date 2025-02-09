from fabric.utils import exec_shell_command_async

import mewline.constants as cnst
from mewline.config import cfg
from mewline.services import bluetooth_client
from mewline.shared.widget_container import ButtonWidget
from mewline.utils.widget_utils import text_icon


class Bluetooth(ButtonWidget):
    """A button for open the Bluetooth menu."""

    def __init__(self, **kwargs):
        super().__init__(name="power", **kwargs)
        self.config = cfg.modules.power

        self.set_tooltip_text("Bluetooth")
        self.update_icon()

        self.connect(
            "clicked",
            lambda *_: exec_shell_command_async(
                f"{cnst.ACTION_COMMAND} dynamic-island-open 'bluetooth'"
            ),
        )
        bluetooth_client.connect(
            "notify::enabled",
            lambda *_: self.update_icon(),
        )

    def update_icon(self):
        if bluetooth_client.enabled:
            icon = cnst.icons["bluetooth"]["bluetooth_connected"]
        else:
            icon = cnst.icons["bluetooth"]["bluetooth_disconnected"]

        self.children = text_icon(
            icon,
            "16px",
            props={"style_classes": "panel-text-icon"},
        )

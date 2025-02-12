from fabric.widgets.box import Box
from fabric.widgets.label import Label

from mewline import constants as cnst
from mewline.config import cfg
from mewline.services.brightness import Brightness
from mewline.shared.widget_container import EventBoxWidget
from mewline.utils.misc import convert_to_percent
from mewline.utils.widget_utils import get_brightness_icon
from mewline.utils.widget_utils import text_icon


class BrightnessWidget(EventBoxWidget):
    """a widget that displays and controls the brightness."""

    def __init__(self, **kwargs):
        super().__init__(events=["scroll", "smooth-scroll"], **kwargs)

        self.config = cfg.modules.brightness
        self.brightness_service = Brightness().get_initial()

        normalized_brightness = convert_to_percent(
            self.brightness_service.screen_brightness,
            self.brightness_service.max_screen,
        )
        self.brightness_label = Label(
            visible=False,
            label=f"{normalized_brightness}%",
        )
        self.icon = text_icon(
            icon=cnst.icons["brightness"]["medium"],
            size=self.config.icon_size,
            props={
                "style_classes": "panel-text-icon overlay-icon",
            },
        )
        self.box = Box(
            spacing=4,
            name="brightness",
            style_classes="panel-box",
            children=(
                self.icon,
                self.brightness_label,
            ),
        )

        self.brightness_service.connect("screen", self.on_brightness_changed)
        self.connect("scroll-event", self.on_scroll)
        self.add(self.box)

        if self.config.label:
            self.brightness_label.show()

    def on_scroll(self, _, event):
        val_y = event.delta_y

        if val_y < 0:  # scroll top
            self.brightness_service.screen_brightness += self.config.step_size
        else:  # scroll down
            self.brightness_service.screen_brightness -= self.config.step_size

        self.on_brightness_changed()

    def on_brightness_changed(self, *_):
        normalized_brightness = convert_to_percent(
            self.brightness_service.screen_brightness,
            self.brightness_service.max_screen,
        )

        self.brightness_label.set_text(f"{normalized_brightness}%")
        self.icon.set_text(get_brightness_icon(normalized_brightness))

        if self.config.tooltip:
            self.set_tooltip_text(f"{normalized_brightness}%")

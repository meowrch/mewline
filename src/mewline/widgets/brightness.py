from fabric.widgets.box import Box
from fabric.widgets.eventbox import EventBox
from fabric.widgets.label import Label
from fabric.widgets.overlay import Overlay
from fabric.widgets.revealer import Revealer
from gi.repository import GLib

from mewline import constants as cnst
from mewline.config import cfg
from mewline.services import brightness_service
from mewline.utils.misc import convert_to_percent
from mewline.utils.widget_utils import get_brightness_icon
from mewline.utils.widget_utils import text_icon


class BrightnessWidget(Overlay):
    """a widget that displays and controls the brightness."""

    def __init__(self, **kwargs):
        super().__init__(events=["scroll", "smooth-scroll"], **kwargs)

        self.config = cfg.modules.brightness
        self.brightness_service = brightness_service

        self.icon = text_icon(
            icon=cnst.icons["brightness"]["medium"],
            size=self.config.icon_size,
            style_classes="panel-text-icon overlay-icon",
        )
        normalized_brightness = convert_to_percent(
            self.brightness_service.screen_brightness,
            self.brightness_service.max_brightness_level,
        )
        self.label = Label(
            visible=False,
            label=f" {normalized_brightness}%",
        )
        self.revealer = Revealer(
            name="brightness-revealer",
            transition_duration=250,
            transition_type="slide-left",
            child=self.label,
            child_revealed=False,
        )
        self.box = Box(
            name="brightness",
            style_classes="panel-box",
            children=(
                self.icon,
                self.revealer,
            ),
        )

        # Common state
        self.hide_timer = None
        self.hover_counter = 0

        # Event setup
        self.event_box = EventBox(
            events=[
                "enter-notify-event",
                "leave-notify-event",
                "scroll",
                "smooth-scroll",
            ]
        )
        self.event_box.connect("enter-notify-event", self.on_mouse_enter)
        self.event_box.connect("leave-notify-event", self.on_mouse_leave)
        self.event_box.connect("scroll-event", self.on_scroll)
        self.brightness_service.connect("screen", self.on_brightness_changed)

        self.overlays = [self.event_box]
        self.add(self.box)

        if self.config.label:
            self.label.show()

    def on_mouse_enter(self, *_):
        self.hover_counter += 1
        if self.hide_timer:
            GLib.source_remove(self.hide_timer)
            self.hide_timer = None
        self.revealer.set_reveal_child(True)
        return False

    def on_mouse_leave(self, *_):
        self.hover_counter = max(0, self.hover_counter - 1)
        if self.hover_counter == 0:
            if self.hide_timer:
                GLib.source_remove(self.hide_timer)
            self.hide_timer = GLib.timeout_add(
                500, lambda: self.revealer.set_reveal_child(False)
            )
        return False

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
            self.brightness_service.max_brightness_level,
        )

        self.label.set_text(f" {normalized_brightness}%")
        self.icon.set_text(get_brightness_icon(normalized_brightness))

        if self.config.tooltip:
            self.set_tooltip_text(f"{normalized_brightness}%")

from abc import ABCMeta
from abc import abstractmethod

from fabric.widgets.box import Box
from fabric.widgets.eventbox import EventBox
from fabric.widgets.label import Label
from fabric.widgets.overlay import Overlay
from fabric.widgets.revealer import Revealer
from gi.repository import GLib
from gi.repository import Gtk

from mewline import constants as cnst
from mewline.config import cfg
from mewline.services import audio_service
from mewline.utils.config_structure import MicrophoneModule
from mewline.utils.config_structure import SpeakersModule
from mewline.utils.widget_utils import get_audio_icon
from mewline.utils.widget_utils import text_icon


class BaseAudioWidgetMeta(type(Gtk.Overlay), ABCMeta):
    pass


class BaseAudioWidget(Overlay, metaclass=BaseAudioWidgetMeta):
    def __init__(
        self, default_icon: str, device_type, config: MicrophoneModule | SpeakersModule
    ):
        super().__init__()
        self.audio_service = audio_service
        self.config = config
        self.device_type = device_type

        # Common widgets
        self.icon = text_icon(icon=default_icon, size=self.config.icon_size)
        self.label = Label()
        self.revealer = Revealer(
            name=f"{device_type}-revealer",
            transition_duration=250,
            transition_type="slide-left",
            child=self.label,
            child_revealed=False,
        )
        self.box = Box(
            name=device_type,
            style_classes="panel-box",
            children=(self.icon, self.revealer),
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
        self.connect("button-press-event", lambda *_: self.toggle_mute())

        self.overlays = [self.event_box]
        self.add(self.box)

        # Initial setup
        self.audio_service.connect(
            f"notify::{self.device_type}", self.on_device_changed
        )

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
            self.current_device.volume += self.config.step_size
        else:  # scroll down
            self.current_device.volume -= self.config.step_size

    @abstractmethod
    def on_toggle(self, muted: bool):
        pass

    @abstractmethod
    def update_volume(self, *_):
        pass

    @property
    @abstractmethod
    def current_device(self):
        pass

    def on_device_changed(self, *_):
        if not self.current_device:
            return
        if self.config.tooltip:
            self.set_tooltip_text(self.current_device.description)
        self.current_device.connect("notify::volume", self.update_volume)
        self.update_volume()

    def toggle_mute(self):
        if not self.current_device:
            return
        self.current_device.muted = not self.current_device.muted
        self.on_toggle(self.current_device.muted)


class MicrophoneControlWidget(BaseAudioWidget):
    def __init__(self):
        super().__init__(
            default_icon=cnst.icons["microphone"]["active"],
            device_type="microphone",
            config=cfg.modules.microphone,
        )

    def on_toggle(self, muted: bool):
        if muted:
            self.icon.set_text(cnst.icons["microphone"]["muted"])
        else:
            self.icon.set_text(cnst.icons["microphone"]["active"])

    @property
    def current_device(self):
        return self.audio_service.microphone

    def update_volume(self, *_):
        if self.current_device:
            self.label.set_text(f" {round(self.current_device.volume)}%")


class SpeakersControlWidget(BaseAudioWidget):
    def __init__(self):
        super().__init__(
            default_icon=cnst.icons["volume"]["medium"],
            device_type="speaker",
            config=cfg.modules.speakers,
        )

    def on_toggle(self, muted: bool):
        self.icon.set_text(
            cnst.icons["volume"]["muted"],
        ) if muted else self.update_volume()

    @property
    def current_device(self):
        return self.audio_service.speaker

    def update_volume(self, *_):
        if self.current_device:
            volume = round(self.current_device.volume)
            self.label.set_text(f" {volume}%")
            self.icon.set_text(get_audio_icon(volume, self.current_device.muted))

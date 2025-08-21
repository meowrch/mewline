import time
from typing import ClassVar
from typing import Literal

from fabric.utils import invoke_repeater
from fabric.widgets.box import Box
from fabric.widgets.label import Label
from fabric.widgets.revealer import Revealer
from fabric.widgets.wayland import WaylandWindow as Window
from gi.repository import GObject

from mewline import constants as cnst
from mewline.config import cfg
from mewline.services import audio_service
from mewline.services import brightness_service
from mewline.utils.misc import convert_to_percent
from mewline.utils.widget_utils import create_scale
from mewline.utils.widget_utils import get_audio_icon
from mewline.utils.widget_utils import get_brightness_icon
from mewline.utils.widget_utils import text_icon


class GenericOSDContainer(Box):
    """A generic OSD container to display the OSD for brightness and audio."""

    def __init__(self, **kwargs):
        super().__init__(
            orientation="h",
            spacing=10,
            name="osd-container",
            **kwargs,
        )
        self.level = Label(
            name="osd-level", h_align="center", h_expand=True, visible=False
        )
        self.icon: Label = text_icon(
            icon=cnst.icons["brightness"]["medium"], size="24px", name="osd-icon"
        )
        self.scale = create_scale()

        self.children = (self.icon, self.scale, self.level)

        self.level.set_visible(True)


class BrightnessOSDContainer(GenericOSDContainer):
    """A widget to display the OSD for brightness."""

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.brightness_service = brightness_service
        self.update_brightness()

        self.scale.connect("value-changed", lambda *_: self.update_brightness())
        self.brightness_service.connect("screen", self.on_brightness_changed)

    def update_brightness(self):
        normalized_brightness = convert_to_percent(
            self.brightness_service.screen_brightness,
            self.brightness_service.max_brightness_level,
        )
        self.scale.animate_value(normalized_brightness)
        self.update_icon(int(normalized_brightness))

    def update_icon(self, current_brightness):
        icon = get_brightness_icon(current_brightness)
        self.level.set_label(f"{current_brightness}%")
        self.icon.set_label(icon)

    def on_brightness_changed(self, _sender, value, *args):
        normalized_brightness = (
            value / self.brightness_service.max_brightness_level
        ) * 101
        self.scale.animate_value(normalized_brightness)


class AudioOSDContainer(GenericOSDContainer):
    """A widget to display the OSD for audio."""

    __gsignals__: ClassVar[dict] = {
        "volume-changed": (GObject.SIGNAL_RUN_FIRST, GObject.TYPE_NONE, ()),
    }

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.audio = audio_service
        self.current_device = "speaker"  # Track which device we're showing

        self.sync_with_audio()

        self.scale.connect("value-changed", self.on_volume_changed)
        self.audio.connect("notify::speaker", self.on_audio_speaker_changed)
        self.audio.connect("notify::microphone", self.on_audio_microphone_changed)

    def sync_with_audio(self, device="speaker"):
        """Sync OSD display with audio device."""
        self.current_device = device
        if device == "speaker" and self.audio.speaker:
            volume = round(self.audio.speaker.volume)
            self.scale.set_value(volume)
            self.update_icon(volume, device)
        elif device == "microphone" and self.audio.microphone:
            volume = round(self.audio.microphone.volume)
            self.scale.set_value(volume)
            self.update_icon(volume, device)

    def on_volume_changed(self, *_):
        # This handles volume changes from the OSD scale itself
        volume = self.scale.value
        if 0 <= volume <= 100:
            if self.current_device == "speaker" and self.audio.speaker:
                self.audio.speaker.set_volume(volume)
                self.update_icon(volume, self.current_device)
                self.emit("volume-changed")
            elif self.current_device == "microphone" and self.audio.microphone:
                self.audio.microphone.set_volume(volume)
                self.update_icon(volume, self.current_device)
                self.emit("volume-changed")

    def on_audio_speaker_changed(self, *_):
        if self.audio.speaker:
            self.audio.speaker.connect("notify::volume", self.update_volume)
            self.audio.speaker.connect("notify::muted", self.update_volume)
            self.update_volume()

    def on_audio_microphone_changed(self, *_):
        if self.audio.microphone:
            self.audio.microphone.connect("notify::volume", self.update_volume)
            self.audio.microphone.connect("notify::muted", self.update_volume)
            self.update_volume()

    def update_volume(self, *_):
        # Update from service - only update if we're not being hovered
        if not self.is_hovered():
            if self.current_device == "speaker" and self.audio.speaker:
                volume = round(self.audio.speaker.volume)
                self.scale.set_value(volume)
                self.update_icon(volume, "speaker")
            elif self.current_device == "microphone" and self.audio.microphone:
                volume = round(self.audio.microphone.volume)
                self.scale.set_value(volume)
                self.update_icon(volume, "microphone")

    def update_icon(self, volume, device="speaker"):
        """Update icon and label based on device type."""
        if device == "speaker" and self.audio.speaker:
            icon_name = get_audio_icon(volume, self.audio.speaker.muted)
        elif device == "microphone":
            is_muted = self.audio.microphone.muted if self.audio.microphone else False
            icon_name = cnst.icons["microphone"]["muted" if is_muted else "active"]
        else:
            # Fallback to speaker icons
            icon_name = get_audio_icon(volume, False)

        self.level.set_label(f"{volume}%")
        self.icon.set_label(icon_name)

    def show_for_device(self, device: str):
        """Show OSD for specific device (speaker or microphone)."""
        self.sync_with_audio(device)

    def show_microphone(self):
        """Show OSD for microphone volume."""
        self.sync_with_audio("microphone")

    def show_speaker(self):
        """Show OSD for speaker volume."""
        self.sync_with_audio("speaker")


class OSDContainer(Window):
    """A widget to display the OSD for audio and brightness."""

    def __init__(
        self,
        transition_duration=200,
        keyboard_mode: Literal["none", "exclusive", "on-demand"] = "on-demand",
        **kwargs,
    ):
        self.config = cfg.modules.osd
        self.audio_container = AudioOSDContainer()
        self.brightness_container = BrightnessOSDContainer()

        self.timeout = self.config.timeout

        self.revealer = Revealer(
            name="osd-revealer",
            transition_type="slide-right",
            transition_duration=transition_duration,
            child_revealed=False,
        )

        super().__init__(
            layer="overlay",
            anchor=self.config.anchor,
            child=self.revealer,
            visible=False,
            pass_through=True,
            keyboard_mode=keyboard_mode,
            **kwargs,
        )
        self.last_activity_time = time.time()

        self.audio_container.audio.connect("notify::speaker", self.show_audio)
        self.brightness_container.brightness_service.connect(
            "screen",
            self.show_brightness,
        )
        self.audio_container.connect("volume-changed", self.show_audio)

        invoke_repeater(100, self.check_inactivity, initial_call=True)

    def show_audio(self, *_):
        """Show audio OSD (defaults to speaker)."""
        self.show_box(box_to_show="audio")
        self.reset_inactivity_timer()

    def show_audio_speaker(self, *_):
        """Show audio OSD for speaker."""
        self.audio_container.show_speaker()
        self.show_box(box_to_show="audio")
        self.reset_inactivity_timer()

    def show_audio_microphone(self, *_):
        """Show audio OSD for microphone."""
        self.audio_container.show_microphone()
        self.show_box(box_to_show="audio")
        self.reset_inactivity_timer()

    def show_brightness(self, *_):
        self.show_box(box_to_show="brightness")
        self.reset_inactivity_timer()

    def show_box(self, box_to_show: Literal["audio", "brightness"]):
        self.set_visible(True)
        if box_to_show == "audio":
            self.revealer.children = self.audio_container
        elif box_to_show == "brightness":
            self.revealer.children = self.brightness_container
        self.revealer.set_reveal_child(True)
        self.reset_inactivity_timer()

    def start_hide_timer(self):
        self.set_visible(False)

    def reset_inactivity_timer(self):
        self.last_activity_time = time.time()

    def check_inactivity(self):
        if time.time() - self.last_activity_time >= (self.timeout / 1000):
            self.start_hide_timer()
        return True

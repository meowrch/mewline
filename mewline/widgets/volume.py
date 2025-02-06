from typing import Literal

from config import cfg
from fabric.widgets.box import Box
from fabric.widgets.label import Label
from services import audio_service
from shared.widget_container import EventBoxWidget
from utils.widget_utils import text_icon


class VolumeWidget(EventBoxWidget):
    """a widget that displays and controls the volume."""

    def __init__(self, **kwargs):
        super().__init__(
            events=["scroll", "smooth-scroll", "enter-notify-event"], **kwargs
        )

        self.audio = audio_service
        self.config = cfg.modules.volume

        self.volume_label = Label(visible=False)
        self.icon = text_icon(icon=self.config.medium_icon, size=self.config.icon_size)
        self.box = Box(
            spacing=10,
            name="volume",
            style_classes="panel-box",
            children=(
                self.icon,
                self.volume_label,
            ),
        )

        self.connect("button-press-event", lambda *_: self.toggle_mute())
        self.audio.connect("notify::speaker", self.on_speaker_changed)
        self.connect("scroll-event", self.on_scroll)

        self.add(self.box)
        if self.config.label:
            self.volume_label.show()

    def on_scroll(self, _, event):
        val_y = event.delta_y

        if val_y < 0:  # scroll top
            self.audio.speaker.volume += self.config.step_size
        else:  # scroll down
            self.audio.speaker.volume -= self.config.step_size

    def on_speaker_changed(self, *_):
        if not self.audio.speaker:
            return

        if self.config.tooltip:
            self.set_tooltip_text(self.audio.speaker.description)

        self.audio.speaker.connect("notify::volume", self.update_volume)
        self.update_volume()

    def toggle_mute(self):
        current_stream = self.audio.speaker
        if current_stream:
            current_stream.muted = not current_stream.muted
            self.icon.set_text(
                self.config.muted_icon,
            ) if current_stream.muted else self.update_volume()

    def update_volume(self, *_):
        if self.audio.speaker:
            volume = round(self.audio.speaker.volume)
            self.volume_label.set_text(f"{volume}%")

        self.icon.set_text(
            self.get_audio_icon_name(volume, self.audio.speaker.muted)["icon_text"]
        )

    def get_audio_icon_name(
        self, volume: int, is_muted: bool
    ) -> dict[Literal["icon_text", "icon"], str]:
        if is_muted:
            return {
                "icon_text": self.config.muted_icon,
                "icon": "audio-volume-muted-symbolic",
            }

        # Define volume ranges and their corresponding values
        volume_levels = {
            (0, 0): (self.config.low_icon, "audio-volume-muted-symbolic"),
            (1, 31): (self.config.low_icon, "audio-volume-low-symbolic"),
            (32, 65): (self.config.medium_icon, "audio-volume-medium-symbolic"),
            (66, 100): (self.config.high_icon, "audio-volume-high-symbolic"),
        }

        for (min_volume, max_volume), (icon_text, icon) in volume_levels.items():
            if min_volume <= volume <= max_volume:
                return {
                    "icon_text": icon_text,
                    "icon": icon,
                }

        # If the volume exceeds 100
        return dict(
            icon_text=self.config.overamplified_icon,
            icon="audio-volume-overamplified-symbolic",
        )

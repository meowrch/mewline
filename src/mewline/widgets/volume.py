from fabric.widgets.box import Box
from fabric.widgets.label import Label

from mewline import constants as cnst
from mewline.config import cfg
from mewline.services import audio_service
from mewline.shared.widget_container import EventBoxWidget
from mewline.utils.widget_utils import get_audio_icon
from mewline.utils.widget_utils import text_icon


class VolumeWidget(EventBoxWidget):
    """a widget that displays and controls the volume."""

    def __init__(self, **kwargs):
        super().__init__(
            events=["scroll", "smooth-scroll", "enter-notify-event"], **kwargs
        )

        self.audio = audio_service
        self.config = cfg.modules.volume

        self.volume_label = Label(visible=False)
        self.icon = text_icon(
            icon=cnst.icons["volume"]["medium"], size=self.config.icon_size
        )
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
                cnst.icons["volume"]["muted"],
            ) if current_stream.muted else self.update_volume()

    def update_volume(self, *_):
        if self.audio.speaker:
            volume = round(self.audio.speaker.volume)
            self.volume_label.set_text(f"{volume}%")

        self.icon.set_text(get_audio_icon(volume, self.audio.speaker.muted))

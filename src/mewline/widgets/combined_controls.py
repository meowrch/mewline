from __future__ import annotations

from fabric.widgets.box import Box
from fabric.widgets.revealer import Revealer
from gi.repository import GObject

from mewline import constants as cnst
from mewline.config import cfg
from mewline.services import audio_service
from mewline.services import brightness_service
from mewline.shared.popover import Popover
from mewline.shared.widget_container import ButtonWidget
from mewline.utils.misc import convert_to_percent
from mewline.utils.widget_utils import create_scale
from mewline.utils.widget_utils import get_audio_icon
from mewline.utils.widget_utils import get_brightness_icon
from mewline.utils.widget_utils import text_icon


class CombinedControlsMenu(Popover):
    """Dropdown menu with sliders for speaker, microphone, brightness."""

    def __init__(self, anchor_widget: GObject.GObject, **kwargs):
        self.anchor_widget = anchor_widget
        self.audio = audio_service
        self.brightness = brightness_service
        self.config = cfg.modules

        # Sliders
        self.speaker_scale = create_scale(style_classes="cc-scale")
        self.mic_scale = create_scale(style_classes="cc-scale")
        self.brightness_scale = create_scale(style_classes="cc-scale")

        # Icons/labels as text icons to match theme
        speaker_icon = text_icon(get_audio_icon(self._get_speaker_volume(), False))
        mic_icon = text_icon(
            cnst.icons["microphone"]["active"]
        )  # toggle handled by volume 0 treated as muted visually
        brightness_icon = text_icon(get_brightness_icon(self._get_brightness()))

        # Percentage labels
        self.speaker_label = text_icon("0%", size="14px")
        self.mic_label = text_icon("0%", size="14px")
        self.brightness_label = text_icon("0%", size="14px")

        sliders_box = Box(
            orientation="v",
            spacing=8,
            style_classes="cc-menu",
            children=(
                Box(
                    orientation="h",
                    spacing=8,
                    children=(speaker_icon, self.speaker_scale, self.speaker_label),
                ),
                Box(
                    orientation="h",
                    spacing=8,
                    children=(mic_icon, self.mic_scale, self.mic_label),
                ),
                Box(
                    orientation="h",
                    spacing=8,
                    children=(
                        brightness_icon,
                        self.brightness_scale,
                        self.brightness_label,
                    ),
                ),
            ),
            all_visible=True,
        )

        revealer = Revealer(
            name="cc-menu-revealer",
            transition_type="slide-down",
            transition_duration=200,
            child=sliders_box,
            child_revealed=True,
        )

        super().__init__(
            content=revealer,
            point_to=self.anchor_widget,
            gap=2,
        )

        # Connect scale changes
        self.speaker_scale.connect("value-changed", self._on_speaker_changed)
        self.mic_scale.connect("value-changed", self._on_mic_changed)
        self.brightness_scale.connect("value-changed", self._on_brightness_changed)

        # Listen to services to keep in sync
        self.audio.connect("notify::speaker", self._bind_speaker)
        self.audio.connect("notify::microphone", self._bind_microphone)
        self.brightness.connect("screen", self._on_brightness_service)

        # Do not continuously reposition on size-allocate to avoid jitter

        # Bind when available
        self._bind_speaker()
        self._bind_microphone()

        # Initial sync after labels exist
        self._sync_from_services()

    # open/close inherited from Popover

    def _get_speaker_volume(self) -> int:
        return round(self.audio.speaker.volume) if self.audio.speaker else 0

    def _get_mic_volume(self) -> int:
        return round(self.audio.microphone.volume) if self.audio.microphone else 0

    def _get_brightness(self) -> int:
        return convert_to_percent(
            self.brightness.screen_brightness, self.brightness.max_brightness_level
        )

    def _sync_from_services(self):
        sp = self._get_speaker_volume()
        mc = self._get_mic_volume()
        br = self._get_brightness()
        self.speaker_scale.set_value(sp)
        self.mic_scale.set_value(mc)
        self.brightness_scale.set_value(br)
        self.speaker_label.set_text(f"{sp}%")
        self.mic_label.set_text(f"{mc}%")
        self.brightness_label.set_text(f"{br}%")

    def _on_speaker_changed(self, *_):
        if self.audio.speaker:
            vol = self.speaker_scale.value
            if 0 <= vol <= 100:
                self.audio.speaker.set_volume(vol)
                self.speaker_label.set_text(f"{int(vol)}%")

    def _on_mic_changed(self, *_):
        if self.audio.microphone:
            vol = self.mic_scale.value
            if 0 <= vol <= 100:
                self.audio.microphone.set_volume(vol)
                self.mic_label.set_text(f"{int(vol)}%")

    def _on_brightness_changed(self, *_):
        val = self.brightness_scale.value
        # translate percent back to raw units
        target = int((val / 100.0) * self.brightness.max_brightness_level)
        self.brightness.screen_brightness = target
        self.brightness_label.set_text(f"{int(val)}%")

    def _bind_speaker(self, *_):
        if self.audio.speaker:
            self.audio.speaker.connect(
                "notify::volume", self._update_speaker_from_service
            )
            self._update_speaker_from_service()

    def _bind_microphone(self, *_):
        if self.audio.microphone:
            self.audio.microphone.connect(
                "notify::volume", self._update_mic_from_service
            )
            self._update_mic_from_service()

    def _on_brightness_service(self, *_):
        val = self._get_brightness()
        self.brightness_scale.set_value(val)
        self.brightness_label.set_text(f"{int(val)}%")

    def _update_speaker_from_service(self, *_):
        sp = self._get_speaker_volume()
        self.speaker_scale.set_value(sp)
        self.speaker_label.set_text(f"{sp}%")

    def _update_mic_from_service(self, *_):
        mc = self._get_mic_volume()
        self.mic_scale.set_value(mc)
        self.mic_label.set_text(f"{mc}%")


class CombinedControlsButton(ButtonWidget):
    """Capsule showing speaker, mic, brightness icons; toggles CombinedControlsMenu."""

    def __init__(self, **kwargs):
        super().__init__(name="combined-controls", **kwargs)
        self.audio = audio_service
        self.brightness = brightness_service
        self.menu: CombinedControlsMenu | None = None

        self.icon_speaker = text_icon(get_audio_icon(0, False))
        self.icon_mic = text_icon(cnst.icons["microphone"]["active"])  # simplified
        self.icon_brightness = text_icon(get_brightness_icon(self._get_brightness()))

        # Initial icon syncs
        self._sync_icons()

        # Connect services to update icons
        self.audio.connect("notify::speaker", self._bind_speaker)
        self.audio.connect("notify::microphone", self._bind_microphone)
        self.brightness.connect("screen", self._on_brightness_changed)

        # Layout
        inner = Box(
            orientation="h",
            spacing=10,
            children=(
                self.icon_speaker,
                self.icon_mic,
                self.icon_brightness,
            ),
        )
        self.children = inner

        self.connect("clicked", self._on_clicked)

    def _on_clicked(self, *_):
        if not self.menu:
            self.menu = CombinedControlsMenu(anchor_widget=self)
        if self.menu.get_visible():
            self.menu.close()
        else:
            self.menu.open()

    def _get_brightness(self) -> int:
        return convert_to_percent(
            self.brightness.screen_brightness, self.brightness.max_brightness_level
        )

    def _sync_icons(self):
        if self.audio.speaker:
            vol = round(self.audio.speaker.volume)
            self.icon_speaker.set_text(get_audio_icon(vol, self.audio.speaker.muted))

        if self.audio.microphone:
            # if mic is muted available? audio_service.microphone.muted maybe;
            # fallback by volume
            icon = cnst.icons["microphone"]["active"]
            self.icon_mic.set_text(icon)

        self.icon_brightness.set_text(get_brightness_icon(self._get_brightness()))

    def _bind_speaker(self, *_):
        if self.audio.speaker:
            self.audio.speaker.connect("notify::volume", self._update_speaker_icon)
            self._update_speaker_icon()

    def _bind_microphone(self, *_):
        if self.audio.microphone:
            self.audio.microphone.connect("notify::volume", self._update_mic_icon)
            self._update_mic_icon()

    def _on_brightness_changed(self, *_):
        self.icon_brightness.set_text(get_brightness_icon(self._get_brightness()))

    def _update_speaker_icon(self, *_):
        if self.audio.speaker:
            vol = round(self.audio.speaker.volume)
            self.icon_speaker.set_text(get_audio_icon(vol, self.audio.speaker.muted))

    def _update_mic_icon(self, *_):
        if self.audio.microphone:
            self.icon_mic.set_text(
                cnst.icons["microphone"]["active"]
            )  # keep constant for now

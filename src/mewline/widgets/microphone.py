from fabric.widgets.box import Box
from fabric.widgets.eventbox import EventBox
from fabric.widgets.label import Label
from fabric.widgets.overlay import Overlay
from fabric.widgets.revealer import Revealer
from gi.repository import GLib

from mewline import constants as cnst
from mewline.config import cfg
from mewline.services import audio_service
from mewline.utils.widget_utils import text_icon


class MicrophoneWidget(Overlay):
    """a widget that displays and controls the microphone."""

    def __init__(self):
        super().__init__()

        self.audio = audio_service
        self.config = cfg.modules.microphone

        self.icon = text_icon(
            icon=cnst.icons["microphone"]["active"], size=self.config.icon_size
        )
        self.label = Label()
        self.revealer = Revealer(
            name="microphone-revealer",
            transition_duration=250,
            transition_type="slide-left",
            child=self.label,
            child_revealed=False,
        )

        self.box = Box(
            name="microphone",
            style_classes="panel-box",
            children=(
                self.icon,
                self.revealer,
            ),
        )

        self.hide_timer = None
        self.hover_counter = 0

        ##==> Устанавливаем ивенты
        ########################################
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
        self.audio.connect("notify::microphone", self.on_microphone_changed)
        self.overlays = [self.event_box]

        ##==> Отображаем все
        ####################################
        self.add(self.box)

    def on_mouse_enter(self, *_):
        self.hover_counter += 1
        if self.hide_timer is not None:
            GLib.source_remove(self.hide_timer)
            self.hide_timer = None
        self.revealer.set_reveal_child(True)
        return False

    def on_mouse_leave(self, *_):
        if self.hover_counter > 0:
            self.hover_counter -= 1
        if self.hover_counter == 0:
            if self.hide_timer is not None:
                GLib.source_remove(self.hide_timer)
            self.hide_timer = GLib.timeout_add(
                500, lambda: self.revealer.set_reveal_child(False)
            )

        return False

    def on_scroll(self, _, event):
        val_y = event.delta_y

        if val_y < 0:  # scroll top
            self.audio.microphone.volume += self.config.step_size
        else:  # scroll down
            self.audio.microphone.volume -= self.config.step_size

        print(self.audio.microphone.volume)

    def on_microphone_changed(self, *_):
        if not self.audio.microphone:
            return

        if self.config.tooltip:
            self.set_tooltip_text(self.audio.microphone.description)

        self.audio.microphone.connect("notify::volume", self.update_volume)
        self.update_volume()

    def toggle_mute(self):
        current_stream = self.audio.microphone
        if current_stream:
            current_stream.muted = not current_stream.muted

            if current_stream.muted:
                self.icon.set_text(cnst.icons["microphone"]["muted"])
            else:
                self.icon.set_text(cnst.icons["microphone"]["active"])

    def update_volume(self, *_):
        if self.audio.microphone:
            volume = round(self.audio.microphone.volume)
            self.label.set_text(f" {volume}%")

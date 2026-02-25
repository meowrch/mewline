from __future__ import annotations

from fabric.widgets.box import Box
from fabric.widgets.eventbox import EventBox
from fabric.widgets.overlay import Overlay
from fabric.widgets.revealer import Revealer
from gi.repository import GLib
from gi.repository import GObject
from gi.repository import Gtk

from mewline import constants as cnst
from mewline.config import cfg
from mewline.services import audio_service
from mewline.services import brightness_service
from mewline.services import privacy_service
from mewline.shared.popover import Popover
from mewline.shared.widget_container import ButtonWidget
from mewline.utils.misc import convert_to_percent
from mewline.utils.widget_utils import create_scale
from mewline.utils.widget_utils import get_audio_icon
from mewline.utils.widget_utils import get_brightness_icon
from mewline.utils.widget_utils import text_icon

# Opacity applied to inactive privacy dots (active dots use 1.0).
# The colour itself is controlled by $privacy-dot-{mic,cam,screen,loc}
# variables in the theme – see default_theme.scss.
_DOT_DIM_OPACITY = 0.12


class CombinedControlsMenu(Popover):
    """Dropdown menu with sliders for speaker, microphone, brightness."""

    def __init__(self, anchor_widget: GObject.GObject, osd_widget=None, **kwargs):
        self.anchor_widget = anchor_widget
        self.audio = audio_service
        self.brightness = brightness_service
        self.config = cfg.modules
        self.osd_widget = osd_widget

        self._updating_brightness_from_service = False
        self._updating_brightness = False

        self.brightness_available = self._is_brightness_available()

        self.speaker_scale = create_scale(style_classes="cc-scale")
        self.mic_scale = create_scale(style_classes="cc-scale")
        if self.brightness_available:
            self.brightness_scale = create_scale(style_classes="cc-scale")

        self._speaker_apply_src: int | None = None
        self._mic_apply_src: int | None = None
        self._brightness_apply_src: int | None = None

        self.speaker_mute_icon = text_icon(
            get_audio_icon(self._get_speaker_volume(), self._get_speaker_muted()),
            size="16px",
        )
        self.speaker_mute_btn = ButtonWidget()
        self.speaker_mute_btn.children = self.speaker_mute_icon
        self.speaker_mute_btn.add_style_class("cc-mute-btn")

        self.mic_mute_icon = text_icon(
            cnst.icons["microphone"]["muted" if self._get_mic_muted() else "active"],
            size="16px",
        )
        self.mic_mute_btn = ButtonWidget()
        self.mic_mute_btn.children = self.mic_mute_icon
        self.mic_mute_btn.add_style_class("cc-mute-btn")

        self.speaker_mute_btn.connect("clicked", self._on_speaker_mute_clicked)
        self.mic_mute_btn.connect("clicked", self._on_mic_mute_clicked)

        self.speaker_label = text_icon(
            "0%", size="14px", style_classes="cc-percent-label"
        )
        self.mic_label = text_icon("0%", size="14px", style_classes="cc-percent-label")
        self.speaker_label.set_size_request(38, -1)
        self.mic_label.set_size_request(38, -1)

        slider_children = [
            Box(
                orientation="h",
                spacing=8,
                children=(
                    self.speaker_mute_btn,
                    self.speaker_scale,
                    self.speaker_label,
                ),
            ),
            Box(
                orientation="h",
                spacing=8,
                children=(self.mic_mute_btn, self.mic_scale, self.mic_label),
            ),
        ]

        if self.brightness_available:
            brightness_icon = text_icon(
                get_brightness_icon(self._get_brightness()), size="16px"
            )
            brightness_icon_box = ButtonWidget()
            brightness_icon_box.children = brightness_icon
            brightness_icon_box.add_style_class("cc-mute-btn")
            brightness_icon_box.set_can_focus(False)

            self.brightness_label = text_icon(
                "0%", size="14px", style_classes="cc-percent-label"
            )
            self.brightness_label.set_size_request(38, -1)

            slider_children.append(
                Box(
                    orientation="h",
                    spacing=8,
                    children=(
                        brightness_icon_box,
                        self.brightness_scale,
                        self.brightness_label,
                    ),
                )
            )

        sliders_box = Box(
            orientation="v",
            spacing=12,
            style_classes="cc-menu",
            children=slider_children,
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

        self.speaker_scale.connect("value-changed", self._on_speaker_changed)
        self.mic_scale.connect("value-changed", self._on_mic_changed)
        if self.brightness_available:
            self.brightness_scale.connect("value-changed", self._on_brightness_changed)

        self.speaker_scale.connect(
            "button-release-event", self._on_scale_release, "speaker"
        )
        self.mic_scale.connect("button-release-event", self._on_scale_release, "mic")
        if self.brightness_available:
            self.brightness_scale.connect(
                "button-release-event", self._on_scale_release, "brightness"
            )

        self.audio.connect("notify::speaker", self._bind_speaker)
        self.audio.connect("notify::microphone", self._bind_microphone)
        if self.brightness_available:
            self.brightness.connect("screen", self._on_brightness_service)

        self._bind_speaker()
        self._bind_microphone()
        self._sync_from_services()

    def _get_speaker_volume(self) -> int:
        return round(self.audio.speaker.volume) if self.audio.speaker else 0

    def _get_mic_volume(self) -> int:
        return round(self.audio.microphone.volume) if self.audio.microphone else 0

    def _get_speaker_muted(self) -> bool:
        return self.audio.speaker.muted if self.audio.speaker else False

    def _get_mic_muted(self) -> bool:
        return self.audio.microphone.muted if self.audio.microphone else False

    def _get_brightness(self) -> int:
        if not self.brightness_available:
            return 0
        return convert_to_percent(
            self.brightness.screen_brightness, self.brightness.max_brightness_level
        )

    def _is_brightness_available(self) -> bool:
        try:
            return bool(
                hasattr(self.brightness, "max_brightness_level")
                and self.brightness.max_brightness_level > 0
            )
        except Exception:
            return False

    def _sync_from_services(self):
        sp = self._get_speaker_volume()
        mc = self._get_mic_volume()
        self.speaker_scale.set_value(sp)
        self.mic_scale.set_value(mc)
        self.speaker_label.set_text(f"{sp}%")
        self.mic_label.set_text(f"{mc}%")
        if self.brightness_available:
            br = self._get_brightness()
            self.brightness_scale.set_value(br)
            self.brightness_label.set_text(f"{br}%")
        self._update_mute_buttons()

    def _on_speaker_changed(self, *_):
        if self.audio.speaker:
            self.speaker_label.set_text(f"{int(self.speaker_scale.value)}%")
            if self._speaker_apply_src:
                GLib.source_remove(self._speaker_apply_src)
            self._speaker_apply_src = GLib.timeout_add(100, self._apply_speaker)

    def _on_mic_changed(self, *_):
        if self.audio.microphone:
            self.mic_label.set_text(f"{int(self.mic_scale.value)}%")
            if self._mic_apply_src:
                GLib.source_remove(self._mic_apply_src)
            self._mic_apply_src = GLib.timeout_add(100, self._apply_mic)

    def _on_brightness_changed(self, *_):
        if not self.brightness_available:
            return
        self.brightness_label.set_text(f"{int(self.brightness_scale.value)}%")
        if self._brightness_apply_src:
            GLib.source_remove(self._brightness_apply_src)
        self._brightness_apply_src = GLib.timeout_add(80, self._apply_brightness)

    def _bind_speaker(self, *_):
        if self.audio.speaker:
            self.audio.speaker.connect(
                "notify::volume", self._update_speaker_from_service
            )
            self.audio.speaker.connect(
                "notify::muted", self._update_speaker_from_service
            )
            self._update_speaker_from_service()

    def _bind_microphone(self, *_):
        if self.audio.microphone:
            self.audio.microphone.connect(
                "notify::volume", self._update_mic_from_service
            )
            self.audio.microphone.connect(
                "notify::muted", self._update_mic_from_service
            )
            self._update_mic_from_service()

    def _on_brightness_service(self, *_):
        if (
            not self.brightness_available
            or self._brightness_apply_src
            or self._updating_brightness_from_service
        ):
            return
        val = self._get_brightness()
        self.brightness_scale.set_value(val)
        self.brightness_label.set_text(f"{int(val)}%")

    def _update_speaker_from_service(self, *_):
        if self._speaker_apply_src:
            return
        sp = self._get_speaker_volume()
        self.speaker_scale.set_value(sp)
        self.speaker_label.set_text(f"{sp}%")
        self._update_mute_buttons()

    def _update_mic_from_service(self, *_):
        if self._mic_apply_src:
            return
        mc = self._get_mic_volume()
        self.mic_scale.set_value(mc)
        self.mic_label.set_text(f"{mc}%")
        self._update_mute_buttons()

    def _update_mute_buttons(self):
        if self.audio.speaker:
            self.speaker_mute_icon.set_text(
                get_audio_icon(self._get_speaker_volume(), self._get_speaker_muted())
            )
        if self.audio.microphone:
            self.mic_mute_icon.set_text(
                cnst.icons["microphone"]["muted" if self._get_mic_muted() else "active"]
            )

    def _on_speaker_mute_clicked(self, *_):
        if self.audio.speaker:
            self.audio.speaker.set_muted(not self._get_speaker_muted())
            self._update_mute_buttons()
            if self.osd_widget:
                self.osd_widget.show_audio_speaker()

    def _on_mic_mute_clicked(self, *_):
        if self.audio.microphone:
            self.audio.microphone.set_muted(not self._get_mic_muted())
            self._update_mute_buttons()
            if self.osd_widget:
                self.osd_widget.show_audio_microphone()

    def _on_scale_release(self, widget, event, which):
        if which == "speaker":
            self._apply_speaker()
        elif which == "mic":
            self._apply_mic()
        elif which == "brightness":
            self._apply_brightness()
        return False

    def _apply_speaker(self):
        if self.audio.speaker:
            vol = max(0, min(100, int(self.speaker_scale.value)))
            self.audio.speaker.set_volume(vol)
            if self.osd_widget:
                self.osd_widget.show_audio_speaker()
        self._speaker_apply_src = None
        return False

    def _apply_mic(self):
        if self.audio.microphone:
            vol = max(0, min(100, int(self.mic_scale.value)))
            self.audio.microphone.set_volume(vol)
            if self.osd_widget:
                self.osd_widget.show_audio_microphone()
        self._mic_apply_src = None
        return False

    def _apply_brightness(self):
        if not self.brightness_available:
            return False
        self._updating_brightness_from_service = True
        val = max(0, min(100, int(self.brightness_scale.value)))
        target = int((val / 100.0) * self.brightness.max_brightness_level)
        self.brightness.screen_brightness = target
        if self.osd_widget:
            self.osd_widget.show_brightness()
        self._brightness_apply_src = None
        GLib.timeout_add(100, self._unblock_service_updates)
        return False

    def _unblock_service_updates(self):
        self._updating_brightness_from_service = False
        return False


class CombinedControlsButton(Overlay):
    """Capsule showing speaker, mic, brightness icons + 2x2 privacy dots."""

    def __init__(self, **kwargs):
        super().__init__(name="combined-controls", **kwargs)
        self.audio = audio_service
        self.brightness = brightness_service
        self.privacy = privacy_service
        self.menu: CombinedControlsMenu | None = None
        self.osd_widget = None

        self._scroll_debounce_src: int | None = None
        self._pending_scroll_updates = {}
        self._updating_brightness = False

        # ── Main icons ──────────────────────────────────────────────────
        self.icon_speaker = text_icon(get_audio_icon(0, False))
        self.icon_mic = text_icon(cnst.icons["microphone"]["active"])
        self.icon_brightness = text_icon(get_brightness_icon(self._get_brightness()))

        for icon in (self.icon_speaker, self.icon_mic, self.icon_brightness):
            icon.set_size_request(24, -1)
            icon.set_halign(Gtk.Align.CENTER)

        self._sync_icons()

        self.audio.connect("notify::speaker", self._bind_speaker)
        self.audio.connect("notify::microphone", self._bind_microphone)
        self.brightness.connect("screen", self._on_brightness_changed)

        # ── Privacy dots (2x2 grid = one icon slot) ────────────────────
        # Colours are defined by $privacy-dot-{mic,cam,screen,loc} in the
        # theme.  When inactive the dot is dimmed via _DOT_DIM_OPACITY so
        # the accent colour still shows through subtly.
        self.dot_mic = text_icon(
            "●", size="10px", style_classes="privacy-dot-mic"
        )
        self.dot_cam = text_icon(
            "●", size="10px", style_classes="privacy-dot-cam"
        )
        self.dot_screen = text_icon(
            "●", size="10px", style_classes="privacy-dot-screen"
        )
        self.dot_loc = text_icon(
            "●", size="10px", style_classes="privacy-dot-loc"
        )

        for dot in (self.dot_mic, self.dot_cam, self.dot_screen, self.dot_loc):
            dot.set_opacity(_DOT_DIM_OPACITY)

        dots_top = Box(
            orientation="h",
            spacing=3,
            children=[self.dot_mic, self.dot_cam],
            h_align="center",
            v_align="center",
            style="margin-bottom: -2px;",
        )
        dots_bot = Box(
            orientation="h",
            spacing=3,
            children=[self.dot_screen, self.dot_loc],
            h_align="center",
            v_align="center",
            style="margin-top: -2px;",
        )

        dots_grid = Box(
            orientation="v",
            spacing=0,
            children=[dots_top, dots_bot],
            h_align="center",
            v_align="center",
        )
        dots_grid.set_size_request(24, -1)

        self.privacy_event_box = EventBox(child=dots_grid)
        self.privacy_event_box.set_valign(Gtk.Align.CENTER)
        self.privacy_event_box.set_halign(Gtk.Align.CENTER)
        self.privacy_event_box.set_has_tooltip(True)
        self.privacy_event_box.connect("query-tooltip", self._on_privacy_tooltip)

        # Connect to privacy service signals
        for sig in (
            "notify::mic-active",
            "notify::cam-active",
            "notify::screen-active",
            "notify::loc-active",
        ):
            self.privacy.connect(sig, self._update_privacy_dots)

        self._update_privacy_dots()

        # ── EventBoxes for scroll ───────────────────────────────────────
        self.speaker_event_box = EventBox(
            child=self.icon_speaker, events=["scroll", "smooth-scroll"]
        )
        self.speaker_event_box.connect("scroll-event", self._on_scroll_speaker)

        self.mic_event_box = EventBox(
            child=self.icon_mic, events=["scroll", "smooth-scroll"]
        )
        self.mic_event_box.connect("scroll-event", self._on_scroll_mic)

        capsule_children = [self.speaker_event_box, self.mic_event_box]

        if self._is_brightness_available():
            self.brightness_event_box = EventBox(
                child=self.icon_brightness, events=["scroll", "smooth-scroll"]
            )
            self.brightness_event_box.connect(
                "scroll-event", self._on_scroll_brightness
            )
            capsule_children.append(self.brightness_event_box)

        capsule_children.append(self.privacy_event_box)

        inner = Box(
            orientation="h",
            spacing=4,
            children=capsule_children,
            style_classes="panel-box",
        )

        self.main_event_box = EventBox(child=inner, events=["button-press-event"])
        self.main_event_box.connect("button-press-event", self._on_clicked)
        self.add(self.main_event_box)

    # ── Privacy dots ───────────────────────────────────────────────────

    def _update_privacy_dots(self, *_):
        self.dot_mic.set_opacity(1.0 if self.privacy.mic_active else _DOT_DIM_OPACITY)
        self.dot_cam.set_opacity(1.0 if self.privacy.cam_active else _DOT_DIM_OPACITY)
        self.dot_screen.set_opacity(
            1.0 if self.privacy.screen_active else _DOT_DIM_OPACITY
        )
        self.dot_loc.set_opacity(1.0 if self.privacy.loc_active else _DOT_DIM_OPACITY)

    def _on_privacy_tooltip(self, widget, x, y, keyboard_mode, tooltip):
        lines = []
        if self.privacy.mic_active:
            apps = ", ".join(self.privacy.mic_apps) or "unknown"
            lines.append(f"󰍬 Mic: {apps}")
        if self.privacy.cam_active:
            apps = ", ".join(self.privacy.cam_apps) or "unknown"
            lines.append(f"󰄀 Camera: {apps}")
        if self.privacy.screen_active:
            apps = ", ".join(self.privacy.screen_apps) or "unknown"
            lines.append(f"󰹑 Screen: {apps}")
        if self.privacy.loc_active:
            apps = ", ".join(self.privacy.loc_apps) or "unknown"
            lines.append(f" Location: {apps}")
        if not lines:
            lines = ["No active privacy accesses"]
        tooltip.set_text("\n".join(lines))
        return True

    # ── General ────────────────────────────────────────────────────────

    def set_osd_widget(self, osd_widget):
        self.osd_widget = osd_widget

    def _on_clicked(self, *_):
        if not self.menu:
            self.menu = CombinedControlsMenu(
                anchor_widget=self, osd_widget=self.osd_widget
            )
        if self.menu.get_visible():
            self.menu.close()
        else:
            self.menu.open()

    def _on_scroll_speaker(self, widget, event):
        if not self.audio.speaker:
            return False
        step = 5
        new_vol = (
            min(100, self.audio.speaker.volume + step)
            if event.delta_y < 0
            else max(0, self.audio.speaker.volume - step)
        )
        self._pending_scroll_updates["speaker"] = new_vol
        self._debounce_scroll_updates()
        return True

    def _on_scroll_mic(self, widget, event):
        if not self.audio.microphone:
            return False
        step = 5
        new_vol = (
            min(100, self.audio.microphone.volume + step)
            if event.delta_y < 0
            else max(0, self.audio.microphone.volume - step)
        )
        self._pending_scroll_updates["microphone"] = new_vol
        self._debounce_scroll_updates()
        return True

    def _on_scroll_brightness(self, widget, event):
        if not self._is_brightness_available():
            return False
        step = 5
        current = self._get_brightness()
        new_val = (
            min(100, current + step) if event.delta_y < 0 else max(0, current - step)
        )
        self._pending_scroll_updates["brightness"] = new_val
        self._debounce_scroll_updates()
        return True

    def _debounce_scroll_updates(self):
        if self._scroll_debounce_src:
            GLib.source_remove(self._scroll_debounce_src)
        self._scroll_debounce_src = GLib.timeout_add(50, self._apply_scroll_updates)

    def _apply_scroll_updates(self):
        for device, value in self._pending_scroll_updates.items():
            if device == "speaker" and self.audio.speaker:
                self.audio.speaker.set_volume(value)
                if self.osd_widget:
                    self.osd_widget.show_audio_speaker()
            elif device == "microphone" and self.audio.microphone:
                self.audio.microphone.set_volume(value)
                if self.osd_widget:
                    self.osd_widget.show_audio_microphone()
            elif device == "brightness" and self._is_brightness_available():
                self._updating_brightness = True
                target = int((value / 100.0) * self.brightness.max_brightness_level)
                self.brightness.screen_brightness = target
                if self.osd_widget:
                    self.osd_widget.show_brightness()
                GLib.timeout_add(
                    100, lambda: setattr(self, "_updating_brightness", False)
                )
        self._pending_scroll_updates.clear()
        self._scroll_debounce_src = None
        return False

    def _get_brightness(self) -> int:
        return convert_to_percent(
            self.brightness.screen_brightness, self.brightness.max_brightness_level
        )

    def _is_brightness_available(self) -> bool:
        try:
            return bool(
                hasattr(self.brightness, "max_brightness_level")
                and self.brightness.max_brightness_level > 0
            )
        except Exception:
            return False

    def _sync_icons(self):
        if self.audio.speaker:
            self.icon_speaker.set_text(
                get_audio_icon(
                    round(self.audio.speaker.volume), self.audio.speaker.muted
                )
            )
        if self.audio.microphone:
            self.icon_mic.set_text(
                cnst.icons["microphone"][
                    "muted" if self.audio.microphone.muted else "active"
                ]
            )
        if self._is_brightness_available():
            self.icon_brightness.set_text(get_brightness_icon(self._get_brightness()))

    def _bind_speaker(self, *_):
        if self.audio.speaker:
            self.audio.speaker.connect("notify::volume", self._update_speaker_icon)
            self.audio.speaker.connect("notify::muted", self._update_speaker_icon)
            self._update_speaker_icon()

    def _bind_microphone(self, *_):
        if self.audio.microphone:
            self.audio.microphone.connect("notify::volume", self._update_mic_icon)
            self.audio.microphone.connect("notify::muted", self._update_mic_icon)
            self._update_mic_icon()

    def _on_brightness_changed(self, *_):
        if self._is_brightness_available() and not self._updating_brightness:
            self.icon_brightness.set_text(get_brightness_icon(self._get_brightness()))

    def _update_speaker_icon(self, *_):
        if self.audio.speaker:
            self.icon_speaker.set_text(
                get_audio_icon(
                    round(self.audio.speaker.volume), self.audio.speaker.muted
                )
            )

    def _update_mic_icon(self, *_):
        if self.audio.microphone:
            self.icon_mic.set_text(
                cnst.icons["microphone"][
                    "muted" if self.audio.microphone.muted else "active"
                ]
            )

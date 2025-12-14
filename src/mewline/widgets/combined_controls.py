from __future__ import annotations

from fabric.widgets.box import Box
from fabric.widgets.eventbox import EventBox
from fabric.widgets.overlay import Overlay
from fabric.widgets.revealer import Revealer
from gi.repository import GLib
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

    def __init__(self, anchor_widget: GObject.GObject, osd_widget=None, **kwargs):
        self.anchor_widget = anchor_widget
        self.audio = audio_service
        self.brightness = brightness_service
        self.config = cfg.modules
        self.osd_widget = osd_widget

        self._updating_brightness_from_service = False
        self._updating_brightness = False

        # Check if brightness control is available
        self.brightness_available = self._is_brightness_available()

        # Sliders
        self.speaker_scale = create_scale(style_classes="cc-scale")
        self.mic_scale = create_scale(style_classes="cc-scale")
        if self.brightness_available:
            self.brightness_scale = create_scale(style_classes="cc-scale")

        # Simple debounce helpers
        self._speaker_apply_src: int | None = None
        self._mic_apply_src: int | None = None
        self._brightness_apply_src: int | None = None

        # Mute buttons as main icons - clickable buttons with nerd font icons
        # Keep direct references to text icons for easy updates
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

        # Connect mute button clicks
        self.speaker_mute_btn.connect("clicked", self._on_speaker_mute_clicked)
        self.mic_mute_btn.connect("clicked", self._on_mic_mute_clicked)

        # Percentage labels
        self.speaker_label = text_icon("0%", size="14px")
        self.mic_label = text_icon("0%", size="14px")

        # Build slider children list (mute buttons as main icons on the left)
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

        # Add brightness only if available (no mute button for brightness)
        if self.brightness_available:
            brightness_icon = text_icon(get_brightness_icon(self._get_brightness()))
            self.brightness_label = text_icon("0%", size="14px")
            slider_children.append(
                Box(
                    orientation="h",
                    spacing=8,
                    children=(
                        brightness_icon,
                        self.brightness_scale,
                        self.brightness_label,
                    ),
                )
            )

        sliders_box = Box(
            orientation="v",
            spacing=8,
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

        # Connect scale changes
        self.speaker_scale.connect("value-changed", self._on_speaker_changed)
        self.mic_scale.connect("value-changed", self._on_mic_changed)
        if self.brightness_available:
            self.brightness_scale.connect("value-changed", self._on_brightness_changed)

        # Simple drag detection for immediate apply on release
        self.speaker_scale.connect(
            "button-release-event", self._on_scale_release, "speaker"
        )
        self.mic_scale.connect("button-release-event", self._on_scale_release, "mic")
        if self.brightness_available:
            self.brightness_scale.connect(
                "button-release-event", self._on_scale_release, "brightness"
            )

        # Listen to services to keep in sync
        self.audio.connect("notify::speaker", self._bind_speaker)
        self.audio.connect("notify::microphone", self._bind_microphone)
        if self.brightness_available:
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
        """Check if brightness control is available on this system."""
        try:
            # Try to get current brightness level
            return bool(
                hasattr(self.brightness, "max_brightness_level")
                and self.brightness.max_brightness_level > 0
            )
        except Exception:
            return False

    def _sync_from_services(self):
        sp = self._get_speaker_volume()
        mc = self._get_mic_volume()
        # Initial sync without animation
        self.speaker_scale.set_value(sp)
        self.mic_scale.set_value(mc)
        self.speaker_label.set_text(f"{sp}%")
        self.mic_label.set_text(f"{mc}%")

        if self.brightness_available:
            br = self._get_brightness()
            self.brightness_scale.set_value(br)
            self.brightness_label.set_text(f"{br}%")

        # Update mute button icons
        self._update_mute_buttons()

    def _on_speaker_changed(self, *_):
        if self.audio.speaker:
            vol = self.speaker_scale.value
            self.speaker_label.set_text(f"{int(vol)}%")
            # Simple debounce
            if self._speaker_apply_src:
                GLib.source_remove(self._speaker_apply_src)
            self._speaker_apply_src = GLib.timeout_add(100, self._apply_speaker)

    def _on_mic_changed(self, *_):
        if self.audio.microphone:
            vol = self.mic_scale.value
            self.mic_label.set_text(f"{int(vol)}%")
            if self._mic_apply_src:
                GLib.source_remove(self._mic_apply_src)
            self._mic_apply_src = GLib.timeout_add(100, self._apply_mic)

    def _on_brightness_changed(self, *_):
        if not self.brightness_available:
            return
        val = self.brightness_scale.value
        self.brightness_label.set_text(f"{int(val)}%")
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
        if not self.brightness_available or self._brightness_apply_src or self._updating_brightness_from_service:
            return  # Don't update while we have a pending change
        val = self._get_brightness()
        self.brightness_scale.set_value(val)
        self.brightness_label.set_text(f"{int(val)}%")

    def _update_speaker_from_service(self, *_):
        if self._speaker_apply_src:
            return  # Don't update while we have a pending change
        sp = self._get_speaker_volume()
        self.speaker_scale.set_value(sp)
        self.speaker_label.set_text(f"{sp}%")
        self._update_mute_buttons()

    def _update_mic_from_service(self, *_):
        if self._mic_apply_src:
            return  # Don't update while we have a pending change
        mc = self._get_mic_volume()
        self.mic_scale.set_value(mc)
        self.mic_label.set_text(f"{mc}%")
        self._update_mute_buttons()

    def _update_mute_buttons(self):
        """Update mute button icons based on current mute state."""
        if self.audio.speaker:
            vol = self._get_speaker_volume()
            is_muted = self._get_speaker_muted()
            icon = get_audio_icon(vol, is_muted)
            # Use direct reference to text icon widget
            self.speaker_mute_icon.set_text(icon)

        if self.audio.microphone:
            is_muted = self._get_mic_muted()
            icon = cnst.icons["microphone"]["muted" if is_muted else "active"]
            # Use direct reference to text icon widget
            self.mic_mute_icon.set_text(icon)

    def _on_speaker_mute_clicked(self, *_):
        """Toggle speaker mute state."""
        if self.audio.speaker:
            current_muted = self._get_speaker_muted()
            self.audio.speaker.set_muted(not current_muted)
            self._update_mute_buttons()
            # Trigger OSD for speaker
            if self.osd_widget:
                self.osd_widget.show_audio_speaker()

    def _on_mic_mute_clicked(self, *_):
        """Toggle microphone mute state."""
        if self.audio.microphone:
            current_muted = self._get_mic_muted()
            self.audio.microphone.set_muted(not current_muted)
            self._update_mute_buttons()
            # Trigger OSD for microphone
            if self.osd_widget:
                self.osd_widget.show_audio_microphone()

    # Apply helpers
    def _on_scale_release(self, widget, event, which):
        # Immediate apply on mouse release
        if which == "speaker":
            self._apply_speaker()
        elif which == "mic":
            self._apply_mic()
        elif which == "brightness":
            self._apply_brightness()
        return False

    def _apply_speaker(self):
        if self.audio.speaker:
            vol = int(self.speaker_scale.value)
            vol = max(0, min(100, vol))
            self.audio.speaker.set_volume(vol)
            # Trigger OSD for speaker
            if self.osd_widget:
                self.osd_widget.show_audio_speaker()
        self._speaker_apply_src = None
        return False

    def _apply_mic(self):
        if self.audio.microphone:
            vol = int(self.mic_scale.value)
            vol = max(0, min(100, vol))
            self.audio.microphone.set_volume(vol)
            # Trigger OSD for microphone
            if self.osd_widget:
                self.osd_widget.show_audio_microphone()
        self._mic_apply_src = None
        return False

    def _apply_brightness(self):
        if not self.brightness_available:
            return False

        self._updating_brightness_from_service = True
        val = int(self.brightness_scale.value)
        val = max(0, min(100, val))
        # translate percent back to raw units
        target = int((val / 100.0) * self.brightness.max_brightness_level)
        self.brightness.screen_brightness = target
        # Trigger OSD for brightness
        if self.osd_widget:
            self.osd_widget.show_brightness()
        self._brightness_apply_src = None

        GLib.timeout_add(100, self.unblock_service_updates)
        return False

    def _unblock_service_updates(self):
        self._updating_brightness_from_service = False
        return False


class CombinedControlsButton(Overlay):
    """Capsule showing speaker, mic, brightness icons; toggles CombinedControlsMenu.

    Also supports mouse wheel scrolling to adjust speaker volume and show OSD.
    """

    def __init__(self, **kwargs):
        super().__init__(name="combined-controls", **kwargs)
        self.audio = audio_service
        self.brightness = brightness_service
        self.menu: CombinedControlsMenu | None = None
        self.osd_widget = None  # Will be set from outside

        # Scroll debouncing
        self._scroll_debounce_src: int | None = None
        self._pending_scroll_updates = {}

        self.icon_speaker = text_icon(get_audio_icon(0, False))
        self.icon_mic = text_icon(cnst.icons["microphone"]["active"])  # simplified
        self.icon_brightness = text_icon(get_brightness_icon(self._get_brightness()))

        # Initial icon syncs
        self._sync_icons()

        # Connect services to update icons
        self.audio.connect("notify::speaker", self._bind_speaker)
        self.audio.connect("notify::microphone", self._bind_microphone)
        self.brightness.connect("screen", self._on_brightness_changed)

        # Create separate EventBoxes for each icon to handle scroll events individually
        self.speaker_event_box = EventBox(
            child=self.icon_speaker, events=["scroll", "smooth-scroll"]
        )
        self.speaker_event_box.connect("scroll-event", self._on_scroll_speaker)

        self.mic_event_box = EventBox(
            child=self.icon_mic, events=["scroll", "smooth-scroll"]
        )
        self.mic_event_box.connect("scroll-event", self._on_scroll_mic)

        # Layout children with EventBoxes
        capsule_children = [self.speaker_event_box, self.mic_event_box]

        if self._is_brightness_available():
            self.brightness_event_box = EventBox(
                child=self.icon_brightness, events=["scroll", "smooth-scroll"]
            )
            self.brightness_event_box.connect(
                "scroll-event", self._on_scroll_brightness
            )
            capsule_children.append(self.brightness_event_box)

        inner = Box(
            orientation="h",
            spacing=15,
            children=capsule_children,
            style_classes="panel-box",
        )

        # Wrap everything in an EventBox to handle clicks on entire capsule
        self.main_event_box = EventBox(child=inner, events=["button-press-event"])
        self.main_event_box.connect("button-press-event", self._on_clicked)

        self.add(self.main_event_box)

    def set_osd_widget(self, osd_widget):
        """Set reference to OSD widget for triggering display."""
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
        """Handle mouse wheel scroll to adjust speaker volume and trigger OSD."""
        if not self.audio.speaker:
            return False

        step = 5
        val_y = event.delta_y

        if val_y < 0:  # scroll up
            new_vol = min(100, self.audio.speaker.volume + step)
        else:  # scroll down
            new_vol = max(0, self.audio.speaker.volume - step)

        # Store pending update and debounce
        self._pending_scroll_updates["speaker"] = new_vol
        self._debounce_scroll_updates()

        return True

    def _on_scroll_mic(self, widget, event):
        """Handle mouse wheel scroll to adjust microphone volume and trigger OSD."""
        if not self.audio.microphone:
            return False

        step = 5
        val_y = event.delta_y

        if val_y < 0:  # scroll up
            new_vol = min(100, self.audio.microphone.volume + step)
        else:  # scroll down
            new_vol = max(0, self.audio.microphone.volume - step)

        # Store pending update and debounce
        self._pending_scroll_updates["microphone"] = new_vol
        self._debounce_scroll_updates()

        return True

    def _on_scroll_brightness(self, widget, event):
        """Handle mouse wheel scroll to adjust brightness and trigger OSD."""
        if not self._is_brightness_available():
            return False

        step = 5
        val_y = event.delta_y

        current = self._get_brightness()
        if val_y < 0:  # scroll up  # noqa: SIM108
            new_val = min(100, current + step)
        else:  # scroll down
            new_val = max(0, current - step)

        # Store pending update and debounce
        self._pending_scroll_updates["brightness"] = new_val
        self._debounce_scroll_updates()

        return True

    def _debounce_scroll_updates(self):
        """Debounce scroll updates to prevent jitter."""
        if self._scroll_debounce_src:
            GLib.source_remove(self._scroll_debounce_src)
        self._scroll_debounce_src = GLib.timeout_add(50, self._apply_scroll_updates)

    def _apply_scroll_updates(self):
        """Apply pending scroll updates."""
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

                GLib.timeout_add(100, lambda: setattr(self, '_updating_brightness', False))

        self._pending_scroll_updates.clear()
        self._scroll_debounce_src = None
        return False

    def _get_brightness(self) -> int:
        return convert_to_percent(
            self.brightness.screen_brightness, self.brightness.max_brightness_level
        )

    def _is_brightness_available(self) -> bool:
        """Check if brightness control is available on this system."""
        try:
            # Try to get current brightness level
            return bool(
                hasattr(self.brightness, "max_brightness_level")
                and self.brightness.max_brightness_level > 0
            )
        except Exception:
            return False

    def _sync_icons(self):
        if self.audio.speaker:
            vol = round(self.audio.speaker.volume)
            self.icon_speaker.set_text(get_audio_icon(vol, self.audio.speaker.muted))

        if self.audio.microphone:
            is_muted = self.audio.microphone.muted
            icon = cnst.icons["microphone"]["muted" if is_muted else "active"]
            self.icon_mic.set_text(icon)

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
            vol = round(self.audio.speaker.volume)
            self.icon_speaker.set_text(get_audio_icon(vol, self.audio.speaker.muted))

    def _update_mic_icon(self, *_):
        if self.audio.microphone:
            is_muted = self.audio.microphone.muted
            icon = cnst.icons["microphone"]["muted" if is_muted else "active"]
            self.icon_mic.set_text(icon)

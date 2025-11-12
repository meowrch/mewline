import contextlib
import json
import os
import re
from typing import TYPE_CHECKING

from fabric.hyprland.widgets import ActiveWindow
from fabric.hyprland.widgets import get_hyprland_connection
from fabric.utils import FormattedString
from fabric.utils import truncate
from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.centerbox import CenterBox
from fabric.widgets.image import Image
from fabric.widgets.label import Label

from mewline.config import cfg
from mewline.constants import WINDOW_TITLE_MAP
from mewline.services.mpris import MprisPlayer
from mewline.services.priority_audio import PriorityAudioManager
from mewline.utils.icon_resolver import get_icon_pixbuf_for_app
from mewline.utils.widget_utils import setup_cursor_hover
from mewline.utils.widget_utils import text_icon
from mewline.widgets.dynamic_island.base import BaseDiWidget

if TYPE_CHECKING:
    from mewline.widgets.dynamic_island import DynamicIsland


class Compact(BaseDiWidget, CenterBox):
    """Dynamic Island compact view with music integration."""

    def __init__(self, di: "DynamicIsland"):
        super().__init__()
        self.config = cfg.modules.dynamic_island.compact
        self.priority_audio_manager = PriorityAudioManager()
        self.current_mpris_player = None

        self.cover = Box(style_classes="cover", visible=False)
        self.music_label = Label(style_classes="panel-text", visible=False)
        self.music_box = Box(children=[self.cover, self.music_label])

        self.window_title = ActiveWindow(
            name="window",
            formatter=FormattedString(
                "{ get_title(win_title, win_class) }",
                get_title=self._format_window_title,
            ),
        )

        # Real app icon next to title (slot that can hold Image or glyph Label)
        self.window_icon_slot = Box(name="di-compact-icon-slot")
        self.window_row = Box(orientation="h", spacing=6)
        self._apply_icon_enablement()

        self.main_container = Box(
            name="di-compact-main-container", children=[self.window_row]
        )
        compact_button = Button(
            name="compact-label",
            child=self.main_container,
            on_clicked=lambda *_: di.open("date-notification"),
        )
        setup_cursor_hover(compact_button)

        CenterBox.__init__(
            self,
            name="dynamic-island-compact",
            center_children=[compact_button],
            v_expand=True,
            h_expand=True,
        )

        if self.config.music.enabled:
            self.priority_audio_manager.connect(
                "active-player-changed", self._on_active_player_changed
            )
            # Also listen to audio stream changes (volume changes in PulseAudio)
            if self.priority_audio_manager.audio_monitor.enabled:
                self.priority_audio_manager.audio_monitor.connect(
                    "active-stream-changed", self._on_audio_stream_changed
                )
            # Initialize current player if available
            if self.priority_audio_manager.active_player:
                self._set_active_player(self.priority_audio_manager.active_player)

        # Update app icon when title changes (only if enabled)
        try:
            self.window_title.connect("notify::label", lambda *_: self._update_window_icon())
            self._update_window_icon()
        except Exception:
            ...

    def _set_active_player(self, player: MprisPlayer | None):
        """Set the active player and connect to its signals."""
        # Disconnect from old player
        if self.current_mpris_player:
            with contextlib.suppress(Exception):
                self.current_mpris_player.disconnect_by_func(self._update_display)
        # Set new player
        self.current_mpris_player = player

        # Connect to new player
        if self.current_mpris_player:
            self.current_mpris_player.connect(
                "notify::playback-status", self._update_display
            )
            self.current_mpris_player.connect("notify::metadata", self._update_display)

        # Update display
        self._update_display()

    def _format_window_title(self, win_title, win_class):
        win_title = (
            truncate(win_title, self.config.window_titles.truncation_size)
            if self.config.window_titles.truncation
            else win_title
        )

        merged_titles = self.config.window_titles.title_map + WINDOW_TITLE_MAP
        matched = next(
            (wt for wt in merged_titles if re.search(wt[0], win_class.lower())), None
        )

        if not matched:
            return win_class.lower()

        if matched[0] == "^$" or win_class == "undefined":
            base = f"{os.getlogin()}@{os.uname().nodename}"
            return base

        # Only text here; visual icon is handled via self.window_icon
        return matched[2]

    def _on_active_player_changed(self, manager, player: MprisPlayer | None):
        """Handle active player changes from PriorityAudioManager."""
        if not self.config.music.enabled:
            return

        self._set_active_player(player)

    def _on_audio_stream_changed(self, monitor, stream):
        """Handle audio stream changes (e.g., volume changes in PulseAudio)."""
        if not self.config.music.enabled:
            return

        # Re-evaluate active player based on new audio stream
        # This handles cases where multiple players are playing
        # and you change volume in one of them
        new_active = self.priority_audio_manager.active_player
        if new_active != self.current_mpris_player:
            self._set_active_player(new_active)

    def _update_display(self, *args):
        if not self.config.music.enabled:
            return

        if self.current_mpris_player and self._is_playing():
            self._show_music_info()
        else:
            self._show_window_title()

    def _is_playing(self):
        return (
            self.current_mpris_player
            and self.current_mpris_player.playback_status.lower() == "playing"
        )

    def _apply_icon_enablement(self):
        enabled = bool(getattr(self.config.window_titles, "enable_icon", True))

        try:
            for ch in list(self.window_row.get_children()):
                self.window_row.remove(ch)
        except Exception:
            ...

        if enabled:
            with contextlib.suppress(Exception):
                self.window_row.add(self.window_icon_slot)

        with contextlib.suppress(Exception):
            self.window_row.add(self.window_title)

    def _update_window_icon(self):
        if not bool(getattr(self.config.window_titles, "enable_icon", True)):
            return
        try:
            conn = get_hyprland_connection()

            if not conn:
                return

            active_window_json = conn.send_command("j/activewindow").reply.decode()
            active_window_data = json.loads(active_window_json)
            app_id = active_window_data.get("initialClass", "") or active_window_data.get("class", "")

            try:
                for ch in list(self.window_icon_slot.get_children()):
                    self.window_icon_slot.remove(ch)
                    ch.destroy()
            except Exception:
                ...

            if app_id == "":
                self.window_icon_slot.add(text_icon("󰣆", size="14px"))
                return

            pixbuf, _source, _name = get_icon_pixbuf_for_app(app_id, 16)
            if pixbuf:
                self.window_icon_slot.add(Image(pixbuf=pixbuf))
            else:
                self.window_icon_slot.add(text_icon("󰣆", size="14px"))
        except Exception:
            try:
                for ch in list(self.window_icon_slot.get_children()):
                    self.window_icon_slot.remove(ch)
                    ch.destroy()
            except Exception:
                ...

            self.window_icon_slot.add(text_icon("󰣆", size="14px"))

    def _show_music_info(self):
        artist = self.current_mpris_player.artist or "Unknown Artist"
        title = self.current_mpris_player.title or "Unknown Track"

        # Форматирование названия трека
        full_title = f"{artist} - {title}"

        if self.config.music.truncation:
            full_title = truncate(full_title, self.config.music.truncation_size)

        self.music_label.set_label(full_title)

        # Обновление обложки
        art_url = (
            self.current_mpris_player.arturl or self.config.music.default_album_logo
        )
        self.cover.set_style(
            f"background-image: url('{art_url}'); background-size: cover;"
        )

        # Обновление контейнера
        self.main_container.children = [self.music_box]
        self.cover.show()
        self.music_label.show()

    def _show_window_title(self):
        # Ensure icon enablement applied before showing row
        self._apply_icon_enablement()
        self.main_container.children = [self.window_row]
        self.cover.hide()
        self.music_label.hide()

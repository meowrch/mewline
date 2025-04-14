import os
import re
from typing import TYPE_CHECKING

from fabric.hyprland.widgets import ActiveWindow
from fabric.utils import FormattedString
from fabric.utils import truncate
from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.centerbox import CenterBox
from fabric.widgets.label import Label

from mewline.config import cfg
from mewline.constants import WINDOW_TITLE_MAP
from mewline.services.mpris import MprisPlayer
from mewline.services.mpris import MprisPlayerManager
from mewline.utils.widget_utils import setup_cursor_hover
from mewline.widgets.dynamic_island.base import BaseDiWidget

if TYPE_CHECKING:
    from mewline.widgets.dynamic_island import DynamicIsland


class Compact(BaseDiWidget, CenterBox):
    """Dynamic Island compact view with music integration."""

    def __init__(self, di: "DynamicIsland"):
        super().__init__()
        self.config = cfg.modules.dynamic_island.compact
        self.mpris_manager = MprisPlayerManager()
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

        self.main_container = Box(
            name="di-compact-main-container",
            children=[self.window_title]
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
            self.mpris_manager.connect("player-appeared", self._on_player_changed)
            self.mpris_manager.connect("player-vanished", self._on_player_changed)
            self._init_players()

    def _init_players(self):
        if not self.config.music.enabled or not self.mpris_manager.players:
            return

        self.current_mpris_player = MprisPlayer(self.mpris_manager.players[0])
        self.current_mpris_player.connect(
            "notify::playback-status", self._update_display
        )
        self.current_mpris_player.connect("notify::metadata", self._update_display)
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
            return f"󰣆 {win_class.lower()}"

        if matched[0] == "^$":
            base = f"{os.getlogin()}@{os.uname().nodename}"
            return (
                f"{matched[1]} {base}"
                if self.config.window_titles.enable_icon
                else base
            )

        return (
            f"{matched[1]} {matched[2]}"
            if self.config.window_titles.enable_icon
            else matched[2]
        )

    def _on_player_changed(self, manager, player):
        if not self.config.music.enabled:
            return

        if self.current_mpris_player:
            self.current_mpris_player.disconnect_by_func(self._update_display)

        if manager.players:
            self.current_mpris_player = MprisPlayer(manager.players[0])
            self.current_mpris_player.connect(
                "notify::playback-status", self._update_display
            )
            self.current_mpris_player.connect("notify::metadata", self._update_display)
        else:
            self.current_mpris_player = None

        self._update_display()

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
            self.current_mpris_player.arturl
            or self.config.music.default_album_logo
        )
        self.cover.set_style(
            f"background-image: url('{art_url}'); background-size: cover;"
        )

        # Обновление контейнера
        self.main_container.children = [self.music_box]
        self.cover.show()
        self.music_label.show()

    def _show_window_title(self):
        self.main_container.children = [self.window_title]
        self.cover.hide()
        self.music_label.hide()

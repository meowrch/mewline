import contextlib
import json
import os
import re
import subprocess
from typing import TYPE_CHECKING

from fabric.utils import FormattedString
from fabric.utils import truncate
from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.centerbox import CenterBox
from fabric.widgets.label import Label
from gi.repository import GLib
from loguru import logger

from mewline.config import cfg
from mewline.constants import WINDOW_TITLE_MAP
from mewline.services import audio_visualizer_service
from mewline.services.mpris import MprisPlayer
from mewline.services.mpris import MprisPlayerManager
from mewline.utils.widget_utils import setup_cursor_hover
from mewline.utils.widget_utils import text_icon
from mewline.widgets.audio_visualizer import AudioVisualizerWidget
from mewline.widgets.dynamic_island.base import BaseDiWidget

if TYPE_CHECKING:
    from mewline.widgets.dynamic_island import DynamicIsland


class Compact(BaseDiWidget, CenterBox):
    """Dynamic Island compact view with music integration and adaptive WM support."""

    def __init__(self, di: "DynamicIsland"):
        super().__init__()
        self.config = cfg.modules.dynamic_island.compact
        self.mpris_manager = MprisPlayerManager()
        self.current_mpris_player = None
        self._music_update_seq = 0
        self._music_last_title = None
        self._music_last_art_url = None
        self._music_last_playing = None

        # Detect window manager and store type
        self.wm_type = self._detect_window_manager()

        # Cache for window class to avoid repeated xprop calls
        self._last_window_class = None

        self.cover = Box(style_classes="cover", visible=False)
        self.music_label = Label(style_classes="panel-text", visible=False)
        viz_enabled = self.config.music.visualizer_enabled
        self.visualizer = (
            AudioVisualizerWidget(
                bar_count=6,
                animated_bars=4,
                min_width=28,
                min_height=20,
                static_level=0.25,
            )
            if viz_enabled
            else None
        )
        if self.visualizer is not None:
            self.visualizer.set_margin_start(4)
            self.visualizer.hide()
        music_children: list = [self.cover, self.music_label]
        if self.visualizer is not None:
            music_children.append(self.visualizer)
        self.music_box = Box(
            orientation="h", spacing=4, children=music_children
        )

        # Create adaptive active window widget
        self.window_title = self._create_active_window_widget()

        # Real app icon next to title (slot that can hold nerd icon Label)
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
            self.mpris_manager.connect("player-appeared", self._on_player_changed)
            self.mpris_manager.connect("player-vanished", self._on_player_changed)
            self._init_players()

        # Update app icon when title changes (only if enabled)
        try:
            self.window_title.connect(
                "notify::label", lambda *_: self._update_window_icon()
            )
            self._update_window_icon()
        except Exception:
            ...

    def _detect_window_manager(self) -> str:
        """Detect current window manager.

        Returns:
            'hyprland', 'bspwm', or 'unknown'
        """
        try:
            # Check for Hyprland
            from fabric.hyprland.widgets import get_hyprland_connection

            conn = get_hyprland_connection()
            if conn:
                logger.info("[Compact] Detected Hyprland")
                return "hyprland"
        except (ImportError, Exception):  # noqa: S110
            pass

        try:
            # Check for bspwm
            result = subprocess.run(
                ["pgrep", "-x", "bspwm"],
                capture_output=True,
                text=True,
                timeout=1,
            )
            if result.returncode == 0 and result.stdout.strip():
                logger.info("[Compact] Detected bspwm")
                return "bspwm"
        except Exception:  # noqa: S110
            pass

        logger.warning("[Compact] Could not detect window manager")
        return "unknown"

    def _create_active_window_widget(self):
        """Create appropriate ActiveWindow widget based on current WM.

        Returns:
            ActiveWindow widget instance (Hyprland or bspwm specific)
        """
        formatter = FormattedString(
            "{ get_title(win_title, win_class) }",
            get_title=self._format_window_title,
        )

        if self.wm_type == "hyprland":
            try:
                from fabric.hyprland.widgets import ActiveWindow

                return ActiveWindow(name="window", formatter=formatter)
            except (ImportError, Exception) as e:
                logger.error(f"[Compact] Failed to create Hyprland widget: {e}")

        elif self.wm_type == "bspwm":
            try:
                from mewline.custom_fabric.bspwm.widgets import BspwmActiveWindow

                return BspwmActiveWindow(name="window", formatter=formatter)
            except (ImportError, Exception) as e:
                logger.error(f"[Compact] Failed to create bspwm widget: {e}")

        # Fallback to simple label
        logger.warning("[Compact] Using fallback label for window title")
        return Label(label="Desktop", name="window")

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
        """Format window title according to config and title map."""
        # Store window class for icon matching
        self._last_window_class = win_class

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
        self._schedule_music_update()

    def _schedule_music_update(self):
        self._music_update_seq += 1
        seq = self._music_update_seq
        GLib.Thread.new("compact-music-update", self._music_update_worker, seq)

    def _music_update_worker(self, seq):
        if not self.config.music.enabled:
            return None

        player = self.current_mpris_player
        playing = False
        try:
            if player is not None:
                playing = player.playback_status.lower() == "playing"
        except Exception:
            playing = False

        if not playing:
            GLib.idle_add(self._apply_music_state, seq, False, None, None)
            return None

        try:
            artist = player.artist or "Unknown Artist"
        except Exception:
            artist = "Unknown Artist"
        try:
            title = player.title or "Unknown Track"
        except Exception:
            title = "Unknown Track"
        try:
            art_url = player.arturl or self.config.music.default_album_logo
        except Exception:
            art_url = self.config.music.default_album_logo

        full_title = f"{artist} - {title}"
        if self.config.music.truncation:
            full_title = truncate(full_title, self.config.music.truncation_size)

        GLib.idle_add(self._apply_music_state, seq, True, full_title, art_url)
        return None

    def _apply_music_state(self, seq, playing: bool, full_title, art_url):
        if seq != self._music_update_seq:
            return False

        if not playing:
            self._music_last_playing = False
            self._show_window_title()
            return False

        if full_title and full_title != self._music_last_title:
            self.music_label.set_label(full_title)
            self._music_last_title = full_title

        if art_url and art_url != self._music_last_art_url:
            self.cover.set_style(
                f"background-image: url('{art_url}'); background-size: cover;"
            )
            self._music_last_art_url = art_url

        if self.visualizer is not None:
            audio_visualizer_service.set_callback(self.visualizer.set_levels)
            audio_visualizer_service.start()
            self.visualizer.show()

        self.main_container.children = [self.music_box]
        self.cover.show()
        self.music_label.show()
        self._music_last_playing = True
        return False

    def _is_playing(self):
        return (
            self.current_mpris_player
            and self.current_mpris_player.playback_status.lower() == "playing"
        )

    def _apply_icon_enablement(self):
        """Apply icon enablement configuration."""
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

    def _get_active_window_class_hyprland(self) -> str:
        """Get active window class for Hyprland.

        Returns:
            Window class/app_id or empty string
        """
        try:
            from fabric.hyprland.widgets import get_hyprland_connection

            conn = get_hyprland_connection()
            if not conn:
                return ""

            active_window_json = conn.send_command("j/activewindow").reply.decode()
            active_window_data = json.loads(active_window_json)
            app_class = active_window_data.get(
                "initialClass", ""
            ) or active_window_data.get("class", "")
            return app_class.lower()
        except Exception as e:
            logger.debug(f"[Compact] Error getting Hyprland window class: {e}")
            return ""

    def _get_active_window_class_bspwm(self) -> str:
        """Get active window class for bspwm.

        Returns:
            Window class (checks both instance and class from WM_CLASS)
        """
        try:
            from mewline.custom_fabric.bspwm.widgets import get_bspwm_connection

            conn = get_bspwm_connection()
            if not conn:
                return ""

            # Get focused node ID
            reply = conn.send_command("query -N -n focused", silent=True)
            if not reply.is_ok or not reply.output:
                return ""

            node_id = reply.output.strip()
            if not node_id:
                return ""

            # Get window class using xprop
            try:
                result = subprocess.run(
                    ["xprop", "-id", node_id, "WM_CLASS"],
                    capture_output=True,
                    text=True,
                    timeout=1,
                )
                if result.returncode == 0 and result.stdout:
                    # WM_CLASS(STRING) = "instance", "Class"
                    # Extract both values and try to match
                    match = re.search(r'"([^"]+)",\s*"([^"]+)"', result.stdout)
                    if match:
                        instance = match.group(1).lower()
                        wm_class = match.group(2).lower()

                        # Log for debugging
                        logger.debug(
                            f"[Compact] WM_CLASS: instance='{instance}', "
                            f"class='{wm_class}'"
                        )

                        # Try to find match with both instance and class
                        merged_titles = (
                            self.config.window_titles.title_map + WINDOW_TITLE_MAP
                        )

                        # First try instance
                        for entry in merged_titles:
                            if re.search(entry[0], instance):
                                return instance

                        # Then try class
                        for entry in merged_titles:
                            if re.search(entry[0], wm_class):
                                return wm_class

                        # Return instance as default
                        return instance
            except Exception as e:
                logger.debug(f"[Compact] xprop failed: {e}")

            return ""
        except Exception as e:
            logger.debug(f"[Compact] Error getting bspwm window class: {e}")
            return ""

    def _get_nerd_icon_for_app(self, app_class: str) -> str:
        """Get nerd font icon for app from WINDOW_TITLE_MAP.

        Args:
            app_class: Application class/id (lowercase)

        Returns:
            Nerd font icon character or default fallback icon
        """
        if not app_class:
            return "󰣆"

        app_class_lower = app_class.lower()
        merged_titles = self.config.window_titles.title_map + WINDOW_TITLE_MAP

        # Search for matching pattern in title map
        for entry in merged_titles:
            try:
                if re.search(entry[0], app_class_lower):  # noqa: SIM102
                    if len(entry) >= 2 and entry[1]:
                        logger.debug(
                            f"[Compact] Matched '{app_class_lower}' -> "
                            f"pattern '{entry[0]}' -> icon '{entry[1]}'"
                        )
                        return entry[1]
            except Exception as e:
                logger.debug(f"[Compact] Error matching pattern '{entry[0]}': {e}")

        # Fallback icon
        logger.debug(f"[Compact] No match for '{app_class_lower}', using fallback")
        return "󰣆"

    def _update_window_icon(self):
        """Update window icon based on current WM and active window."""
        if not bool(getattr(self.config.window_titles, "enable_icon", True)):
            return

        try:
            # Get app_class based on WM type
            if self.wm_type == "hyprland":
                app_class = self._get_active_window_class_hyprland()
            elif self.wm_type == "bspwm":
                app_class = self._get_active_window_class_bspwm()
            else:
                # Fallback: use cached class from title formatter
                app_class = self._last_window_class or ""

            # Get nerd icon for app
            nerd_icon = self._get_nerd_icon_for_app(app_class)

            # Clear existing icon
            try:
                for ch in list(self.window_icon_slot.get_children()):
                    self.window_icon_slot.remove(ch)
                    ch.destroy()
            except Exception:
                ...

            # Add nerd icon
            self.window_icon_slot.add(text_icon(nerd_icon, size="14px"))

        except Exception as e:
            logger.debug(f"[Compact] Error updating window icon: {e}")
            try:
                for ch in list(self.window_icon_slot.get_children()):
                    self.window_icon_slot.remove(ch)
                    ch.destroy()
            except Exception:
                ...

            self.window_icon_slot.add(text_icon("󰣆", size="14px"))

    def _show_music_info(self):
        """Show music player information."""
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

        if self.visualizer is not None:
            audio_visualizer_service.set_callback(self.visualizer.set_levels)
            audio_visualizer_service.start()
            self.visualizer.show()

        # Обновление контейнера
        self.main_container.children = [self.music_box]
        self.cover.show()
        self.music_label.show()

    def _show_window_title(self):
        """Show window title with icon."""
        if self.visualizer is not None:
            audio_visualizer_service.remove_callback(self.visualizer.set_levels)
            # Only stop if no callbacks remain
            if not audio_visualizer_service._callbacks:
                audio_visualizer_service.stop()
            self.visualizer.hide()
        # Ensure icon enablement applied before showing row
        self._apply_icon_enablement()
        self.main_container.children = [self.window_row]
        self.cover.hide()
        self.music_label.hide()

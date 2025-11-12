"""Priority-based audio player manager combining MPRIS and PulseAudio."""


from fabric.core.service import Property
from fabric.core.service import Service
from fabric.core.service import Signal
from loguru import logger

from mewline.services.audio_monitor import AudioStream
from mewline.services.audio_monitor import AudioStreamMonitor
from mewline.services.mpris import MprisPlayer
from mewline.services.mpris import MprisPlayerManager


class PriorityAudioManager(Service):
    """Manages audio player priority based on:
    1. Playing status (playing > paused)
    2. Audio stream volume (from PulseAudio)
    3. Most recent activity.
    """  # noqa: D205

    __gtype_name__ = "PriorityAudioManager"

    @Signal
    def active_player_changed(self, player: object) -> object:
        """Emitted when the active player changes."""
        ...

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        # MPRIS integration
        self.mpris_manager = MprisPlayerManager()
        self._mpris_players: dict[str, MprisPlayer] = {}

        # PulseAudio integration
        self.audio_monitor = AudioStreamMonitor(update_interval=1.0)

        # Current active player
        self._active_player: MprisPlayer | None = None

        # Setup MPRIS callbacks
        self.mpris_manager.connect("player-appeared", self._on_mpris_player_appeared)
        self.mpris_manager.connect("player-vanished", self._on_mpris_player_vanished)

        # Setup audio monitor callbacks
        if self.audio_monitor.enabled:
            self.audio_monitor.connect(
                "streams-changed", self._on_audio_streams_changed
            )
            self.audio_monitor.connect(
                "active-stream-changed", self._on_active_stream_changed
            )

        # Initialize existing players
        self._init_existing_players()

        # Determine initial active player
        self._update_active_player()

    def _init_existing_players(self):
        """Initialize existing MPRIS players."""
        for player in self.mpris_manager.players:
            player_name = player.get_property("player-name")
            mpris_player = MprisPlayer(player)
            self._mpris_players[player_name] = mpris_player

            # Connect to player changes
            mpris_player.connect(
                "notify::playback-status", self._on_player_status_changed
            )
            mpris_player.connect("notify::metadata", self._on_player_metadata_changed)

    def _on_mpris_player_appeared(self, manager, player):
        """Handle new MPRIS player appearing."""
        player_name = player.get_property("player-name")
        logger.debug(f"[PriorityAudioManager] Player appeared: {player_name}")

        mpris_player = MprisPlayer(player)
        self._mpris_players[player_name] = mpris_player

        # Connect to player changes
        mpris_player.connect("notify::playback-status", self._on_player_status_changed)
        mpris_player.connect("notify::metadata", self._on_player_metadata_changed)

        self._update_active_player()

    def _on_mpris_player_vanished(self, manager, player_name: str):
        """Handle MPRIS player disappearing."""
        logger.debug(f"[PriorityAudioManager] Player vanished: {player_name}")

        if player_name in self._mpris_players:
            vanished_player = self._mpris_players.pop(player_name)

            # If this was the active player, update
            if self._active_player == vanished_player:
                self._update_active_player()

    def _on_player_status_changed(self, player, *args):
        """Handle playback status changes."""
        self._update_active_player()

    def _on_player_metadata_changed(self, player, *args):
        """Handle metadata changes (might indicate new track)."""
        # Only update if this player is playing
        if player.playback_status.lower() == "playing":
            self._update_active_player()

    def _on_audio_streams_changed(self, monitor):
        """Handle audio stream list changes."""
        self._update_active_player()

    def _on_active_stream_changed(self, monitor, stream: AudioStream | None):
        """Handle active audio stream changes."""
        self._update_active_player()

    def _update_active_player(self):
        """Determine and update the active player based on priority."""
        old_active = self._active_player
        new_active = self._determine_active_player()

        if old_active != new_active:
            self._active_player = new_active
            logger.debug(
                f"[PriorityAudioManager] Active player changed: "
                f"{getattr(old_active, 'player_name', None)} -> "
                f"{getattr(new_active, 'player_name', None)}"
            )
            self.emit("active-player-changed", new_active)
            self.notify("active-player")

    def _determine_active_player(self) -> MprisPlayer | None:
        """Determine the most active player based on priority:
        1. Playing status (playing > paused)
        2. Audio volume from PulseAudio (loudest)
        3. Most recent MPRIS player.
        """  # noqa: D205
        if not self._mpris_players:
            return None

        # Get all players
        players = list(self._mpris_players.values())

        # Filter playing players
        playing_players = [p for p in players if p.playback_status.lower() == "playing"]

        # If no one is playing, return None (show window title instead)
        if not playing_players:
            return None

        # If only one is playing, return it
        if len(playing_players) == 1:
            return playing_players[0]

        # Multiple players playing - use PulseAudio volume to decide
        if self.audio_monitor.enabled:
            return self._select_by_audio_volume(playing_players)

        # Fallback: return the first playing player
        return playing_players[0]

    def _select_by_audio_volume(self, players: list[MprisPlayer]) -> MprisPlayer:
        """Select player based on audio volume from PulseAudio."""
        active_stream = self.audio_monitor.active_stream

        if not active_stream:
            # No audio stream info, return first player
            return players[0]

        # Try to match player with audio stream by app name
        active_app_lower = active_stream.app_name.lower()

        for player in players:
            player_name_lower = player.player_name.lower()

            # Match by player name (e.g., "firefox" in "firefox.instance123")
            if (
                player_name_lower in active_app_lower
                or active_app_lower in player_name_lower
            ):
                return player

        # If no match found, return the player with highest priority (first playing)
        return players[0]

    # Properties
    @Property(object, "readable")
    def active_player(self) -> MprisPlayer | None:
        """Get the currently active/prioritized player."""
        return self._active_player

    @Property(object, "readable")
    def players(self) -> dict[str, MprisPlayer]:
        """Get all available MPRIS players."""
        return self._mpris_players

    @Property(bool, "readable", default_value=False)
    def has_active_player(self) -> bool:
        """Check if there's an active player."""
        return self._active_player is not None

    @Property(object, "readable")
    def active_audio_stream(self) -> AudioStream | None:
        """Get the currently active audio stream from PulseAudio."""
        if self.audio_monitor.enabled:
            return self.audio_monitor.active_stream
        return None

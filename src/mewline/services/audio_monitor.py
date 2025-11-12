"""Service for monitoring audio streams through PulseAudio."""

import threading
import time
from dataclasses import dataclass

from fabric.core.service import Property
from fabric.core.service import Service
from fabric.core.service import Signal
from gi.repository import GLib
from loguru import logger

try:
    import pulsectl
except ImportError:
    logger.error(
        "pulsectl is not installed, please install it with: pip install pulsectl"
    )
    pulsectl = None


@dataclass
class AudioStream:
    """Represents an active audio stream."""

    index: int
    app_name: str
    media_name: str | None
    volume: float  # 0.0 to 1.0 (can be >1.0 with software boost)
    is_muted: bool

    @property
    def display_name(self) -> str:
        """Get human-readable stream name."""
        if self.media_name:
            return f"{self.app_name} — {self.media_name}"
        return self.app_name


class AudioStreamMonitor(Service):
    """Monitors active audio streams via PulseAudio."""

    __gtype_name__ = "AudioStreamMonitor"

    @Signal
    def streams_changed(self) -> None:
        """Emitted when the list of active streams changes."""
        ...

    @Signal
    def active_stream_changed(self, stream: object) -> object:
        """Emitted when the most active stream changes."""
        ...

    def __init__(self, update_interval: float = 1.0, **kwargs):
        super().__init__(**kwargs)

        if pulsectl is None:
            logger.error("AudioStreamMonitor disabled: pulsectl not available")
            self._enabled = False
            return

        self._enabled = True
        self._update_interval = update_interval
        self._streams: dict[int, AudioStream] = {}
        self._pulse: pulsectl.Pulse | None = None
        self._monitor_thread: threading.Thread | None = None
        self._stop_flag = threading.Event()

        self._start_monitoring()

    def _start_monitoring(self):
        """Start the monitoring thread."""
        if not self._enabled:
            return

        self._stop_flag.clear()
        self._monitor_thread = threading.Thread(target=self._monitor_loop, daemon=True)
        self._monitor_thread.start()

    def _monitor_loop(self):
        """Main monitoring loop running in a separate thread."""
        try:
            with pulsectl.Pulse("mewline-audio-monitor") as pulse:
                self._pulse = pulse

                while not self._stop_flag.is_set():
                    try:
                        self._update_streams()
                    except Exception as e:
                        logger.debug(f"Error updating audio streams: {e}")

                    time.sleep(self._update_interval)

        except Exception as e:
            logger.error(f"AudioStreamMonitor thread error: {e}")
            self._enabled = False

    def _update_streams(self):
        """Update the list of active audio streams."""
        if not self._pulse:
            return

        try:
            sink_inputs = self._pulse.sink_input_list()
            new_streams = {}

            for si in sink_inputs:
                stream = self._parse_sink_input(si)
                new_streams[stream.index] = stream

            # Check if streams changed
            if new_streams != self._streams:
                old_streams = self._streams
                self._streams = new_streams

                # Emit changes on main thread
                GLib.idle_add(lambda: self.emit("streams-changed"))

                # Check if active stream changed
                old_active = self._get_most_active_stream_from(old_streams)
                new_active = self.active_stream

                if old_active != new_active:
                    GLib.idle_add(
                        lambda: self.emit("active-stream-changed", new_active)
                    )

        except Exception as e:
            logger.debug(f"Error in _update_streams: {e}")

    def _parse_sink_input(self, si) -> AudioStream:
        """Parse PulseAudio sink input into AudioStream."""
        props = si.proplist or {}

        app_name = (
            props.get("application.name")
            or props.get("application.process.binary")
            or "Unknown"
        )
        media_name = props.get("media.name")

        volume = si.volume.value_flat  # 0.0..1.0 (can be >1.0 with boost)
        is_muted = bool(si.mute)

        return AudioStream(
            index=si.index,
            app_name=app_name,
            media_name=media_name,
            volume=volume,
            is_muted=is_muted,
        )

    def _get_most_active_stream_from(
        self, streams: dict[int, AudioStream]
    ) -> AudioStream | None:
        """Get the most active stream from a collection."""
        if not streams:
            return None

        # Filter out muted streams
        active_streams = [s for s in streams.values() if not s.is_muted]

        if not active_streams:
            return None

        # Sort by volume (loudest first)
        return max(active_streams, key=lambda s: s.volume)

    def stop(self):
        """Stop monitoring."""
        self._stop_flag.set()
        if self._monitor_thread:
            self._monitor_thread.join(timeout=2.0)

    # Properties
    @Property(object, "readable")
    def streams(self) -> dict[int, AudioStream]:
        """Get all active audio streams."""
        return self._streams

    @Property(object, "readable")
    def active_stream(self) -> AudioStream | None:
        """Get the currently most active stream (loudest unmuted)."""
        return self._get_most_active_stream_from(self._streams)

    @Property(bool, "readable", default_value=False)
    def enabled(self) -> bool:
        """Check if monitoring is enabled."""
        return self._enabled

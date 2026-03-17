"""Service that provides audio level data for the waveform visualizer.

Emits waveform bar levels at ~30 FPS. Uses mock/simulated data when playing;
optionally scales by system volume if pulsectl is available.
"""

import math
import random
from collections.abc import Callable
from gi.repository import GLib

try:
    import pulsectl
except ImportError:
    pulsectl = None

from loguru import logger


class AudioVisualizerService:
    """Emits waveform level data for visualization.

    When started, runs a timer that pushes lists of float levels (0.0–1.0)
    for each bar. Uses smoothed mock data; can optionally scale by PulseAudio
    volume if pulsectl is available.
    """

    def __init__(
        self,
        bar_count: int = 6,
        fps: int = 50,
        smoothing: float = 0.7,
        on_levels: Callable[[list[float]], None] | None = None,
    ):
        self._bar_count = bar_count
        self._interval_ms = max(16, int(1000 / fps))
        self._smoothing = max(0.01, min(1.0, smoothing))
        self._time = 0.0
        self._levels: list[float] = [0.0] * bar_count
        self._targets: list[float] = [0.0] * bar_count
        self._velocities: list[float] = [0.0] * bar_count
        self._source_id: int | None = None
        self._callbacks: list[Callable[[list[float]], None]] = []
        if on_levels is not None:
            self._callbacks.append(on_levels)
        self._pulse = None
        if pulsectl is not None:
            try:
                self._pulse = pulsectl.Pulse("billpanel-visualizer")
            except Exception as e:
                logger.debug(f"[AudioVisualizer] Pulse connection failed: {e}")

    @property
    def bar_count(self) -> int:
        return self._bar_count

    def _get_volume_scale(self) -> float:
        """Return 0.0–1.0 scale from default sink volume if Pulse is available."""
        if self._pulse is None:
            return 1.0
        try:
            for sink in self._pulse.sink_list():
                vol = getattr(sink, "volume", None)
                if vol is None:
                    continue
                values = getattr(vol, "values", None) or getattr(vol, "value_list", None)
                if values:
                    total = sum(values) / len(values)
                    return min(1.0, total / 65536.0)
            return 1.0
        except Exception:
            return 1.0

    def _tick(self) -> bool:
        """Advance waveform with bouncy spring-like animation."""
        self._time += self._interval_ms / 1000.0
        scale = self._get_volume_scale()

        stiffness = 0.35
        damping = 0.55

        for i in range(self._bar_count):
            phase = self._time * 4.0 + i * 1.2
            wave = 0.25 + 0.65 * abs(math.sin(phase))
            jitter = 0.35 * (random.random() - 0.5)
            if random.random() < 0.12:
                jitter += 0.3 * (random.random() - 0.3)
            target = scale * max(0.0, min(1.0, wave + jitter))
            self._targets[i] = target

            diff = self._targets[i] - self._levels[i]
            self._velocities[i] += diff * stiffness
            self._velocities[i] *= damping
            self._levels[i] += self._velocities[i]
            self._levels[i] = max(0.0, min(1.0, self._levels[i]))

        self.emit_levels(self._levels)
        return True

    def set_callback(self, callback: Callable[[list[float]], None] | None) -> None:
        """Add or remove callback invoked with list of bar levels (0.0–1.0) each frame."""
        if callback is None:
            return
        if callback not in self._callbacks:
            self._callbacks.append(callback)

    def remove_callback(self, callback: Callable[[list[float]], None] | None) -> None:
        """Remove a previously registered callback."""
        if callback is not None and callback in self._callbacks:
            self._callbacks.remove(callback)

    def emit_levels(self, levels: list[float]) -> None:
        """Notify all registered callbacks with current levels."""
        for callback in self._callbacks:
            try:
                callback(levels)
            except Exception as e:
                logger.debug(f"[AudioVisualizer] Callback error: {e}")

    def start(self) -> None:
        """Start emitting level updates."""
        if self._source_id is not None:
            return
        self._source_id = GLib.timeout_add(
            self._interval_ms,
            self._tick,
            priority=GLib.PRIORITY_DEFAULT,
        )

    def stop(self) -> None:
        """Stop emitting level updates."""
        if self._source_id is not None:
            GLib.source_remove(self._source_id)
            self._source_id = None
        self._levels = [0.0] * self._bar_count
        self._targets = [0.0] * self._bar_count
        self._velocities = [0.0] * self._bar_count

    def close(self) -> None:
        """Release Pulse connection if any."""
        self.stop()
        if self._pulse is not None:
            try:
                self._pulse.close()
            except Exception:
                pass
            self._pulse = None

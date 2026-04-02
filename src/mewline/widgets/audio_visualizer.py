"""Waveform audio visualizer widget for the Dynamic Island."""

import math

import cairo
from gi.repository import Gtk


class AudioVisualizerWidget(Gtk.DrawingArea):
    """Compact icon-like waveform visualizer with pill-shaped bars.

    Has static padding bars on left/right edges; inner bars are animated.
    """

    def __init__(
        self,
        bar_count: int = 6,
        animated_bars: int = 4,
        min_width: int = 36,
        min_height: int = 20,
        static_level: float = 0.25,
        **kwargs,
    ):
        super().__init__(**kwargs)
        self._bar_count = bar_count
        self._animated_bars = min(animated_bars, bar_count)
        self._static_level = static_level
        self._levels: list[float] = [0.0] * animated_bars
        self.set_size_request(min_width, min_height)
        self.set_name("di-audio-visualizer")
        self.connect("draw", self._on_draw)

    def set_levels(self, levels: list[float]) -> None:
        """Update animated bar levels (0.0-1.0). Triggers redraw."""
        n = min(len(levels), self._animated_bars)
        for i in range(n):
            self._levels[i] = max(0.0, min(1.0, float(levels[i])))
        for i in range(n, self._animated_bars):
            self._levels[i] = 0.0
        self.queue_draw()

    def _draw_pill_bar(
        self,
        cr: cairo.Context,
        x: float,
        y_top: float,
        bar_width: float,
        bar_h: float,
    ) -> None:
        """Draw a single vertical pill/capsule (rounded top and bottom)."""
        if bar_h < 1:
            return
        radius = min(bar_width, bar_h) / 2
        if radius <= 0:
            return
        cx = x + bar_width / 2
        if bar_h <= bar_width:
            cr.arc(cx, y_top + bar_h / 2, radius, 0, 2 * math.pi)
            cr.fill()
            return
        # Top cap (half circle)
        cr.arc(cx, y_top + radius, radius, math.pi, 0)
        # Right edge
        cr.line_to(cx + radius, y_top + bar_h - radius)
        # Bottom cap
        cr.arc(cx, y_top + bar_h - radius, radius, 0, math.pi)
        # Left edge
        cr.line_to(cx - radius, y_top + radius)
        cr.close_path()
        cr.fill()

    def _on_draw(self, widget, cr: cairo.Context) -> bool:
        width = widget.get_allocated_width()
        height = widget.get_allocated_height()
        if width <= 0 or height <= 0:
            return False

        style = widget.get_style_context()
        color = style.get_color(Gtk.StateFlags.NORMAL)
        if color:
            r, g, b, a = color.red, color.green, color.blue, color.alpha
            cr.set_source_rgba(r, g, b, a)
        else:
            cr.set_source_rgba(0.7, 0.7, 0.7, 0.9)

        padding = 2
        center_y = height / 2
        gap = 2
        bar_width = max(2, (width - 2 * padding - (self._bar_count - 1) * gap) / self._bar_count)
        max_h = (height - 2 * padding) / 2

        total_bars_width = self._bar_count * bar_width + (self._bar_count - 1) * gap
        start_x = (width - total_bars_width) / 2

        padding_bars_left = (self._bar_count - self._animated_bars) // 2
        padding_bars_right = self._bar_count - self._animated_bars - padding_bars_left

        for i in range(self._bar_count):
            if i < padding_bars_left:
                level = self._static_level
            elif i >= self._bar_count - padding_bars_right:
                level = self._static_level
            else:
                anim_idx = i - padding_bars_left
                level = self._levels[anim_idx] if anim_idx < len(self._levels) else 0.0

            bar_h = max(2, level * max_h)
            x = start_x + i * (bar_width + gap)
            y_top = center_y - bar_h / 2
            cr.new_path()
            self._draw_pill_bar(cr, x, y_top, bar_width, bar_h)
        return False

import contextlib
import json
import re

import gi
from fabric.hyprland import Hyprland
from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.label import Label
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk

from mewline.config import cfg
from mewline.constants import WINDOW_TITLE_MAP
from mewline.utils.widget_utils import text_icon
from mewline.widgets.dynamic_island.base import BaseDiWidget

BASE_SCALE = 0.10  # target scale per monitor (approx like competitor)


class WorkspacesOverview(BaseDiWidget, Box):
    """Dynamic Island widget: 2x5 grid of workspaces with scaled app miniatures."""

    focuse_kb = True

    def __init__(self, **kwargs):
        Box.__init__(
            self,
            name="workspaces-overview",
            orientation="v",
            spacing=8,
            **kwargs,
        )

        gi.require_version("Gtk", "3.0")

        # Hypr connection
        self._hypr = Hyprland()

        # Workspace config
        self._ws_start = 1
        self._ws_end = min(10, int(getattr(cfg.modules.workspaces, "count", 10)))

        # Containers per workspace
        self._ws_fixed: dict[int, Gtk.Fixed] = {}
        self._ws_eventbox: dict[int, Gtk.EventBox] = {}

        # Grid rows
        self.row_top = Box(orientation="h", spacing=8)
        self.row_bottom = Box(orientation="h", spacing=8)
        self.children = [self.row_top, self.row_bottom]

        # Navigation state
        self._mini: list[dict] = []  # each: {btn, ws, gx, gy, w, h, addr}
        self._focus_idx: int | None = None
        self._pending_focus_ws: int | None = None
        self._pending_focus_addr: str | None = None

        # Accept keyboard events
        try:
            self.add_events(Gdk.EventMask.KEY_PRESS_MASK)
            self.set_can_focus(True)
            self.connect("key-press-event", self._on_key_press)
        except Exception:
            ...

        # Build tiles and initial content
        self._build_grid()
        self.refresh()
        self._hook_hypr_events()

    def open_widget_from_di(self):
        # Refresh when opened to ensure fresh layout
        self.refresh()
        # Ensure widget grabs focus so arrow keys work
        GLib.idle_add(lambda: (self.grab_focus(), False)[1])

    def _hook_hypr_events(self):
        try:
            self._hypr.connect("event::openwindow", lambda *_: self._queue_refresh())
            self._hypr.connect("event::closewindow", lambda *_: self._queue_refresh())
            self._hypr.connect("event::movewindow", lambda *_: self._queue_refresh())
            self._hypr.connect("event::workspace", lambda *_: self._queue_refresh())
        except Exception:
            ...

    def _queue_refresh(self):
        GLib.timeout_add(100, lambda: (self.refresh(), False)[1])
        return False

    def _monitor_dims(self) -> tuple[int, int, dict[int, dict]]:
        """Return (width,height) of focused monitor and monitors map."""
        try:
            mons = json.loads(self._hypr.send_command("j/monitors").reply.decode())
        except Exception:
            mons = []
        focused = next((m for m in mons if m.get("focused")), mons[0] if mons else {})
        width = int(focused.get("width", 1920))
        height = int(focused.get("height", 1080))
        monmap = {m.get("id", i): m for i, m in enumerate(mons)}
        return width, height, monmap

    def _build_grid(self):
        # Clear rows
        try:
            for row in (self.row_top, self.row_bottom):
                for child in list(row.get_children()):
                    row.remove(child)
        except Exception:
            ...
        self._ws_fixed.clear()
        self._ws_eventbox.clear()

        # Create 2x5 workspace tiles
        ids = list(range(self._ws_start, self._ws_end + 1))
        top_ids, bottom_ids = ids[:5], ids[5:10]
        for ws_id in top_ids:
            self.row_top.add(self._build_workspace_tile(ws_id))
        for ws_id in bottom_ids:
            self.row_bottom.add(self._build_workspace_tile(ws_id))

    def _build_workspace_tile(self, ws_id: int) -> Box:
        # Fixed area wrapped in EventBox to allow sizing and hover
        fixed = Gtk.Fixed.new()
        ev = Gtk.EventBox()
        ev.add(fixed)

        with contextlib.suppress(Exception):
            ev.set_visible(True)

        # Store refs
        self._ws_fixed[ws_id] = fixed
        self._ws_eventbox[ws_id] = ev

        # Outer box per tile
        tile = Box(
            name="overview-workspace-box",
            orientation="v",
            spacing=4,
            children=[ev],
        )
        return tile

    def refresh(self):
        # Compute target tile size from monitor dims
        mon_w, mon_h, monmap = self._monitor_dims()
        tile_w = max(120, int(mon_w * BASE_SCALE))
        tile_h = max(80, int(mon_h * BASE_SCALE))
        eff_scale = tile_w / max(1, mon_w)
        H_GAP = 8
        V_GAP = 8

        # Preserve current focused address/workspace or pending request
        prev_addr = None
        prev_ws = None
        if self._focus_idx is not None and 0 <= self._focus_idx < len(self._mini):
            prev_addr = self._mini[self._focus_idx].get("addr")
            prev_ws = self._mini[self._focus_idx].get("ws")
        sel_addr = self._pending_focus_addr or prev_addr
        sel_ws = self._pending_focus_ws or prev_ws

        # Reset miniatures
        self._mini.clear()
        self._focus_idx = None

        # Resize tiles
        for _ws_id, ev in self._ws_eventbox.items():
            with contextlib.suppress(Exception):
                ev.set_size_request(tile_w, tile_h)

        # Clear existing clients
        for fixed in self._ws_fixed.values():
            try:
                for child in list(fixed.get_children()):
                    fixed.remove(child)
            except Exception:
                ...

        # Fetch clients
        try:
            clients = json.loads(self._hypr.send_command("j/clients").reply.decode())
        except Exception:
            clients = []

        used_ws: set[int] = set()
        # Place clients into their workspace containers
        for c in clients:
            try:
                ws = int(c.get("workspace", {}).get("id", -1))
                if ws < self._ws_start or ws > self._ws_end:
                    continue
                mon_id = c.get("monitor")
                mon = monmap.get(mon_id, {})
                mon_x = int(mon.get("x", 0))
                mon_y = int(mon.get("y", 0))
                cx, cy = c.get("at", [0, 0])
                cw, ch = c.get("size", [80, 60])
                # Relative position within monitor, then scale
                rel_x = max(0, int((cx - mon_x) * eff_scale))
                rel_y = max(0, int((cy - mon_y) * eff_scale))
                bw = max(8, int(cw * eff_scale))
                bh = max(8, int(ch * eff_scale))

                # Compute grid origin for this workspace tile
                col = (ws - self._ws_start) % 5
                row = 0 if ws <= (self._ws_start + 4) else 1
                origin_x = col * (tile_w + H_GAP)
                origin_y = row * (tile_h + V_GAP)
                gx = origin_x + rel_x
                gy = origin_y + rel_y

                # Create window miniature as a button
                glyph = (
                    self._resolve_icon_for_class(
                        (c.get("initialClass") or c.get("class") or "").lower()
                    )
                    or "󰣆"
                )
                glyph_label = text_icon(glyph, size="14px")
                btn = Button(
                    name="overview-client-box",
                    tooltip_text=(c.get("title") or c.get("class") or "")[:128],
                    child=glyph_label,
                    on_clicked=lambda *_a, addr=c.get["address"]: self._focus(addr),
                    on_button_press_event=(
                        lambda _w, event, addr=c["address"]: self._maybe_close(
                            event, addr
                        )
                    ),
                )
                # Hover highlight
                try:
                    btn.add_events(
                        Gdk.EventMask.ENTER_NOTIFY_MASK
                        | Gdk.EventMask.LEAVE_NOTIFY_MASK
                    )
                    btn.connect(
                        "enter-notify-event",
                        lambda _w, _e, b=btn: (b.add_style_class("hover"), False)[1],
                    )
                    btn.connect(
                        "leave-notify-event",
                        lambda _w, _e, b=btn: (b.remove_style_class("hover"), False)[1],
                    )
                except Exception:
                    ...

                # Ensure button has the desired miniature size
                with contextlib.suppress(Exception):
                    btn.set_size_request(bw, bh)

                # Put into the workspace fixed container
                fixed = self._ws_fixed.get(ws)
                if fixed is not None:
                    fixed.put(btn, rel_x, rel_y)

                used_ws.add(ws)

                # Track miniature for navigation
                self._mini.append(
                    {
                        "btn": btn,
                        "ws": ws,
                        "gx": gx,
                        "gy": gy,
                        "w": bw,
                        "h": bh,
                        "addr": c.get("address"),
                    }
                )
            except Exception:
                ...

        # Add empty workspace placeholders if enabled
        try:
            if getattr(cfg.modules.workspaces, "navigate_empty", False):
                ids = list(range(self._ws_start, self._ws_end + 1))
                for ws in ids:
                    if ws in used_ws:
                        continue
                    # compute tile origin
                    col = (ws - self._ws_start) % 5
                    row = 0 if ws <= (self._ws_start + 4) else 1
                    origin_x = col * (tile_w + H_GAP)
                    origin_y = row * (tile_h + V_GAP)

                    # button filling the tile
                    ws_num_label = Label(
                        name="ws-number",
                        label=str(ws),
                        h_align="center",
                        v_align="center",
                    )
                    placeholder = Button(
                        name="overview-client-box",
                        tooltip_text=f"Switch to workspace {ws}",
                        child=ws_num_label,
                        on_clicked=lambda *_a, wid=ws: self._on_placeholder_clicked(wid),
                    )
                    try:
                        placeholder.set_size_request(tile_w, tile_h)
                        placeholder.add_events(
                            Gdk.EventMask.ENTER_NOTIFY_MASK
                            | Gdk.EventMask.LEAVE_NOTIFY_MASK
                        )
                        placeholder.connect(
                            "enter-notify-event",
                            lambda _w, _e, b=placeholder: (
                                b.add_style_class("hover"),
                                False,
                            )[1],
                        )
                        placeholder.connect(
                            "leave-notify-event",
                            lambda _w, _e, b=placeholder: (
                                b.remove_style_class("hover"),
                                False,
                            )[1],
                        )
                    except Exception:
                        ...

                    fixed = self._ws_fixed.get(ws)
                    if fixed is not None:
                        fixed.put(placeholder, 0, 0)

                    # Track as navigable item
                    self._mini.append(
                        {
                            "btn": placeholder,
                            "ws": ws,
                            "gx": origin_x,
                            "gy": origin_y,
                            "w": tile_w,
                            "h": tile_h,
                            "addr": None,
                        }
                    )
        except Exception:
            ...

        # Show all new children
        with contextlib.suppress(Exception):
            self.show_all()

        # Restore focus preference: by address, then workspace (placeholder first),
        # else first
        if self._mini:
            focused = False
            if sel_addr is not None:
                try:
                    idx = next(i for i, m in enumerate(self._mini) if m.get("addr") == sel_addr)
                    self._set_focus(idx)
                    focused = True
                except StopIteration:
                    focused = False
            if not focused and sel_ws is not None:
                # Prefer placeholder for that workspace
                try:
                    idx = next(
                        i for i, m in enumerate(self._mini) if m.get("ws") == sel_ws and m.get("addr") is None
                    )
                    self._set_focus(idx)
                    focused = True
                except StopIteration:
                    # Fallback to any item in that workspace
                    try:
                        idx = next(i for i, m in enumerate(self._mini) if m.get("ws") == sel_ws)
                        self._set_focus(idx)
                        focused = True
                    except StopIteration:
                        focused = False
            if not focused:
                self._set_focus(0)

        # Clear pending focus request
        self._pending_focus_ws = None
        self._pending_focus_addr = None

    def _focus(self, address: str | None):
        if not address:
            return

        with contextlib.suppress(Exception):
            self._hypr.send_command(f"/dispatch focuswindow address:{address}")

    def _maybe_close(self, event, address: str | None):
        try:
            if getattr(event, "button", 1) == 3 and address:
                self._hypr.send_command(f"/dispatch closewindow address:{address}")
                return True
        except Exception:
            ...
        return False

    def _on_placeholder_clicked(self, ws_id: int):
        # Remember we want to focus this workspace tile after rebuild
        self._pending_focus_ws = int(ws_id)
        self._pending_focus_addr = None
        self._switch_workspace(ws_id)

    def _switch_workspace(self, ws_id: int | None):
        if not ws_id:
            return

        with contextlib.suppress(Exception):
            self._hypr.send_command(f"/dispatch workspace {int(ws_id)}")

    def _resolve_icon_for_class(self, win_class: str) -> str | None:
        # Try user-defined title_map first (same map as compact view)
        try:
            user_map = getattr(
                cfg.modules.dynamic_island.compact.window_titles, "title_map", []
            )
        except Exception:
            user_map = []
        for pattern, icon, _title in [*user_map, *WINDOW_TITLE_MAP]:
            try:
                if re.search(pattern, win_class):
                    return icon
            except re.error:
                continue
        return None

    # Navigation helpers
    def _on_key_press(self, _widget, event):
        key = getattr(event, "keyval", None)
        if key in (Gdk.KEY_Left, Gdk.KEY_Right, Gdk.KEY_Up, Gdk.KEY_Down):
            direction = {
                Gdk.KEY_Left: "left",
                Gdk.KEY_Right: "right",
                Gdk.KEY_Up: "up",
                Gdk.KEY_Down: "down",
            }[key]
            self._move_focus(direction)
            return True
        if key in (Gdk.KEY_Return, Gdk.KEY_KP_Enter, Gdk.KEY_space):
            self._activate_focused()
            return True
        return False

    def _set_focus(self, idx: int):
        if not self._mini:
            self._focus_idx = None
            return
        idx = max(0, min(idx, len(self._mini) - 1))
        # Remove previous
        if self._focus_idx is not None and 0 <= self._focus_idx < len(self._mini):
            with contextlib.suppress(Exception):
                self._mini[self._focus_idx]["btn"].remove_style_class("focused")

        self._focus_idx = idx

        with contextlib.suppress(Exception):
            self._mini[self._focus_idx]["btn"].add_style_class("focused")

    def _activate_focused(self):
        if self._focus_idx is None or not self._mini:
            return
        item = self._mini[self._focus_idx]
        addr = item.get("addr")
        if addr:
            self._focus(addr)
        else:
            self._switch_workspace(item.get("ws"))

    def _move_focus(self, direction: str):
        # Two-stage navigation:
        # 1) try move between items INSIDE the current workspace tile
        # 2) if none in that direction, move to the adjacent tile (2x5 grid)
        if not self._mini:
            return
        if self._focus_idx is None:
            self._set_focus(0)
            return
        cur = self._mini[self._focus_idx]
        cur_ws = cur.get("ws") or self._ws_start
        cx = cur["gx"] + cur["w"] / 2
        cy = cur["gy"] + cur["h"] / 2

        # Stage 1: intra-workspace move (prefer windows over placeholder)
        def pick_best(cands: list[tuple[int, dict]]):
            best_i = None
            best_score = None
            for i, m in cands:
                if i == self._focus_idx:
                    continue
                tx = m["gx"] + m["w"] / 2
                ty = m["gy"] + m["h"] / 2
                dx = tx - cx
                dy = ty - cy
                match direction:
                    case "left":
                        if dx >= 0:
                            continue
                        score = (-dx) * 2 + abs(dy)
                    case "right":
                        if dx <= 0:
                            continue
                        score = (dx) * 2 + abs(dy)
                    case "up":
                        if dy >= 0:
                            continue
                        score = (-dy) * 2 + abs(dx)
                    case "down":
                        if dy <= 0:
                            continue
                        score = (dy) * 2 + abs(dx)
                    case _:
                        continue
                if best_score is None or score < best_score:
                    best_score = score
                    best_i = i
            return best_i

        same_ws = [(i, m) for i, m in enumerate(self._mini) if m.get("ws") == cur_ws]
        # First windows (addr != None), then placeholder (addr == None)
        win_cands = [(i, m) for i, m in same_ws if m.get("addr")]
        ph_cands = [(i, m) for i, m in same_ws if not m.get("addr")]

        best = pick_best(win_cands)
        if best is None:
            best = pick_best(ph_cands)
        if best is not None:
            self._set_focus(best)
            return

        # Stage 2: move to adjacent tile (like wallpapers grid)
        cols = 5
        rows = 2
        idx0 = cur_ws - self._ws_start  # 0-based
        idx0 = max(0, min(idx0, (self._ws_end - self._ws_start)))
        col = idx0 % cols
        row = idx0 // cols

        match direction:
            case "left":
                new_col = max(0, col - 1)
                new_row = row
            case "right":
                new_col = min(cols - 1, col + 1)
                new_row = row
            case "up":
                new_row = max(0, row - 1)
                new_col = col
            case "down":
                new_row = min(rows - 1, row + 1)
                new_col = col
            case _:
                new_col, new_row = col, row

        target_idx0 = new_row * cols + new_col
        max_idx0 = (self._ws_end - self._ws_start)
        if target_idx0 > max_idx0:
            target_idx0 = max_idx0
        target_ws = self._ws_start + target_idx0

        self._focus_any_in_workspace(target_ws)

    def _focus_any_in_workspace(self, ws: int):
        if not self._mini:
            return
        # Prefer placeholder (addr None) when available
        try:
            idx = next(i for i, m in enumerate(self._mini) if m.get("ws") == ws and m.get("addr") is None)
            self._set_focus(idx)
            return
        except StopIteration:
            pass
        # Fallback to any window in that workspace
        try:
            idx = next(i for i, m in enumerate(self._mini) if m.get("ws") == ws)
            self._set_focus(idx)
        except StopIteration:
            # No item in that workspace, keep current focus
            return

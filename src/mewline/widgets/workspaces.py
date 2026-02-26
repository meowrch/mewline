import contextlib
import subprocess
import threading

from fabric.hyprland.widgets import WorkspaceButton
from fabric.hyprland.widgets import Workspaces as HyprlandWorkspaces
from fabric.widgets.box import Box
from fabric.widgets.eventbox import EventBox
from gi.repository import Gdk
from gi.repository import GLib

from mewline.config import cfg
from mewline.shared.widget_container import BoxWidget
from mewline.shared.widget_container import ButtonWidget
from mewline.utils.misc import unique_list
from mewline.utils.window_manager import WindowManager
from mewline.utils.window_manager import detect_window_manager

# ──────────────────────────────────────────────
# HYPRLAND
# ──────────────────────────────────────────────

class HyprlandWorkSpacesWidget(BoxWidget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.config = cfg.modules.workspaces

        self.workspace = HyprlandWorkspaces(
            name="workspaces",
            buttons_factory=self._buttons_factory,
            spacing=4,
            invert_scroll=self.config.reverse_scroll,
            empty_scroll=self.config.empty_scroll,
        )
        self.add(self.workspace)

    def _buttons_factory(self, workspace_id: int) -> WorkspaceButton:
        label = self.config.icon_map.get(str(workspace_id), str(workspace_id))
        btn = WorkspaceButton(id=workspace_id, label=label)

        btn.connect("notify::empty", self._on_btn_state_changed)
        btn.connect("notify::active", self._on_btn_state_changed)

        GLib.idle_add(lambda b=btn: self._update_visibility(b))
        return btn

    def _on_btn_state_changed(self, btn: WorkspaceButton, _param):
        self._update_visibility(btn)

    def _update_visibility(self, btn: WorkspaceButton):
        ignored = unique_list(self.config.ignored)
        if btn.id in ignored or btn.id == -99:
            btn.set_visible(False)
            return

        if self.config.hide_unoccupied:
            btn.set_visible(btn.active or not btn.empty)
        else:
            btn.set_visible(True)


# ──────────────────────────────────────────────
# BSPWM
# ──────────────────────────────────────────────


class BspwmWorkspaceButton(ButtonWidget):
    def __init__(self, workspace_id: int):
        self.workspace_id = workspace_id
        self._active = False
        self._occupied = False

        label = cfg.modules.workspaces.icon_map.get(
            str(workspace_id), str(workspace_id)
        )
        super().__init__(
            label=label,
            name="workspace-button",
            visible=False,
        )
        self.connect("clicked", self._on_clicked)
        self._sync_classes()

    def _on_clicked(self, _):
        subprocess.run(["bspc", "desktop", "-f", str(self.workspace_id)])

    def update_state(self, active: bool, occupied: bool):
        self._active = active
        self._occupied = occupied
        self._sync_classes()

        ignored = unique_list(cfg.modules.workspaces.ignored)
        if self.workspace_id in ignored:
            self.set_visible(False)
            return

        if cfg.modules.workspaces.hide_unoccupied:
            self.set_visible(active or occupied)
        else:
            self.set_visible(True)

    def _sync_classes(self):
        ctx = self.get_style_context()
        for cls in ("active", "occupied", "urgent", "empty"):
            ctx.remove_class(cls)
        if self._active:
            ctx.add_class("active")
        elif self._occupied:
            ctx.add_class("occupied")
        else:
            ctx.add_class("empty")


class BspwmWorkSpacesWidget(BoxWidget):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.config = cfg.modules.workspaces

        self.event_box = EventBox(events="scroll")
        self.add(self.event_box)

        self.workspace_container = Box(name="workspaces", spacing=4)
        self.event_box.add(self.workspace_container)

        self.event_box.connect("scroll-event", self._on_scroll)

        self._buttons: dict[int, BspwmWorkspaceButton] = {}

        GLib.idle_add(self._full_refresh)
        thread = threading.Thread(target=self._subscribe_events, daemon=True)
        thread.start()

    def _on_scroll(self, _, event: Gdk.EventScroll):
        # Логика направления (UP -> next, DOWN -> prev, если не инвертировано)
        is_next = event.direction == Gdk.ScrollDirection.UP
        if self.config.reverse_scroll:
            is_next = not is_next

        target = "next" if is_next else "prev"

        # Учет empty_scroll: если False, ищем только занятые (.occupied)
        selector = f"{target}.local"
        if not self.config.empty_scroll:
            selector += ".occupied"

        subprocess.run(["bspc", "desktop", "-f", selector])

    def _subscribe_events(self):
        try:
            proc = subprocess.Popen(
                [
                    "bspc",
                    "subscribe",
                    "desktop_focus",
                    "node_add",
                    "node_remove",
                    "node_transfer",
                    "desktop_add",
                    "desktop_remove",
                ],
                stdout=subprocess.PIPE,
                text=True,
            )
            for _ in proc.stdout:
                GLib.idle_add(self._full_refresh)
        except Exception:
            GLib.timeout_add(500, self._full_refresh)

    def _full_refresh(self):
        with contextlib.suppress(Exception):
            desktop_ids = self._query_desktops()
            focused_id = self._query_focused()
            occupied_ids = self._query_occupied(desktop_ids)

            for wid in desktop_ids:
                if wid not in self._buttons:
                    btn = BspwmWorkspaceButton(workspace_id=wid)
                    self._buttons[wid] = btn
                    self.workspace_container.add(btn)

            for wid in list(self._buttons):
                if wid not in desktop_ids:
                    self.workspace_container.remove(self._buttons.pop(wid))

            for wid, btn in self._buttons.items():
                btn.update_state(
                    active=(wid == focused_id), occupied=(wid in occupied_ids)
                )

    def _query_desktops(self) -> list[int]:
        r = subprocess.run(
            ["bspc", "query", "-D", "--names"], capture_output=True, text=True
        )
        return [int(n) for n in r.stdout.strip().split("\n") if n.strip().isdigit()]

    def _query_focused(self) -> int | None:
        r = subprocess.run(
            ["bspc", "query", "-D", "-d", "focused", "--names"],
            capture_output=True,
            text=True,
        )
        with contextlib.suppress(ValueError):
            return int(r.stdout.strip())
        return None

    def _query_occupied(self, desktop_ids: list[int]) -> set[int]:
        occupied = set()
        for wid in desktop_ids:
            r = subprocess.run(
                ["bspc", "query", "-N", "-d", str(wid), "-n", ".window"],
                capture_output=True,
                text=True,
            )
            if r.stdout.strip():
                occupied.add(wid)
        return occupied


def create_workspaces_widget(**kwargs):
    wm = detect_window_manager()
    if wm == WindowManager.BSPWM:
        return BspwmWorkSpacesWidget(**kwargs)
    return HyprlandWorkSpacesWidget(**kwargs)

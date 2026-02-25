from __future__ import annotations

import gi
from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.image import Image
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import GLib
from gi.repository import Gray
from gi.repository import Gtk

from mewline.config import cfg
from mewline.shared.popover import Popover
from mewline.shared.widget_container import ButtonWidget
from mewline.utils.widget_utils import text_icon

gi.require_version("Gray", "0.1")
gi.require_version("Gtk", "3.0")

MAX_COLUMNS = 4


class SystemTrayGrid(Box):
    """Popup menu that lays out tray items in a fixed-column grid."""

    def __init__(self, **kwargs):
        super().__init__(
            name="system-tray-popup",
            orientation="v",
            all_visible=True,
            **kwargs,
        )

        self.grid = Gtk.Grid(
            row_spacing=8,
            column_spacing=12,
            margin_top=6,
            margin_bottom=6,
            margin_start=12,
            margin_end=12,
            visible=True,
        )
        self.add(self.grid)

        self._row = 0
        self._col = 0

    def add_item(self, button: Button) -> None:
        self.grid.attach(button, self._col, self._row, 1, 1)
        button.show_all()
        self._col += 1
        if self._col >= MAX_COLUMNS:
            self._col = 0
            self._row += 1

    def remove_item(self, button: Button) -> None:
        self.grid.remove(button)
        children = self.grid.get_children()
        for child in children:
            self.grid.remove(child)
        self._row = 0
        self._col = 0
        for child in reversed(children):
            self.grid.attach(child, self._col, self._row, 1, 1)
            self._col += 1
            if self._col >= MAX_COLUMNS:
                self._col = 0
                self._row += 1

    def has_items(self) -> bool:
        return bool(self.grid.get_children())


class SystemTray(ButtonWidget):
    """System tray widget.

    The widget is a clickable capsule on the status bar.
    Items whose title matches an entry in `config.pinned` are shown
    directly on the bar; all remaining items land in a popup grid
    that opens when the chevron is clicked.
    """

    _shared_watcher: Gray.Watcher | None = None

    def __init__(self, **kwargs) -> None:
        super().__init__(name="system-tray", **kwargs)

        self.config = cfg.modules.system_tray

        if SystemTray._shared_watcher is None:
            SystemTray._shared_watcher = Gray.Watcher()
        self.watcher = SystemTray._shared_watcher

        # Pinned icons live here — always visible on the bar
        self.tray_box = Box(
            name="system-tray-pinned",
            orientation="h",
            spacing=8,
        )
        self.tray_box.set_no_show_all(True)
        self.tray_box.hide()

        # Chevron: shows open/closed state of the popup
        self.chevron = text_icon("", size="13px")
        self.chevron.add_style_class("chevron-icon")

        self.children = Box(
            orientation="h",
            spacing=12,
            halign="center",
            valign="center",
            children=[self.chevron, self.tray_box],
        )

        self.popup_menu = SystemTrayGrid()
        self.popup: Popover | None = None
        self._fake_open = False

        # identifier -> (button, is_pinned)
        self._item_buttons: dict[str, tuple[Button, bool]] = {}

        self.watcher.connect("item-added", self._on_item_added)
        self.connect("clicked", self._on_clicked)

        self.hide()

    # ------------------------------------------------------------------
    # Popup toggle
    # ------------------------------------------------------------------
    def _on_clicked(self, *_) -> None:
        has_items = self.popup_menu.has_items()

        # If empty, just toggle visual state (feedback)
        if not has_items:
            self._fake_open = not self._fake_open
            self._sync_chevron()
            # Reset after a short delay if it's a "fake" open
            if self._fake_open:
                GLib.timeout_add(800, self._reset_fake_open)
            return

        if self.popup is None:
            self.popup = Popover(
                content=self.popup_menu,
                point_to=self,
                gap=0,
            )
            self.popup.connect("popover-closed", lambda *_: self._sync_chevron())

        if self.popup.get_visible():
            self.popup.close()
        else:
            self.popup.open()

        self._sync_chevron()

    def _reset_fake_open(self) -> bool:
        if self._fake_open:
            self._fake_open = False
            self._sync_chevron()
        return False

    def _sync_chevron(self) -> None:
        # Check either real popover visibility or our fake toggle state
        is_open = (self.popup is not None and self.popup.get_visible()) or self._fake_open
        
        self.chevron.set_label("" if is_open else "")
        if is_open:
            self.add_style_class("active")
        else:
            self.remove_style_class("active")

    # ------------------------------------------------------------------
    # Item lifecycle
    # ------------------------------------------------------------------
    def _on_item_added(self, _, identifier: str) -> None:
        item = self.watcher.get_item_for_identifier(identifier)
        
        if item is None or str(item.get_property("title")) == "None":
            return

        title = item.get_property("title") or ""

        if any(t.lower() in title.lower() for t in self.config.ignore):
            return

        button = self._bake_button(item)

        is_pinned = any(t.lower() in title.lower() for t in self.config.pinned)
        self._item_buttons[identifier] = (button, is_pinned)

        if is_pinned:
            self.tray_box.pack_start(button, False, False, 0)
            button.show_all()
            self.tray_box.show()
        else:
            self.popup_menu.add_item(button)
            if self._fake_open:
                self._fake_open = False
                self._sync_chevron()

        self.show()
        self.chevron.show()

    def _on_item_removed(self, identifier: str) -> None:
        entry = self._item_buttons.pop(identifier, None)
        if entry is None:
            return

        button, is_pinned = entry
        if is_pinned:
            self.tray_box.remove(button)
            if not self.tray_box.get_children():
                self.tray_box.hide()
        else:
            self.popup_menu.remove_item(button)
        button.destroy()

        has_pinned = bool(self.tray_box.get_children())
        has_popup = self.popup_menu.has_items()
        if not has_pinned and not has_popup:
            if self.popup:
                self.popup.close()
            self.hide()

    # ------------------------------------------------------------------
    # Button factory
    # ------------------------------------------------------------------
    def _bake_button(self, item: Gray.Item) -> Button:
        button = Button()
        button.add_style_class("tray-item-btn")
        button.set_tooltip_text(item.get_property("title") or "")
        button.connect(
            "button-press-event",
            lambda btn, ev: self._on_icon_click(btn, item, ev),
        )
        self._update_button_icon(item, button)
        return button

    def _update_button_icon(self, item: Gray.Item, button: Button) -> None:
        size = self.config.icon_size
        theme = Gtk.IconTheme.get_default()

        icon_name = item.get_icon_name() or ""
        if icon_name:
            for candidate in (
                f"{icon_name}-symbolic" if not icon_name.endswith("-symbolic") else None,
                icon_name,
            ):
                if candidate and theme.has_icon(candidate):
                    button.set_image(Image(icon_name=candidate, icon_size=size))
                    return

        pixmap = Gray.get_pixmap_for_pixmaps(item.get_icon_pixmaps(), size)
        if pixmap is not None:
            try:
                pixbuf = pixmap.as_pixbuf(size, GdkPixbuf.InterpType.HYPER)
                button.set_image(Image(pixbuf=pixbuf, pixel_size=size))
                return
            except GLib.GError:
                pass

        if icon_name:
            try:
                pixbuf = theme.load_icon(icon_name, size, Gtk.IconLookupFlags.FORCE_SIZE)
                button.set_image(Image(pixbuf=pixbuf, pixel_size=size))
                return
            except GLib.GError:
                pass

        try:
            pixbuf = theme.load_icon("image-missing", size, Gtk.IconLookupFlags.FORCE_SIZE)
            button.set_image(Image(pixbuf=pixbuf, pixel_size=size))
        except GLib.GError:
            pass

    def _on_icon_click(self, button: Button, item: Gray.Item, event) -> None:
        if event.button not in (1, 3):
            return
        button.unset_state_flags(Gtk.StateFlags.PRELIGHT)
        menu = item.get_property("menu")
        if menu:
            menu.set_name("system-tray-menu")
            menu.connect(
                "hide",
                lambda *_: button.unset_state_flags(Gtk.StateFlags.PRELIGHT),
            )
            menu.popup_at_widget(
                button,
                Gdk.Gravity.SOUTH,
                Gdk.Gravity.NORTH,
                event,
            )
        else:
            item.context_menu(event.x, event.y)

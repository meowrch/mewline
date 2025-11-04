import gi
from fabric.widgets.button import Button
from fabric.widgets.image import Image
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import GLib
from gi.repository import Gray
from gi.repository import Gtk

from mewline.config import cfg
from mewline.shared.widget_container import BoxWidget

gi.require_version("Gray", "0.1")
gi.require_version("Gtk", "3.0")


class SystemTray(BoxWidget):
    """A widget to display the system tray items."""

    def __init__(self, **kwargs) -> None:
        super().__init__(name="system-tray", **kwargs)

        self.config = cfg.modules.system_tray
        self.watcher = Gray.Watcher()
        self.watcher.connect("item-added", self.on_item_added)
        self.count_items = 0
        self.hide()

    def on_item_added(self, _, identifier: str):
        item = self.watcher.get_item_for_identifier(identifier)

        if (
            self.config.ignore
            and item.get_property("title") in self.config.ignore
        ):
            return

        if not item.get_property("title"):
            return

        item_button = self.do_bake_item_button(item)
        item.connect(
            "removed", lambda *_: self.destroy_btn(item_button)
        )
        item.connect(
            "icon-changed",
            lambda icon_item: self.do_update_item_button(
                icon_item, item_button
            ),
        )
        item_button.show_all()
        self.add(item_button)

        # Show the tray if it was hidden before
        if self.count_items < 1:
            self.show()

        self.count_items += 1

    def destroy_btn(self, btn: Button):
        btn.destroy()
        self.count_items -= 1

        # Hide the tray if no items are left
        if self.count_items == 0:
            self.hide()

    def do_bake_item_button(self, item: Gray.Item) -> Button:
        button = Button()
        # context menu handler
        button.connect(
            "button-press-event",
            lambda button, event: self.on_button_click(
                button, item, event
            ),
        )
        button.set_tooltip_text(item.get_property("title"))

        self.do_update_item_button(item, button)

        return button

    def do_update_item_button(
        self, item: Gray.Item, item_button: Button
    ):
        pixmap = Gray.get_pixmap_for_pixmaps(
            item.get_icon_pixmaps(), 24
        )

        icon = item.get_icon_name() or "image-missing"

        # Prefer a symbolic variant if available to allow CSS recoloring
        theme = Gtk.IconTheme.get_default()
        symbolic_icon = None
        if icon:
            if icon.endswith("-symbolic"):
                symbolic_icon = icon
            elif theme.has_icon(f"{icon}-symbolic"):
                symbolic_icon = f"{icon}-symbolic"

        # If we have a symbolic icon name, render by name so GTK can tint it via CSS
        if symbolic_icon is not None:
            item_button.set_image(
                Image(icon_name=symbolic_icon, icon_size=self.config.icon_size)
            )
            return

        # Fallback: render provided pixmap or load by name as pixbuf, then tint it
        try:
            pixbuf: GdkPixbuf.Pixbuf = (
                pixmap.as_pixbuf(
                    self.config.icon_size,
                    GdkPixbuf.InterpType.HYPER,
                )
                if pixmap is not None
                else theme.load_icon(
                    icon,
                    self.config.icon_size,
                    Gtk.IconLookupFlags.FORCE_SIZE,
                )
            )
        except GLib.GError:
            pixbuf = theme.load_icon(
                "image-missing",
                self.config.icon_size,
                Gtk.IconLookupFlags.FORCE_SIZE,
            )

        item_button.set_image(
            Image(pixbuf=pixbuf, pixel_size=self.config.icon_size)
        )

    def on_button_click(self, button, item: Gray.Item, event):
        match event.button:
            case 1 | 3:
                menu = item.get_property("menu")
                menu.set_name("system-tray-menu")
                if menu:
                    menu.popup_at_widget(
                        button,
                        Gdk.Gravity.SOUTH,
                        Gdk.Gravity.NORTH,
                        event,
                    )
                else:
                    item.context_menu(event.x, event.y)

import subprocess
from typing import TYPE_CHECKING

from fabric.utils import idle_add
from fabric.utils import remove_handler
from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.entry import Entry
from fabric.widgets.image import Image
from fabric.widgets.label import Label
from fabric.widgets.scrolledwindow import ScrolledWindow
from gi.repository import Gdk
from gi.repository import GdkPixbuf
from gi.repository import GLib
from loguru import logger

from mewline import constants as cnst
from mewline.utils.misc import check_icon_exists
from mewline.utils.misc import copy_image
from mewline.utils.misc import copy_text
from mewline.widgets.dynamic_island.base import BaseDiWidget

if TYPE_CHECKING:
    from mewline.widgets.dynamic_island import DynamicIsland


class Clipboard(BaseDiWidget, Box):
    focuse_kb = True

    def __init__(self, dynamic_island: "DynamicIsland") -> None:
        Box.__init__(self, name="clipboard")

        self.di = dynamic_island
        self.selected_index = -1
        self._arranger_handler: int = 0
        self.history: list[dict] = []
        self.cache_dir = cnst.CLIPBOARD_THUMBS_DIR
        self.cache_dir.mkdir(exist_ok=True)

        self.viewport = Box(orientation="v", spacing=10)
        self.scrolled_window = ScrolledWindow(
            name="clipboard-scrolled-window",
            min_content_size=(450, 200),
            max_content_size=(450, 600),
            child=self.viewport,
        )

        self.search_entry = Entry(
            name="clipboard-search-entry",
            placeholder="Search Clipboard History...",
            h_expand=True,
            notify_text=lambda e, *_: self.arrange_viewport(e.get_text()),
            on_activate=self.on_entry_activate,
            on_key_press_event=self.on_key_press,
        )
        self.search_entry.props.xalign = 0.5

        self.header = Box(
            orientation="h",
            spacing=10,
            children=[
                self.search_entry,
                Button(
                    name="clipboard-close-button",
                    image=Image(
                        style_classes="clipboard-close-label",
                        icon_name=check_icon_exists(
                            "close-symbolic",
                            cnst.icons["ui"]["close"],
                        ),
                        icon_size=16,
                    ),
                    tooltip_text="Exit",
                    on_clicked=lambda *_: self.close(),
                ),
            ],
        )

        self.main_box = Box(
            orientation="v", spacing=8, children=[self.header, self.scrolled_window]
        )

        self.load_history()
        self.arrange_viewport()

        self.add(self.main_box)
        self.show_all()

    def close(self) -> None:
        self.di.close()

    def load_history(self) -> None:
        self.history.clear()
        try:
            output = subprocess.check_output(  # noqa: S603
                ["cliphist", "list"],  # noqa: S607
                text=True,
                stderr=subprocess.PIPE,
            )
            for line in output.splitlines():
                if "\t" not in line:
                    continue

                identifier, content = line.split("\t", 1)
                content = content.strip()

                entry = {
                    "type": "text",
                    "identifier": identifier,
                    "raw": line,
                    "content": content,
                }

                if "binary data" in content:
                    entry["type"] = "image"
                    entry["path"] = self.cache_image(line, identifier)

                self.history.append(entry)
        except Exception as e:
            print(f"Error loading history: {e}\n{e.stderr}")

    def cliphist_decode(self, raw: str) -> bytes | None:
        try:
            proc = subprocess.run(  # noqa: S603
                ["cliphist", "decode"],  # noqa: S607
                input=raw.encode(),
                capture_output=True,
                check=True,
            )
            return proc.stdout
        except Exception:
            return None

    def cache_image(self, raw_data: str, identifier: str) -> str | None:
        img_path = self.cache_dir / f"{identifier}.png"
        decoded = self.cliphist_decode(raw_data)

        if decoded:
            with open(img_path, "wb") as f:
                f.write(decoded)
        else:
            logger.error("Image cache error")
            return None

        return str(img_path)

    def arrange_viewport(self, query: str = "") -> None:
        remove_handler(self._arranger_handler) if self._arranger_handler else None
        self.viewport.children = []
        self.selected_index = -1

        filtered = [
            entry
            for entry in self.history
            if query.lower() in entry.get("content", "").lower()
        ]

        self._arranger_handler = idle_add(
            lambda: self.populate_items(filtered),
            pin=True,
        )

    def populate_items(self, items: list) -> None:
        for entry in items:
            widget = self.create_item_widget(entry)
            self.viewport.add(widget)
        self.viewport.show_all()
        if items:
            self.update_selection(0)

    def create_item_widget(self, entry: dict) -> Button:
        content = Box(orientation="h", spacing=8)
        if entry["type"] == "image" and entry.get("path"):
            try:
                pixbuf = GdkPixbuf.Pixbuf.new_from_file_at_scale(
                    entry["path"],
                    100,
                    100,
                    True,  # Сохранять пропорции
                )
                image = Image(pixbuf=pixbuf, name="clip-image")
                content.add(image)
            except Exception:
                content.add(Label(label="[Image]"))
        else:
            text = entry["content"]
            text = text[:40] + "..." if len(text) > 40 else text
            content.add(Label(label=text, wrap=True))
        return Button(
            child=content,
            on_clicked=lambda *_: self.select_item(entry),
            name="clipboard-item-button",
        )

    def select_item(self, entry: dict) -> None:
        try:
            if entry["type"] == "image":
                copy_image(entry["path"])
            else:
                decoded = self.cliphist_decode(entry["raw"])
                if decoded:
                    copy_text(decoded.decode())
                else:
                    raise
        except Exception:
            logger.error("Copy failed!")

        self.close()

    def update_selection(self, new_index: int) -> None:
        if self.selected_index != -1 and self.selected_index < len(
            self.viewport.get_children()
        ):
            current_button = self.viewport.get_children()[self.selected_index]
            current_button.get_style_context().remove_class("selected")

        if new_index != -1 and new_index < len(self.viewport.get_children()):
            new_button = self.viewport.get_children()[new_index]
            new_button.get_style_context().add_class("selected")
            self.selected_index = new_index
            self.scroll_to_selected(new_button)
        else:
            self.selected_index = -1

    def scroll_to_selected(self, button: Button) -> None:
        def scroll():
            adj = self.scrolled_window.get_vadjustment()
            alloc = button.get_allocation()
            if alloc.height == 0:
                return False

            y = alloc.y
            height = alloc.height
            page_size = adj.get_page_size()
            current_value = adj.get_value()

            if y < current_value:
                adj.set_value(y)
            elif y + height > current_value + page_size:
                adj.set_value(y + height - page_size)
            return False

        GLib.idle_add(scroll)

    def on_key_press(self, _, event) -> bool:
        keyval = event.keyval
        if keyval == Gdk.KEY_Down:
            self.move_selection(1)
            return True
        elif keyval == Gdk.KEY_Up:
            self.move_selection(-1)
            return True
        elif keyval == Gdk.KEY_Escape:
            self.close()
            return True
        return False

    def move_selection(self, delta: int) -> None:
        children = self.viewport.get_children()
        if not children:
            return

        new_index = self.selected_index + delta
        if self.selected_index == -1 and delta == 1:
            new_index = 0
        else:
            new_index = max(0, min(new_index, len(children) - 1))

        self.update_selection(new_index)

    def on_entry_activate(self, *_) -> None:
        children = self.viewport.get_children()
        if not children:
            return
        if self.selected_index == -1:
            return

        selected_button = children[self.selected_index]
        selected_button.clicked()

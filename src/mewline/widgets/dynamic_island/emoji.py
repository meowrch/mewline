from typing import TYPE_CHECKING

from emoji.unicode_codes import EMOJI_DATA
from fabric.utils import remove_handler
from fabric.widgets.box import Box
from fabric.widgets.button import Button
from fabric.widgets.entry import Entry
from fabric.widgets.label import Label
from fabric.widgets.stack import Stack
from gi.repository import Gdk
from gi.repository import Gtk

from mewline.widgets.dynamic_island.base import BaseDiWidget

if TYPE_CHECKING:
    from mewline.widgets.dynamic_island import DynamicIsland


class EmojiPicker(BaseDiWidget, Box):
    focuse_kb: bool = True

    def __init__(self, di: "DynamicIsland") -> None:
        Box.__init__(
            self,
            name="emoji",
            visible=False,
            all_visible=False,
        )

        self.di = di
        self.selected_index = -1
        self.emojis_per_page = 9 * 3
        self.current_page_index = 0
        self.filtered_emojis = []
        self.total_pages = 0

        self._arranger_handler: int = 0
        self._all_emojis = self._load_emoji_data()

        self.stack = Stack(
            name="viewport",
            spacing=4,
            orientation="v",
            transition_type="slide-up-down",
            transition_duration=200,
        )
        self.search_entry = Entry(
            name="search-entry",
            placeholder="Search Emojis...",
            h_expand=True,
            notify_text=lambda entry, *_: self.arrange_viewport(entry.get_text()),
            on_activate=lambda entry, *_: self.on_search_entry_activate(
                entry.get_text()
            ),
            on_key_press_event=self.on_search_entry_key_press,
        )
        self.search_entry.props.xalign = 0.5
        self.header_box = Box(
            name="header_box",
            spacing=10,
            orientation="h",
            children=[
                self.search_entry,
            ],
        )

        self.picker_box = Box(
            name="picker-box",
            spacing=10,
            h_expand=True,
            orientation="v",
            children=[
                self.header_box,
                self.stack,
            ],
        )

        self.resize_viewport()

        self.add(self.picker_box)
        self.show_all()

    def _load_emoji_data(self):
        return EMOJI_DATA

    def close_picker(self):
        self.stack.children = []
        self.selected_index = -1
        self.di.close()

    def open_picker(self):
        self.search_entry.set_text("")
        self.current_page_index = 0
        self.arrange_viewport()
        self.search_entry.grab_focus()

    def arrange_viewport(self, query: str = ""):
        remove_handler(self._arranger_handler) if self._arranger_handler else None
        self.stack.children = []
        self.selected_index = -1
        self.current_page_index = 0

        query_terms = query.casefold().split()

        self.filtered_emojis = [
            (emoji_char, emoji_info)
            for emoji_char, emoji_info in self._all_emojis.items()
            if all(
                term
                in (
                    emoji_info.get("en", "")
                    + " "  # Основное название
                    + " ".join(emoji_info.get("alias", []))
                    + " "  # Алиасы
                    + " ".join(emoji_info.get("tags", []))
                    + " "  # Теги/ключевые слова
                    + emoji_info.get("category", "")  # Группа/категория
                ).casefold()
                for term in query_terms
            )
        ]

        self.total_pages = (
            (len(self.filtered_emojis) + self.emojis_per_page - 1)
            // self.emojis_per_page
            if self.filtered_emojis
            else 0
        )

        self.load_page(self.current_page_index)

        should_resize = not query

        if should_resize:
            self.resize_viewport()
        if query.strip() != "" and self.get_all_emoji_buttons():
            self.update_selection(0)

    def load_page(self, page_index):
        for child in self.stack.get_children():
            child.destroy()  # Уничтожаем виджеты

        self.update_selection(-1)
        page_box = Box(name=f"page-box-{page_index}", orientation="v", spacing=4)
        start_index = page_index * self.emojis_per_page
        end_index = min(
            (page_index + 1) * self.emojis_per_page, len(self.filtered_emojis)
        )
        page_emojis = self.filtered_emojis[start_index:end_index]

        grid_box = Box(name="emoji-grid-box", orientation="v", spacing=2)

        row_box = None
        for i, (emoji_char, emoji_info) in enumerate(page_emojis):
            if i % 9 == 0:
                row_box = Box(name="emoji-row-box", orientation="h", spacing=2)
                grid_box.add(row_box)
            if row_box is not None:
                row_box.add(self.bake_emoji_slot(emoji_char, emoji_info))
        page_box.add(grid_box)
        self.stack.add_named(page_box, f"page-{page_index}")
        self.stack.set_visible_child_name(f"page-{page_index}")
        page_box.show_all()

        buttons = self.get_all_emoji_buttons()
        if buttons and self.selected_index != -1:
            page_relative_index = self.selected_index % self.emojis_per_page
            if page_relative_index < len(buttons):
                self.update_selection(page_relative_index)
            else:
                self.update_selection(len(buttons) - 1)

    def resize_viewport(self):
        return False

    def bake_emoji_slot(self, emoji_char: str, emoji_info: dict, **kwargs) -> Button:
        button = Button(
            name="emoji-slot-button",
            child=Box(
                name="emoji-slot-box",
                orientation="horizontal",
                halign="center",
                valign="center",
                children=[
                    Label(
                        name="emoji-char-label",
                        label=emoji_char,
                        use_markup=True,
                        v_align="center",
                        h_align="center",
                        css_name="emoji-char-label",
                    ),
                ],
            ),
            tooltip_text=emoji_info.get("name", "Unknown"),
            on_clicked=lambda *_: (
                self.copy_emoji_to_clipboard(emoji_char),
                self.close_picker(),
            ),
            **kwargs,
        )
        return button

    def update_selection(self, new_index: int):
        buttons = self.get_all_emoji_buttons()
        if not buttons:
            self.selected_index = -1
            return

        if self.selected_index != -1 and self.selected_index < len(buttons):
            current_button = buttons[self.selected_index]
            current_button.get_style_context().remove_class("selected")
            if not buttons or current_button not in buttons:
                self.selected_index = -1

        if 0 <= new_index < len(buttons):
            new_button = buttons[new_index]
            new_button.get_style_context().add_class("selected")
            self.selected_index = new_index
        else:
            self.selected_index = -1

    def get_all_emoji_buttons(self):
        buttons = []
        current_page = self.stack.get_visible_child()
        if current_page and current_page.get_children():  # noqa: SIM102
            if current_page.get_children()[0].get_children():
                for row_box in current_page.get_children()[0].get_children():
                    buttons.extend(row_box.get_children())
        return buttons

    def on_search_entry_activate(self, text):
        buttons = self.get_all_emoji_buttons()
        if buttons:
            if self.selected_index != -1:
                buttons[self.selected_index].clicked()
            elif buttons and text.strip() != "":
                buttons[0].clicked()

    def on_search_entry_key_press(self, widget, event):
        if event.keyval in (Gdk.KEY_Up, Gdk.KEY_Down, Gdk.KEY_Left, Gdk.KEY_Right):
            self.move_selection_2d(event.keyval)
            return True
        elif event.keyval == Gdk.KEY_Escape:
            self.close_picker()
            return True
        return False

    def move_selection_2d(self, keyval):
        buttons = self.get_all_emoji_buttons()
        total_items_current_page = len(buttons)
        if total_items_current_page == 0:
            return

        rows = 3
        columns = 9

        if self.selected_index == -1:
            if keyval in (Gdk.KEY_Down, Gdk.KEY_Right):
                new_index = 0
            elif keyval in (Gdk.KEY_Up, Gdk.KEY_Left):
                new_index = total_items_current_page - 1
            else:
                return
        else:
            current_index_page = self.selected_index
            row = current_index_page // columns
            col = current_index_page % columns

            if keyval == Gdk.KEY_Right:
                new_col = (col + 1) % columns
                new_row = row
                if new_col == 0:
                    new_row = row + 1
            elif keyval == Gdk.KEY_Left:
                new_col = (col - 1) % columns
                new_row = row
                if new_col == (columns - 1):
                    new_row = row - 1
            elif keyval == Gdk.KEY_Down:
                new_row = row + 1
                new_col = col
            elif keyval == Gdk.KEY_Up:
                new_row = row - 1
                new_col = col
            else:
                return

            if new_row >= rows:
                if self.current_page_index < self.total_pages - 1:
                    current_col = col  # Keep track of current column
                    self.current_page_index += 1
                    self.load_page(self.current_page_index)
                    new_index = current_col  # Try to keep the same column
                    if (
                        new_index >= total_items_current_page
                    ):  # if column is out of bound, select last
                        new_index = total_items_current_page - 1
                    self.selected_index = -1
                    self.update_selection(new_index)
                    return
                else:
                    new_index = total_items_current_page - 1
            elif new_row < 0:
                if self.current_page_index > 0:
                    current_col = col  # Keep track of current column
                    self.current_page_index -= 1
                    self.load_page(self.current_page_index)
                    new_index = (
                        rows - 1
                    ) * columns + current_col  # Select last row, same column
                    if (
                        new_index >= total_items_current_page
                    ):  # if column is out of bound, select last
                        new_index = total_items_current_page - 1
                    self.selected_index = -1
                    self.update_selection(new_index)
                    return
                else:
                    new_index = 0
            else:
                new_index = new_row * columns + new_col
                if new_index >= total_items_current_page:
                    new_index = total_items_current_page - 1

        if new_index < 0:
            new_index = 0
        elif new_index >= total_items_current_page:
            new_index = total_items_current_page - 1

        self.update_selection(new_index)

    def copy_emoji_to_clipboard(self, emoji_char: str):
        clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        clipboard.set_text(emoji_char, -1)
        clipboard.store()

from fabric import Application
from fabric.widgets.box import Box
from fabric.widgets.centerbox import CenterBox
from fabric.widgets.stack import Stack
from fabric.widgets.wayland import WaylandWindow as Window
from gi.repository import GLib

from mewline.widgets.dynamic_island.app_launcher import AppLauncher
from mewline.widgets.dynamic_island.base import BaseDiWidget
from mewline.widgets.dynamic_island.bluetooth import BluetoothConnections
from mewline.widgets.dynamic_island.clipboard import Clipboard
from mewline.widgets.dynamic_island.compact import Compact
from mewline.widgets.dynamic_island.date_notification import DateNotificationMenu
from mewline.widgets.dynamic_island.emoji import EmojiPicker
from mewline.widgets.dynamic_island.network import NetworkConnections
from mewline.widgets.dynamic_island.notifications import NotificationContainer
from mewline.widgets.dynamic_island.pawlette_themes import PawletteThemes
from mewline.widgets.dynamic_island.power import PowerMenu
from mewline.widgets.dynamic_island.wallpapers import WallpaperSelector
from mewline.widgets.screen_corners import MyCorner


class DynamicIsland(Window):
    """A dynamic island window for the status bar."""

    def __init__(self):
        super().__init__(
            name="dynamic_island",
            layer="top",
            anchor="top",
            margin="-41px 10px 10px 41px",
            keyboard_mode="none",
            exclusivity="normal",
            visible=False,
            all_visible=False,
        )

        self.hidden = False

        ##==> Defining the widgets
        #########################################
        self.compact = Compact(self)
        self.notification = NotificationContainer(self)
        self.date_notification = DateNotificationMenu()
        self.power_menu = PowerMenu(self)
        self.bluetooth = BluetoothConnections()
        self.app_launcher = AppLauncher(self)
        self.wallpapers = WallpaperSelector()
        self.emoji = EmojiPicker(self)
        self.clipboard = Clipboard(self)
        self.network = NetworkConnections()
        self.pawlette_themes = PawletteThemes()

        self.widgets: dict[str, type[BaseDiWidget]] = {
            "compact": self.compact,
            "notification": self.notification,
            "date-notification": self.date_notification,
            "power-menu": self.power_menu,
            "bluetooth": self.bluetooth,
            "app-launcher": self.app_launcher,
            "wallpapers": self.wallpapers,
            "emoji": self.emoji,
            "clipboard": self.clipboard,
            "network": self.network,
            "pawlette-themes": self.pawlette_themes,
        }
        self.current_widget: str | None = None

        self.stack = Stack(
            name="dynamic-island-content",
            v_expand=True,
            h_expand=True,
            transition_type="none",
            transition_duration=0,
            children=[*self.widgets.values()],
        )

        # Система защиты анимаций
        self.is_animating = False
        self.pending_operation = None

        ##==> Customizing the hotkeys
        ########################################################
        Application.action("dynamic-island-open")(self.open)
        Application.action("dynamic-island-close")(self.close)
        self.add_keybinding("Escape", lambda *_: self.close())

        self.di_box = CenterBox(
            name="dynamic-island-box",
            orientation="h",
            h_align="center",
            v_align="center",
            start_children=Box(
                children=[
                    Box(
                        name="dynamic-island-corner-left",
                        orientation="v",
                        children=[
                            MyCorner("top-right"),
                            Box(),
                        ],
                    )
                ]
            ),
            center_children=self.stack,
            end_children=Box(
                children=[
                    Box(
                        name="dynamic-island-corner-right",
                        orientation="v",
                        children=[
                            MyCorner("top-left"),
                            Box(),
                        ],
                    )
                ]
            ),
        )

        ##==> Show the dynamic island
        ######################################
        self.add(self.di_box)
        self.show()

    def call_module_method_if_exists(
        self, module: BaseDiWidget, method_name: str, **kwargs
    ) -> bool:
        if hasattr(module, method_name) and callable(getattr(module, method_name)):
            method = getattr(module, method_name)
            method(**kwargs)
            return True
        return False

    def safe_operation(self, operation, *args):
        """Выполняет операции с защитой от конфликтов анимации."""
        if self.is_animating:
            # Если уже идет анимация, запоминаем последнюю запрошенную операцию
            self.pending_operation = (operation, args)
            return

        self.is_animating = True
        operation(*args)

    def reset_animation(self):
        """Сбрасывает флаг анимации и выполняет отложенные операции."""
        self.is_animating = False

        if self.pending_operation:
            op, args = self.pending_operation
            self.pending_operation = None
            self.safe_operation(op, *args)

        return False

    def close(self):
        """Закрывает активный виджет и возвращается к компактному режиму."""
        self.safe_operation(self._perform_close)

    def _perform_close(self):
        """Фактическая логика закрытия."""
        # Если нет активного виджета, просто показываем компактный вид
        if self.current_widget is None:
            self.stack.set_visible_child(self.compact)
            # Сбрасываем анимацию сразу
            GLib.timeout_add(self.stack.get_transition_duration(), self.reset_animation)
            return

        # Сбрасываем фокус клавиатуры
        self.set_keyboard_mode("none")

        # Вызываем метод закрытия виджета
        widget = self.widgets[self.current_widget]
        self.call_module_method_if_exists(widget, "close_widget_from_di")

        # Убираем стили
        widget.remove_style_class("open")
        self.stack.remove_style_class(self.current_widget)

        # Переключаем на компактный вид
        self.stack.set_visible_child(self.compact)

        # Сбрасываем текущий виджет
        self.current_widget = None

        # Обновляем скрытое состояние
        if self.hidden:
            self.di_box.remove_style_class("hideshow")
            self.di_box.add_style_class("hidden")

        # Сбрасываем флаг анимации после завершения перехода
        GLib.timeout_add(self.stack.get_transition_duration(), self.reset_animation)

    def open(self, widget: str = "date-notification") -> None:
        """Открывает указанный виджет в Dynamic Island."""
        self.safe_operation(self._perform_open, widget)

    def _perform_open(self, widget: str):
        """Фактическая логика открытия."""
        if widget == "compact":
            self._perform_close()
            return

        if widget not in self.widgets:
            widget = "date-notification"

        if self.current_widget == widget:
            # Сбрасываем анимацию сразу
            GLib.timeout_add(self.stack.get_transition_duration(), self.reset_animation)
            return

        # Убираем скрытое состояние
        if self.hidden:
            self.di_box.remove_style_class("hidden")
            self.di_box.add_style_class("hideshow")

        # Сбрасываем стили предыдущего виджета
        if self.current_widget is not None:
            prev_widget = self.widgets[self.current_widget]
            prev_widget.remove_style_class("open")
            self.stack.remove_style_class(self.current_widget)

        # Устанавливаем новый виджет
        self.current_widget = widget
        new_widget = self.widgets[widget]

        # Применяем стили
        self.stack.add_style_class(widget)
        new_widget.add_style_class("open")

        # Показываем виджет
        self.stack.set_visible_child(new_widget)

        # Управление фокусом клавиатуры
        if hasattr(new_widget, "focuse_kb") and new_widget.focuse_kb:
            self.set_keyboard_mode("exclusive")
        else:
            self.set_keyboard_mode("none")

        # Вызываем метод открытия виджета
        self.call_module_method_if_exists(new_widget, "open_widget_from_di")

        # Сбрасываем флаг анимации после завершения перехода
        GLib.timeout_add(self.stack.get_transition_duration(), self.reset_animation)

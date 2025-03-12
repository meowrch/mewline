from fabric.widgets.box import Box
from fabric.widgets.image import Image
from fabric.widgets.label import Label
from fabric.widgets.revealer import Revealer
from gi.repository import GLib

from mewline.config import cfg
from mewline.services import battery_service
from mewline.shared.widget_container import ButtonWidget
from mewline.utils.misc import format_time


class Battery(ButtonWidget):
    """A widget to display the current battery status."""

    def __init__(self):
        # Initialize the Box with specific name and style
        super().__init__(name="battery")

        self.client = battery_service
        self.client.connect("changed", lambda *_: self.update_ui())
        self.config = cfg.modules.battery
        self.full_battery_level = 100

        # for revealer
        self.hide_timer = None
        self.hover_counter = 0

        self.icon = Image(
            icon_name=self.client.get_property("IconName"),
            icon_size=14,
        )

        is_present = self.client.get_property("IsPresent")
        battery_percent = (
            round(self.client.get_property("Percentage")) if is_present else 0
        )
        self.label = Label(label=f"{battery_percent}%", style_classes="panel-text")
        self.revealer = Revealer(
            name="battery-label-revealer",
            transition_duration=250,
            transition_type="slide-left",
            child=self.label,
            child_revealed=False,
        )

        self.box = Box(children=[self.icon, self.revealer])
        self.connect("enter-notify-event", self.on_mouse_enter)
        self.connect("leave-notify-event", self.on_mouse_leave)
        self.add(self.box)
        self.update_ui()

    def on_mouse_enter(self, *_):
        self.hover_counter += 1
        if self.hide_timer:
            GLib.source_remove(self.hide_timer)
            self.hide_timer = None
        self.revealer.set_reveal_child(True)
        return False

    def on_mouse_leave(self, *_):
        self.hover_counter = max(0, self.hover_counter - 1)
        if self.hover_counter == 0:
            if self.hide_timer:
                GLib.source_remove(self.hide_timer)
            self.hide_timer = GLib.timeout_add(
                500, lambda: self.revealer.set_reveal_child(False)
            )
        return False

    def update_ui(self):
        """Update the battery status."""
        is_present = self.client.get_property("IsPresent")
        battery_percent = (
            round(self.client.get_property("Percentage")) if is_present else 0
        )
        self.label.set_text(f"{battery_percent}%")
        self.icon.set_from_icon_name(
            icon_name=self.client.get_property("IconName"), icon_size=14
        )

        if self.config.tooltip:
            battery_state = self.client.get_property("State")
            is_charging = battery_state == 1 if is_present else False
            temperature = self.client.get_property("Temperature")
            capacity = self.client.get_property("Capacity")
            time_remaining = (
                self.client.get_property("TimeToFull")
                if is_charging
                else self.client.get_property("TimeToEmpty")
            )

            tool_tip_text = f"󱐋 Capacity : {capacity}\n Temperature: {temperature}°C"
            if battery_percent == self.full_battery_level:
                self.set_tooltip_text(f"Full\n{tool_tip_text}")
            elif is_charging and battery_percent < self.full_battery_level:
                self.set_tooltip_text(
                    f"󰄉 Time to full: {format_time(time_remaining)}\n{tool_tip_text}"
                )
            else:
                self.set_tooltip_text(
                    f"󰄉 Time to empty: {format_time(time_remaining)}\n{tool_tip_text}"
                )

        return True

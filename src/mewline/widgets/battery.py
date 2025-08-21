from fabric.widgets.box import Box
from fabric.widgets.image import Image
from fabric.widgets.label import Label
from fabric.widgets.revealer import Revealer
from gi.repository import Gdk
from gi.repository import GLib
from gi.repository import Gtk

from mewline.config import cfg
from mewline.services import battery_service
from mewline.services.battery import PowerProfiles
from mewline.shared.widget_container import ButtonWidget
from mewline.utils.misc import format_time
from mewline.utils.widget_utils import text_icon


class Battery(ButtonWidget):
    """A widget to display the current battery status."""

    def __init__(self):
        # Initialize the Box with specific name and style
        super().__init__(name="battery")

        self.client = battery_service
        self.power_profiles_client = PowerProfiles()
        self.client.connect("changed", lambda *_: self.update_ui())
        self.config = cfg.modules.battery
        self.full_battery_level = 100

        # for revealer
        self.hide_timer = None
        self.hover_counter = 0

        is_present = self.client.get_property("IsPresent")

        self.icon = (
            text_icon(icon="󰐧", size="18px")
            if not is_present
            else Image(
                icon_name=self.client.get_property("IconName"),
                icon_size=14,
            )
        )
        battery_percent = (
            round(self.client.get_property("Percentage")) if is_present else 0
        )
        self.label = Label(
            label="AC" if not is_present else f"{battery_percent}%",
            style_classes="panel-text",
        )

        self.revealer = Revealer(
            name="battery-label-revealer",
            transition_duration=250,
            transition_type="slide-left",
            child=self.label,
            child_revealed=self.config.show_label,  # Use the new config option
        )

        self.box = Box(children=[self.icon, self.revealer])

        # Conditionally connect hover events
        if not self.config.show_label:
            self.connect("enter-notify-event", self.on_mouse_enter)
            self.connect("leave-notify-event", self.on_mouse_leave)

        self.connect("clicked", self.show_power_profiles_menu)
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
        if is_present:
            battery_percent = round(self.client.get_property("Percentage"))
            self.label.set_text(f"{battery_percent}%")
        else:
            self.label.set_text("AC")

        self.icon = (
            text_icon(icon="󰐧", size="18px")
            if not is_present
            else Image(
                icon_name=self.client.get_property("IconName"),
                icon_size=14,
            )
        )

        if self.config.tooltip:
            if not is_present:
                self.set_tooltip_text("The unit operates on AC power")
            else:
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

    def show_power_profiles_menu(self, _):
        profiles = self.power_profiles_client.power_profiles

        menu = Gtk.Menu()
        menu.set_name("power-profiles-menu")

        for profile_id, profile_data in profiles.items():
            box = Gtk.Box(spacing=6)
            icon = Gtk.Image.new_from_icon_name(
                profile_data["icon_name"],
                Gtk.IconSize.BUTTON,
            )
            label = Gtk.Label(label=profile_data["name"])

            box.pack_start(icon, False, False, 0)
            box.pack_start(label, True, True, 0)

            item = Gtk.MenuItem()
            item.add(box)

            if profile_id == self.power_profiles_client.get_current_profile():
                item.get_style_context().add_class("selected")

            item.connect(
                "activate",
                lambda _, pp_name: self.power_profiles_client.set_power_profile(
                    pp_name
                ),
                profile_id,
            )
            menu.append(item)

        menu.show_all()
        menu.popup_at_widget(self, Gdk.Gravity.SOUTH, Gdk.Gravity.NORTH, None)

import math

from fabric.widgets.box import Box
from fabric.widgets.image import Image
from fabric.widgets.label import Label

from mewline.config import cfg
from mewline.shared.widget_container import ButtonWidget
from mewline.utils.misc import format_time
from mewline.utils.psutil import psutil_fabricator


class Battery(ButtonWidget):
    """A widget to display the current battery status."""

    def __init__(self, **kwargs) -> None:
        # Initialize the Box with specific name and style
        super().__init__(
            name="battery",
            **kwargs,
        )
        self.config = cfg.modules.battery
        self.full_battery_level = 100

        self.box = Box()
        self.children = self.box

        # Set up a repeater to call the update_battery_status method
        psutil_fabricator.connect("changed", self.update_ui)

    def update_ui(self, _, value):
        """Update the battery status by fetching the current battery information.

        This method updates the widget based on the current battery information.
        It hides the widget if the battery status is not available, updates the
        battery percentage label, and sets the appropriate icon and tooltip based
        on the battery status and configuration.
        """
        battery = value.get("battery")  # Get the battery status

        if battery is None:
            self.hide()
            return None

        battery_percent = round(battery.percent) if battery else 0

        self.battery_label = Label(
            label=f"{battery_percent}%", style_classes="panel-text", visible=False
        )

        is_charging = battery.power_plugged if battery else False

        self.battery_icon = Image(
            icon_name=self.get_icon_name(
                battery_percent=battery_percent,
                is_charging=is_charging,
            ),
            icon_size=14,
        )

        self.box.children = (self.battery_icon, self.battery_label)

        # Update the label with the battery percentage if enabled
        if self.config.label:
            self.battery_label.show()

            ## Hide the label when the battery is full
            if (
                self.config.hide_label_when_full
                and battery_percent == self.full_battery_level
            ):
                self.battery_label.hide()

        # Update the tooltip with the battery status details if enabled
        if self.config.tooltip:
            if battery_percent == self.full_battery_level:
                self.set_tooltip_text("Full")
            elif is_charging and battery_percent < self.full_battery_level:
                self.set_tooltip_text(f"Time to full: {format_time(battery.secsleft)}")
            else:
                self.set_tooltip_text(f"Time to empty: {format_time(battery.secsleft)}")

        return True

    def get_icon_name(self, battery_percent: int, is_charging: bool):
        """Determine the icon name based on the percentage and charging status."""
        if battery_percent == self.full_battery_level:
            return "battery-level-100-charged-symbolic"

        icon_level = math.floor(battery_percent / 10) * 10

        return (
            f"battery-level-{icon_level}{'-charging' if is_charging else ''}-symbolic"
        )

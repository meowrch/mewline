from typing import Literal

import dbus
from dbus.mainloop.glib import DBusGMainLoop
from fabric import Service
from fabric import Signal
from loguru import logger

DeviceState = {
    0: "UNKNOWN",
    1: "CHARGING",
    2: "DISCHARGING",
    3: "EMPTY",
    4: "FULLY_CHARGED",
    5: "PENDING_CHARGE",
    6: "PENDING_DISCHARGE",
}


class BatteryService(Service):
    """Service to interact with the PowerProfiles service."""

    @Signal
    def changed(self) -> None:
        """Signal emitted when battery changes."""

    instance = None

    @staticmethod
    def get_default():
        if BatteryService.instance is None:
            BatteryService.instance = BatteryService()

        return BatteryService.instance

    def __init__(
        self,
        **kwargs,
    ):
        super().__init__(
            **kwargs,
        )

        self.bus_name = "org.freedesktop.UPower"
        self.object_path = "/org/freedesktop/UPower/devices/DisplayDevice"

        # Set up the dbus main loop
        DBusGMainLoop(set_as_default=True)

        self.bus = dbus.SystemBus()

        self.power_profiles_obj = self.bus.get_object(self.bus_name, self.object_path)

        self.iface = dbus.Interface(
            self.power_profiles_obj, "org.freedesktop.DBus.Properties"
        )

        # Connect the 'g-properties-changed' signal to the handler
        self.iface.connect_to_signal("PropertiesChanged", self.handle_property_change)

    def get_property(
        self,
        property: Literal[
            "Percentage",
            "Temperature",
            "TimeToEmpty",
            "TimeToFull",
            "IconName",
            "State",
            "Capacity",
            "IsPresent",
        ],
    ):
        try:
            return self.iface.Get("org.freedesktop.UPower.Device", property)

        except dbus.DBusException as e:
            logger.error(f"[Battery] Error retrieving info: {e}")

    # Function to handle properties change signals
    def handle_property_change(self, *_):
        self.emit("changed")

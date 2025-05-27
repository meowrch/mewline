from typing import Literal

import dbus
from dbus.mainloop.glib import DBusGMainLoop
from fabric import Service
from fabric import Signal
from gi.repository import Gio
from gi.repository import GLib
from loguru import logger

from mewline import constants as cnst
from mewline.shared.dbus_helper import GioDBusHelper


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


class PowerProfiles(Service):
    """Service to interact with the PowerProfiles service via GIO."""

    @Signal
    def profile(self, value: str) -> None:
        """Signal emitted when profile changes."""

    _instance = None  # Class-level private instance variable

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def __init__(self, **kwargs):
        super().__init__(**kwargs)

        self.bus_name = "net.hadess.PowerProfiles"
        self.object_path = "/net/hadess/PowerProfiles"
        self.interface_name = "net.hadess.PowerProfiles"

        self.power_profiles = {
            "power-saver": {
                "name": "Power Saver",
                "icon_name": cnst.icons["powerprofiles"]["power-saver"],
            },
            "balanced": {
                "name": "Balanced",
                "icon_name": cnst.icons["powerprofiles"]["balanced"],
            },
            "performance": {
                "name": "Performance",
                "icon_name": cnst.icons["powerprofiles"]["performance"],
            },
        }

        self.dbus_helper = GioDBusHelper(
            bus_type=Gio.BusType.SYSTEM,
            bus_name=self.bus_name,
            object_path=self.object_path,
            interface_name=self.interface_name,
        )

        self.bus = self.dbus_helper.bus
        self.proxy = self.dbus_helper.proxy

        # Listen for PropertiesChanged signals
        self.dbus_helper.listen_signal(
            sender=self.bus_name,
            interface_name="org.freedesktop.DBus.Properties",
            member="PropertiesChanged",
            object_path=self.object_path,
            callback=self.handle_property_change,
        )

    def get_current_profile(self):
        try:
            value = self.proxy.get_cached_property("ActiveProfile")
            return value.unpack().strip() if value else "balanced"
        except Exception as e:
            logger.error(f"[PowerProfile] Error retrieving current power profile: {e}")
            return "balanced"

    def set_power_profile(self, profile: str):
        try:
            self.dbus_helper.set_property(
                self.bus_name,
                self.object_path,
                self.interface_name,
                "ActiveProfile",
                GLib.Variant("s", profile),
            )
            logger.info(f"[PowerProfile] Power profile set to {profile}")
        except Exception as e:
            logger.error(
                f"[PowerProfile] Could not change power level to {profile}: {e}"
            )

    def handle_property_change(self, *_args):
        """Callback for property change signals.

        Args:
            - connection
            - sender_name
            - object_path
            - interface_name
            - signal_name
            - parameters.
        """
        parameters = _args[-1]
        _interface, changed_props, _invalidated = parameters.unpack()
        if "ActiveProfile" in changed_props:
            new_profile = changed_props["ActiveProfile"]
            logger.info(f"Profile changed: {new_profile}")
            self.emit("profile", new_profile)

    def get_profile_icon(self, profile: str) -> str:
        return self.power_profiles.get(profile, self.power_profiles["balanced"]).get(
            "icon_name"
        )

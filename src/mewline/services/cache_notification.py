import contextlib
import json
import os

from fabric import Signal
from fabric.core.service import Service
from fabric.notifications import Notification
from loguru import logger

import mewline.constants as cnst


class NotificationCacheService(Service):
    """A service to manage the notifications."""

    @property
    def count(self) -> int:
        """Return the count of notifications."""
        return self._count

    @property
    def dont_disturb(self) -> bool:
        """Return the pause status."""
        return self._dont_disturb

    @dont_disturb.setter
    def dont_disturb(self, value: bool):
        """Set the pause status."""
        self._dont_disturb = value
        self.emit("dnd", value)

    def __init__(self, **kwargs):
        super().__init__(
            **kwargs,
        )
        self._notifications = self.do_read_notifications()
        self._count = len(self._notifications)

        self.notifications = []  # this is deserialized data
        # Keep live Notification objects for active session (actions will work)
        self._live_notifications: dict[int, Notification] = {}
        self._dont_disturb = False

    def do_read_notifications(self):
        # Check if the cache file exists and read existing data
        if os.path.exists(cnst.NOTIFICATION_CACHE_FILE):
            with open(cnst.NOTIFICATION_CACHE_FILE) as file:
                try:
                    # Load existing data if the file is not empty
                    existing_data = json.load(file)
                except (json.JSONDecodeError, KeyError, ValueError, IndexError) as e:
                    logger.error("[Notification]", e)
                    existing_data = []  # If the file is empty or malformed
        else:
            existing_data = []
        return existing_data

    def remove_notification(self, id: int):
        """Remove the notification of goven id."""
        item = next((p for p in self._notifications if p["id"] == id), None)
        if item is None:
            return
        index = self._notifications.index(item)
        self._notifications.pop(index)
        self.write_notifications(self._notifications)
        # Drop live reference
        with contextlib.suppress(Exception):
            self._live_notifications.pop(id, None)
        self._count -= 1
        self.emit("notification_count", self._count)

        # Emit clear_all signal if there are no notifications left
        if self._count == 0:
            self.emit("clear_all", True)

    def cache_notification(self, data: Notification):
        """Cache the notification."""
        existing_data = self._notifications

        # Assign a stable id for this session/history
        new_id = self._count + 1
        serialized_data = data.serialize()
        # Persist local metadata alongside serialized notification
        serialized_data.update(
            {
                "id": new_id,
                # Whether user has already clicked any action for this notif in history
                "actions_clicked": False,
            }
        )

        # Append the new notification to the existing data
        existing_data.append(serialized_data)

        # Persist to disk
        self.write_notifications(existing_data)

        # Track live object so actions keep working during the session
        self._live_notifications[new_id] = data

        self._count += 1
        self._notifications = existing_data
        self.emit("notification_count", self._count)

    def clear_all_notifications(self):
        """Empty the notifications."""
        self._notifications = []
        self._count = 0
        self._live_notifications.clear()

        # Write the updated data back to the cache file
        self.write_notifications(self._notifications)
        self.emit("clear_all", True)
        self.emit("notification_count", self._count)

    def write_notifications(self, data):
        """Write the notifications to the cache file."""
        with open(cnst.NOTIFICATION_CACHE_FILE, "w") as f:
            json.dump(data, f, indent=4, ensure_ascii=False)
        logger.info("[Notification] Notifications written successfully.")

    def get_deserialized(self) -> list[Notification]:
        """Return the notifications.
        Prefer live objects when available so actions work.
        """  # noqa: D205
        self._notifications = self.do_read_notifications()

        # Build list using live objects if present, else deserialize
        result: list[Notification] = []
        for data in self._notifications:
            nid = data.get("id")
            live = self._live_notifications.get(nid)
            if live is not None:
                result.append(live)
            else:
                try:
                    result.append(Notification.deserialize(data))
                except Exception:
                    continue
        self.notifications = result
        return self.notifications

    def mark_action_clicked(self, id: int):
        """Mark that an action was clicked for the given cached notification id."""
        try:
            item = next((p for p in self._notifications if p.get("id") == id), None)
            if not item:
                return
            if not item.get("actions_clicked", False):
                item["actions_clicked"] = True
                self.write_notifications(self._notifications)
                # Invalidate cached deserialized list so next get reflects state
                self.notifications = []
                self.emit("notification_clicked", id)
        except Exception:
            ...

    @Signal
    def clear_all(self, value: bool) -> None:
        """Signal emitted when notifications are emptied."""
        # Implement as needed for your application

    @Signal
    def notification_count(self, value: int) -> None:
        """Signal emitted when a new notification is added."""
        # Implement as needed for your application

    @Signal
    def notification_clicked(self, value: int) -> None:
        """Signal emitted when an action gets clicked for a cached notification."""

    @Signal
    def dnd(self, value: bool) -> None:
        """Signal emitted when dnd is toggled."""
        # Implement as needed for your application

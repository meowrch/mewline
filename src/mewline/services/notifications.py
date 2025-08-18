import subprocess

from fabric.notifications import Notifications
from loguru import logger

from mewline.config import cfg


class MyNotifications(Notifications):
    NOTIFICATION_DAEMONS = (
        "dunst",
        "mako",
        "swaync",
        "xfce4-notifyd",
        "notify-osd",
        "wxWidgets-notify",
    )

    def __init__(self, *args, **kwargs) -> None:
        if cfg.options.intercept_notifications:
            self.kill_all_notification_daemons()

        super().__init__(*args, **kwargs)

    @staticmethod
    def is_running(process_name: str) -> bool:
        """Checks if the process is running by name."""
        try:
            result = subprocess.run(
                ["pgrep", "-x", process_name],
                capture_output=True,
                text=True,
            )
            return bool(result.stdout.strip())
        except subprocess.SubprocessError as e:
            logger.warning(f"Error checking if {process_name} is running: {e}")
            return False

    @staticmethod
    def kill_process(process_name: str) -> bool:
        """Tries to terminate the process by name."""
        try:
            subprocess.run(
                ["pkill", "-x", process_name],
                capture_output=True,
                text=True,
                check=True,
            )
            logger.info(f"Killed {process_name}")
            return True
        except subprocess.CalledProcessError:
            logger.warning(f"{process_name} is not running (or couldn't be killed)")
            return False
        except Exception as e:
            logger.error(f"Failed to kill {process_name}: {e}")
            return False

    def kill_all_notification_daemons(self) -> list[str]:
        """Stops all known notification managers."""
        killed = []
        for daemon in self.NOTIFICATION_DAEMONS:
            if self.is_running(daemon):
                self.kill_process(daemon)
                killed.append(daemon)
        return killed

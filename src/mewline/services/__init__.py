from fabric.audio import Audio
from fabric.bluetooth import BluetoothClient
from fabric.notifications import Notifications

from mewline.services.cache_notification import NotificationCacheService

cache_notification_service = NotificationCacheService().get_initial()

audio_service = Audio()

notification_service = Notifications()


bluetooth_client = BluetoothClient()
# to run notify closures thus display the status
# without having to wait until an actual change
bluetooth_client.notify("scanning")
bluetooth_client.notify("enabled")

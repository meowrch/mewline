from fabric.audio import Audio
from fabric.bluetooth import BluetoothClient
from fabric.notifications import Notifications

from mewline.services.battery import BatteryService
from mewline.services.cache_notification import NotificationCacheService

audio_service = Audio()

notification_service = Notifications()
cache_notification_service = NotificationCacheService().get_initial()
battery_service = BatteryService()

bluetooth_client = BluetoothClient()
# to run notify closures thus display the status
# without having to wait until an actual change
bluetooth_client.notify("scanning")
bluetooth_client.notify("enabled")

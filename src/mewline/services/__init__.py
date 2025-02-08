from fabric.audio import Audio
from fabric.notifications import Notifications

from mewline.services.cache_notification import NotificationCacheService

cache_notification_service = NotificationCacheService().get_initial()


# Fabric services
audio_service = Audio()
notification_service = Notifications()

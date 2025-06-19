import base64

import gi
from fabric.notifications.service import NotificationImagePixmap

gi.require_version("Gtk", "3.0")

from gi.repository import GdkPixbuf  # noqa: E402
from gi.repository import GLib  # noqa: E402


@classmethod
def new_deserialize(
    cls, data: tuple[int, int, int, bool, int, int, str]
) -> "NotificationImagePixmap":
    """Load image data from a serialized data tuple (using the `serialize` method)
    and return the newly created Pixmap object.

    :param data: the tuple which is holding the image's data
    :type data: tuple[int, int, int, bool, int, int, str]
    :return: the newly loaded image pixmap
    :rtype: NotificationImagePixmap
    """  # noqa: D205
    self = cls.__new__(cls)

    (
        self.width,
        self.height,
        self.rowstride,
        self.has_alpha,
        self.bits_per_sample,
        self.channels,
        pixmap_data,
    ) = data

    # if this doesn't work, please report.
    loader = GdkPixbuf.PixbufLoader.new_with_type("png")
    decoded_data = base64.b64decode(pixmap_data)
    bytes_data = GLib.Bytes.new(decoded_data)
    loader.write_bytes(bytes_data)  # type: ignore
    loader.close()

    self._pixbuf = loader.get_pixbuf()  # type: ignore
    self.byte_array = None

    return self


NotificationImagePixmap.deserialize = new_deserialize

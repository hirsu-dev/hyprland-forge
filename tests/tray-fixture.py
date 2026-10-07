import asyncio
import os
import signal

from dbus_next import Message, MessageType, PropertyAccess
from dbus_next.aio import MessageBus
from dbus_next.service import ServiceInterface, dbus_property, method
from mpris_fixture import MprisRoot, MprisPlayer


class TrayItem(ServiceInterface):
    def __init__(self):
        super().__init__("org.kde.StatusNotifierItem")

    @dbus_property(access=PropertyAccess.READ)
    def Category(self) -> "s":
        return "ApplicationStatus"

    @dbus_property(access=PropertyAccess.READ)
    def Id(self) -> "s":
        return "forge-fixture"

    @dbus_property(access=PropertyAccess.READ)
    def Title(self) -> "s":
        return "Forge fixture"

    @dbus_property(access=PropertyAccess.READ)
    def Status(self) -> "s":
        return "Active"

    @dbus_property(access=PropertyAccess.READ)
    def IconName(self) -> "s":
        return "application-x-executable"

    @dbus_property(access=PropertyAccess.READ)
    def IconPixmap(self) -> "a(iiay)":
        return []

    @dbus_property(access=PropertyAccess.READ)
    def ToolTip(self) -> "(sa(iiay)ss)":
        return ["application-x-executable", [], "Forge fixture", "Runtime tray validation"]

    @dbus_property(access=PropertyAccess.READ)
    def ItemIsMenu(self) -> "b":
        return False

    @dbus_property(access=PropertyAccess.READ)
    def Menu(self) -> "o":
        return "/"

    @method()
    def Activate(self, x: "i", y: "i"):
        pass

    @method()
    def SecondaryActivate(self, x: "i", y: "i"):
        pass

    @method()
    def Scroll(self, delta: "i", orientation: "s"):
        pass


async def main():
    bus = await MessageBus().connect()
    name = f"org.kde.StatusNotifierItem-{os.getpid()}-1"
    await bus.request_name(name)
    bus.export("/StatusNotifierItem", TrayItem())
    await bus.request_name("org.mpris.MediaPlayer2.forgefixture")
    bus.export("/org/mpris/MediaPlayer2", MprisRoot())
    bus.export("/org/mpris/MediaPlayer2", MprisPlayer())
    reply = await bus.call(Message(destination="org.kde.StatusNotifierWatcher", path="/StatusNotifierWatcher", interface="org.kde.StatusNotifierWatcher", member="RegisterStatusNotifierItem", signature="s", body=[name]))
    if reply.message_type == MessageType.ERROR:
        raise RuntimeError(reply.body)
    stop = asyncio.Event()
    for item in (signal.SIGTERM, signal.SIGINT):
        asyncio.get_running_loop().add_signal_handler(item, stop.set)
    await stop.wait()
    bus.disconnect()


asyncio.run(main())

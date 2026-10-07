from dbus_next import PropertyAccess, Variant
from dbus_next.service import ServiceInterface, dbus_property, method


class MprisRoot(ServiceInterface):
    def __init__(self):
        super().__init__("org.mpris.MediaPlayer2")

    @dbus_property(access=PropertyAccess.READ)
    def Identity(self) -> "s":
        return "Forge fixture"

    @dbus_property(access=PropertyAccess.READ)
    def CanQuit(self) -> "b":
        return False

    @dbus_property(access=PropertyAccess.READ)
    def CanRaise(self) -> "b":
        return False

    @dbus_property(access=PropertyAccess.READ)
    def HasTrackList(self) -> "b":
        return False

    @dbus_property(access=PropertyAccess.READ)
    def SupportedUriSchemes(self) -> "as":
        return ["file"]

    @dbus_property(access=PropertyAccess.READ)
    def SupportedMimeTypes(self) -> "as":
        return ["audio/ogg"]


class MprisPlayer(ServiceInterface):
    def __init__(self):
        super().__init__("org.mpris.MediaPlayer2.Player")
        self.index = 0
        self.playing = True

    @dbus_property(access=PropertyAccess.READ)
    def PlaybackStatus(self) -> "s":
        return "Playing" if self.playing else "Paused"

    @dbus_property(access=PropertyAccess.READ)
    def Metadata(self) -> "a{sv}":
        return {"mpris:trackid": Variant("o", f"/forge/track{self.index}"), "mpris:length": Variant("x", 180000000), "xesam:title": Variant("s", ("Orbit", "Dawn")[self.index]), "xesam:artist": Variant("as", ["Forge"])}

    @dbus_property(access=PropertyAccess.READ)
    def CanControl(self) -> "b":
        return True

    @dbus_property(access=PropertyAccess.READ)
    def CanPlay(self) -> "b":
        return True

    @dbus_property(access=PropertyAccess.READ)
    def CanPause(self) -> "b":
        return True

    @dbus_property(access=PropertyAccess.READ)
    def CanGoNext(self) -> "b":
        return True

    @dbus_property(access=PropertyAccess.READ)
    def CanGoPrevious(self) -> "b":
        return True

    @dbus_property(access=PropertyAccess.READ)
    def CanSeek(self) -> "b":
        return False

    @dbus_property(access=PropertyAccess.READ)
    def Position(self) -> "x":
        return 0

    @dbus_property(access=PropertyAccess.READ)
    def MinimumRate(self) -> "d":
        return 1.0

    @dbus_property(access=PropertyAccess.READ)
    def MaximumRate(self) -> "d":
        return 1.0

    @dbus_property(access=PropertyAccess.READ)
    def Rate(self) -> "d":
        return 1.0

    @dbus_property(access=PropertyAccess.READ)
    def Volume(self) -> "d":
        return 1.0

    @method()
    def PlayPause(self):
        self.playing = not self.playing
        self.emit_properties_changed({"PlaybackStatus": self.PlaybackStatus})

    @method()
    def Play(self):
        self.playing = True
        self.emit_properties_changed({"PlaybackStatus": self.PlaybackStatus})

    @method()
    def Pause(self):
        self.playing = False
        self.emit_properties_changed({"PlaybackStatus": self.PlaybackStatus})

    @method()
    def Next(self):
        self.index = (self.index + 1) % 2
        self.emit_properties_changed({"Metadata": self.Metadata})

    @method()
    def Previous(self):
        self.Next()

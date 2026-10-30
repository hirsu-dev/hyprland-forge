import os
import subprocess
from pathlib import Path

os.environ.setdefault("QT_QUICK_BACKEND", "software")

from PySide6.QtCore import QAbstractListModel, QModelIndex, QObject, QMetaObject, QUrl, Qt, Property, Signal, Slot
from PySide6.QtGui import QGuiApplication
from PySide6.QtQuick import QQuickView
from PySide6.QtTest import QTest


class SessionModel(QAbstractListModel):
    def rowCount(self, parent=QModelIndex()):
        return 2

    def roleNames(self):
        return {Qt.ItemDataRole.UserRole + 1: b"name"}

    def data(self, index, role):
        return ("Hyprland", "Test session")[index.row()]

    @Property(int, constant=True)
    def lastIndex(self):
        return 0


class UserModel(QObject):
    @Property(str, constant=True)
    def lastUser(self):
        return ""


class Proxy(QObject):
    loginFailed = Signal()
    loginSucceeded = Signal()

    def __init__(self):
        super().__init__()
        self.calls = []

    @Property(bool, constant=True)
    def canReboot(self):
        return False

    @Property(bool, constant=True)
    def canPowerOff(self):
        return False

    @Slot(str, str, int)
    def login(self, user, password, session):
        self.calls.append((user, password, session))


app = QGuiApplication([])
view = QQuickView()
proxy, users, sessions = Proxy(), UserModel(), SessionModel()
context = view.rootContext()
for name, value in (("sddm", proxy), ("userModel", users), ("sessionModel", sessions), ("config", {"Motion": "false", "DefaultUser": "forge-preview", "BootGate": "false"})):
    context.setContextProperty(name, value)
view.setResizeMode(QQuickView.ResizeMode.SizeRootObjectToView)
view.resize(1920, 1080)
view.setSource(QUrl.fromLocalFile(str(Path("iso/boot/sddm/Main.qml").resolve())))
assert view.status() == QQuickView.Status.Ready, view.errors()
view.show()
QTest.qWait(150)
root = view.rootObject()
username = root.findChild(QObject, "forgeUsername")
password = root.findChild(QObject, "forgePassword")
picker = root.findChild(QObject, "forgeSessions")
assert username.property("text") == "forge-preview"
assert picker.property("currentIndex") == 0
popup = picker.property("popup")
QMetaObject.invokeMethod(popup, "open")
QTest.qWait(100)
assert popup.property("visible"), "The session picker did not open"
picker.setProperty("currentIndex", 1)
QMetaObject.invokeMethod(popup, "close")
assert picker.property("currentIndex") == 1
QMetaObject.invokeMethod(root, "login")
assert not proxy.calls, "Empty passwords must not be submitted"
password.setProperty("text", "ephemeral-fixture-password")
QMetaObject.invokeMethod(root, "login")
QMetaObject.invokeMethod(root, "login")
assert len(proxy.calls) == 1 and root.property("busy"), "Duplicate submission was not blocked"
assert proxy.calls[0][2] == 1, "The selected session was not passed to SDDM"
proxy.loginFailed.emit()
QTest.qWait(50)
assert not root.property("busy") and password.property("text") == ""
assert "ACCESS DENIED" in root.property("notice")
results = Path("test-results/iso-login")
results.mkdir(parents=True, exist_ok=True)
assert view.grabWindow().save(str(results / "login-1920.png"))
view.resize(1280, 720)
QTest.qWait(100)
assert abs(root.property("unit") - 2 / 3) < .01
assert view.grabWindow().save(str(results / "login-1280.png"))
password.setProperty("text", "ephemeral-fixture-password")
QMetaObject.invokeMethod(root, "login")
proxy.loginSucceeded.emit()
QTest.qWait(50)
assert password.property("text") == "" and root.property("reveal") == 0
assert "ACCESS GRANTED" in root.property("notice")
root.setProperty("motion", True)
root.setProperty("reveal", 1)
QTest.qWait(150)
assert 0 < root.property("reveal") < 1, "The intro must animate through intermediate frames"
assert view.grabWindow().save(str(results / "login-transition.png"))
QTest.qWait(800)
assert root.property("reveal") == 1
region = view.grabWindow().rect()
region.setLeft(region.width() // 2)
moving = view.grabWindow().copy(region)
QTest.qWait(240)
assert moving != view.grabWindow().copy(region), "Optical tracers must animate"
root.setProperty("motion", False)
QTest.qWait(120)
still = view.grabWindow().copy(region)
QTest.qWait(240)
assert still == view.grabWindow().copy(region), "Reduced motion must leave the optical field static"
view.close()
command = ["sddm-greeter-qt6", "--test-mode", "--theme", str(Path("iso/boot/sddm").resolve())]
try:
    result = subprocess.run(command, capture_output=True, text=True, timeout=4)
except subprocess.TimeoutExpired as exc:
    log = (exc.stdout or b"") + (exc.stderr or b"")
    log = log.decode(errors="replace")
else:
    log = result.stdout + result.stderr
    assert result.returncode == 0, log
(results / "greeter.log").write_text(log)
for error in ("is not a type", "is not installed", "Cannot assign to non-existent", "ReferenceError", "TypeError", "Binding loop", "Main.qml:"):
    assert error not in log, log
print("Forge login: native SDDM load, account/session selection, rejection, duplicate protection, password clearing and 1080p/720p verified")

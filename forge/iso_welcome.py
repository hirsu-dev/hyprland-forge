import argparse
import os
import platform
import sys
from pathlib import Path

from .storage import write_json
from .iso_apps import CATALOGUE, selection


def main(argv=None):
    parser = argparse.ArgumentParser()
    parser.add_argument('--preview', action='store_true')
    parser.add_argument('--screenshot', type=Path)
    parser.add_argument('--preview-page', choices=('welcome', 'apps'), default='welcome')
    args = parser.parse_args(argv)
    if not args.preview and (platform.system() != 'Linux' or not Path('/etc/forge-live').is_file() or not Path('/run/archiso').is_dir()):
        parser.error('Start this welcome screen from the Forge installation USB.')
    if args.screenshot and not args.preview:
        parser.error('Screenshots require preview mode.')
    os.environ.setdefault('QT_QUICK_CONTROLS_STYLE', 'Basic')
    from PySide6.QtCore import QObject, Property, QProcess, QTimer, QUrl, Signal, Slot
    from PySide6.QtGui import QGuiApplication
    from PySide6.QtQml import QQmlApplicationEngine
    from PySide6.QtQuick import QQuickWindow

    class Installer(QObject):
        changed = Signal()

        def __init__(self):
            super().__init__()
            self._busy = False
            self._status = 'Explore the setup. Your installation starts only after the final disk review.'
            self.process = QProcess(self)
            self.process.finished.connect(self.finished)
            self.process.errorOccurred.connect(self.failed)

        @Property(bool, notify=changed)
        def busy(self):
            return self._busy

        @Property(str, notify=changed)
        def status(self):
            return self._status

        @Property('QVariantList', constant=True)
        def apps(self):
            return [{'id': app['id'], 'name': app['name'], 'description': app['description']} for app in CATALOGUE]

        @Slot(bool, bool, 'QVariantList')
        def start(self, gaming, motion, apps):
            selection(apps)
            if args.preview:
                self._status = 'Preview mode · installation is unavailable.'
                self.changed.emit()
                return
            if self._busy:
                return
            directory = Path('/run/forge-installer')
            directory.mkdir(mode=0o700, exist_ok=True)
            if directory.is_symlink() or directory.stat().st_uid != 0:
                self._status = 'Could not prepare installation settings.'
                self.changed.emit()
                return
            write_json(directory / 'options.json', {'gaming': gaming, 'motion': motion, 'apps': apps})
            self._busy = True
            self._status = 'Setup is open. Review every disk change before installing.'
            self.changed.emit()
            self.process.start('calamares', [])

        @Slot(int, QProcess.ExitStatus)
        def finished(self, code, status):
            self._busy = False
            self._status = 'Setup closed. You can review your choices again.' if code == 0 else 'Setup stopped. Open the installer to review the reported error.'
            self.changed.emit()

        @Slot(QProcess.ProcessError)
        def failed(self, error):
            self._busy = False
            self._status = 'The installer could not start. This build needs repair.'
            self.changed.emit()

        @Slot()
        def network(self):
            if not args.preview:
                QProcess.startDetached('nm-connection-editor', [])

        @Slot()
        def reboot(self):
            if not args.preview and not self._busy:
                QProcess.startDetached('systemctl', ['reboot'])

    app = QGuiApplication(sys.argv[:1])
    app.setApplicationName('Forge Setup')
    app.setOrganizationName('Hyprland Forge')
    engine = QQmlApplicationEngine()
    bridge = Installer()
    engine.rootContext().setContextProperty('installer', bridge)
    engine.rootContext().setContextProperty('previewMode', args.preview)
    engine.rootContext().setContextProperty('previewApps', args.preview and args.preview_page == 'apps')
    engine.load(QUrl.fromLocalFile(str(Path(__file__).resolve().parent.parent / 'iso/ui/Welcome.qml')))
    if not engine.rootObjects():
        return 1
    if args.screenshot:
        def capture():
            try:
                window = engine.rootObjects()[0]
                if not isinstance(window, QQuickWindow):
                    raise TypeError('The preview did not create a Qt Quick window.')
                args.screenshot.parent.mkdir(parents=True, exist_ok=True)
                saved = window.grabWindow().save(str(args.screenshot))
                app.exit(0 if saved else 1)
            except Exception as error:
                print(str(error), file=sys.stderr)
                app.exit(1)
        QTimer.singleShot(5500, capture)
    return app.exec()


if __name__ == '__main__':
    raise SystemExit(main())

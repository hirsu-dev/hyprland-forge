from .manifest import ForgeError


CATALOGUE = (
    {'id': 'brave', 'name': 'Brave', 'description': 'Browser · Flatpak', 'flatpak': 'com.brave.Browser'},
    {'id': 'equicord', 'name': 'Discord + Equicord', 'description': 'Equibop · Discord client with Equicord included', 'flatpak': 'io.github.equicord.equibop'},
    {'id': 'discord', 'name': 'Discord', 'description': 'Official desktop client', 'package': 'discord'},
    {'id': 'spotify', 'name': 'Spotify', 'description': 'Music · Flatpak', 'flatpak': 'com.spotify.Client'},
    {'id': 'obs', 'name': 'OBS Studio', 'description': 'Recording and streaming', 'package': 'obs-studio'},
    {'id': 'code', 'name': 'Code - OSS', 'description': 'Open source code editor', 'package': 'code'},
    {'id': 'libreoffice', 'name': 'LibreOffice', 'description': 'Documents, spreadsheets and presentations', 'package': 'libreoffice-fresh'},
    {'id': 'vlc', 'name': 'VLC', 'description': 'Media player', 'package': 'vlc'},
    {'id': 'gimp', 'name': 'GIMP', 'description': 'Image editor', 'package': 'gimp'},
    {'id': 'krita', 'name': 'Krita', 'description': 'Digital painting', 'package': 'krita'},
    {'id': 'keepassxc', 'name': 'KeePassXC', 'description': 'Local password manager', 'package': 'keepassxc'},
    {'id': 'thunderbird', 'name': 'Thunderbird', 'description': 'Email and calendars', 'package': 'thunderbird'},
    {'id': 'signal', 'name': 'Signal', 'description': 'Private messaging', 'package': 'signal-desktop'},
)


def selection(values):
    if not isinstance(values, list) or any(not isinstance(value, str) for value in values):
        raise ForgeError('Select apps from the installation screen.')
    known = {app['id'] for app in CATALOGUE}
    if len(values) != len(set(values)) or not set(values) <= known:
        raise ForgeError('The selected app list is invalid.')
    if {'discord', 'equicord'} <= set(values):
        raise ForgeError('Choose either the official Discord client or Discord with Equicord.')
    return [app for app in CATALOGUE if app['id'] in values]


def flatpak_commands(values):
    apps = [app['flatpak'] for app in selection(values) if 'flatpak' in app]
    if not apps:
        return []
    return [
        ['flatpak', 'remote-add', '--system', '--if-not-exists', 'flathub', 'https://flathub.org/repo/flathub.flatpakrepo'],
        ['flatpak', 'install', '--system', '--assumeyes', '--noninteractive', 'flathub', *apps],
    ]

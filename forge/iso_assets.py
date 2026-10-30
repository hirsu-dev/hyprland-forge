import shutil
import re
import subprocess
from pathlib import Path

from .storage import atomic_write


def render_assets(destination):
    from PIL import Image, ImageDraw, ImageFont
    destination.mkdir(parents=True, exist_ok=True)
    background = Image.new('RGB', (1920, 1080), '#10191f')
    draw = ImageDraw.Draw(background)
    for x in range(48, 1920, 96):
        draw.line((x, 0, x, 1080), fill='#1b2a33')
    for y in range(48, 1080, 96):
        draw.line((0, y, 1920, y), fill='#1b2a33')
    for n in range(7):
        x, y = 930 + n * 36, 150 + n * 22
        draw.line([(x, y), (1650 - n * 18, y), (1830 - n * 18, 350), (1830 - n * 18, 760), (1650 - n * 18, 940 - n * 22), (x, 940 - n * 22)], fill='#536d78', width=2)
    draw.polygon([(1210,350),(1560,350),(1510,415),(1280,415),(1240,500),(1465,500),(1410,565),(1210,565),(1120,760),(1030,760)], fill='#b4d9de')
    fonts = list(Path('/usr/share/fonts').rglob('JetBrainsMonoNerdFont-Regular.ttf'))
    font = ImageFont.truetype(str(fonts[0]), 48) if fonts else ImageFont.load_default(size=48)
    draw.text((100, 96), 'FORGE_', font=font, fill='#e1edf0')
    background.save(destination / 'background.png')
    logo = Image.new('RGBA', (440, 180))
    draw = ImageDraw.Draw(logo)
    left, top, right, bottom = draw.textbbox((0, 0), 'FORGE_', font=font)
    draw.text(((440 - right + left) / 2 - left, (180 - bottom + top) / 2 - top), 'FORGE_', font=font, fill='#b4d9de')
    logo.save(destination / 'logo.png')
    Image.new('RGBA', (100, 3), '#94dce5').save(destination / 'beam.png')


def install_boot_assets(root, source, motion=True, username=''):
    if username and not re.fullmatch(r'[a-z_][a-z0-9_-]{0,31}', username):
        raise ValueError('The default login account is invalid.')
    atomic_write(root / 'usr/local/bin/forge-start', (source / 'iso/boot/forge-start').read_bytes(), 0o755)
    atomic_write(root / 'usr/share/wayland-sessions/forge.desktop', (source / 'iso/boot/forge.desktop').read_bytes(), 0o644)
    atomic_write(root / 'usr/share/wayland-sessions/forge-software.desktop', (source / 'iso/boot/forge-software.desktop').read_bytes(), 0o644)
    theme = root / 'boot/grub/themes/forge'
    render_assets(theme)
    shutil.copyfile(source / 'iso/boot/grub-theme.txt', theme / 'theme.txt')
    plymouth = root / 'usr/share/plymouth/themes/forge'
    plymouth.mkdir(parents=True, exist_ok=True)
    for name in ('logo.png', 'beam.png'):
        shutil.copyfile(theme / name, plymouth / name)
    shutil.copyfile(source / 'iso/boot/forge.plymouth', plymouth / 'forge.plymouth')
    script = (source / 'iso/boot/forge.script').read_text()
    if not motion:
        script = script.replace('motion = 1;', 'motion = 0;', 1)
    atomic_write(plymouth / 'forge.script', script.encode(), 0o644)
    atomic_write(root / 'etc/plymouth/plymouthd.conf', b'[Daemon]\nTheme=forge\nShowDelay=0\n', 0o644)
    greeter = root / 'usr/share/sddm/themes/forge'
    shutil.copytree(source / 'iso/boot/sddm', greeter)
    atomic_write(greeter / 'theme.conf', ('[General]\nMotion=' + str(motion).lower() + '\nDefaultUser=' + username + '\n').encode(), 0o644)
    atomic_write(root / 'etc/sddm.conf.d/forge.conf', b'[Theme]\nCurrent=forge\n[General]\nDisplayServer=wayland\nGreeterEnvironment=QT_QUICK_CONTROLS_STYLE=Basic\n[Wayland]\nCompositorCommand=weston --shell=kiosk-shell.so\n', 0o644)
    subprocess.run(['arch-chroot', str(root), 'grub-mkfont', '-s', '20', '-o', '/boot/grub/themes/forge/font.pf2', '/usr/share/fonts/TTF/DejaVuSans.ttf'], check=True)

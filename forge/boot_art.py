from pathlib import Path

from .manifest import ForgeError


def font_path():
    candidates = (
        "/usr/share/fonts/TTF/JetBrainsMonoNerdFont-Regular.ttf",
        "/usr/share/fonts/TTF/JetBrainsMonoNerdFontMono-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "C:/Windows/Fonts/consola.ttf",
    )
    for name in candidates:
        if Path(name).is_file():
            return Path(name)
    raise ForgeError("A monospaced TrueType font is needed to render the boot artwork")


def render(destination, font=None):
    from PIL import Image, ImageDraw, ImageFont

    destination = Path(destination)
    destination.mkdir(parents=True, exist_ok=True)
    font = font or font_path()
    fonts = {size: ImageFont.truetype(str(font), size) for size in (16, 20, 24, 32, 52, 118)}
    ink, muted, yellow, cyan, red = "#f4edf5", "#bdaab8", "#fcee0a", "#74f7ef", "#ff4d61"

    def scene(mode):
        image = Image.new("RGB", (1920, 1080), "#100d16")
        draw = ImageDraw.Draw(image)
        for y in range(1080):
            value = 1 - abs(y - 510) / 600
            draw.line((0, y, 1919, y), fill=(16 + int(max(value, 0) * 8), 13, 22 + int(max(value, 0) * 6)))
        for x in range(48, 1920, 64):
            draw.line((x, 0, x, 1080), fill="#211923")
        for y in range(42, 1080, 64):
            draw.line((0, y, 1920, y), fill="#211923")
        for inset in range(0, 150, 30):
            draw.line([(1140 + inset, 178 + inset), (1530 - inset, 178 + inset), (1770 - inset, 418), (1770 - inset, 742 - inset), (1560 - inset, 930 - inset), (1170 + inset, 930 - inset), (970 + inset, 730 - inset), (970 + inset, 340 + inset), (1140 + inset, 178 + inset)], fill="#50303e", width=2)
        draw.polygon([(1200, 330), (1560, 330), (1500, 400), (1300, 400), (1270, 465), (1460, 465), (1405, 532), (1240, 532), (1160, 713), (1065, 713)], fill=yellow)
        draw.line([(1540, 496), (1640, 396), (1640, 748), (1495, 893)], fill=red, width=5)
        draw.line([(1000, 796), (1128, 924), (1440, 924)], fill=cyan, width=3)
        draw.text((96, 72), "F /  OVERDRIVE SYSTEMS", font=fonts[20], fill=yellow)
        draw.text((1440, 72), "FORGE  //  BOOT VECTOR", font=fonts[16], fill=muted)
        draw.line((96, 118, 1824, 118), fill="#693642", width=2)
        draw.text((96, 194), "01 / ACCESS CONTROL" if mode == "auth" else "02 / SYSTEM SELECT", font=fonts[20], fill=cyan)
        draw.text((88, 246), "FORGE", font=fonts[118], fill=yellow)
        draw.text((96, 386), "YOUR MACHINE. YOUR SIGNAL.", font=fonts[24], fill=ink)
        draw.line((96, 452, 790, 452), fill=red, width=3)
        draw.text((96, 478), "IDENTITY CHECK" if mode == "auth" else "CHOOSE YOUR ENVIRONMENT", font=fonts[24], fill=ink)
        if mode == "auth":
            draw.rectangle((96, 536, 826, 926), fill="#100d16", outline="#693642", width=2)
            draw.text((96, 940), "BOOT USER  forge  /  AUTHENTICATE TO REVEAL SYSTEMS", font=fonts[16], fill=cyan)
        else:
            draw.rectangle((96, 538, 826, 790), fill="#100d16", outline="#693642", width=2)
            draw.text((96, 836), "UP / DOWN   SELECT     ENTER   LAUNCH", font=fonts[20], fill=cyan)
            draw.text((96, 904), "AUTHENTICATED  /  AWAITING YOUR COMMAND", font=fonts[20], fill=muted)
        draw.line((96, 972, 1824, 972), fill="#693642", width=2)
        draw.text((96, 1000), "LOCAL CONSOLE  //  NO NETWORK REQUIRED", font=fonts[16], fill=muted)
        draw.text((1370, 1000), "REDLINE / ORIGINAL SERIES", font=fonts[16], fill=red)
        return image

    scene("auth").save(destination / "auth.png")
    selector = scene("selector")
    selector.save(destination / "selector.png")
    draw = ImageDraw.Draw(selector)
    draw.polygon([(118, 560), (782, 560), (802, 580), (802, 634), (138, 634), (118, 614)], fill="#fcee0a")
    draw.text((148, 576), "Forge OS", font=fonts[32], fill="#100d16")
    draw.text((148, 682), "Windows 11", font=fonts[32], fill=ink)
    selector.save(destination / "design-preview.png")
    for name in ("select_c.png", "select_w.png", "select_e.png", "select_n.png", "select_s.png", "select_nw.png", "select_ne.png", "select_sw.png", "select_se.png"):
        tile = Image.new("RGB", (8, 8), yellow)
        tile.save(destination / name)
    return font

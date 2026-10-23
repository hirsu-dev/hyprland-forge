import json
import os
import subprocess
import sys
import time

assert "--disposable-vm" in sys.argv
assert subprocess.check_output(["systemd-detect-virt", "--vm"], text=True).strip() == "oracle"
assert os.geteuid() != 0


def call(*args):
    return subprocess.check_output(args, text=True, timeout=10).strip()


def ipc(*args):
    return call("quickshell", "-c", "forge", "ipc", "call", "forge", *args)


monitors = json.loads(call("hyprctl", "-j", "monitors"))
output = next(item for item in monitors if item["focused"])
assert output["name"] == "Virtual-1"
try:
    call("hyprctl", "dispatch", 'function() hl.monitor({output="Virtual-1",mode="1920x1080@60",position="0x0",scale=1}) end')
    call("hyprctl", "dispatch", 'hl.dsp.dpms({action="on"})')
    time.sleep(2)
    for page in ("hardware", "customize", "alerts"):
        if page == "alerts":
            subprocess.run(["notify-send", "--expire-time=10000", "FORGE / SIGNAL ONLINE", "System deck modules validated in the Arch VM. Physical laptop checks remain pending."], check=True)
        ipc("hub", page)
        time.sleep(2)
        subprocess.run(["grim", "/tmp/forge-system-deck-" + page + ".png"], check=True, timeout=10)
    print(json.dumps({"screenshots": ["/tmp/forge-system-deck-" + page + ".png" for page in ("hardware", "customize", "alerts")]}))
finally:
    ipc("close")
    call("quickshell", "-c", "forge", "ipc", "call", "forgeAlerts", "clear")
    mode = str(output["width"]) + "x" + str(output["height"]) + "@" + str(output["refreshRate"])
    call("hyprctl", "dispatch", 'function() hl.monitor({output="Virtual-1",mode=' + json.dumps(mode) + ',position="0x0",scale=' + str(output["scale"]) + '}) end')

import subprocess
import sys


def choose(runner=subprocess.run):
    history = runner(["cliphist", "list"], capture_output=True, check=True, timeout=10).stdout
    if not history.strip():
        return False
    selection = runner(["fuzzel", "--dmenu", "--prompt", "Clipboard > "], input=history, capture_output=True)
    if selection.returncode == 1:
        return False
    selection.check_returncode()
    if not selection.stdout.strip():
        return False
    if selection.stdout.rstrip(b"\n") not in history.splitlines():
        raise ValueError("Choose an existing clipboard entry")
    content = runner(["cliphist", "decode"], input=selection.stdout, capture_output=True, check=True, timeout=10).stdout
    if not content:
        return False
    runner(["wl-copy"], input=content, capture_output=True, check=True, timeout=10)
    return True


def main():
    try:
        choose()
        return 0
    except (OSError, ValueError, subprocess.SubprocessError):
        print("Forge clipboard: unable to restore the selected entry", file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())

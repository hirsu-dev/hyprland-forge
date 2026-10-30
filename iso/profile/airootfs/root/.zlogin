if [[ -z ${DISPLAY:-} && $(tty) == /dev/tty1 && -f /etc/forge-live ]]; then
    plymouth quit 2>/dev/null || true
    exec startx /usr/local/bin/forge-live-session -- -nolisten tcp
fi

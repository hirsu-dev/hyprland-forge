if [[ -z ${DISPLAY:-} && $(tty) == /dev/tty1 && -f /etc/forge-live ]]; then
    exec startx /usr/local/bin/forge-live-session -- -nolisten tcp
fi

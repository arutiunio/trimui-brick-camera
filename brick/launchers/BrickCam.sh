#!/bin/bash

APP="/userdata/roms/ports/camera/camera_sdl.py"
LOG="/userdata/camera/sdl-launcher.log"

mkdir -p /userdata/camera
cd /userdata/roms/ports/camera || exit 1

unset DISPLAY
unset WAYLAND_DISPLAY
unset SDL_VIDEODRIVER

export XDG_RUNTIME_DIR=/var/run
export PYTHONFAULTHANDLER=1

echo "===== START $(date) =====" > "$LOG"

/usr/bin/python3 -u -X faulthandler "$APP" >>"$LOG" 2>&1
STATUS=$?

echo >>"$LOG"
echo "EXIT STATUS: $STATUS" >>"$LOG"
echo "===== END =====" >>"$LOG"

exit 0

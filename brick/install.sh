#!/bin/sh
set -eu

SRC_DIR="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
PORTS_DIR="/userdata/roms/ports"
CAMERA_DIR="$PORTS_DIR/camera"
GALLERY_DIR="$PORTS_DIR/gallery"
DATA_DIR="/userdata/camera"

mkdir -p "$CAMERA_DIR" "$GALLERY_DIR" "$DATA_DIR"

cp "$SRC_DIR/camera_sdl.py" "$CAMERA_DIR/camera_sdl.py"
cp "$SRC_DIR/gallery.py" "$GALLERY_DIR/gallery.py"
cp "$SRC_DIR/launchers/BrickCam.sh" "$PORTS_DIR/BrickCam.sh"
cp "$SRC_DIR/launchers/Gallery.sh" "$PORTS_DIR/Gallery.sh"

chmod +x \
  "$CAMERA_DIR/camera_sdl.py" \
  "$GALLERY_DIR/gallery.py" \
  "$PORTS_DIR/BrickCam.sh" \
  "$PORTS_DIR/Gallery.sh"

echo "BrickCam installed."
echo "Refresh the Ports list (or reboot Knulli), then launch BrickCam."

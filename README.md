# BrickCam

**BrickCam** turns a Freenove ESP32-S3 + OV3660 camera board into a camera accessory for the **TrimUI Brick** running **Knulli**. One USB-C connection carries both the MJPEG camera stream (UVC) and RGB flash control (HID).

> Status: work in progress. The current public baseline keeps the known-working 720p firmware quality setting (`q2`); the Brick UI currently exposes the tested FAST and NORMAL preview modes.

## Architecture

```text
OV3660
  ↓
ESP32-S3 (ESP-IDF)
  ├─ USB UVC  ──→ /dev/video0
  └─ USB HID  ──→ /dev/hidraw0
                    ↓
            TrimUI Brick / Knulli
                    ↓
              BrickCam SDL2 UI
```

The ESP32-S3 appears as a composite USB device. UVC carries MJPEG video and a vendor-defined HID interface controls the board's WS2812 LED on GPIO48.

## Current features

- low-latency fullscreen SDL2 preview on the TrimUI Brick
- original-MJPEG photo capture (no re-encode for stills)
- MJPEG video recording into AVI without re-encoding
- photo/video gallery
- physical Brick button controls
- selectable RGB photo flash using the ESP32-S3's onboard WS2812
- flash defaults to OFF and is forced OFF on startup/exit
- red 1 s ON / 1 s OFF recording indicator on GPIO48
- UVC + HID over one USB-C cable
- firmware advertises 1280×720 @ 15 FPS plus lower-resolution modes

## Hardware used for development

- TrimUI Brick
- Knulli (tested on Scarab)
- Freenove ESP32-S3 camera board
- OV3660 sensor
- 8 MB PSRAM
- onboard WS2812 RGB LED on GPIO48

Freenove board USB ports:

- **USB-UART** (left/upright in the development setup): flashing and serial monitor
- **USB-OTG** (native ESP32-S3 USB): connection to the TrimUI Brick

### Camera pinout

| Signal | GPIO |
| --- | ---: |
| PWDN | -1 |
| RESET | -1 |
| XCLK | 15 |
| SIOD | 4 |
| SIOC | 5 |
| VSYNC | 6 |
| HREF | 7 |
| PCLK | 13 |
| Y2 / D0 | 11 |
| Y3 / D1 | 9 |
| Y4 / D2 | 8 |
| Y5 / D3 | 10 |
| Y6 / D4 | 12 |
| Y7 / D5 | 18 |
| Y8 / D6 | 17 |
| Y9 / D7 | 16 |

XCLK is 20 MHz.

## Controls

| Brick button | Action |
| --- | --- |
| A | Take photo |
| X | Start / stop recording |
| Y | Switch camera mode |
| R1 | Cycle flash color |
| L1 | Open gallery |
| B | Back / exit |

Flash cycle:

```text
OFF → WHITE → ICE → PINK → LIME → AMBER → OFF
```

## Camera modes

The firmware UVC descriptor exposes:

| Resolution | FPS | Notes |
| ---: | ---: | --- |
| 1280×720 | 15 | HD firmware mode, q2 baseline |
| 640×480 | 15 | NORMAL mode in BrickCam UI |
| 480×320 | 30 | Advertised by firmware |
| 320×240 | 30 | FAST mode in BrickCam UI |

The current Brick UI intentionally exposes only FAST and NORMAL while HD UI integration remains under development.

For OV3660, lower `jpeg_quality` numbers mean higher JPEG quality. The repository uses **q2 at 720p** because it has been verified to stream in this setup. q0 remains an experiment; see [`docs/q0-experiment.md`](docs/q0-experiment.md).

## Repository layout

```text
trimui-brick-camera/
├── brick/
│   ├── camera_sdl.py
│   ├── gallery.py
│   ├── install.sh
│   └── launchers/
│       ├── BrickCam.sh
│       └── Gallery.sh
├── docs/
│   └── q0-experiment.md
├── esp32/
│   ├── main/
│   ├── CMakeLists.txt
│   ├── dependencies.lock
│   ├── partitions.csv
│   ├── patch_uvc_hid.py
│   └── sdkconfig.defaults
├── LICENSE
└── NOTICE
```

## Install the Brick side

The app expects these Knulli paths:

```text
/userdata/roms/ports/camera/camera_sdl.py
/userdata/roms/ports/gallery/gallery.py
/userdata/roms/ports/BrickCam.sh
/userdata/roms/ports/Gallery.sh
```

Copy the `brick` directory to the device, then run its installer as root:

```sh
cd /path/to/brick
chmod +x install.sh
./install.sh
```

After installation, refresh the Knulli Ports list or reboot and launch **BrickCam**.

Runtime output and logs are written below:

```text
/userdata/camera/
```

### Runtime requirements on Knulli

The current implementation expects:

- Python 3
- FFmpeg with V4L2 and fbdev support
- SDL2
- SDL2_ttf
- SDL2_gfx
- `/dev/video0` for the UVC camera
- `/dev/hidraw0` (or another matching hidraw node) for RGB control
- `/dev/input/event3` for the current TrimUI Brick button mapping

The input device is currently hard-coded and may need adjustment on other firmware/device revisions.

## Build and flash the ESP32-S3 firmware

The current baseline was developed with **ESP-IDF 5.5.5**. The component lock file records the tested component versions, including `esp32-camera 2.0.15`, `usb_device_uvc 1.3.1`, TinyUSB `0.19.0~3`, and `led_strip 3.0.3`.

From an ESP-IDF shell:

```sh
cd esp32
idf.py set-target esp32s3
idf.py reconfigure
python patch_uvc_hid.py
idf.py build
idf.py -p COM3 flash
```

Replace `COM3` with the USB-UART port used by your board. On Linux/macOS use the appropriate serial device.

`idf.py reconfigure` downloads the managed components first. `patch_uvc_hid.py` then adds the HID interface to Espressif's managed UVC component. Run the patch **after** dependency/reconfigure steps that recreate `managed_components`.

To monitor the ESP32:

```sh
idf.py -p COM3 monitor
```

Connect the board's native **USB-OTG** port to the TrimUI Brick for UVC/HID operation. USB-UART and USB-OTG can be connected simultaneously while debugging.

## HID flash protocol

BrickCam writes a 65-byte hidraw packet:

```text
byte 0  report ID (0)
byte 1  command
byte 2  R
byte 3  G
byte 4  B
bytes 5..64  zero padding
```

Commands:

- `0` — LED OFF
- `1` — set RGB

Example colors used by the UI:

```text
WHITE  255 255 255
ICE    100 210 255
PINK   255  80 180
LIME   150 255  60
AMBER  255 150  35
REC    255   0   0
```

## Known limitations

- HD is supported by the firmware but is not yet exposed as a selectable mode in the Brick UI.
- OV3660 q0 at 720p currently fails with repeated `NO-EOI` capture errors in the tested driver path even after increasing the JPEG/UVC buffers to 512 KiB.
- Button input currently assumes `/dev/input/event3`.
- The HID integration is applied by a patch script to a pinned managed component rather than implemented as a standalone USB descriptor component.
- This repository currently targets the specific Freenove ESP32-S3 + OV3660 hardware used for development.

## License

Apache-2.0. The ESP32 firmware contains code derived from Espressif examples; upstream copyright/SPDX notices are retained. See [`NOTICE`](NOTICE).

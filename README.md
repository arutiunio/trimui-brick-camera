# BrickCam

**BrickCam** is a camera project for the **TrimUI Brick** handheld running **Knulli**, using an **ESP32-S3 + OV3660** camera board as a USB camera and control device.

The repository name is `trimui-brick-camera`; the project itself is called **BrickCam**.

## What it does

BrickCam turns an ESP32-S3 camera board into a single-cable accessory for the TrimUI Brick:

```text
OV3660
  ↓
ESP32-S3
  ├─ USB UVC  → /dev/video0
  └─ USB HID  → /dev/hidraw0
       ↓
TrimUI Brick / Knulli
       ↓
BrickCam SDL2 app
```

Current functionality includes:

- live camera preview on the TrimUI Brick
- photo capture
- MJPEG video recording without unnecessary re-encoding
- gallery for photos and videos
- hardware button controls
- onboard ESP32-S3 RGB LED used as a configurable photo flash
- red recording indicator on the ESP32-S3 LED
- composite USB device: UVC camera + HID control over one USB-C cable
- experimental 1280×720 @ 15 FPS mode

## Hardware

Current development hardware:

- TrimUI Brick
- Knulli
- Freenove ESP32-S3 camera board
- OV3660 camera sensor
- 8 MB PSRAM
- onboard WS2812 RGB LED on GPIO48
- one USB-C OTG connection between ESP32-S3 and TrimUI Brick

The Freenove board has two USB-C ports:

- **USB-UART** — flashing/debugging from a PC
- **USB-OTG** — UVC + HID connection to the TrimUI Brick

## Controls

| Button | Action |
| --- | --- |
| A | Take photo |
| X | Start / stop recording |
| Y | Change camera mode |
| R1 | Cycle flash color |
| L1 | Open gallery |
| B | Back / exit |

Current flash cycle:

```text
OFF → WHITE → ICE → PINK → LIME → AMBER → OFF
```

The flash is **OFF by default**.

While recording, GPIO48 blinks red at approximately:

```text
1 second ON / 1 second OFF
```

## USB devices on Knulli

When the ESP32-S3 is connected to the Brick through its native USB-OTG port:

```text
/dev/video0   UVC camera
/dev/hidraw0  HID LED/flash control
```

The current HID report is 65 bytes:

```text
[report_id, command, R, G, B, ...padding]
```

Commands:

- `0` — LED off
- `1` — set RGB color

## Camera modes

The currently proven capture modes are:

| Mode | Resolution | FPS | Status |
| --- | ---: | ---: | --- |
| Fast | 320×240 | ~30 | Working |
| Normal | 640×480 | 15 | Working |
| HD | 1280×720 | 15 | Experimental / tuning |

For 720p, OV3660 JPEG quality and camera/UVC frame-buffer limits are being tested to find the highest stable image quality.

## Software architecture

### TrimUI Brick side

The frontend is a native **SDL2** application written in Python using `ctypes`.

FFmpeg is used for:

- V4L2 MJPEG input
- decoding preview frames to YUV420P
- preserving the original MJPEG stream for photos/video

The preview path intentionally drops stale frames to keep latency low.

### ESP32-S3 side

Firmware is based on ESP-IDF and Espressif components:

- `esp32-camera`
- `usb_device_uvc`
- TinyUSB
- `led_strip`

The ESP32-S3 exposes a composite USB device containing:

- UVC video
- generic HID

CDC ACM is intentionally not required because the current TrimUI Brick kernel does not provide USB ACM support.

## Knulli paths

Current development paths on the Brick:

```text
/userdata/roms/ports/camera/camera_sdl.py
/userdata/roms/ports/camera/camera.py
/userdata/roms/ports/camera/gallery/gallery.py
/userdata/roms/ports/Camera SDL.sh
/userdata/roms/ports/Gallery.sh
```

Camera output/logs are stored under:

```text
/userdata/camera/
```

## Development status

BrickCam is currently a work in progress.

Working:

- UVC camera enumeration
- HID control
- SDL2/Mali rendering
- low-latency preview
- photos
- video recording
- gallery
- RGB flash
- recording LED
- 720p15 UVC enumeration and transport at practical JPEG quality levels

In progress:

- maximum-quality OV3660 JPEG at 720p
- HD mode integration into the SDL UI
- cleaner installation/package layout
- documentation and reproducible firmware configuration

## Planned repository layout

```text
trimui-brick-camera/
├── README.md
├── brick/
│   ├── camera_sdl.py
│   ├── gallery.py
│   └── launchers/
├── esp32/
│   ├── main/
│   ├── CMakeLists.txt
│   └── sdkconfig.defaults
└── docs/
```

## Notes

This project is currently developed specifically around the TrimUI Brick + Knulli + Freenove ESP32-S3/OV3660 combination. Support for other handhelds or camera boards may be possible later but is not yet a design guarantee.

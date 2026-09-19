# OV3660 720p q0 experiment

BrickCam currently ships the **q2** JPEG-quality setting for 1280×720 because it is the highest setting that has been verified to stream reliably in the current setup. On the OV3660 driver used here, a lower numeric `jpeg_quality` value means higher JPEG quality.

## Observed q0 behavior

With 1280×720 at 15 FPS and `jpeg_quality = 0`, the camera initialized successfully but FFmpeg on the TrimUI Brick never received a usable first frame. The ESP32 serial log repeatedly reported:

```text
cam_hal: NO-EOI
usbd_uvc: Failed to capture picture
```

The initial automatic camera JPEG framebuffer was 184320 bytes (`1280 × 720 / 5`). Increasing both the camera JPEG framebuffer and the UVC frame buffer to 512 KiB changed the camera allocation to 524288 bytes, but the repeated `NO-EOI` condition remained. This shows that the q0 failure is not explained solely by the original 184320-byte framebuffer limit.

## Current baseline

The repository therefore keeps:

```text
1280×720 @ 15 FPS
OV3660 jpeg_quality = 2
UVC max frame buffer = 200 KiB
JPEG framebuffer = automatic
```

Further q0 work should be done on a separate branch/commit so the known-working q2 baseline stays easy to recover.

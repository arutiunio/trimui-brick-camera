# Flashing BrickCam firmware

BrickCam's GitHub Actions workflow builds the ESP32-S3 firmware with ESP-IDF 5.5.5 and publishes a `brickcam-esp32s3` artifact for every successful firmware build.

## Use a CI artifact

1. Open the repository's **Actions** tab.
2. Open a successful **ESP32 firmware build** run.
3. Download the `brickcam-esp32s3` artifact.
4. Extract it.

The artifact contains:

```text
bootloader/bootloader.bin
partition_table/partition-table.bin
usb_webcam.bin
flasher_args.json
flash_args
```

Connect the Freenove board's **USB-UART** port to the computer. With Python/esptool installed, flash the extracted files with:

```sh
python -m esptool --chip esp32s3 -b 460800 \
  --before default_reset --after hard_reset \
  write_flash \
  --flash_mode dio --flash_size 4MB --flash_freq 80m \
  0x0 bootloader/bootloader.bin \
  0x8000 partition_table/partition-table.bin \
  0x10000 usb_webcam.bin
```

The generated `flasher_args.json` and `flash_args` files contain the same offsets/settings used by ESP-IDF.

## Build and flash from source

From an ESP-IDF 5.5.5 shell:

```sh
cd esp32
idf.py set-target esp32s3
idf.py reconfigure
python patch_uvc_hid.py
idf.py build
idf.py -p COM3 flash
```

Replace `COM3` with the board's USB-UART serial port.

The native **USB-OTG** port is the camera connection to the TrimUI Brick. USB-UART and USB-OTG can remain connected at the same time during debugging.

## Serial monitor

```sh
idf.py -p COM3 monitor
```

Use `Ctrl+]` to leave the ESP-IDF serial monitor.

#!/usr/bin/env python3

import os
import struct
import select
import subprocess
import signal
import time

INPUT_DEV = "/dev/input/event3"

PHOTO_DIR = "/userdata/camera/photos"
VIDEO_DIR = "/userdata/camera/videos"

BASE_DIR = "/userdata/camera"
STATUS_FILE = BASE_DIR + "/gallery_status.txt"
LOG_FILE = BASE_DIR + "/gallery.log"

BUTTON_A = 305
BUTTON_B = 304

EV_KEY = 1
EV_ABS = 3

ABS_HAT0X = 16

os.makedirs(BASE_DIR, exist_ok=True)

log = open(LOG_FILE, "w", buffering=1)


def logmsg(text):
    print(text, file=log)


def write_status(text):
    tmp = STATUS_FILE + ".tmp"

    with open(tmp, "w", encoding="utf-8") as f:
        f.write(text)

    os.replace(tmp, STATUS_FILE)


def get_files():
    files = []

    if os.path.isdir(PHOTO_DIR):
        for name in os.listdir(PHOTO_DIR):
            if name.lower().endswith((".jpg", ".jpeg", ".png")):
                files.append(
                    ("photo", os.path.join(PHOTO_DIR, name))
                )

    if os.path.isdir(VIDEO_DIR):
        for name in os.listdir(VIDEO_DIR):
            if name.lower().endswith(
                (".avi", ".mp4", ".mkv", ".mov")
            ):
                files.append(
                    ("video", os.path.join(VIDEO_DIR, name))
                )

    files.sort(
        key=lambda item: os.path.getmtime(item[1]),
        reverse=True
    )

    return files


def make_filter():
    return (
        "scale=1024:768:"
        "force_original_aspect_ratio=decrease,"
        "pad=1024:768:(ow-iw)/2:(oh-ih)/2:black,"
        "drawtext="
            f"textfile='{STATUS_FILE}':"
            "reload=1:"
            "fontcolor=white:"
            "fontsize=28:"
            "box=1:"
            "boxcolor=black@0.60:"
            "boxborderw=12:"
            "x=(w-text_w)/2:"
            "y=h-text_h-26"
    )


def render_selected(files, index):
    kind, path = files[index]

    name = os.path.basename(path)

    if kind == "photo":
        status = (
            f"{index + 1}/{len(files)}   "
            f"PHOTO   "
            f"LEFT/RIGHT BROWSE   B EXIT"
        )
    else:
        status = (
            f"{index + 1}/{len(files)}   "
            f"VIDEO   "
            f"A PLAY   LEFT/RIGHT BROWSE   B EXIT"
        )

    write_status(status)

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",
    ]

    if kind == "video":
        cmd += [
            "-ss", "0",
        ]

    cmd += [
        "-i", path,
        "-frames:v", "1",
        "-vf", make_filter(),
        "-pix_fmt", "bgra",
        "-f", "fbdev",
        "/dev/fb0",
    ]

    subprocess.run(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=log,
    )

    logmsg("SHOW: " + name)


def render_empty():
    write_status("NO PHOTOS OR VIDEOS   B EXIT")

    subprocess.run(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",
            "-f", "lavfi",
            "-i", "color=c=black:s=1024x768:r=1",
            "-frames:v", "1",
            "-vf", make_filter(),
            "-pix_fmt", "bgra",
            "-f", "fbdev",
            "/dev/fb0",
        ],
        stdout=subprocess.DEVNULL,
        stderr=log,
    )


def play_video(path, event_fd, event_struct):
    write_status("PLAYING VIDEO   B STOP")

    player = subprocess.Popen(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",

            "-re",
            "-i", path,

            "-an",
            "-vf", make_filter(),
            "-pix_fmt", "bgra",
            "-f", "fbdev",
            "/dev/fb0",
        ],
        stdout=subprocess.DEVNULL,
        stderr=log,
    )

    try:
        while player.poll() is None:

            ready, _, _ = select.select(
                [event_fd],
                [],
                [],
                0.1
            )

            if not ready:
                continue

            try:
                data = os.read(
                    event_fd,
                    event_struct.size * 32
                )
            except BlockingIOError:
                continue

            for pos in range(
                0,
                len(data) - event_struct.size + 1,
                event_struct.size
            ):

                sec, usec, ev_type, code, value = \
                    event_struct.unpack_from(data, pos)

                if (
                    ev_type == EV_KEY
                    and code == BUTTON_B
                    and value == 1
                ):
                    player.terminate()

                    try:
                        player.wait(timeout=2)
                    except Exception:
                        player.kill()

                    return

    finally:
        if player.poll() is None:
            player.terminate()


files = get_files()

event_struct = struct.Struct("llHHi")

event_fd = os.open(
    INPUT_DEV,
    os.O_RDONLY | os.O_NONBLOCK
)

index = 0
running = True

try:

    if not files:
        render_empty()
    else:
        render_selected(files, index)

    while running:

        ready, _, _ = select.select(
            [event_fd],
            [],
            [],
            0.2
        )

        if not ready:
            continue

        try:
            data = os.read(
                event_fd,
                event_struct.size * 32
            )
        except BlockingIOError:
            continue

        for pos in range(
            0,
            len(data) - event_struct.size + 1,
            event_struct.size
        ):

            sec, usec, ev_type, code, value = \
                event_struct.unpack_from(data, pos)

            # B = EXIT
            if (
                ev_type == EV_KEY
                and code == BUTTON_B
                and value == 1
            ):
                running = False
                break

            if not files:
                continue

            # LEFT / RIGHT
            if (
                ev_type == EV_ABS
                and code == ABS_HAT0X
            ):

                if value == -1:
                    index = (index - 1) % len(files)
                    render_selected(files, index)

                elif value == 1:
                    index = (index + 1) % len(files)
                    render_selected(files, index)

            # A = PLAY VIDEO
            if (
                ev_type == EV_KEY
                and code == BUTTON_A
                and value == 1
            ):

                kind, path = files[index]

                if kind == "video":
                    play_video(
                        path,
                        event_fd,
                        event_struct
                    )

                    render_selected(files, index)

finally:

    try:
        os.close(event_fd)
    except Exception:
        pass

    log.close()

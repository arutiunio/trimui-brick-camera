#!/usr/bin/env python3
import ctypes
import fcntl
import glob
import os
import select
import struct
import subprocess
import time
from datetime import datetime

VIDEO_DEV = "/dev/video0"
INPUT_DEV = "/dev/input/event3"
GALLERY_APP = "/userdata/roms/ports/gallery/gallery.py"

BASE_DIR = "/userdata/camera"
PHOTO_DIR = BASE_DIR + "/photos"
VIDEO_DIR = BASE_DIR + "/videos"
LOG_FILE = BASE_DIR + "/camera_sdl.log"

LOGICAL_W = 1024
LOGICAL_H = 768

BUTTON_A = 305
BUTTON_B = 304
BUTTON_X = 307
BUTTON_Y = 308
BUTTON_L1 = 310
BUTTON_R1 = 311

MODES = [
    {"name": "FAST", "width": 320, "height": 240, "fps": 30},
    {"name": "NORMAL", "width": 640, "height": 480, "fps": 15},
]
mode_index = 1

FLASH_MODES = [
    ("OFF", None),
    ("WHITE", (255, 255, 255)),
    ("ICE", (100, 210, 255)),
    ("PINK", (255, 80, 180)),
    ("LIME", (150, 255, 60)),
    ("AMBER", (255, 150, 35)),
]
flash_index = 0

REC_LED_RGB = (255, 0, 0)
REC_LED_ON_TIME = 1.0
REC_LED_OFF_TIME = 1.0

os.makedirs(PHOTO_DIR, exist_ok=True)
os.makedirs(VIDEO_DIR, exist_ok=True)
log = open(LOG_FILE, "w", buffering=1)

def logmsg(s):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {s}", file=log)

def now_name():
    return datetime.now().strftime("%Y-%m-%d_%H-%M-%S")

def current_mode():
    return MODES[mode_index]

# ---------- HID flash ----------
def find_flash_hid():
    if os.path.exists("/dev/hidraw0"):
        return "/dev/hidraw0"
    for p in sorted(glob.glob("/dev/hidraw*")):
        name = os.path.basename(p)
        uevent = f"/sys/class/hidraw/{name}/device/uevent"
        try:
            text = open(uevent, "r", encoding="utf-8", errors="ignore").read().upper()
        except Exception:
            continue
        if ("303A" in text and "8000" in text) or "ESP UVC DEVICE" in text:
            return p
    return None

flash_dev = find_flash_hid()
flash_fd = None
flash_is_on = False
if flash_dev:
    try:
        flash_fd = os.open(flash_dev, os.O_WRONLY)
        logmsg("HID " + flash_dev)
    except Exception as e:
        logmsg("HID open failed: " + repr(e))

def hid_send(cmd, r=0, g=0, b=0):
    global flash_fd
    if flash_fd is None:
        return False
    packet = bytes([0, cmd, r, g, b]) + bytes(60)
    try:
        return os.write(flash_fd, packet) == 65
    except Exception as e:
        logmsg("HID write failed: " + repr(e))
        try:
            os.close(flash_fd)
        except Exception:
            pass
        flash_fd = None
        return False

def flash_off():
    global flash_is_on
    hid_send(0)
    flash_is_on = False

def flash_on(rgb):
    global flash_is_on
    if rgb is None:
        return False
    flash_is_on = hid_send(1, *rgb)
    return flash_is_on

flash_off()

# ---------- SDL ----------
class SDL_Rect(ctypes.Structure):
    _fields_ = [
        ("x", ctypes.c_int), ("y", ctypes.c_int),
        ("w", ctypes.c_int), ("h", ctypes.c_int),
    ]

class SDL_Color(ctypes.Structure):
    _fields_ = [
        ("r", ctypes.c_uint8), ("g", ctypes.c_uint8),
        ("b", ctypes.c_uint8), ("a", ctypes.c_uint8),
    ]

SDL = ctypes.CDLL("/usr/lib/libSDL2-2.0.so.0")
TTF = ctypes.CDLL("/usr/lib/libSDL2_ttf-2.0.so.0")
GFX = ctypes.CDLL("/usr/lib/libSDL2_gfx-1.0.so.0")

SDL.SDL_Init.argtypes = [ctypes.c_uint32]
SDL.SDL_Init.restype = ctypes.c_int
SDL.SDL_Quit.argtypes = []
SDL.SDL_GetError.restype = ctypes.c_char_p

SDL.SDL_CreateWindow.argtypes = [
    ctypes.c_char_p, ctypes.c_int, ctypes.c_int,
    ctypes.c_int, ctypes.c_int, ctypes.c_uint32,
]
SDL.SDL_CreateWindow.restype = ctypes.c_void_p
SDL.SDL_DestroyWindow.argtypes = [ctypes.c_void_p]

SDL.SDL_CreateRenderer.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_uint32]
SDL.SDL_CreateRenderer.restype = ctypes.c_void_p
SDL.SDL_DestroyRenderer.argtypes = [ctypes.c_void_p]

SDL.SDL_RenderSetLogicalSize.argtypes = [ctypes.c_void_p, ctypes.c_int, ctypes.c_int]
SDL.SDL_SetRenderDrawBlendMode.argtypes = [ctypes.c_void_p, ctypes.c_int]
SDL.SDL_SetRenderDrawColor.argtypes = [
    ctypes.c_void_p, ctypes.c_uint8, ctypes.c_uint8,
    ctypes.c_uint8, ctypes.c_uint8,
]
SDL.SDL_RenderClear.argtypes = [ctypes.c_void_p]
SDL.SDL_RenderPresent.argtypes = [ctypes.c_void_p]
SDL.SDL_RenderCopy.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p,
    ctypes.c_void_p, ctypes.POINTER(SDL_Rect),
]

SDL.SDL_CreateTexture.argtypes = [
    ctypes.c_void_p, ctypes.c_uint32, ctypes.c_int,
    ctypes.c_int, ctypes.c_int,
]
SDL.SDL_CreateTexture.restype = ctypes.c_void_p
SDL.SDL_DestroyTexture.argtypes = [ctypes.c_void_p]

SDL.SDL_UpdateYUVTexture.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p,
    ctypes.c_void_p, ctypes.c_int,
    ctypes.c_void_p, ctypes.c_int,
    ctypes.c_void_p, ctypes.c_int,
]
SDL.SDL_UpdateYUVTexture.restype = ctypes.c_int

SDL.SDL_CreateTextureFromSurface.argtypes = [ctypes.c_void_p, ctypes.c_void_p]
SDL.SDL_CreateTextureFromSurface.restype = ctypes.c_void_p
SDL.SDL_FreeSurface.argtypes = [ctypes.c_void_p]
SDL.SDL_QueryTexture.argtypes = [
    ctypes.c_void_p, ctypes.c_void_p, ctypes.c_void_p,
    ctypes.POINTER(ctypes.c_int), ctypes.POINTER(ctypes.c_int),
]
SDL.SDL_SetTextureAlphaMod.argtypes = [ctypes.c_void_p, ctypes.c_uint8]
SDL.SDL_ShowCursor.argtypes = [ctypes.c_int]

TTF.TTF_Init.restype = ctypes.c_int
TTF.TTF_Quit.argtypes = []
TTF.TTF_OpenFont.argtypes = [ctypes.c_char_p, ctypes.c_int]
TTF.TTF_OpenFont.restype = ctypes.c_void_p
TTF.TTF_CloseFont.argtypes = [ctypes.c_void_p]
TTF.TTF_RenderUTF8_Blended.argtypes = [ctypes.c_void_p, ctypes.c_char_p, SDL_Color]
TTF.TTF_RenderUTF8_Blended.restype = ctypes.c_void_p

gfx_funcs = {
    "roundedBoxRGBA": [
        ctypes.c_void_p,
        ctypes.c_short, ctypes.c_short, ctypes.c_short, ctypes.c_short,
        ctypes.c_short,
        ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8,
    ],
    "roundedRectangleRGBA": [
        ctypes.c_void_p,
        ctypes.c_short, ctypes.c_short, ctypes.c_short, ctypes.c_short,
        ctypes.c_short,
        ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8,
    ],
    "filledCircleRGBA": [
        ctypes.c_void_p,
        ctypes.c_short, ctypes.c_short, ctypes.c_short,
        ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8,
    ],
    "aacircleRGBA": [
        ctypes.c_void_p,
        ctypes.c_short, ctypes.c_short, ctypes.c_short,
        ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8,
    ],
    "boxRGBA": [
        ctypes.c_void_p,
        ctypes.c_short, ctypes.c_short, ctypes.c_short, ctypes.c_short,
        ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8, ctypes.c_uint8,
    ],
}
for fn, args in gfx_funcs.items():
    getattr(GFX, fn).argtypes = args

def sdl_error():
    e = SDL.SDL_GetError()
    return e.decode("utf-8", "replace") if e else "unknown"

def find_font(bold=False):
    names = ["DejaVuSans-Bold.ttf"] if bold else ["DejaVuSans.ttf"]
    bases = [
        "/usr/share/fonts/truetype/dejavu",
        "/usr/share/fonts/dejavu",
        "/usr/share/fonts/TTF",
    ]
    for base in bases:
        for name in names:
            p = base + "/" + name
            if os.path.exists(p):
                return p
    fonts = glob.glob("/usr/share/fonts/**/*.ttf", recursive=True)
    if fonts:
        return fonts[0]
    raise RuntimeError("No TTF font found")

SDL_INIT_VIDEO = 0x20
SDL_WINDOW_FULLSCREEN_DESKTOP = 0x1001
SDL_RENDERER_ACCELERATED = 0x2
SDL_RENDERER_PRESENTVSYNC = 0x4
SDL_TEXTUREACCESS_STREAMING = 1
SDL_BLENDMODE_BLEND = 1
SDL_PIXELFORMAT_IYUV = (
    ord("I") |
    (ord("Y") << 8) |
    (ord("U") << 16) |
    (ord("V") << 24)
)

if SDL.SDL_Init(SDL_INIT_VIDEO) != 0:
    raise SystemExit("SDL_Init failed: " + sdl_error())
if TTF.TTF_Init() != 0:
    raise SystemExit("TTF_Init failed")

window = SDL.SDL_CreateWindow(
    b"Camera",
    0, 0,
    LOGICAL_W, LOGICAL_H,
    SDL_WINDOW_FULLSCREEN_DESKTOP,
)
if not window:
    raise SystemExit("SDL_CreateWindow failed: " + sdl_error())

renderer = SDL.SDL_CreateRenderer(
    window, -1,
    SDL_RENDERER_ACCELERATED | SDL_RENDERER_PRESENTVSYNC,
)
if not renderer:
    renderer = SDL.SDL_CreateRenderer(window, -1, 0)
if not renderer:
    raise SystemExit("SDL_CreateRenderer failed: " + sdl_error())

SDL.SDL_RenderSetLogicalSize(renderer, LOGICAL_W, LOGICAL_H)
SDL.SDL_SetRenderDrawBlendMode(renderer, SDL_BLENDMODE_BLEND)
SDL.SDL_ShowCursor(0)

font_path = find_font(False)
bold_path = find_font(True)

font_micro = TTF.TTF_OpenFont(font_path.encode(), 15)
font_small = TTF.TTF_OpenFont(font_path.encode(), 18)
font_medium = TTF.TTF_OpenFont(font_path.encode(), 22)
font_bold = TTF.TTF_OpenFont(bold_path.encode(), 22)
font_big = TTF.TTF_OpenFont(bold_path.encode(), 27)
fonts = [font_micro, font_small, font_medium, font_bold, font_big]

text_cache = {}

def text_tex(text, font, color=(240, 248, 250, 255)):
    key = (text, int(font), color)
    if key in text_cache:
        return text_cache[key]

    surface = TTF.TTF_RenderUTF8_Blended(
        font,
        text.encode("utf-8"),
        SDL_Color(*color),
    )
    if not surface:
        return None

    texture = SDL.SDL_CreateTextureFromSurface(renderer, surface)
    SDL.SDL_FreeSurface(surface)
    if not texture:
        return None

    w = ctypes.c_int()
    h = ctypes.c_int()
    SDL.SDL_QueryTexture(
        texture, None, None,
        ctypes.byref(w), ctypes.byref(h),
    )

    item = (texture, w.value, h.value)
    text_cache[key] = item
    return item

def draw_text(
    text, x, y,
    font=font_small,
    color=(240, 248, 250, 255),
    alpha=255,
    center=False,
):
    item = text_tex(text, font, color)
    if not item:
        return

    texture, w, h = item
    SDL.SDL_SetTextureAlphaMod(
        texture,
        max(0, min(255, int(alpha))),
    )

    if center:
        x -= w // 2

    rect = SDL_Rect(int(x), int(y), w, h)
    SDL.SDL_RenderCopy(
        renderer, texture, None,
        ctypes.byref(rect),
    )
    SDL.SDL_SetTextureAlphaMod(texture, 255)

def glass(x, y, w, h, radius=16, accent=False, alpha=174):
    GFX.roundedBoxRGBA(
        renderer,
        x + 3, y + 4,
        x + w + 3, y + h + 4,
        radius,
        0, 0, 0, 55,
    )
    GFX.roundedBoxRGBA(
        renderer,
        x, y,
        x + w, y + h,
        radius,
        8, 14, 20, alpha,
    )

    if accent:
        r, g, b = 130, 235, 255
    else:
        r, g, b = 170, 195, 210

    GFX.roundedRectangleRGBA(
        renderer,
        x, y,
        x + w, y + h,
        radius,
        r, g, b, 105,
    )
    GFX.roundedRectangleRGBA(
        renderer,
        x + 2, y + 2,
        x + w - 2, y + h - 2,
        max(1, radius - 2),
        255, 255, 255, 18,
    )

def badge(cx, cy, label):
    GFX.filledCircleRGBA(
        renderer,
        cx, cy, 21,
        7, 12, 18, 210,
    )
    GFX.aacircleRGBA(
        renderer,
        cx, cy, 21,
        145, 238, 255, 205,
    )
    draw_text(
        label,
        cx, cy - 10,
        font_bold,
        (174, 244, 255, 255),
        center=True,
    )

def draw_button(cx, label, key):
    badge(cx, 704, key)
    draw_text(
        label,
        cx + 31, 695,
        font_micro,
        (235, 245, 248, 255),
    )

# ---------- Capture ----------
capture = None
mjpeg_r = None
mjpeg_w = None
camera_texture = None

preview_ready = False
preview_warmup = 0

raw = bytearray()
jpeg_buffer = bytearray()

y_size = 0
uv_size = 0
raw_frame_size = 0

def stop_capture():
    global capture, mjpeg_r, mjpeg_w
    global camera_texture, raw, jpeg_buffer
    global preview_ready, preview_warmup

    if capture is not None:
        try:
            capture.terminate()
            capture.wait(timeout=2)
        except Exception:
            try:
                capture.kill()
            except Exception:
                pass
        capture = None

    if mjpeg_r is not None:
        try:
            os.close(mjpeg_r)
        except Exception:
            pass
        mjpeg_r = None

    if mjpeg_w is not None:
        try:
            os.close(mjpeg_w)
        except Exception:
            pass
        mjpeg_w = None

    if camera_texture:
        SDL.SDL_DestroyTexture(camera_texture)
        camera_texture = None

    raw = bytearray()
    jpeg_buffer = bytearray()

    preview_ready = False
    preview_warmup = 0

def start_capture():
    global capture, mjpeg_r, mjpeg_w
    global camera_texture, raw, jpeg_buffer
    global y_size, uv_size, raw_frame_size
    global preview_ready, preview_warmup

    stop_capture()

    m = current_mode()

    preview_ready = False

    # Первые кадры после старта/reconfigure UVC
    # не показываем.
    # NORMAL: ~0.20 сек
    # FAST:   ~0.17 сек
    preview_warmup = (
        5 if m["fps"] >= 25 else 3
    )

    camera_texture = SDL.SDL_CreateTexture(
        renderer,
        SDL_PIXELFORMAT_IYUV,
        SDL_TEXTUREACCESS_STREAMING,
        m["width"], m["height"],
    )
    if not camera_texture:
        raise RuntimeError(
            "Camera texture failed: " + sdl_error()
        )

    y_size = m["width"] * m["height"]
    uv_size = (m["width"] // 2) * (m["height"] // 2)
    raw_frame_size = y_size + uv_size * 2

    mjpeg_r, mjpeg_w = os.pipe()

    try:
        fcntl.fcntl(
            mjpeg_r,
            fcntl.F_SETPIPE_SZ,
            1024 * 1024,
        )
    except Exception:
        pass

    os.set_blocking(mjpeg_r, False)

    cmd = [
        "ffmpeg",
        "-hide_banner",
        "-loglevel", "error",

        "-fflags", "nobuffer",
        "-flags", "low_delay",
        "-analyzeduration", "0",
        "-probesize", "32",
        "-thread_queue_size", "1",

        "-f", "v4l2",
        "-input_format", "mjpeg",
        "-video_size",
        f"{m['width']}x{m['height']}",
        "-framerate", str(m["fps"]),
        "-i", VIDEO_DEV,

        # Low-latency SDL preview
        "-map", "0:v:0",
        "-pix_fmt", "yuv420p",
        "-f", "rawvideo",
        "pipe:1",

        # Original MJPEG for photos/video
        "-map", "0:v:0",
        "-c:v", "copy",
        "-f", "mjpeg",
        f"pipe:{mjpeg_w}",
    ]

    capture = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=log,
        bufsize=0,
        pass_fds=(mjpeg_w,),
    )

    os.close(mjpeg_w)
    mjpeg_w = None

    os.set_blocking(
        capture.stdout.fileno(),
        False,
    )

    raw = bytearray()
    jpeg_buffer = bytearray()

    logmsg(
        f"CAPTURE {m['name']} "
        f"{m['width']}x{m['height']} @{m['fps']}"
    )

# ---------- Photo / recording ----------
recorder = None
recording_path = None
recording_started_at = None

rec_led_is_on = False
rec_led_next_toggle = 0.0

photo_pending = False
photo_wait_frames = 0
photo_flash_deadline = 0.0

toast_text = ""
toast_until = 0.0
toast_started = 0.0

screen_flash_until = 0.0
screen_flash_started = 0.0

def set_toast(text, seconds=0.9):
    global toast_text, toast_until, toast_started

    toast_text = text
    toast_started = time.monotonic()
    toast_until = toast_started + seconds

def recording_led_start():
    global rec_led_is_on, rec_led_next_toggle

    if flash_fd is None:
        return

    hid_send(1, *REC_LED_RGB)
    rec_led_is_on = True
    rec_led_next_toggle = (
        time.monotonic() + REC_LED_ON_TIME
    )

def recording_led_stop():
    global rec_led_is_on, rec_led_next_toggle

    flash_off()
    rec_led_is_on = False
    rec_led_next_toggle = 0.0

def recording_led_tick():
    global rec_led_is_on, rec_led_next_toggle

    if recorder is None or flash_fd is None:
        return

    now = time.monotonic()

    if now < rec_led_next_toggle:
        return

    if rec_led_is_on:
        flash_off()
        rec_led_is_on = False
        rec_led_next_toggle = (
            now + REC_LED_OFF_TIME
        )
    else:
        hid_send(1, *REC_LED_RGB)
        rec_led_is_on = True
        rec_led_next_toggle = (
            now + REC_LED_ON_TIME
        )

def start_recording():
    global recorder
    global recording_path
    global recording_started_at

    if recorder is not None:
        return

    m = current_mode()

    recording_path = os.path.join(
        VIDEO_DIR,
        (
            f"VID_{now_name()}_"
            f"{m['width']}x{m['height']}.avi"
        ),
    )

    recorder = subprocess.Popen(
        [
            "ffmpeg",
            "-hide_banner",
            "-loglevel", "error",

            "-f", "mjpeg",
            "-framerate", str(m["fps"]),
            "-i", "pipe:0",

            "-c:v", "copy",
            "-f", "avi",
            recording_path,
        ],
        stdin=subprocess.PIPE,
        stdout=subprocess.DEVNULL,
        stderr=log,
        bufsize=0,
    )

    recording_started_at = time.monotonic()
    recording_led_start()
    set_toast("REC START", 0.65)

    logmsg("REC START " + recording_path)

def stop_recording():
    global recorder
    global recording_path
    global recording_started_at

    if recorder is None:
        return

    recording_led_stop()

    try:
        recorder.stdin.close()
    except Exception:
        pass

    try:
        recorder.wait(timeout=4)
    except Exception:
        try:
            recorder.terminate()
            recorder.wait(timeout=1)
        except Exception:
            try:
                recorder.kill()
            except Exception:
                pass

    logmsg("REC STOP " + str(recording_path))

    recorder = None
    recording_path = None
    recording_started_at = None

    set_toast("REC SAVED", 0.8)

def request_photo():
    global photo_pending
    global photo_wait_frames
    global photo_flash_deadline

    if photo_pending:
        return

    if recorder is not None:
        set_toast("STOP REC FIRST", 0.9)
        return

    rgb = FLASH_MODES[flash_index][1]

    photo_pending = True
    photo_wait_frames = 0
    photo_flash_deadline = 0.0

    if rgb is not None and flash_fd is not None:
        if flash_on(rgb):
            if current_mode()["fps"] >= 25:
                photo_wait_frames = 5
            else:
                photo_wait_frames = 3

            photo_flash_deadline = (
                time.monotonic() + 1.25
            )
        else:
            set_toast("FLASH ERROR", 0.9)

def save_photo(frame):
    global photo_pending
    global photo_wait_frames
    global photo_flash_deadline
    global screen_flash_until
    global screen_flash_started

    m = current_mode()

    path = os.path.join(
        PHOTO_DIR,
        (
            f"IMG_{now_name()}_"
            f"{m['width']}x{m['height']}.jpg"
        ),
    )

    with open(path, "wb") as f:
        f.write(frame)

    flash_off()

    photo_pending = False
    photo_wait_frames = 0
    photo_flash_deadline = 0.0

    screen_flash_started = time.monotonic()
    screen_flash_until = (
        screen_flash_started + 0.17
    )

    set_toast("SAVED", 0.9)
    logmsg("PHOTO " + path)

def feed_jpeg(frame):
    global photo_wait_frames

    if photo_pending:
        if photo_wait_frames > 0:
            photo_wait_frames -= 1
        else:
            save_photo(frame)

    if recorder is not None:
        try:
            recorder.stdin.write(frame)
        except (BrokenPipeError, OSError):
            stop_recording()

def parse_mjpeg():
    global jpeg_buffer

    while True:
        soi = jpeg_buffer.find(b"\xff\xd8")

        if soi < 0:
            if len(jpeg_buffer) > 1:
                jpeg_buffer = jpeg_buffer[-1:]
            return

        if soi > 0:
            del jpeg_buffer[:soi]

        eoi = jpeg_buffer.find(
            b"\xff\xd9",
            2,
        )
        next_soi = jpeg_buffer.find(
            b"\xff\xd8",
            2,
        )

        if (
            next_soi >= 0
            and (
                eoi < 0
                or next_soi < eoi
            )
        ):
            del jpeg_buffer[:next_soi]
            continue

        if eoi < 0:
            return

        frame = bytes(
            jpeg_buffer[:eoi + 2]
        )
        del jpeg_buffer[:eoi + 2]

        feed_jpeg(frame)

# ---------- Input ----------
event_struct = struct.Struct("llHHi")
event_fd = os.open(
    INPUT_DEV,
    os.O_RDONLY | os.O_NONBLOCK,
)

# ---------- UI ----------
def flash_color():
    rgb = FLASH_MODES[flash_index][1]
    if rgb is None:
        return (105, 125, 135)
    return rgb

def render_ui():
    m = current_mode()
    now = time.monotonic()

    # Y2K corner markers
    c = (165, 238, 255, 95)

    GFX.boxRGBA(
        renderer,
        22, 22, 82, 24,
        *c,
    )
    GFX.boxRGBA(
        renderer,
        22, 22, 24, 82,
        *c,
    )
    GFX.boxRGBA(
        renderer,
        942, 22, 1002, 24,
        *c,
    )
    GFX.boxRGBA(
        renderer,
        1000, 22, 1002, 82,
        *c,
    )

    # Camera info
    glass(
        28, 30,
        300, 66,
        17,
        True,
        168,
    )

    draw_text(
        "CAM 01",
        48, 42,
        font_bold,
        (168, 244, 255, 255),
    )

    draw_text(
        (
            f"{m['name']}  ·  "
            f"{m['width']}×{m['height']}  ·  "
            f"{m['fps']} fps"
        ),
        48, 68,
        font_micro,
        (216, 230, 235, 255),
    )

    # Flash
    glass(
        792, 30,
        204, 66,
        17,
        True,
        168,
    )

    draw_text(
        "FLASH",
        812, 42,
        font_micro,
        (179, 198, 207, 255),
    )

    draw_text(
        FLASH_MODES[flash_index][0],
        812, 66,
        font_bold,
        (227, 247, 251, 255),
    )

    fc = flash_color()

    GFX.filledCircleRGBA(
        renderer,
        962, 63, 8,
        fc[0], fc[1], fc[2], 240,
    )

    GFX.aacircleRGBA(
        renderer,
        962, 63, 12,
        fc[0], fc[1], fc[2], 90,
    )

    # REC chip
    if (
        recorder is not None
        and recording_started_at is not None
    ):
        seconds = int(
            now - recording_started_at
        )

        glass(
            420, 28,
            184, 50,
            16,
            False,
            184,
        )

        GFX.filledCircleRGBA(
            renderer,
            444, 53, 7,
            255, 65, 83, 255,
        )

        draw_text(
            (
                f"REC  "
                f"{seconds // 60:02d}:"
                f"{seconds % 60:02d}"
            ),
            462, 41,
            font_bold,
            (255, 225, 230, 255),
        )

    # Bottom control dock
    glass(
        175, 660,
        674, 82,
        22,
        False,
        180,
    )

    draw_button(
        222,
        "PHOTO",
        "A",
    )

    draw_button(
        390,
        "VIDEO",
        "X",
    )

    draw_button(
        558,
        "MODE",
        "Y",
    )

    GFX.boxRGBA(
        renderer,
        662, 680,
        663, 722,
        150, 205, 215, 65,
    )

    draw_text(
        "R1  FLASH",
        686, 678,
        font_micro,
        (178, 239, 250, 255),
    )

    draw_text(
        "L1  GALLERY",
        686, 706,
        font_micro,
        (178, 239, 250, 255),
    )

    glass(
        30, 684,
        118, 42,
        14,
        False,
        155,
    )

    draw_text(
        "B  BACK",
        49, 696,
        font_micro,
        (205, 218, 223, 255),
    )

    # Toast with fade
    if (
        toast_text
        and now < toast_until
    ):
        remaining = toast_until - now
        age = now - toast_started
        alpha = 255

        if age < 0.12:
            alpha = int(
                255 * age / 0.12
            )
        elif remaining < 0.18:
            alpha = int(
                255 * remaining / 0.18
            )

        alpha = max(
            0,
            min(255, alpha),
        )

        w = max(
            150,
            34 + len(toast_text) * 15,
        )

        x = (
            LOGICAL_W - w
        ) // 2

        GFX.roundedBoxRGBA(
            renderer,
            x, 116,
            x + w, 164,
            16,
            5, 11, 16,
            int(175 * alpha / 255),
        )

        GFX.roundedRectangleRGBA(
            renderer,
            x, 116,
            x + w, 164,
            16,
            160, 239, 255,
            int(105 * alpha / 255),
        )

        draw_text(
            toast_text,
            LOGICAL_W // 2,
            129,
            font_bold,
            (229, 249, 252, 255),
            alpha,
            True,
        )

    # Screen shutter flash
    if now < screen_flash_until:
        duration = max(
            0.01,
            (
                screen_flash_until
                - screen_flash_started
            ),
        )

        alpha = int(
            185
            * (
                screen_flash_until
                - now
            )
            / duration
        )

        GFX.boxRGBA(
            renderer,
            0, 0,
            LOGICAL_W, LOGICAL_H,
            255, 255, 255,
            max(
                0,
                min(185, alpha),
            ),
        )

def switch_mode():
    global mode_index

    if recorder is not None:
        set_toast(
            "STOP REC FIRST",
            0.9,
        )
        return

    if photo_pending:
        set_toast(
            "WAIT",
            0.7,
        )
        return

    flash_off()

    mode_index = (
        mode_index + 1
    ) % len(MODES)

    start_capture()

    set_toast(
        current_mode()["name"],
        0.7,
    )

def cycle_flash():
    global flash_index

    if recorder is not None:
        set_toast(
            "STOP REC FIRST",
            0.9,
        )
        return

    flash_off()

    if flash_fd is None:
        flash_index = 0
        set_toast(
            "FLASH N/A",
            0.9,
        )
        return

    flash_index = (
        flash_index + 1
    ) % len(FLASH_MODES)

    set_toast(
        (
            "FLASH "
            + FLASH_MODES[flash_index][0]
        ),
        0.7,
    )

# ---------- Main ----------
running = True
open_gallery = False

dst = SDL_Rect(
    0, 0,
    LOGICAL_W, LOGICAL_H,
)

try:
    start_capture()
    set_toast("READY", 0.55)

    while running:
        now = time.monotonic()

        recording_led_tick()

        # Physical flash fail-safe
        if (
            flash_is_on
            and photo_flash_deadline
            and now > photo_flash_deadline
        ):
            flash_off()

            photo_pending = False
            photo_wait_frames = 0
            photo_flash_deadline = 0.0

            set_toast(
                "PHOTO TIMEOUT",
                0.9,
            )

        if (
            capture is None
            or capture.poll() is not None
        ):
            logmsg("Capture process exited")
            break

        sources = [
            capture.stdout,
            event_fd,
        ]

        if mjpeg_r is not None:
            sources.append(mjpeg_r)

        ready, _, _ = select.select(
            sources,
            [],
            [],
            0.002,
        )

        for source in ready:

            # Buttons
            if source == event_fd:

                try:
                    data = os.read(
                        event_fd,
                        event_struct.size * 32,
                    )
                except BlockingIOError:
                    data = b""

                for pos in range(
                    0,
                    (
                        len(data)
                        - event_struct.size
                        + 1
                    ),
                    event_struct.size,
                ):
                    (
                        sec,
                        usec,
                        ev_type,
                        code,
                        value,
                    ) = event_struct.unpack_from(
                        data,
                        pos,
                    )

                    if (
                        ev_type != 1
                        or value != 1
                    ):
                        continue

                    if code == BUTTON_A:
                        request_photo()

                    elif code == BUTTON_X:
                        if recorder is None:
                            start_recording()
                        else:
                            stop_recording()

                    elif code == BUTTON_Y:
                        switch_mode()

                    elif code == BUTTON_R1:
                        cycle_flash()

                    elif code == BUTTON_L1:

                        if recorder is not None:
                            set_toast(
                                "STOP REC FIRST",
                                0.9,
                            )

                        elif photo_pending:
                            set_toast(
                                "WAIT",
                                0.7,
                            )

                        else:
                            open_gallery = True
                            running = False
                            break

                    elif code == BUTTON_B:
                        running = False
                        break

            # YUV preview
            elif source == capture.stdout:

                try:
                    chunk = os.read(
                        capture.stdout.fileno(),
                        4 * 1024 * 1024,
                    )
                except BlockingIOError:
                    chunk = b""

                if chunk:
                    raw.extend(chunk)

                    if len(raw) >= raw_frame_size:

                        # Drop stale full frames.
                        complete = (
                            len(raw)
                            // raw_frame_size
                        )

                        start = (
                            complete - 1
                        ) * raw_frame_size

                        frame = bytes(
                            raw[
                                start:
                                start + raw_frame_size
                            ]
                        )

                        del raw[
                            :complete
                            * raw_frame_size
                        ]

                        if preview_warmup > 0:
                            preview_warmup -= 1

                        else:
                            pixels = (
                                ctypes.c_uint8
                                * raw_frame_size
                            ).from_buffer_copy(
                                frame
                            )

                            base = ctypes.addressof(
                                pixels
                            )

                            m = current_mode()

                            SDL.SDL_UpdateYUVTexture(
                                camera_texture,
                                None,

                                ctypes.c_void_p(
                                    base
                                ),
                                m["width"],

                                ctypes.c_void_p(
                                    base + y_size
                                ),
                                m["width"] // 2,

                                ctypes.c_void_p(
                                    (
                                        base
                                        + y_size
                                        + uv_size
                                    )
                                ),
                                m["width"] // 2,
                            )

                            preview_ready = True

            # Original JPEG stream
            elif source == mjpeg_r:

                try:
                    chunk = os.read(
                        mjpeg_r,
                        512 * 1024,
                    )
                except BlockingIOError:
                    chunk = b""

                if chunk:
                    jpeg_buffer.extend(chunk)

                    if (
                        len(jpeg_buffer)
                        > 8 * 1024 * 1024
                    ):
                        jpeg_buffer = (
                            jpeg_buffer[
                                -1024 * 1024:
                            ]
                        )

                    parse_mjpeg()

        SDL.SDL_SetRenderDrawColor(
            renderer,
            0, 0, 0, 255,
        )

        SDL.SDL_RenderClear(
            renderer
        )

        if camera_texture and preview_ready:
            SDL.SDL_RenderCopy(
                renderer,
                camera_texture,
                None,
                ctypes.byref(dst),
            )

        render_ui()

        SDL.SDL_RenderPresent(
            renderer
        )

finally:
    recording_led_stop()
    flash_off()

    stop_recording()
    stop_capture()

    try:
        os.close(event_fd)
    except Exception:
        pass

    if flash_fd is not None:
        try:
            os.close(flash_fd)
        except Exception:
            pass

    for texture, _, _ in text_cache.values():
        SDL.SDL_DestroyTexture(texture)

    for font in fonts:
        if font:
            TTF.TTF_CloseFont(font)

    SDL.SDL_DestroyRenderer(renderer)
    SDL.SDL_DestroyWindow(window)

    TTF.TTF_Quit()
    SDL.SDL_Quit()

    log.close()

if (
    open_gallery
    and os.path.exists(GALLERY_APP)
):
    subprocess.call([
        "/usr/bin/python3",
        GALLERY_APP,
    ])

    os.execv(
        "/usr/bin/python3",
        [
            "/usr/bin/python3",
            __file__,
        ],
    )

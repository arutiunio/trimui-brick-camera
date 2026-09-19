from pathlib import Path
import re
import shutil

root = Path(".")
uvc = root / "managed_components" / "espressif__usb_device_uvc" / "tusb"

main = root / "main" / "usb_webcam_main.c"
cfg  = uvc / "tusb_config.h"
desc = uvc / "usb_descriptors.c"
hdr  = uvc / "usb_descriptors.h"

# Дополнительные backup именно текущего рабочего состояния
for p in (main, cfg, desc, hdr):
    backup = p.with_name(p.name + ".pre_hid")
    if not backup.exists():
        shutil.copy2(p, backup)

# ------------------------------------------------------------
# 1. TinyUSB: включаем HID
# ------------------------------------------------------------

s = cfg.read_text(encoding="utf-8")

if "CFG_TUD_HID_EP_BUFSIZE" not in s:
    anchor = "// video streaming endpoint size"
    if anchor not in s:
        raise SystemExit("ERROR: tusb_config.h anchor not found")

    s = s.replace(
        anchor,
        """// HID flash-control interface
#define CFG_TUD_HID                 1
#define CFG_TUD_HID_EP_BUFSIZE      64

""" + anchor,
        1
    )

cfg.write_text(s, encoding="utf-8")

# ------------------------------------------------------------
# 2. Интерфейс + endpoints
# UVC = IN 0x81
# HID = OUT 0x02 + IN 0x83
# ------------------------------------------------------------

s = hdr.read_text(encoding="utf-8")

if "EPNUM_HID_OUT" not in s:
    enum_anchor = "enum {"

    pos = s.find(enum_anchor)
    if pos < 0:
        raise SystemExit("ERROR: interface enum not found")

    endpoint_block = """
// HID flash-control endpoints
#define EPNUM_HID_OUT         0x02
#define EPNUM_HID_IN          0x83

"""

    s = s[:pos] + endpoint_block + s[pos:]

if "ITF_NUM_HID" not in s:
    old = "    ITF_NUM_TOTAL\n};"

    if old not in s:
        raise SystemExit("ERROR: ITF_NUM_TOTAL anchor not found")

    s = s.replace(
        old,
        "    ITF_NUM_HID,\n    ITF_NUM_TOTAL\n};",
        1
    )

hdr.write_text(s, encoding="utf-8")

# ------------------------------------------------------------
# 3. USB descriptors: UVC + HID
# ------------------------------------------------------------

s = desc.read_text(encoding="utf-8")

if "TRIMUI_FLASH_HID_REPORT" not in s:
    include_anchor = '#include "usb_descriptors.h"'

    if include_anchor not in s:
        raise SystemExit("ERROR: usb_descriptors include not found")

    hid_report = r'''

// TRIMUI_FLASH_HID_REPORT
// 64-byte vendor-defined HID IN/OUT report.
// Linux hidraw writes:
//   byte 0 = report ID (0)
//   report byte 0 = command
//   report byte 1 = R
//   report byte 2 = G
//   report byte 3 = B
uint8_t const desc_hid_report[] = {
    TUD_HID_REPORT_DESC_GENERIC_INOUT(CFG_TUD_HID_EP_BUFSIZE)
};

uint8_t const *tud_hid_descriptor_report_cb(uint8_t instance)
{
    (void) instance;
    return desc_hid_report;
}

// Implemented in usb_webcam_main.c
extern void camera_flash_set_rgb(uint8_t r, uint8_t g, uint8_t b);

uint16_t tud_hid_get_report_cb(uint8_t instance,
                               uint8_t report_id,
                               hid_report_type_t report_type,
                               uint8_t *buffer,
                               uint16_t reqlen)
{
    (void) instance;
    (void) report_id;
    (void) report_type;
    (void) buffer;
    (void) reqlen;
    return 0;
}

void tud_hid_set_report_cb(uint8_t instance,
                           uint8_t report_id,
                           hid_report_type_t report_type,
                           uint8_t const *buffer,
                           uint16_t bufsize)
{
    (void) instance;
    (void) report_id;
    (void) report_type;

    if (bufsize < 1) {
        return;
    }

    // command 0 = OFF
    if (buffer[0] == 0) {
        camera_flash_set_rgb(0, 0, 0);
        return;
    }

    // command 1 = SET RGB
    if (buffer[0] == 1 && bufsize >= 4) {
        camera_flash_set_rgb(buffer[1], buffer[2], buffer[3]);
    }
}
'''

    s = s.replace(
        include_anchor,
        include_anchor + hid_report,
        1
    )

old_total = (
    "#define CONFIG_TOTAL_LEN    "
    "(TUD_CONFIG_DESC_LEN + TUD_CAM1_VIDEO_CAPTURE_DESC_LEN + "
    "TUD_CAM2_VIDEO_CAPTURE_DESC_LEN)"
)

new_total = (
    "#define CONFIG_TOTAL_LEN    "
    "(TUD_CONFIG_DESC_LEN + TUD_CAM1_VIDEO_CAPTURE_DESC_LEN + "
    "TUD_CAM2_VIDEO_CAPTURE_DESC_LEN + TUD_HID_INOUT_DESC_LEN)"
)

if old_total in s:
    s = s.replace(old_total, new_total, 1)
elif "TUD_HID_INOUT_DESC_LEN" not in s:
    raise SystemExit("ERROR: CONFIG_TOTAL_LEN anchor not found")

if "TUD_HID_INOUT_DESCRIPTOR(ITF_NUM_HID" not in s:
    close_anchor = """};

 // Invoked when received GET CONFIGURATION DESCRIPTOR"""

    # tolerate exact source formatting without leading space
    if close_anchor not in s:
        close_anchor = """};

// Invoked when received GET CONFIGURATION DESCRIPTOR"""

    if close_anchor not in s:
        raise SystemExit("ERROR: configuration descriptor end not found")

    hid_descriptor = """    // HID flash control
    TUD_HID_INOUT_DESCRIPTOR(
        ITF_NUM_HID,
        0,
        HID_ITF_PROTOCOL_NONE,
        sizeof(desc_hid_report),
        EPNUM_HID_OUT,
        EPNUM_HID_IN,
        CFG_TUD_HID_EP_BUFSIZE,
        10
    ),

};

"""

    s = s.replace(
        close_anchor,
        hid_descriptor + "// Invoked when received GET CONFIGURATION DESCRIPTOR",
        1
    )

desc.write_text(s, encoding="utf-8")

# ------------------------------------------------------------
# 4. GPIO48 WS2812: превращаем startup-test
#    в постоянный flash controller
# ------------------------------------------------------------

s = main.read_text(encoding="utf-8")

# гарантируем includes
if '#include "led_strip.h"' not in s:
    s = s.replace(
        '#include "esp_log.h"',
        '#include "esp_log.h"\n#include "led_strip.h"\n#include "led_strip_rmt.h"',
        1
    )

if "camera_flash_set_rgb" not in s:
    app_anchor = "void app_main(void)"

    if app_anchor not in s:
        raise SystemExit("ERROR: app_main not found")

    flash_controller = r'''
static led_strip_handle_t s_flash_strip = NULL;

void camera_flash_set_rgb(uint8_t r, uint8_t g, uint8_t b)
{
    if (s_flash_strip == NULL) {
        return;
    }

    if (r == 0 && g == 0 && b == 0) {
        led_strip_clear(s_flash_strip);
        return;
    }

    led_strip_set_pixel(s_flash_strip, 0, r, g, b);
    led_strip_refresh(s_flash_strip);
}

'''

    s = s.replace(app_anchor, flash_controller + app_anchor, 1)

# Удаляем старый тест, который включал белый LED на 700 мс
pattern = re.compile(
    r'\n\s*// Freenove RGB LED test: WS2812 on GPIO48'
    r'.*?'
    r'led_strip_clear\(strip\);\s*'
    r'\n\s*}\s*',
    re.S
)

match = pattern.search(s)

if match:
    init = r'''
    // GPIO48 WS2812 flash controller
    led_strip_config_t strip_config = {
        .strip_gpio_num = 48,
        .max_leds = 1,
        .led_model = LED_MODEL_WS2812,
        .color_component_format = LED_STRIP_COLOR_COMPONENT_FMT_GRB,
        .flags = {
            .invert_out = false,
        },
    };

    led_strip_rmt_config_t rmt_config = {
        .clk_src = RMT_CLK_SRC_DEFAULT,
        .resolution_hz = 10000000,
        .mem_block_symbols = 0,
        .flags = {
            .with_dma = false,
        },
    };

    if (led_strip_new_rmt_device(
            &strip_config,
            &rmt_config,
            &s_flash_strip) == ESP_OK) {
        led_strip_clear(s_flash_strip);
    }
'''
    s = s[:match.start()] + "\n" + init + "\n" + s[match.end():]

elif "GPIO48 WS2812 flash controller" not in s:
    raise SystemExit(
        "ERROR: old GPIO48 startup test not found; no main.c changes written"
    )

main.write_text(s, encoding="utf-8")

print("OK: UVC + HID flash-control patch applied")
print("Command 0: LED OFF")
print("Command 1: SET RGB")

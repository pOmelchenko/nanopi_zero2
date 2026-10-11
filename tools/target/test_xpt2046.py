#!/usr/bin/env python3
"""Guided ILI9341/XPT2046 evdev test for the NanoPi Zero2."""

from __future__ import annotations

import argparse
import fcntl
import importlib.util
import json
import os
import select
import struct
import time
from pathlib import Path

from PIL import Image, ImageDraw


EV_KEY = 0x01
EV_ABS = 0x03
BTN_TOUCH = 0x14A
ABS_X = 0x00
ABS_Y = 0x01
ABS_PRESSURE = 0x18
INPUT_EVENT = struct.Struct("llHHi")
ABS_INFO = struct.Struct("iiiiii")
TARGETS = ((25, 25), (214, 25), (120, 160), (25, 294), (214, 294))


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--event", help="event device; auto-detected by default")
    parser.add_argument("--bus", type=int, default=1)
    parser.add_argument("--device", type=int, default=0)
    parser.add_argument("--speed", type=int, default=1_000_000)
    parser.add_argument(
        "--timeout",
        type=float,
        default=60,
        help="seconds to wait for each highlighted target",
    )
    parser.add_argument("--gpiochip", default="/dev/gpiochip4")
    parser.add_argument("--dc", type=int, default=22)
    parser.add_argument("--reset", type=int, default=0)
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("/tmp/xpt2046-guided-samples.json"),
    )
    return parser.parse_args()


def load_display_module():
    script = Path(__file__).with_name("test_ili9341.py")
    spec = importlib.util.spec_from_file_location("ili9341_test", script)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"cannot load {script}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def find_event_device() -> str:
    matches = []
    for event in sorted(Path("/sys/class/input").glob("event*")):
        try:
            name = (event / "device/name").read_text().strip()
        except OSError:
            continue
        if name == "ADS7846 Touchscreen":
            matches.append(f"/dev/input/{event.name}")
    if len(matches) != 1:
        raise RuntimeError(f"expected one ADS7846 Touchscreen, found {matches}")
    return matches[0]


def read_abs_info(fd: int, axis: int) -> dict[str, int]:
    data = bytearray(ABS_INFO.size)
    fcntl.ioctl(fd, 0x80184540 + axis, data, True)
    value, minimum, maximum, fuzz, flat, resolution = ABS_INFO.unpack(data)
    return {
        "value": value,
        "minimum": minimum,
        "maximum": maximum,
        "fuzz": fuzz,
        "flat": flat,
        "resolution": resolution,
    }


def make_target(index: int, target: tuple[int, int], font, success: bool = False):
    image = Image.new("RGB", (240, 320), (8, 20, 48))
    draw = ImageDraw.Draw(image)
    draw.text((8, 150), f"TOUCH {index + 1}/{len(TARGETS)}", font=font, fill="white")
    x, y = target
    color = (70, 255, 120) if success else (255, 220, 40)
    draw.ellipse((x - 16, y - 16, x + 16, y + 16), outline=color, width=5)
    draw.line((x - 24, y, x + 24, y), fill=color, width=3)
    draw.line((x, y - 24, x, y + 24), fill=color, width=3)
    draw.ellipse((x - 3, y - 3, x + 3, y + 3), fill=(255, 70, 70))
    return image


def drain(fd: int) -> None:
    while True:
        try:
            if not os.read(fd, INPUT_EVENT.size * 64):
                return
        except BlockingIOError:
            return


def capture_touch(fd: int, timeout: float = 60) -> dict[str, int]:
    deadline = time.monotonic() + timeout
    pressed = False
    values: dict[str, int] = {}
    while time.monotonic() < deadline:
        ready, _, _ = select.select([fd], [], [], 0.5)
        if not ready:
            continue
        data = os.read(fd, INPUT_EVENT.size * 64)
        for offset in range(0, len(data), INPUT_EVENT.size):
            event = data[offset : offset + INPUT_EVENT.size]
            if len(event) != INPUT_EVENT.size:
                continue
            _, _, event_type, code, value = INPUT_EVENT.unpack(event)
            if event_type == EV_ABS:
                if code == ABS_X:
                    values["event_x"] = value
                elif code == ABS_Y:
                    values["event_y"] = value
                elif code == ABS_PRESSURE:
                    values["pressure"] = value
            elif event_type == EV_KEY and code == BTN_TOUCH:
                if value:
                    pressed = True
                elif pressed and "event_x" in values and "event_y" in values:
                    return values
    raise TimeoutError("no complete BTN_TOUCH press/release received")


def fit_axis(samples: list[dict[str, int]], event_key: str, pixel_key: str):
    points = [(sample[event_key], sample[pixel_key]) for sample in samples]
    count = len(points)
    source_sum = sum(source for source, _ in points)
    target_sum = sum(target for _, target in points)
    source_squared = sum(source * source for source, _ in points)
    cross = sum(source * target for source, target in points)
    slope = (count * cross - source_sum * target_sum) / (
        count * source_squared - source_sum * source_sum
    )
    intercept = (target_sum - slope * source_sum) / count
    errors = [abs(slope * source + intercept - target) for source, target in points]
    return {"slope": slope, "intercept": intercept, "max_error_px": max(errors)}


def main() -> None:
    args = parse_args()
    event_device = args.event or find_event_device()
    display_module = load_display_module()
    display = display_module.ILI9341(
        args.gpiochip,
        args.dc,
        args.reset,
        args.bus,
        args.device,
        args.speed,
        0,
    )
    fd = os.open(event_device, os.O_RDONLY | os.O_NONBLOCK)
    try:
        ranges = {
            "x": read_abs_info(fd, ABS_X),
            "y": read_abs_info(fd, ABS_Y),
            "pressure": read_abs_info(fd, ABS_PRESSURE),
        }
        print("RANGES", json.dumps(ranges, sort_keys=True), flush=True)
        display.initialize()
        target_font = display_module.load_font(18)
        drain(fd)
        samples = []
        for index, target in enumerate(TARGETS):
            display.show(make_target(index, target, target_font))
            print(f"TARGET {index + 1}/{len(TARGETS)} pixel={target}", flush=True)
            sample = capture_touch(fd, timeout=args.timeout)
            sample["pixel_x"], sample["pixel_y"] = target
            samples.append(sample)
            print("CAPTURED", json.dumps(sample, sort_keys=True), flush=True)
            display.show(make_target(index, target, target_font, success=True))
            time.sleep(0.35)
            drain(fd)

        calibration = {
            "x": fit_axis(samples, "event_x", "pixel_x"),
            "y": fit_axis(samples, "event_y", "pixel_y"),
        }
        result = {
            "event_device": event_device,
            "ranges": ranges,
            "samples": samples,
            "calibration": calibration,
        }
        args.output.write_text(json.dumps(result, indent=2, sort_keys=True) + "\n")
        image = Image.new("RGB", (240, 320), (10, 80, 35))
        draw = ImageDraw.Draw(image)
        font = display_module.load_font(25)
        error = max(axis["max_error_px"] for axis in calibration.values())
        draw.multiline_text(
            (25, 110),
            f"EVDEV TOUCH\nOK\nerror {error:.1f}px",
            font=font,
            fill="white",
            align="center",
        )
        display.show(image)
        print(f"SAVED {args.output}", flush=True)
        print("CALIBRATION", json.dumps(calibration, sort_keys=True), flush=True)
    finally:
        os.close(fd)
        display.close()


if __name__ == "__main__":
    main()

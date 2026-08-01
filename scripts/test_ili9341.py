#!/usr/bin/env python3
"""Standalone ILI9341 SPI display test for the NanoPi Zero2."""

from __future__ import annotations

import argparse
import time

import gpiod
import spidev
from gpiod.line import Direction, Value
from PIL import Image, ImageDraw, ImageFont


DEFAULT_GPIOCHIP = "/dev/gpiochip4"
# Safe GPIOs routed to the NanoPi Zero2 30-pin FPC connector.
# DC: FPC pin 25 / GPIO4_C6; RESET: FPC pin 23 / GPIO4_A0.
DEFAULT_DC = 22
DEFAULT_RESET = 0


class ILI9341:
    def __init__(
        self,
        gpiochip: str,
        dc: int,
        reset: int,
        bus: int,
        device: int,
        speed_hz: int,
        rotation: int,
    ) -> None:
        self.dc = dc
        self.reset = reset
        self.rotation = rotation
        self.width = 320 if rotation in (90, 270) else 240
        self.height = 240 if rotation in (90, 270) else 320

        self.spi = spidev.SpiDev()
        self.spi.open(bus, device)
        self.spi.max_speed_hz = speed_hz
        self.spi.mode = 0
        self.spi.bits_per_word = 8
        self.lines = gpiod.request_lines(
            gpiochip,
            consumer="ili9341-test",
            config={
                dc: gpiod.LineSettings(
                    direction=Direction.OUTPUT,
                    output_value=Value.INACTIVE,
                ),
                reset: gpiod.LineSettings(
                    direction=Direction.OUTPUT,
                    output_value=Value.ACTIVE,
                ),
            },
        )

    def close(self) -> None:
        self.lines.release()
        self.spi.close()

    def gpio(self, line: int, high: bool) -> None:
        self.lines.set_value(line, Value.ACTIVE if high else Value.INACTIVE)

    def command(self, command: int, data: bytes | list[int] = b"") -> None:
        self.gpio(self.dc, False)
        self.spi.writebytes2([command])
        if data:
            self.gpio(self.dc, True)
            self.spi.writebytes2(list(data))

    def read_command(self, command: int, length: int) -> bytes:
        self.gpio(self.dc, False)
        self.spi.xfer2([command])
        self.gpio(self.dc, True)
        return bytes(self.spi.xfer2([0] * length))

    def hardware_reset(self) -> None:
        self.gpio(self.reset, True)
        time.sleep(0.01)
        self.gpio(self.reset, False)
        time.sleep(0.02)
        self.gpio(self.reset, True)
        time.sleep(0.15)

    def initialize(self) -> None:
        self.hardware_reset()
        self.command(0x01)  # Software reset
        time.sleep(0.15)

        # Complete power, timing, VCOM and gamma setup used by ILI9341 modules.
        sequence = (
            (0xEF, [0x03, 0x80, 0x02]),
            (0xCF, [0x00, 0xC1, 0x30]),
            (0xED, [0x64, 0x03, 0x12, 0x81]),
            (0xE8, [0x85, 0x00, 0x78]),
            (0xCB, [0x39, 0x2C, 0x00, 0x34, 0x02]),
            (0xF7, [0x20]),
            (0xEA, [0x00, 0x00]),
            (0xC0, [0x23]),
            (0xC1, [0x10]),
            (0xC5, [0x3E, 0x28]),
            (0xC7, [0x86]),
            (0x3A, [0x55]),  # 16-bit RGB565
            (0xB1, [0x00, 0x18]),
            (0xB6, [0x08, 0x82, 0x27]),
            (0xF2, [0x00]),
            (0x26, [0x01]),
            (
                0xE0,
                [
                    0x0F,
                    0x31,
                    0x2B,
                    0x0C,
                    0x0E,
                    0x08,
                    0x4E,
                    0xF1,
                    0x37,
                    0x07,
                    0x10,
                    0x03,
                    0x0E,
                    0x09,
                    0x00,
                ],
            ),
            (
                0xE1,
                [
                    0x00,
                    0x0E,
                    0x14,
                    0x03,
                    0x11,
                    0x07,
                    0x31,
                    0xC1,
                    0x48,
                    0x08,
                    0x0F,
                    0x0C,
                    0x31,
                    0x36,
                    0x0F,
                ],
            ),
        )
        for command, data in sequence:
            self.command(command, data)

        madctl = {
            0: 0x48,
            90: 0x28,
            180: 0x88,
            270: 0xE8,
        }[self.rotation]
        self.command(0x36, [madctl])
        self.command(0x11)  # Sleep out
        time.sleep(0.15)
        self.command(0x29)  # Display on
        time.sleep(0.05)

    def set_window(self, x0: int, y0: int, x1: int, y1: int) -> None:
        self.command(0x2A, [x0 >> 8, x0 & 0xFF, x1 >> 8, x1 & 0xFF])
        self.command(0x2B, [y0 >> 8, y0 & 0xFF, y1 >> 8, y1 & 0xFF])
        self.command(0x2C)

    def show(self, image: Image.Image) -> None:
        image = image.convert("RGB")
        if image.size != (self.width, self.height):
            raise ValueError(
                f"expected {self.width}x{self.height}, got {image.width}x{image.height}"
            )

        self.set_window(0, 0, self.width - 1, self.height - 1)
        pixels = image.load()
        self.gpio(self.dc, True)
        for y in range(self.height):
            row: list[int] = []
            for x in range(self.width):
                red, green, blue = pixels[x, y]
                value = ((red & 0xF8) << 8) | ((green & 0xFC) << 3) | (blue >> 3)
                row.extend((value >> 8, value & 0xFF))
            # This is a transmit-only operation.  Using xfer2() here also
            # enables RX for every row and can lock the RK3528 SPI controller.
            self.spi.writebytes2(row)


def load_font(size: int) -> ImageFont.ImageFont:
    for path in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ):
        try:
            return ImageFont.truetype(path, size)
        except OSError:
            pass
    return ImageFont.load_default()


def make_test_pattern(width: int, height: int, message: str | None = None) -> Image.Image:
    image = Image.new("RGB", (width, height), "black")
    draw = ImageDraw.Draw(image)

    if message:
        draw.rectangle((0, 0, width - 1, height - 1), fill=(10, 28, 70))
        font = load_font(max(28, width // 8))
        rendered = message.replace("! ", "!\n")
        bbox = draw.multiline_textbbox(
            (0, 0), rendered, font=font, spacing=10, align="center"
        )
        text_width = bbox[2] - bbox[0]
        text_height = bbox[3] - bbox[1]
        x = (width - text_width) // 2
        y = (height - text_height) // 2 - bbox[1]
        draw.multiline_text(
            (x + 2, y + 2),
            rendered,
            font=font,
            fill="black",
            spacing=10,
            align="center",
        )
        draw.multiline_text(
            (x, y),
            rendered,
            font=font,
            fill=(255, 235, 80),
            spacing=10,
            align="center",
        )
        draw.rectangle((2, 2, width - 3, height - 3), outline="cyan", width=4)
        return image

    colors = ("red", "lime", "blue", "white", "yellow", "cyan", "magenta")
    bar_height = max(44, height // 5)
    for index, color in enumerate(colors):
        x0 = index * width // len(colors)
        x1 = (index + 1) * width // len(colors) - 1
        draw.rectangle((x0, 0, x1, bar_height - 1), fill=color)

    font_large = load_font(max(20, width // 10))
    font_small = load_font(max(14, width // 16))
    title = "ILI9341 OK"
    bbox = draw.textbbox((0, 0), title, font=font_large)
    title_width = bbox[2] - bbox[0]
    title_y = bar_height + max(18, height // 14)
    draw.text(((width - title_width) // 2, title_y), title, font=font_large, fill="white")

    detail = f"{width} x {height}  RGB565"
    bbox = draw.textbbox((0, 0), detail, font=font_small)
    detail_width = bbox[2] - bbox[0]
    draw.text(
        ((width - detail_width) // 2, title_y + max(36, height // 8)),
        detail,
        font=font_small,
        fill="yellow",
    )

    grid_top = height * 2 // 3
    cell = max(12, min(width, height) // 12)
    for y in range(grid_top, height):
        for x in range(0, width, cell):
            shade = 55 if ((x // cell) + (y // cell)) % 2 else 150
            draw.rectangle(
                (x, y, min(x + cell - 1, width - 1), min(y + cell - 1, height - 1)),
                fill=(shade, shade, shade),
            )

    draw.rectangle((0, 0, width - 1, height - 1), outline="white", width=3)
    draw.line((0, 0, width - 1, height - 1), fill="orange", width=2)
    draw.line((width - 1, 0, 0, height - 1), fill="orange", width=2)
    return image


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--gpiochip", default=DEFAULT_GPIOCHIP)
    parser.add_argument("--dc", type=int, default=DEFAULT_DC)
    parser.add_argument("--reset", type=int, default=DEFAULT_RESET)
    parser.add_argument("--bus", type=int, default=0, help="Linux SPI bus number")
    parser.add_argument("--device", type=int, default=0, help="SPI chip-select number")
    parser.add_argument("--speed", type=int, default=4_000_000, help="SPI clock in Hz")
    parser.add_argument("--rotation", type=int, choices=(0, 90, 180, 270), default=0)
    parser.add_argument("--text", help="show a custom UTF-8 message instead of the test pattern")
    parser.add_argument("--read-id", action="store_true", help="read D3 over MISO")
    parser.add_argument(
        "--hold",
        action="store_true",
        help="keep SPI/GPIO handles open after drawing (RK3528 diagnostic)",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    width = 320 if args.rotation in (90, 270) else 240
    height = 240 if args.rotation in (90, 270) else 320
    print("Рендеринг изображения...", flush=True)
    image = make_test_pattern(width, height, args.text)
    print("Открытие SPI и GPIO...", flush=True)
    display = ILI9341(
        args.gpiochip,
        args.dc,
        args.reset,
        args.bus,
        args.device,
        args.speed,
        args.rotation,
    )
    try:
        print("Инициализация дисплея...", flush=True)
        display.initialize()
        print("Дисплей инициализирован.", flush=True)
        if args.read_id:
            display_id = display.read_command(0xD3, 4)
            print("Display ID (D3):", display_id.hex(" "))
            if display_id in (b"\x00" * 4, b"\xff" * 4):
                print("MISO не подключён или дисплей не ответил.")
        print("Передача пикселей...", flush=True)
        display.show(image)
        if args.text:
            print(f"Готово: на экране должно быть: {args.text}", flush=True)
        else:
            print(
                f"Готово: ожидается таблица {display.width}x{display.height} "
                "с надписью ILI9341 OK.",
                flush=True,
            )
        if args.hold:
            print("SPI/GPIO удерживаются открытыми; Ctrl+C завершит тест.", flush=True)
            while True:
                time.sleep(3600)
    finally:
        print("Закрытие SPI и GPIO...", flush=True)
        display.close()


if __name__ == "__main__":
    main()

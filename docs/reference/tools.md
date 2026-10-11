# Инструменты NanoPi Zero2

Все исполняемые скрипты находятся в `tools/target/` и работают в Linux
самой NanoPi. Команды копирования выполняются с рабочей станции из корня
репозитория. Python требует libgpiod v2, spidev, Pillow и DejaVu Sans для UTF-8.
Установка runtime: [Ubuntu](../guides/ubuntu-spi.md#установить-runtime),
[Armbian](../guides/armbian-spi.md#1-подготовить-чистый-armbian).

## Установщик FriendlyElec

[`enable_spi1.sh`](../../tools/target/enable_spi1.sh) — автономный Bash-скрипт
с закреплённым kernel commit и встроенными вариантами DTS-патча. Достаточно
скопировать один файл. Обычный вызов собирает и проверяет образ; `--install`
разрешает запись раздела `resource`, `--reboot` — перезагрузку после записи,
`--touch` — XPT2046 на CS1 и автозагрузку `ads7846`.

Рабочий каталог по умолчанию — `/var/lib/nanopi-zero2-spi1`:
`kernel-rk3528/` содержит закреплённый checkout, `runs/` — образы и проверки,
`backups/` — постоянные бэкапы перед установкой. Его можно задать через
`--work-dir`. Не включать тач до подключения его IRQ.

Требуется Bash с `mapfile` и Linux-инструменты сборки; скрипт сам устанавливает
APT-зависимости. Работает с официальным FriendlyElec-образом и от root.
Режимы и проверки перед записью: [руководство Ubuntu](../guides/ubuntu-spi.md#автоматическая-установка).

## Общий тест ILI9341

[`tools/target/test_ili9341.py`](../../tools/target/test_ili9341.py) поддерживает:

- полный ILI9341 init и RGB565;
- тестовую таблицу и UTF-8 текст через Pillow;
- `--gpiochip`, `--dc` и `--reset`;
- выбор Linux SPI устройства через `--bus` и `--device`;
- частоту и поворот изображения.

Armbian создал `/dev/spidev0.0`, поэтому используются значения по умолчанию.
Vendor kernel FriendlyElec содержит SPI aliases и ожидаемо создаёт
`/dev/spidev1.0`, для него передаётся `--bus 1`.

Framebuffer отправляется через `writebytes2()`. Не заменять его на `xfer2()`:
отрисовка требует только TX, а лишний RX приводил к нестабильности RK3528 SPI.

## Guided-тест XPT2046

[`test_xpt2046.py`](../../tools/target/test_xpt2046.py) читает стандартное
Linux input-устройство `ADS7846 Touchscreen`, автоматически находит его
`/dev/input/eventX` и показывает пять мишеней на ILI9341. После полного нажатия
и отпускания мишень становится зелёной. CS1 напрямую не открывается:
проверяются kernel-драйвер, IRQ, координаты и pressure вместе с выводом на CS0.

Оба Python-файла держать в одном каталоге: touch-тест загружает
`test_ili9341.py` относительно своего пути. По умолчанию touch-тест выбирает
`--bus 1`, `--device 0`, 1 MHz, RESET=0, DC=22; результат сохраняет в
`/tmp/xpt2046-guided-samples.json`. Доступны `--event`, `--timeout`, `--output`
и параметры SPI/GPIO. Запуск — в [руководстве Ubuntu](../guides/ubuntu-spi.md#проверить-тачскрин),
границы калибровки — в [справочнике тача](display-and-touch.md).

## Device Tree

- [Armbian overlay](../../tools/target/overlays/rk3528-spidev.dts) включает только SPI1/CS0.
- [Патчи FriendlyElec и версии исходников](../../tools/dependencies/friendlyelec-kernel/README.md) задают display-only и display+touch варианты для ручной сборки.

## Контроль целостности

[`tools/SHA256SUMS`](../../tools/SHA256SUMS) содержит SHA-256 всех шести
исполняемых/Device Tree файлов. Пути в нём разрешаются от корня репозитория:

```bash
# Linux:
sha256sum -c tools/SHA256SUMS
# macOS:
shasum -a 256 -c tools/SHA256SUMS
```

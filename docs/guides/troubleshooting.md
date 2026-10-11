# Диагностика и восстановление NanoPi Zero2

Применимо к конфигурациям из [справочника проверок](../reference/validation/README.md).
Сначала сверить [распиновку и запрет GPIO регуляторов](../reference/hardware.md).

## Дисплей и GPIO

### Плата зависает сразу после запуска скрипта

1. Отключить питание.
2. Убедиться, что `DC` идёт на FPC 25, а `RESET` — на FPC 23.
3. Никогда не передавать скрипту `--dc 19`, `--dc 20`, `--dc 21`,
   `--reset 19`, `--reset 20` или `--reset 21` для `/dev/gpiochip4`.
4. Запустить сначала на 1 MHz без `--read-id` и `--hold`.

### Подсветка есть, изображения нет

Проверить `CS`, `DC`, `RESET`, MOSI и SCK, затем наличие `/dev/spidev1.0`
в FriendlyElec Ubuntu или `/dev/spidev0.0` в указанной сборке Armbian.
`LED` управляет только подсветкой и сам по себе не подтверждает работу SPI.
MISO для первой проверки можно не подключать.

### Изображение искажено или нестабильно

Снизить частоту до 500 kHz или 1 MHz, укоротить провода и проверить общий GND:

```bash
# Armbian Debian с пакетным libgpiod v2:
python3 /root/test_ili9341.py --speed 500000

# FriendlyElec Ubuntu с подготовленным venv:
sudo /opt/ili9341/bin/python /home/pi/test_ili9341.py --bus 1 --speed 500000
```

### Вместо кириллицы квадраты

```bash
apt-get install --reinstall -y fonts-dejavu-core
ls -l /usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf
```

## Тачскрин

Проверить подключение CS1/FPC22, MISO/FPC20 и IRQ/FPC4, загрузку `ads7846`
и наличие `ADS7846 Touchscreen`. Имя `/dev/input/eventX` определять по устройству,
а не фиксировать по номеру. Проверка, сообщения vendor-драйвера и признаки
сбоя описаны в [справочнике дисплея и тача](../reference/display-and-touch.md).

## UART

Отладочный UART NanoPi Zero2 работает на нестандартной скорости:

```text
1500000 baud, 8N1
```

В проверенной конфигурации на macOS адаптер появился как
`/dev/cu.usbserial-31110`. `pyserial-miniterm` корректно работал с этой
скоростью, тогда как `screen` мог показывать нечитаемые символы:

```bash
python3 -m serial.tools.miniterm \
  /dev/cu.usbserial-31110 1500000 \
  --raw
```

Если зависла вся SoC, UART также перестаёт отвечать — тогда нужен power cycle.

## Восстановление FriendlyElec Ubuntu

Если новая `resource.img` не загрузилась:

1. загрузиться с recovery/microSD;
2. проверить PARTLABEL целевого раздела;
3. вернуть проверенный бэкап в раздел `resource`: `resource.img.before-spi`
   для ручного маршрута или файл `resource.before-spi*.img` из
   `/var/lib/nanopi-zero2-spi1/backups/` для установщика;
4. при невозможности загрузки использовать eFlasher или loader mode;
5. для диагностики подключить UART `1500000 8N1`.

Полный eFlasher-образ остаётся наиболее надёжным способом повторной установки.

Отдельный прогон восстановления и установщика с тачем остаётся
в [списке квалификации](../development/README.md). Описание recovery-процедуры
само по себе не является результатом её выполнения.

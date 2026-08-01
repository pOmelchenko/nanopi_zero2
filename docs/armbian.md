# NanoPi Zero2: Armbian, SPI1 и дисплей ILI9341

> **Статус: экспериментальный, не окончательно квалифицированный.** Документ
> фиксирует рабочий результат, полученный на указанном ниже Armbian rolling
> build, но последние сквозные эксперименты и доводка автоматической установки
> выполнялись на официальной Ubuntu FriendlyElec. После обновления rolling-образа
> путь необходимо проверять заново; совместная работа дисплея и XPT2046 на
> Armbian пока не подтверждена.

Эта инструкция описывает экспериментальную рабочую конфигурацию NanoPi Zero2 с
дисплеем `2.8" TFT 240xRGBx320 V1.1`: от чистого Armbian до вывода
кириллического текста через SPI. Это не основной рекомендуемый маршрут для
новой установки — для него используйте
[официальную Ubuntu FriendlyElec](./ubuntu.md). Все номера FPC ниже относятся к
30-контактному разъёму NanoPi Zero2. Все команды с локальными путями `scripts/`
и `overlays/` выполняются из корня этого repository.

Проверенная конфигурация:

```text
NanoPi Zero2 / RK3528
Armbian 26.8 rolling, Debian 13 Trixie
Linux 6.18.41-current-rockchip64
SPI device: /dev/spidev0.0
Display controller: ILI9341-compatible
```

Используемые артефакты:

- [`../overlays/rk3528-spidev.dts`](../overlays/rk3528-spidev.dts) — Armbian Device Tree overlay;
- [`../scripts/test_ili9341.py`](../scripts/test_ili9341.py) — общий тест дисплея и UTF-8 текста.

## Критическое предупреждение о GPIO

**Не использовать `/dev/gpiochip4` линии 19, 20 и 21 для дисплея.** Это
`GPIO4_C3`, `GPIO4_C4` и `GPIO4_C5`. В официальном FriendlyElec DTS они заняты
PWM-регуляторами `vdd_gpu`, `vdd_cpu` и `vdd_logic`; FPC24 / линия 19 поэтому
небезопасна для общей распиновки. Попытка запросить линии 20/21 как обычные GPIO
останавливала плату: замирал heartbeat LED, пропадали SSH и UART, помогал только
перезапуск питания.

Рабочие и безопасные линии управления дисплеем:

```text
RESET = FPC 23 = GPIO4_A0 = /dev/gpiochip4 line 0
DC    = FPC 25 = GPIO4_C6 = /dev/gpiochip4 line 22
```

Все сигнальные GPIO RK3528 имеют уровень 3.3 V. На них нельзя подавать 5 V.
Переставлять провода следует только при отключённом питании платы.

## Подключение дисплея

Минимальная рабочая распиновка:

| Дисплей | FPC NanoPi | Назначение в Linux |
|---|---:|---|
| `VCC` | 1 | 5 V; также доступны контакты 2 и 3 |
| `GND` | 9 | GND; также 16, 18, 26, 28 и 30 |
| `CS` | 21 | SPI1 CS0 / GPIO1_C1 |
| `RESET` | 23 | GPIO4_A0, gpiochip4 line 0 |
| `DC` | 25 | GPIO4_C6, gpiochip4 line 22 |
| `SDI (MOSI)` | 19 | SPI1 MOSI / GPIO1_B7 |
| `SCK` | 17 | SPI1 CLK / GPIO1_B6 |
| `LED` | 10 | 3.3 V; также доступен контакт 11 |
| `SDO (MISO)` | 20 | SPI1 MISO / GPIO1_C0; для вывода необязателен |

Контакты резистивного тачскрина подключаются к той же SPI-шине:

| Touch header | FPC NanoPi | Назначение |
|---|---:|---|
| `T_CLK` | 17 | SPI1 CLK |
| `T_CS` | 22 | SPI1 CS1 / GPIO1_C2 |
| `T_DIN` | 19 | SPI1 MOSI |
| `T_DO` | 20 | SPI1 MISO |
| `T_IRQ` | 4 | GPIO4_A4, active low |

Это физическая разводка проверенного общего жгута. Тач-драйвер и CS1 overlay
на Armbian ещё не квалифицированы: текущий проверенный Armbian route использует
только дисплей, поэтому наличие проводов не означает software-support claim.

### Полная распиновка 30-pin FPC

| FPC | Сигнал | FPC | Сигнал |
|---:|---|---:|---|
| 1 | 5 V | 16 | GND |
| 2 | 5 V | 17 | GPIO1_B6 / SPI1 CLK |
| 3 | 5 V | 18 | GND |
| 4 | GPIO4_A4 | 19 | GPIO1_B7 / SPI1 MOSI |
| 5 | GPIO4_A5 | 20 | GPIO1_C0 / SPI1 MISO |
| 6 | GPIO4_A6 | 21 | GPIO1_C1 / SPI1 CS0 |
| 7 | GPIO4_A7 | 22 | GPIO1_C2 / SPI1 CS1 |
| 8 | GPIO4_B4 | 23 | GPIO4_A0 |
| 9 | GND | 24 | GPIO4_C3 / PWM0 / `vdd_gpu`; не использовать как GPIO |
| 10 | 3.3 V | 25 | GPIO4_C6 |
| 11 | 3.3 V | 26 | GND |
| 12 | GPIO1_B2 | 27 | AOL, аналоговый аудиовыход |
| 13 | GPIO1_B3 | 28 | GND |
| 14 | GPIO1_B4 | 29 | AOR, аналоговый аудиовыход |
| 15 | GPIO1_B5 | 30 | GND |

## 1. Подготовить чистый Armbian

Установить актуальный community/rolling образ Armbian для NanoPi Zero2 на eMMC
обычным способом и выполнить первичную настройку сети и SSH. Дальнейшие команды
выполняются на плате от `root`.

Убедиться, что загружен DTB именно NanoPi Zero2:

```bash
uname -a
grep -E '^(overlay_prefix|fdtfile|user_overlays)=' /boot/armbianEnv.txt
```

Для проверенной системы ожидаются как минимум:

```ini
overlay_prefix=rk35xx
fdtfile=rockchip/rk3528-nanopi-zero2.dtb
```

Установить компилятор Device Tree, Python-библиотеки и шрифт с кириллицей:

```bash
apt-get update
apt-get install -y \
  device-tree-compiler \
  fonts-dejavu-core \
  gpiod \
  python3 \
  python3-libgpiod \
  python3-pil \
  python3-spidev \
  spi-tools
```

На проверенной Debian 13 использовался `python3-libgpiod` 2.2.1. Скрипт применяет
API libgpiod v2 (`gpiod.request_lines`) и без адаптации не запустится с libgpiod
1.x.

### Armbian с Ubuntu 24.04 userspace

SPI overlay и остальные разделы этой инструкции остаются прежними, если
система действительно использует `/boot/armbianEnv.txt`. Пакетный
`python3-libgpiod` Ubuntu 24.04 имеет API 1.6.3, поэтому создать отдельный venv:

```bash
apt-get install -y python3-dev python3-pip python3-venv
python3 -m venv --system-site-packages /opt/ili9341
/opt/ili9341/bin/pip install 'gpiod==2.2.1'
/opt/ili9341/bin/python -c \
  'from gpiod.line import Direction, Value; print("libgpiod v2 API: OK")'
```

В последующих командах заменить `python3` на `/opt/ili9341/bin/python`.

## 2. Установить SPI overlay

С рабочей станции скопировать два файла на плату:

```bash
scp \
  overlays/rk3528-spidev.dts \
  scripts/test_ili9341.py \
  root@192.168.1.88:/root/
```

На NanoPi скомпилировать overlay:

```bash
install -d -m 0755 /boot/overlay-user
dtc -@ -I dts -O dtb \
  -o /boot/overlay-user/rk3528-spidev.dtbo \
  /root/rk3528-spidev.dts
```

Ключ `-@` обязателен: он сохраняет ссылки `&spi1`, `&spi1_pins` и
`&spi1_csn0`, которые bootloader разрешит относительно основного DTB.

Сделать резервную копию конфигурации:

```bash
cp -a /boot/armbianEnv.txt /boot/armbianEnv.txt.before-spi
```

Добавить `rk3528-spidev` в `user_overlays`. На чистой системе, где этой строки
ещё нет:

```bash
printf '%s\n' 'user_overlays=rk3528-spidev' >> /boot/armbianEnv.txt
```

Если `user_overlays` уже существует, не добавлять вторую строку и не удалять
другие overlays: дописать `rk3528-spidev` через пробел к существующему значению.
Итоговый фрагмент должен выглядеть так:

```ini
overlay_prefix=rk35xx
fdtfile=rockchip/rk3528-nanopi-zero2.dtb
user_overlays=rk3528-spidev
```

Проверить файл и перезагрузить плату:

```bash
grep -E '^(overlay_prefix|fdtfile|user_overlays)=' /boot/armbianEnv.txt
reboot
```

## 3. Проверить SPI после перезагрузки

```bash
tr -d '\0' </proc/device-tree/soc/spi@ff9d0000/status
printf '\n'
ls -l /sys/class/spi_master/
ls -l /dev/spidev*
spi-config -d /dev/spidev0.0 -q
```

Ожидается:

```text
okay
/dev/spidev0.0
mode=0, lsb=0, bits=8, speed=10000000
```

Аппаратный контроллер называется SPI1, но Linux зарегистрировал его как
`spi0`, поэтому userspace-путь имеет имя `/dev/spidev0.0`. Это нормально.

Необязательный тест передачи:

```bash
printf '\xAA\x55\x00\xFF' \
  | spi-pipe -d /dev/spidev0.0 -s 1000000 \
  | od -An -tx1
```

Нули или `ff` на приёме не означают, что передача сломана: многие модули не
выводят SDO, а для отрисовки MISO вообще не нужен.

## 4. Вывести тестовую картинку

Сначала ещё раз сверить проводку и особенно `RESET`, `DC`, питание и GND. Затем:

```bash
chmod +x /root/test_ili9341.py
python3 /root/test_ili9341.py --speed 1000000
```

На экране должны появиться цветные полосы, надпись `ILI9341 OK`, размер
`240 x 320 RGB565`, сетка и диагонали. После успешного теста скорость можно
поднять, например до 4 MHz:

```bash
python3 /root/test_ili9341.py --speed 4000000
```

Overlay ограничивает верхнюю частоту 10 MHz. Начинать диагностику следует с
1 MHz — это менее чувствительно к длине и качеству проводов.

Скрипт передаёт строки framebuffer через `writebytes2()`. Не заменять этот вызов
на `xfer2()`: для отрисовки нужен только TX, а включение RX для каждого ряда на
этой конфигурации приводило к нестабильности контроллера.

## 5. Вывести русский текст

Пакет `fonts-dejavu-core` обязателен: встроенный bitmap-шрифт Pillow не содержит
кириллических глифов и вместо текста показывает квадраты.

```bash
fc-match 'DejaVu Sans'
python3 /root/test_ili9341.py \
  --speed 1000000 \
  --text 'Привет чат! Чо как?'
```

Ожидаемый результат — две строки жёлтого текста на тёмно-синем фоне:

```text
Привет чат!
Чо как?
```

Скрипт принимает любой UTF-8 текст через `--text`. Для альбомной ориентации:

```bash
python3 /root/test_ili9341.py \
  --speed 1000000 \
  --rotation 90 \
  --text 'Привет чат! Чо как?'
```

## Почему overlay необходим

В использованном Armbian готового SPI overlay для RK3528 не было. Штатный DTB
содержал контроллер `spi@ff9d0000`, но с `status = "disabled"`. Это можно
перепроверить после обновления ядра:

```bash
dtc -I dtb -O dts \
  -o /tmp/rk3528-nanopi-zero2.dts \
  /boot/dtb/rockchip/rk3528-nanopi-zero2.dtb

grep -n -A20 -B5 'spi@ff9d0000' /tmp/rk3528-nanopi-zero2.dts
grep -n -A20 -B5 -Ei \
  'spi1.*pins|spi1-csn|spi1m' \
  /tmp/rk3528-nanopi-zero2.dts
```

Найденные pinctrl-группы соответствовали линиям:

```text
spi1_pins: GPIO1_B6 CLK, GPIO1_B7 MOSI, GPIO1_C0 MISO
spi1_csn0: GPIO1_C1 CS0
```

Одного включения SPI master недостаточно: без дочернего узла `spidev@0` Linux
не создаёт `/dev/spidev0.0`. В overlay используется
`compatible = "rohm,dh2228fv"`, поскольку современные ядра обычно отвергают
универсальный `compatible = "spidev"` в Device Tree.

## Диагностика

### Плата зависает сразу после запуска скрипта

1. Отключить питание.
2. Убедиться, что `DC` идёт на FPC 25, а `RESET` — на FPC 23.
3. Никогда не передавать скрипту `--dc 19`, `--dc 20`, `--dc 21`,
   `--reset 19`, `--reset 20` или `--reset 21` для `/dev/gpiochip4`.
4. Запустить сначала на 1 MHz без `--read-id` и `--hold`.

### Подсветка есть, изображения нет

Проверить `CS`, `DC`, `RESET`, MOSI и SCK, затем наличие `/dev/spidev0.0`.
`LED` управляет только подсветкой и сам по себе не подтверждает работу SPI.
MISO для первой проверки можно не подключать.

### Изображение искажено или нестабильно

Снизить частоту до 500 kHz или 1 MHz, укоротить провода и проверить общий GND:

```bash
python3 /root/test_ili9341.py --speed 500000
```

### Вместо кириллицы квадраты

```bash
apt-get install --reinstall -y fonts-dejavu-core
ls -l /usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf
```

### Восстановление через UART

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

## Повторное развёртывание после очистки eMMC

Короткий чек-лист:

1. Записать и загрузить Armbian для NanoPi Zero2, настроить сеть и SSH.
2. Установить перечисленные пакеты, включая `fonts-dejavu-core`.
3. Скопировать `rk3528-spidev.dts` и `test_ili9341.py` из этого каталога.
4. Скомпилировать `.dtbo`, добавить `user_overlays=rk3528-spidev` и
   перезагрузиться.
5. Убедиться, что появился `/dev/spidev0.0`.
6. Подключить дисплей по безопасной распиновке при выключенном питании.
7. Запустить тест сначала на 1 MHz, затем вывести UTF-8 текст.

После обновления ядра или DTB повторно проверить статус `spi@ff9d0000` и
наличие `/dev/spidev0.0`. Исходник overlay хранится в репозитории, поэтому его
можно заново скомпилировать под установленный DTB.

## Смежные документы

- [Обзор NanoPi Zero2](../README.md)
- [Официальная Ubuntu FriendlyElec](./ubuntu.md)
- [Общие сведения о vendor-образах FriendlyElec](./friendlyelec-vendor.md)

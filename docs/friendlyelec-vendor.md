# Официальные FriendlyElec-образы NanoPi Zero2

Этот документ описывает общую загрузочную схему официальных Ubuntu и Debian для
NanoPi Zero2, а также воспроизводимый маршрут для официального Debian 13.
Все команды с локальными путями `patches/` выполняются из корня этого
repository.

Подробная инструкция для обследованной Ubuntu 24.04 находится в
[`ubuntu.md`](./ubuntu.md). Электрическая распиновка и общие предупреждения
находятся в [`README.md`](../README.md).

## Общая архитектура

Официальные образы FriendlyElec используют vendor kernel 6.1 и не применяют
Armbian-механизм `/boot/armbianEnv.txt`. DTB упакован в `resource.img`.

Исходники, исследованные 2026-08-01:

```text
friendlyarm/kernel-rockchip nanopi6-v6.1.y
221af17f44d3b513b53b694d5b41614e53c5ab1b

friendlyarm/sd-fuse_rk3528 kernel-6.1.y
b35de9f870e0a0702ea33369154c9ec12494bcd1
```

В vendor DTS подтверждено:

```text
SPI1 node: spi@ff9d0000
initial status: disabled
pinctrl: spi1_pins, spi1_csn0
pins: GPIO1_B6 CLK, GPIO1_B7 MOSI, GPIO1_C0 MISO, GPIO1_C1 CS0
aliases: spi1 = &spi1
```

В kernel config уже включены:

```text
CONFIG_OF_OVERLAY=y
CONFIG_SPI_ROCKCHIP=y
CONFIG_SPI_SPIDEV=y
```

Поэтому [`official-friendlyelec-spi1.patch`](../patches/official-friendlyelec-spi1.patch)
меняет только DTS NanoPi Zero2: включает SPI1 и добавляет `spidev@0`. Ожидаемый
userspace-путь — `/dev/spidev1.0`.

`dtbo.img` в `sd-fuse_rk3528` используется для OverlayFS rootfs и не является
аналогом Armbian Device Tree overlay.

## Цели сборки

| Система | Каталог/аргумент `sd-fuse_rk3528` | Python GPIO |
|---|---|---|
| Debian 13 Trixie | `debian-trixie-core-arm64` | пакетный libgpiod 2.2.1 совместим |
| Ubuntu 24.04 Noble | `ubuntu-noble-core-arm64` | пакетный libgpiod 1.6.3 несовместим; нужен venv |

## Официальный Debian 13

Маршрут проверен по исходникам и сборочным скриптам, но загрузка изменённого
образа на физической плате пока не выполнена.

### 1. Получить исходники и комплект образа

Сборку выполнять на Linux x86_64 или ARM64. FriendlyElec рекомендует Ubuntu
20.04 или новее.

```bash
git clone --depth 1 --branch kernel-6.1.y \
  https://github.com/friendlyarm/sd-fuse_rk3528.git
cd sd-fuse_rk3528

wget \
  https://downloads.friendlyelec.com/os-images/rk3528/images/debian-trixie-core-arm64-images.tgz
tar xvzf debian-trixie-core-arm64-images.tgz

git clone --depth 1 --branch nanopi6-v6.1.y \
  https://github.com/friendlyarm/kernel-rockchip.git \
  kernel-rk3528
```

Если HEAD веток отличается от зафиксированных выше commits, повторно проверить
SPI-разделы DTS и применимость patch.

### 2. Применить общий vendor patch

```bash
NANOPI_SPI_REPO=/path/to/nanopi-zero2-spi

git -C kernel-rk3528 apply --check \
  "$NANOPI_SPI_REPO/patches/official-friendlyelec-spi1.patch"

git -C kernel-rk3528 apply \
  "$NANOPI_SPI_REPO/patches/official-friendlyelec-spi1.patch"

git -C kernel-rk3528 diff --check
git -C kernel-rk3528 diff -- \
  arch/arm64/boot/dts/rockchip/rk3528-nanopi-rev01.dts
```

### 3. Собрать kernel, resource.img и rootfs

```bash
BUILD_THIRD_PARTY_DRIVER=0 \
KERNEL_SRC="$PWD/kernel-rk3528" \
./build-kernel.sh debian-trixie-core-arm64
```

Скрипт обновляет `kernel.img`, `resource.img` и kernel modules в
`debian-trixie-core-arm64`.

### 4. Собрать установщик очищенной eMMC

```bash
wget \
  https://downloads.friendlyelec.com/os-images/rk3528/images/emmc-flasher-images.tgz
tar xvzf emmc-flasher-images.tgz

./mk-emmc-image.sh debian-trixie-core-arm64 autostart=yes
```

Ожидаемый образ:

```text
out/rk3528-eflasher-debian-trixie-core-6.1-arm64-YYYYMMDD.img
```

Записать его на microSD и установить на eMMC штатным eFlasher. Полный образ
предпочтительнее ручной записи разделов: kernel, DTB и модули остаются
согласованными.

### 5. Проверить систему

```bash
cat /etc/os-release
uname -a

od -An -tc /proc/device-tree/spi@ff9d0000/status
ls -l /sys/class/spi_master/
ls -l /dev/spidev*

gpiodetect
gpioinfo /dev/gpiochip4
```

Ожидаются `okay` и `/dev/spidev1.0`. Фактическое имя всегда имеет приоритет:
номер до точки передаётся тесту через `--bus`, после точки — через `--device`.

### 6. Установить runtime и вывести текст

```bash
apt-get update
apt-get install -y \
  fonts-dejavu-core \
  gpiod \
  python3 \
  python3-libgpiod \
  python3-pil \
  python3-spidev \
  spi-tools

python3 -c \
  'from gpiod.line import Direction, Value; print("libgpiod v2 API: OK")'

python3 /root/test_ili9341.py \
  --gpiochip /dev/gpiochip4 \
  --dc 22 --reset 0 \
  --bus 1 --device 0 --speed 1000000 \
  --text 'Привет чат! Чо как?'
```

Перед запуском проверить соответствие GPIO4 и `/dev/gpiochip4`. Если порядок
gpiochip отличается, передать фактический путь. Смещения RESET=0 и DC=22
остаются теми же. Линии 19/20/21 использовать запрещено: в vendor DTS они
связаны с PWM-регуляторами GPU, CPU и logic.

## Наблюдаемая разметка официальной Ubuntu

На голой Ubuntu 24.04.3 с eMMC 233 GiB по SSH обнаружено:

```text
/dev/mmcblk2p3  PARTLABEL=dtbo
/dev/mmcblk2p4  PARTLABEL=resource
/dev/mmcblk2p5  PARTLABEL=kernel
/dev/mmcblk2p8  PARTLABEL=rootfs
/dev/mmcblk2p9  PARTLABEL=userdata
```

Это наблюдение нельзя превращать в универсальное предположение. Перед любой
записью раздела проверять `PARTLABEL`; подробная процедура резервного копирования
описана в [`ubuntu.md`](./ubuntu.md).

## Статус проверки

| Часть | Статус |
|---|---|
| Распиновка и ILI9341 | Проверены на Armbian и официальной Ubuntu 24.04 |
| Vendor DTS и kernel config | Подтверждены исходниками FriendlyElec |
| Patch к `rk3528-nanopi-rev01.dts` | Проверен через `git apply` |
| `sd-fuse_rk3528` для Debian | Соответствует официальному маршруту |
| Совместимость Debian 13 с libgpiod 2.2.1 | Подтверждена пакетами Debian |
| Загрузка изменённого официального Debian | Не выполнена |
| Вывод картинки на официальном Debian | Не выполнен |

## Источники

- [FriendlyELEC NanoPi Zero2 Wiki](https://wiki.friendlyelec.com/wiki/index.php/NanoPi_Zero2)
- [FriendlyElec kernel 6.1](https://github.com/friendlyarm/kernel-rockchip/tree/nanopi6-v6.1.y)
- [FriendlyElec sd-fuse RK3528](https://github.com/friendlyarm/sd-fuse_rk3528/tree/kernel-6.1.y)
- [Debian 13 python3-libgpiod](https://packages.debian.org/trixie/python/python3-libgpiod)

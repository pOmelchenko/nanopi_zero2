# ОС и загрузочная схема NanoPi Zero2

Официальные FriendlyElec-образы хранят DTB в `resource.img`; Armbian использует
`/boot/armbianEnv.txt` и пользовательский `.dtbo`. Способ включения SPI выбирается
по образу ОС. Команды установки находятся в [руководствах](../README.md).

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

Поэтому [`official-friendlyelec-spi1.patch`](../../tools/dependencies/friendlyelec-kernel/official-friendlyelec-spi1.patch)
меняет только DTS NanoPi Zero2: включает SPI1 и добавляет `spidev@0`. Ожидаемый
userspace-путь — `/dev/spidev1.0`.

`dtbo.img` в `sd-fuse_rk3528` используется для OverlayFS rootfs и не является
аналогом Armbian Device Tree overlay.

## Цели сборки

| Система | Каталог/аргумент `sd-fuse_rk3528` | Python GPIO |
|---|---|---|
| Debian 13 Trixie | `debian-trixie-core-arm64` | пакетный libgpiod 2.2.1 совместим |
| Ubuntu 24.04 Noble | `ubuntu-noble-core-arm64` | пакетный libgpiod 1.6.3 несовместим; нужен venv |

## Официальная Ubuntu: применимая конфигурация

```text
Board: FriendlyElec NanoPi Zero2
OS: Ubuntu 24.04.3 LTS (Noble Numbat)
Kernel: 6.1.141, FriendlyElec build #27
Architecture: arm64
Python: 3.12.3
Boot media: eMMC
```

Загруженный Device Tree:

```text
model: FriendlyElec NanoPi Zero2
compatible: friendlyelec,nanopi-zero2, rockchip,rk3528a
SPI1 node: /proc/device-tree/spi@ff9d0000
SPI1 status: disabled
SPI1 alias: /spi@ff9d0000
```

Исходное состояние устройств:

```text
/dev/gpiochip0 ... /dev/gpiochip4 существуют
/dev/gpiochip4: crw------- root root
/dev/spidev* отсутствует
/sys/class/spi_master пуст
```

В eMMC обнаружена следующая разметка:

| Раздел | PARTLABEL | Размер | Назначение |
|---|---|---:|---|
| `/dev/mmcblk2p1` | `uboot` | 4 MiB | U-Boot |
| `/dev/mmcblk2p2` | `misc` | 4 MiB | служебный раздел |
| `/dev/mmcblk2p3` | `dtbo` | 4 MiB | OverlayFS FriendlyElec, не Armbian DT overlay |
| `/dev/mmcblk2p4` | `resource` | 16 MiB | DTB и boot resources |
| `/dev/mmcblk2p5` | `kernel` | 40 MiB | kernel image |
| `/dev/mmcblk2p6` | `boot` | 32 MiB | служебный boot-раздел |
| `/dev/mmcblk2p7` | `recovery` | 32 MiB | recovery |
| `/dev/mmcblk2p8` | `rootfs` | 2.2 GiB | неизменяемая базовая rootfs |
| `/dev/mmcblk2p9` | `userdata` | остальное | writable data и OverlayFS upper layer |

Номера разделов относятся только к обследованной eMMC. Перед любой записью
проверять `PARTLABEL` через `lsblk`: другой размер накопителя или версия образа
может иметь другую нумерацию.

Корень работает как:

```text
overlay on /
lowerdir=/root
upperdir=/data/root
workdir=/data/work
```

Поэтому `/boot` внутри rootfs пуст и не управляет загрузкой. Установленные через
APT пакеты и изменённые файлы попадают в writable upper layer на `userdata`.

## Различия загрузочных схем

Официальная Ubuntu не читает `/boot/armbianEnv.txt` и не загружает файлы из
`/boot/overlay-user`. DTB упакован в `resource.img`.

Кроме того, vendor DTS содержит aliases:

```dts
spi0 = &spi0;
spi1 = &spi1;
```

Поэтому после включения контроллера ожидается `/dev/spidev1.0`, а не
Armbian-путь `/dev/spidev0.0`.

Раздел и файл `dtbo.img` в инструментах FriendlyElec используются для
OverlayFS. К Device Tree overlay из Armbian они отношения не имеют.

## Armbian

Для проверенной сборки Armbian 26.8 rolling / Debian 13 / kernel
`6.18.41-current-rockchip64` аппаратный SPI1 зарегистрирован как `spi0`,
userspace-путь — `/dev/spidev0.0`. Overlay и процедура относятся к этой
конфигурации: [Armbian SPI](../guides/armbian-spi.md).

## Источники

- [Официальные источники](../vendor/README.md).
- [Закреплённые исходники FriendlyElec](../../tools/dependencies/friendlyelec-kernel/source.lock.json).
- [Результаты аппаратной проверки](validation/README.md).

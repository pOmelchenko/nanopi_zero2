# FriendlyElec Debian 13: сборочный маршрут SPI1

**Статус: разработка, без аппаратного запуска.** DTS, применимость патча
и сборочные скрипты исследованы для закреплённых исходников; загрузка
изменённого Debian и вывод картинки не выполнены. Этот документ не является
готовой инструкцией с аппаратной квалификацией.

Локальные пути `tools/` разрешаются от корня репозитория.
[Загрузочная схема](../reference/boot.md), [проводка](../reference/hardware.md)
и [версии исходников](../../tools/dependencies/friendlyelec-kernel/README.md)
задают входные условия. Для проверенного варианта использовать
[FriendlyElec Ubuntu](../guides/ubuntu-spi.md).

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
  "$NANOPI_SPI_REPO/tools/dependencies/friendlyelec-kernel/official-friendlyelec-spi1.patch"

git -C kernel-rk3528 apply \
  "$NANOPI_SPI_REPO/tools/dependencies/friendlyelec-kernel/official-friendlyelec-spi1.patch"

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

### 6. Скопировать тест, установить runtime и вывести текст

С рабочей станции, от корня репозитория:

```bash
scp tools/target/test_ili9341.py root@192.168.1.88:/root/
```

Дальнейшие команды выполнять на NanoPi:

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

## Критерии проверки

Собрать полный образ, сохранить его хеш, загрузить на NanoPi, проверить
фактический SPI-путь и GPIO, тестовую таблицу и UTF-8, доступ по SSH,
перезагрузку и восстановление. Touch требует отдельной квалификации.
Результаты фиксировать в [справочнике проверок](../reference/validation/README.md).

## Источники

- [FriendlyELEC NanoPi Zero2 Wiki](https://wiki.friendlyelec.com/wiki/index.php/NanoPi_Zero2)
- [FriendlyElec kernel 6.1](https://github.com/friendlyarm/kernel-rockchip/tree/nanopi6-v6.1.y)
- [FriendlyElec sd-fuse RK3528](https://github.com/friendlyarm/sd-fuse_rk3528/tree/kernel-6.1.y)
- [Debian 13 python3-libgpiod](https://packages.debian.org/trixie/python/python3-libgpiod)

# Полный eFlasher-образ FriendlyElec Ubuntu

**Статус: разработка.** Описан сборочный маршрут официального
`ubuntu-noble-core-arm64`; сборка полного Ubuntu eFlasher и аппаратная установка
этого комплекта не выполнены. Проверенный маршрут для заводской Ubuntu —
[нативная сборка resource.img](../guides/resource-image.md).
Исходники и patch зафиксированы в [описании зависимости](../../tools/dependencies/friendlyelec-kernel/README.md).
Локальные пути `tools/` разрешаются от корня репозитория.

## Собрать полный образ

В этом сборочном маршруте kernel, `resource.img`, модули и rootfs
формируются одним комплектом. Полная сборка eFlasher-образа Ubuntu
и его аппаратная установка не выполнены.

Сборку выполнять на Linux x86_64 или ARM64. FriendlyElec рекомендует Ubuntu
20.04 или новее.

### 1. Получить официальный комплект и kernel

```bash
git clone --depth 1 --branch kernel-6.1.y \
  https://github.com/friendlyarm/sd-fuse_rk3528.git
cd sd-fuse_rk3528

wget \
  https://downloads.friendlyelec.com/os-images/rk3528/images/ubuntu-noble-core-arm64-images.tgz
tar xvzf ubuntu-noble-core-arm64-images.tgz

git clone --depth 1 --branch nanopi6-v6.1.y \
  https://github.com/friendlyarm/kernel-rockchip.git \
  kernel-rk3528
```

Исходники, на которых runbook проверялся 2026-08-01:

```text
friendlyarm/kernel-rockchip
221af17f44d3b513b53b694d5b41614e53c5ab1b

friendlyarm/sd-fuse_rk3528
b35de9f870e0a0702ea33369154c9ec12494bcd1
```

Если HEAD веток изменился, обязательно повторить `git apply --check` и проверить
SPI-разделы DTS.

### 2. Применить изменение DTS

```bash
NANOPI_SPI_REPO=/path/to/nanopi-zero2-spi
PATCH="$NANOPI_SPI_REPO/tools/dependencies/friendlyelec-kernel/official-friendlyelec-spi1.patch"
# Для подключённого XPT2046 использовать combined patch вместо display-only:
# PATCH="$NANOPI_SPI_REPO/tools/dependencies/friendlyelec-kernel/official-friendlyelec-spi1-touch.patch"

git -C kernel-rk3528 apply --check \
  "$PATCH"

git -C kernel-rk3528 apply \
  "$PATCH"

git -C kernel-rk3528 diff --check
git -C kernel-rk3528 diff -- \
  arch/arm64/boot/dts/rockchip/rk3528-nanopi-rev01.dts
```

Patch изменяет только `rk3528-nanopi-rev01.dts`. В vendor kernel уже включены
`CONFIG_SPI_ROCKCHIP=y` и `CONFIG_SPI_SPIDEV=y`; пересобирать конфигурацию
драйверов специально для spidev не требуется. Для combined touch patch также
уже доступны `CONFIG_TOUCHSCREEN_ADS7846=m` и установленный `ads7846.ko`; в
готовой rootfs нужно добавить `ads7846` в `/etc/modules-load.d/`.

### 3. Собрать kernel и resource.img

```bash
BUILD_THIRD_PARTY_DRIVER=0 \
KERNEL_SRC="$PWD/kernel-rk3528" \
./build-kernel.sh ubuntu-noble-core-arm64
```

Скрипт обновляет в `ubuntu-noble-core-arm64`:

```text
kernel.img
resource.img
rootfs.img с соответствующими kernel modules
```

### 4. Собрать установщик eMMC

```bash
wget \
  https://downloads.friendlyelec.com/os-images/rk3528/images/emmc-flasher-images.tgz
tar xvzf emmc-flasher-images.tgz

./mk-emmc-image.sh ubuntu-noble-core-arm64 autostart=yes
```

Ожидаемый результат:

```text
out/rk3528-eflasher-ubuntu-noble-core-6.1-arm64-YYYYMMDD.img
```

Записать его на microSD и установить систему на eMMC по штатной процедуре
FriendlyElec. Это уничтожает прежнее содержимое целевой eMMC, поэтому перед
установкой сохранить необходимые данные.

## Обновление только resource.img на тестовой плате

Этот способ быстрее, но рискованнее полного eFlasher-образа. Использовать только
для разработки при наличии UART и загрузочной recovery/microSD.

Скопировать собранный файл на плату:

```bash
scp ubuntu-noble-core-arm64/resource.img \
  pi@192.168.1.88:/home/pi/resource.img.new
```

На обследованной плате `resource` — `/dev/mmcblk2p4`. Перед записью проверить
это повторно:

```bash
lsblk -o NAME,PATH,SIZE,PARTLABEL,FSTYPE,MOUNTPOINTS /dev/mmcblk2
lsblk -n -o PARTLABEL /dev/mmcblk2p4
```

Вторая команда обязана вывести только:

```text
resource
```

Сначала сохранить текущий раздел:

```bash
sudo dd \
  if=/dev/mmcblk2p4 \
  of=/home/pi/resource.img.before-spi \
  bs=1M status=progress conv=fsync

sha256sum /home/pi/resource.img.before-spi
sha256sum /home/pi/resource.img.new
```

Только после проверки PARTLABEL и резервной копии записать новый ресурс:

```bash
sudo dd \
  if=/home/pi/resource.img.new \
  of=/dev/mmcblk2p4 \
  bs=1M status=progress conv=fsync

sync
sudo reboot
```

На другой разметке нельзя вслепую использовать `/dev/mmcblk2p4`: запись не в
тот раздел может сделать систему незагружаемой.

## Проверка готового решения

После сборки и установки пройти [проверки Ubuntu](../guides/ubuntu-spi.md),
сохранить версии и хеши образов, результаты холодной загрузки, дисплея,
тача и восстановления. До этого полный образ остаётся сборочным вариантом.

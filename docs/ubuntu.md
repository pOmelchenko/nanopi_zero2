# NanoPi Zero2: FriendlyElec Ubuntu 24.04, ILI9341 и XPT2046

Это текущий рекомендуемый и наиболее полно проверенный маршрут проекта. Все
последние сквозные эксперименты с дисплеем, тачскрином и автономной подготовкой
чистой системы проводились на этой Ubuntu.

Этот runbook относится к официальному образу FriendlyElec
`ubuntu-noble-core-arm64`, а не к Armbian Ubuntu. Он описывает подготовку образа
с включённым SPI1, установку на eMMC, запуск ILI9341 и опциональный XPT2046.
Все команды с локальными путями `scripts/` и `patches/` выполняются из корня
этого repository.

Полный путь аппаратно проверен 2026-08-01: на голой Ubuntu нативно собран DTB,
перепакован и установлен `resource.img`, после перезагрузки появился
`/dev/spidev1.0`, а ILI9341 вывел тестовую таблицу и кириллицу. После финального
теста плата осталась доступна по SSH, а в `dmesg` не появилось ошибок SPI или
конфликтов pinmux. Путь дисплей + тач также физически проверен 2026-08-01:
ILI9341 работал через `/dev/spidev1.0`, XPT2046 через штатный `ads7846` как
`/dev/input/event2`, пять подсвеченных точек при точном нажатии дали
максимальную ошибку `2.1 px`, а после контрольной перезагрузки оба устройства
поднялись вместе.

Связанные файлы:

- [`../scripts/enable_spi1.sh`](../scripts/enable_spi1.sh) — автономно собирает и проверяет
  `resource.img`, а с `--install` делает backup и устанавливает его;
- [`../patches/official-friendlyelec-spi1.patch`](../patches/official-friendlyelec-spi1.patch) —
  включает SPI1 и добавляет `spidev@0` в vendor DTS NanoPi Zero2;
- [`../patches/official-friendlyelec-spi1-touch.patch`](../patches/official-friendlyelec-spi1-touch.patch) —
  включает дисплей на CS0 и XPT2046 на CS1 с IRQ FPC4;
- [`../scripts/test_ili9341.py`](../scripts/test_ili9341.py) — тест дисплея с выбором SPI bus через
  `--bus`.
- [`../scripts/test_xpt2046.py`](../scripts/test_xpt2046.py) — guided evdev-тест, который
  подсвечивает точки на дисплее и читает нажатия через kernel-драйвер.

Электрическая распиновка и запрет GPIO4_C3/C4/C5 описаны в
[`../README.md`](../README.md). Они одинаковы для Armbian и официальной Ubuntu.
Общая архитектура vendor-образов и маршрут официального Debian находятся в
[`friendlyelec-vendor.md`](./friendlyelec-vendor.md).

## Обследованная исходная система

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

## Почему инструкция Armbian неприменима

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

## Автоматическая установка

Для обследованного официального образа достаточно скопировать один автономный
скрипт. По умолчанию он устанавливает зависимости, собирает и полностью
проверяет новый `resource.img`, но ничего не записывает в eMMC:

```bash
scp scripts/enable_spi1.sh \
  pi@192.168.1.88:/home/pi/

ssh -t pi@192.168.1.88 \
  'sudo bash /home/pi/enable_spi1.sh'
```

В конце команда напечатает точный путь к проверенному `resource.img.spi` и
сообщение `Build-only mode`. Чтобы создать постоянную резервную копию, записать
только раздел с `PARTLABEL=resource`, проверить его чтением обратно и
перезагрузиться:

```bash
ssh -t pi@192.168.1.88 \
  'sudo bash /home/pi/enable_spi1.sh --install --reboot'
```

Это display-only режим и безопасное значение по умолчанию. Если общий
CLK/MOSI-жгут, CS1, MISO и T_IRQ уже подключены по таблице в
[`../README.md`](../README.md), включить оба устройства одной командой:

```bash
ssh -t pi@192.168.1.88 \
  'sudo bash /home/pi/enable_spi1.sh --touch --install --reboot'
```

`--touch` добавляет второй chip select и узел `ti,tsc2046`, но не пересобирает
kernel: модуль `ads7846.ko` уже входит в заводской kernel. Скрипт устанавливает
`/etc/modules-load.d/nanopi-xpt2046.conf`, потому что в kernel `6.1.141 #27`
OF-таблица знает `ti,tsc2046`, но SPI module alias автоматически загружается
только как `ads7846`.

Флаг `--install` является явным разрешением на запись eMMC. Скрипт прекращает
работу до записи при любом из условий:

- модель платы или vendor-образ не совпали;
- найдено не ровно одно устройство с `PARTLABEL=resource`;
- commit kernel source отличается от проверенного;
- чисто собранный DTB не совпал побайтно с заводским DTB текущего образа;
- после упаковки изменился любой файл, кроме целевого DTB;
- итоговый образ не содержит `spi1=okay` и `spidev@0`;
- в `--touch`-режиме отсутствуют CS1, `touchscreen@1`, IRQ, regulator или
  измеренные raw-range свойства;
- записанный раздел не совпал с образом при чтении обратно.

После перезагрузки проверить:

```bash
od -An -tc /proc/device-tree/spi@ff9d0000/status
ls -l /dev/spidev1.0
```

После `--touch` дополнительно проверить:

```bash
lsmod | grep ads7846
grep -A8 -B2 'ADS7846 Touchscreen' /proc/bus/input/devices
ls -l /dev/input/event*
```

Скрипт включает Linux SPI-устройство. Python runtime и тест дисплея
устанавливаются отдельным разделом ниже.

## Аппаратно проверенный XPT2046

Проверенная общая SPI1-схема:

- дисплей: CS0/FPC21, RESET/FPC23, DC/FPC25;
- touch `T_CLK` разделяет FPC17 с SCK дисплея;
- touch `T_DIN` разделяет FPC19 с MOSI дисплея;
- touch `T_CS` идёт отдельно на CS1/FPC22;
- touch `T_DO` идёт на MISO/FPC20; SDO самого дисплея не подключён;
- touch `T_IRQ` идёт на FPC4/GPIO4_A4/gpiochip4 line 4.

Все сигналы имеют уровень 3.3 V. Жгут переставлять только при полностью
отключённом питании. FPC24 и gpiochip4 lines 19/20/21 не использовать.

Проверенный Device Tree использует:

```dts
num-cs = <2>;
pinctrl-0 = <&spi1_pins &spi1_csn0 &spi1_csn1>;

touchscreen@1 {
    compatible = "ti,tsc2046";
    reg = <1>;
    interrupts = <RK_PA4 IRQ_TYPE_EDGE_FALLING>;
    spi-max-frequency = <1000000>;
    pendown-gpio = <&gpio4 RK_PA4 GPIO_ACTIVE_LOW>;
    vcc-supply = <&vcc_3v3_s3>;
    ti,x-min = /bits/ 16 <250>;
    ti,x-max = /bits/ 16 <3800>;
    ti,y-min = /bits/ 16 <350>;
    ti,y-max = /bits/ 16 <3650>;
    ti,x-plate-ohms = /bits/ 16 <400>;
    ti,pressure-max = /bits/ 16 <2000>;
    ti,debounce-max = /bits/ 16 <10>;
    ti,debounce-tol = /bits/ 16 <50>;
    ti,debounce-rep = /bits/ 16 <2>;
    touchscreen-inverted-x;
};
```

Raw-калибровка проведена экранными мишенями, а не угадана: X уменьшался слева
направо (`~3520 -> ~514`), Y увеличивался сверху вниз (`~500 -> ~3490`). Поэтому
оси не меняются местами, X инвертируется в DT ровно один раз. После драйвера
ядро объявило диапазоны X `0..3550`, Y `350..3650`, pressure `0..2000`.
Точный прогон стилусом для этого экземпляра дал диагностическую проекцию
`pixel_x = 0.0663308 * event_x + 4.3834` и
`pixel_y = 0.0891104 * event_y - 17.605`, с максимальной ошибкой `2.1 px`.
Эти коэффициенты не следует слепо переносить на другой экземпляр панели.

Для guided-проверки скопировать оба файла в один каталог:

```bash
scp scripts/test_ili9341.py scripts/test_xpt2046.py \
  pi@192.168.1.88:/home/pi/

ssh -t pi@192.168.1.88 \
  'sudo /opt/ili9341/bin/python /home/pi/test_xpt2046.py'
```

Скрипт сам находит handler по имени `ADS7846 Touchscreen`. На дисплее
последовательно появляются пять жёлтых мишеней; каждую нужно нажать и полностью
отпустить. Принятая мишень кратко становится зелёной. Результат с evdev
диапазонами, pressure, samples и линейной ошибкой сохраняется в
`/tmp/xpt2046-guided-samples.json`.

Vendor kernel при загрузке модуля печатает сообщения вида
`SPI driver ads7846 has no spi_device_id for ti,tsc2046`. Это известная
особенность его неполной SPI ID-таблицы: OF binding и input device после этого
успешно создаются. Ошибками считаются отсутствие `ADS7846 Touchscreen`, IRQ
storm, зависший `BTN_TOUCH`, SPI transfer errors или потеря SSH.
В проверенном прогоне IRQ-счётчик не изменился за пять секунд без касаний
(`delta=0`), то есть активного idle storm не было.

Проверенный `resource.img` с дисплеем и тачем имел SHA-256:

```text
4c34f6602fa120ad5599e6502348b62cd3a444bc832cf37a13590fc6f86543c4
```

Hash относится только к обследованному заводскому образу и служит для аудита,
а не как универсальная проверка других релизов.

## Аппаратно проверенный путь: собрать resource.img на NanoPi

Ниже приведён ручной эквивалент [`enable_spi1.sh`](../scripts/enable_spi1.sh). Маршрут
проверен на официальном образе с kernel `6.1.141 #27`. Он меняет только DTB
внутри раздела `resource`; kernel и модули остаются заводскими. Наличие UART
или загрузочной recovery/microSD обязательно.

С рабочей станции скопировать patch:

```bash
scp patches/official-friendlyelec-spi1.patch \
  pi@192.168.1.88:/home/pi/

# Вместо предыдущего файла для уже подключённого тача:
# scp patches/official-friendlyelec-spi1-touch.patch \
#   pi@192.168.1.88:/home/pi/
```

На NanoPi установить инструменты и получить vendor kernel:

```bash
sudo -i
apt-get update
apt-get install -y \
  bc bison build-essential device-tree-compiler flex git \
  libelf-dev libssl-dev rsync u-boot-tools

BUILD=/root/nanopi-spi-build
KERNEL="$BUILD/kernel-rk3528"
mkdir -p "$BUILD"

git clone --depth 1 --branch nanopi6-v6.1.y \
  https://github.com/friendlyarm/kernel-rockchip.git "$KERNEL"
test "$(git -C "$KERNEL" rev-parse HEAD)" = \
  221af17f44d3b513b53b694d5b41614e53c5ab1b

cp /home/pi/official-friendlyelec-spi1.patch "$BUILD/"
# Для touch-варианта скопировать сюда combined patch с именем
# official-friendlyelec-spi1-touch.patch.
```

Если проверка commit не прошла, не продолжать автоматически: нужно сопоставить
версию исходников с образом и снова проверить patch. Для обследованного образа
чисто собранный DTB побайтно совпал с заводским — это обязательный защитный
барьер от замены несвязанной части Device Tree.

Найти раздел по метке, сохранить его и распаковать:

```bash
mapfile -t TARGETS < <(lsblk -rpn -o PATH,PARTLABEL | \
  awk '$2 == "resource" { print $1 }')
test "${#TARGETS[@]}" -eq 1
TARGET=${TARGETS[0]}
test "$(lsblk -n -o PARTLABEL "$TARGET")" = resource

test ! -e "$BUILD/resource.img.original"
dd if="$TARGET" of="$BUILD/resource.img.original" \
  bs=1M status=progress conv=fsync
sha256sum "$BUILD/resource.img.original"

cd "$KERNEL"
make ARCH=arm64 nanopi6_linux_defconfig
make -j4 ARCH=arm64 rockchip/rk3528-nanopi-rev01.dtb
make -j4 ARCH=arm64 scripts

ORIGINAL="$BUILD/resource-original-unpacked"
test ! -e "$ORIGINAL"
scripts/resource_tool --unpack \
  --image="$BUILD/resource.img.original" "$ORIGINAL"

cmp arch/arm64/boot/dts/rockchip/rk3528-nanopi-rev01.dtb \
  "$ORIGINAL/rk3528-nanopi-rev01.dtb"
```

`cmp` обязан завершиться с кодом `0`. На проверенной плате SHA-256 заводского
раздела был
`553d5b6b97512e00c2ab9d671ba30ae07324d3b1c1b52ea0b82ef3e961561297`.
Этот hash приведён для аудита, а не для слепой проверки других версий образа.

Применить patch, собрать новый DTB и перепаковать все файлы ресурса:

```bash
# display-only; для подключённого тача выбрать вместо него
# official-friendlyelec-spi1-touch.patch. Эти patches взаимоисключающие.
PATCH="$BUILD/official-friendlyelec-spi1.patch"

git apply --check "$PATCH"
git apply "$PATCH"
git diff --check
make -j4 ARCH=arm64 rockchip/rk3528-nanopi-rev01.dtb

cp arch/arm64/boot/dts/rockchip/rk3528-nanopi-rev01.dtb \
  "$ORIGINAL/rk3528-nanopi-rev01.dtb"

(cd "$ORIGINAL" && \
  "$KERNEL/scripts/resource_tool" --dtbname --pack \
    --image="$BUILD/resource.img.spi" *)

RESOURCE_SIZE=$(blockdev --getsize64 "$TARGET")
test "$(stat -c %s "$BUILD/resource.img.spi")" -le "$RESOURCE_SIZE"
truncate -s "$RESOURCE_SIZE" "$BUILD/resource.img.spi"
```

Флаг `--dtbname` обязателен: без него `resource_tool` переименует первый DTB в
`rk-kernel.dtb`. Перед записью повторно распаковать результат и проверить, что
все заводские файлы, кроме целевого DTB, сохранились:

```bash
NEW="$BUILD/resource-new-unpacked"
scripts/resource_tool --unpack --image="$BUILD/resource.img.spi" "$NEW"

for file in "$ORIGINAL"/*; do
  name=${file##*/}
  test "$name" = rk3528-nanopi-rev01.dtb && continue
  cmp "$file" "$NEW/$name"
done

cmp arch/arm64/boot/dts/rockchip/rk3528-nanopi-rev01.dtb \
  "$NEW/rk3528-nanopi-rev01.dtb"
test "$(fdtget "$NEW/rk3528-nanopi-rev01.dtb" \
  /spi@ff9d0000 status)" = okay
test "$(fdtget "$NEW/rk3528-nanopi-rev01.dtb" \
  /spi@ff9d0000/spidev@0 compatible)" = rohm,dh2228fv
```

Записать только после всех проверок, затем прочитать раздел обратно и сравнить:

```bash
dd if="$BUILD/resource.img.spi" of="$TARGET" \
  bs=1M status=progress conv=fsync
sync
dd if="$TARGET" of="$BUILD/resource.img.readback" \
  bs=1M status=none
cmp "$BUILD/resource.img.spi" "$BUILD/resource.img.readback"
sha256sum "$BUILD/resource.img.spi" "$BUILD/resource.img.readback"
reboot
```

На проверенной сборке оба hash после записи были
`0fa020c4b3d754efd39ad543dbf43a6a1c5cd9eb719408c65faf03caae021df1`.

## Рекомендуемый способ: собрать полный образ

Это предпочтительный воспроизводимый маршрут после очистки eMMC. Kernel,
`resource.img`, модули и rootfs формируются одним комплектом.

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
PATCH="$NANOPI_SPI_REPO/patches/official-friendlyelec-spi1.patch"
# Для подключённого XPT2046 использовать combined patch вместо display-only:
# PATCH="$NANOPI_SPI_REPO/patches/official-friendlyelec-spi1-touch.patch"

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

## Проверить SPI после загрузки

```bash
od -An -tc /proc/device-tree/spi@ff9d0000/status
ls -l /sys/class/spi_master/
ls -l /dev/spidev*
```

Ожидается:

```text
okay\0
/dev/spidev1.0
```

Если появилось другое имя, номер между `spidev` и точкой передавать скрипту как
`--bus`, а число после точки — как `--device`.

## Установить runtime

В Ubuntu 24.04 пакет `python3-libgpiod` имеет версию 1.6.3 и несовместим с
`gpiod.request_lines`, используемым тестом. Официальные bindings 2.2.1 нужно
изолировать в venv.

```bash
sudo apt-get update
sudo apt-get install -y \
  fonts-dejavu-core \
  python3-dev \
  python3-pil \
  python3-pip \
  python3-spidev \
  python3-venv \
  spi-tools

sudo python3 -m venv --system-site-packages /opt/ili9341
sudo /opt/ili9341/bin/pip install 'gpiod==2.2.1'

/opt/ili9341/bin/python -c \
  'from gpiod.line import Direction, Value; print("libgpiod v2 API: OK")'
```

Голый образ уже содержал `fonts-dejavu-core`, но пакет оставлен в команде для
повторяемости после смены версии rootfs.

Обследованный `/etc/apt/sources.list` включает `noble-proposed`, поэтому версии
пакетов могут отличаться от стабильного Noble. После установки сохранить:

```bash
apt-cache policy python3-pil python3-spidev
/opt/ili9341/bin/pip freeze
```

## Скопировать и запустить тест

С рабочей станции:

```bash
scp scripts/test_ili9341.py \
  pi@192.168.1.88:/home/pi/
```

В голом образе `/dev/gpiochip4` имеет права `0600 root:root`, поэтому первый
тест запускать через `sudo`:

```bash
sudo /opt/ili9341/bin/python /home/pi/test_ili9341.py \
  --gpiochip /dev/gpiochip4 \
  --dc 22 \
  --reset 0 \
  --bus 1 \
  --device 0 \
  --speed 1000000
```

После появления тестовой таблицы вывести русский текст:

```bash
sudo /opt/ili9341/bin/python /home/pi/test_ili9341.py \
  --gpiochip /dev/gpiochip4 \
  --dc 22 \
  --reset 0 \
  --bus 1 \
  --device 0 \
  --speed 1000000 \
  --text 'Привет чат! Чо как?'
```

Не менять `DC` и `RESET` на линии 19/20/21. В vendor DTS PWM0, PWM1 и PWM2
управляют питанием GPU, CPU и logic. Запрос линии 19 переключает `vdd_gpu` из
PWM в GPIO и вызывает kernel warning; запрос линий 20/21 может полностью
остановить SoC.

## Доступ и автоматический запуск

Пользователь `pi` входит в группу `sudo`, но на обследованной системе
`sudo -n` не работает: требуется интерактивный пароль. Для ручного теста это
нормально.

Для production лучше запускать приложение как root через отдельный systemd
service либо создать ограниченные udev rules и группы для `gpiochip` и
`spidev`. Не выдавать пользователю общий passwordless sudo только ради
дисплея.

## Восстановление

Если новая `resource.img` не загрузилась:

1. загрузиться с recovery/microSD;
2. проверить PARTLABEL целевого раздела;
3. вернуть `resource.img.before-spi` в раздел `resource`;
4. при невозможности загрузки использовать eFlasher или loader mode;
5. для диагностики подключить UART `1500000 8N1`.

Полный eFlasher-образ остаётся наиболее надёжным способом повторной установки.

## Статус проверки

| Этап | Статус |
|---|---|
| Инвентаризация голой Ubuntu 24.04.3 | Выполнена по SSH |
| SPI1 в исходном DTB имеет `disabled` | Проверено на работающей плате |
| GPIO4 соответствует `/dev/gpiochip4` | Проверено на работающей плате |
| Vendor patch применяется к kernel tree | Проверено через `git apply` |
| Python-скрипт с `--bus 1 --reset 0` | Проверено на дисплее |
| Нативная сборка DTB и `resource.img` на NanoPi | Выполнена |
| Загрузка изменённого `resource.img` | Выполнена, `/dev/spidev1.0` создан |
| Вывод тестовой таблицы и кириллицы | Выполнен на 1 MHz |
| Проверка SSH и `dmesg` после вывода | Выполнена, ошибок нет |
| Сборка полного eFlasher Ubuntu image | Не выполнена |

## Источники

- [FriendlyELEC NanoPi Zero2 Wiki](https://wiki.friendlyelec.com/wiki/index.php/NanoPi_Zero2)
- [FriendlyElec kernel 6.1](https://github.com/friendlyarm/kernel-rockchip/tree/nanopi6-v6.1.y)
- [FriendlyElec sd-fuse RK3528](https://github.com/friendlyarm/sd-fuse_rk3528/tree/kernel-6.1.y)
- [Ubuntu 24.04 python3-libgpiod](https://packages.ubuntu.com/noble/python3-libgpiod)
- [Python gpiod 2.2.1](https://pypi.org/project/gpiod/2.2.1/)

# Нативная сборка resource.img на NanoPi Zero2

Ручная подготовка DTB для официальной Ubuntu 24.04.3 с kernel `6.1.141 #27`.
Нативная сборка, запись с чтением обратно и загрузка дисплея проверены
2026-08-01. Хеши и результаты — в [справочнике проверок](../reference/validation/README.md).
Локальные пути `tools/` разрешаются от корня репозитория; команды сборки
и записи выполняются на NanoPi. Перед началом сверить
[проводку](../reference/hardware.md).

Ниже приведён ручной эквивалент [`enable_spi1.sh`](../../tools/target/enable_spi1.sh). Маршрут
проверен на официальном образе с kernel `6.1.141 #27`. Он меняет только DTB
внутри раздела `resource`; kernel и модули остаются заводскими. Наличие UART
или загрузочной recovery/microSD обязательно.

С рабочей станции скопировать patch:

```bash
scp tools/dependencies/friendlyelec-kernel/official-friendlyelec-spi1.patch \
  pi@192.168.1.88:/home/pi/

# Вместо предыдущего файла для уже подключённого тача:
# scp tools/dependencies/friendlyelec-kernel/official-friendlyelec-spi1-touch.patch \
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

## После перезагрузки

Продолжить с [проверки SPI и Python runtime](ubuntu-spi.md#проверить-spi-после-загрузки).
В случае сбоя использовать [восстановление](troubleshooting.md#восстановление-friendlyelec-ubuntu).

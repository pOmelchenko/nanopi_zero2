# Armbian: SPI1 и дисплей ILI9341

Процедура проверена для NanoPi Zero2 / RK3528, Armbian 26.8 rolling,
Debian 13 Trixie, kernel `6.18.41-current-rockchip64`, `/dev/spidev0.0`.
Результат — тестовая таблица ILI9341 и UTF-8 текст. После обновления rolling-образа
нужна повторная проверка. Совместная работа с XPT2046 и актуальное сквозное
развёртывание остаются в [разработке](../development/README.md).

Для новой установки основной маршрут — [официальная Ubuntu FriendlyElec](ubuntu-spi.md).
Все номера FPC относятся к 30-pin разъёму NanoPi. Перед началом сверить
[общую распиновку](../reference/hardware.md): RESET — FPC23 / line 0,
DC — FPC25 / line 22; FPC24 и gpiochip4 lines 19/20/21 использовать запрещено.
Провода переставлять при отключённом питании. Наличие touch-проводов
не подтверждает работу драйвера на Armbian.

Все команды с путями `tools/` выполняются от корня репозитория.

- [Armbian overlay](../../tools/target/overlays/rk3528-spidev.dts).
- [Тест ILI9341](../../tools/target/test_ili9341.py).
- [Загрузочная схема](../reference/boot.md) и [результаты проверки](../reference/validation/README.md).

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
  tools/target/overlays/rk3528-spidev.dts \
  tools/target/test_ili9341.py \
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

## Диагностика

Сбой изображения, GPIO и подключение UART описаны в
[диагностике и восстановлении](troubleshooting.md).

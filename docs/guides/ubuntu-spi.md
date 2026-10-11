# FriendlyElec Ubuntu 24.04: ILI9341 и XPT2046

Основной аппаратно проверенный маршрут для официального
`ubuntu-noble-core-arm64`: Ubuntu 24.04.3, kernel `6.1.141 #27`, eMMC,
Python 3.12.3. Он включает SPI1 в заводской системе, запускает ILI9341 и
опциональный XPT2046. Дисплей и тач проверены вместе после перезагрузки
2026-08-01; подробные результаты — в [справочнике проверок](../reference/validation/README.md).
Отдельный сквозной прогон установщика с `--touch` остаётся в
[разработке](../development/README.md).

Перед началом сверить [проводку и GPIO](../reference/hardware.md), подготовить
UART или recovery/microSD. Команды с путями `tools/` выполнять от корня
репозитория. Скрипты запускаются в Linux самой NanoPi.

[Загрузочная схема](../reference/boot.md) задаёт применимость этой процедуры.
[Справочник инструментов](../reference/tools.md) описывает режимы установщика,
Python runtime и диагностические скрипты.

## Автоматическая установка

Для обследованного официального образа достаточно скопировать один автономный
скрипт. По умолчанию он устанавливает зависимости, собирает и полностью
проверяет новый `resource.img`, но ничего не записывает в eMMC:

```bash
scp tools/target/enable_spi1.sh \
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
[аппаратном справочнике](../reference/hardware.md), включить оба устройства одной командой:

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
scp tools/target/test_ili9341.py \
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

## Проверить тачскрин

Для guided-проверки скопировать оба файла в один каталог:

```bash
scp tools/target/test_ili9341.py tools/target/test_xpt2046.py \
  pi@192.168.1.88:/home/pi/

ssh -t pi@192.168.1.88 \
  'sudo /opt/ili9341/bin/python /home/pi/test_xpt2046.py'
```

Скрипт сам находит handler по имени `ADS7846 Touchscreen`. На дисплее
последовательно появляются пять жёлтых мишеней; каждую нужно нажать и полностью
отпустить. Принятая мишень кратко становится зелёной. Результат с evdev
диапазонами, pressure, samples и линейной ошибкой сохраняется в
`/tmp/xpt2046-guided-samples.json`.

Диапазоны координат, калибровка и сообщения драйвера описаны в
[справочнике дисплея и тача](../reference/display-and-touch.md).

## Дополнительные процедуры

- [Ручная сборка и проверка resource.img](resource-image.md) — нативный маршрут для того же заводского образа.
- [Диагностика и восстановление](troubleshooting.md) — SPI, GPIO, UART и возврат бэкапа.
- [Полный eFlasher-образ Ubuntu](../development/ubuntu-image.md) — сборочный маршрут в разработке.
- [Официальный Debian 13](../development/friendlyelec-debian.md) — отдельный неподтверждённый на плате вариант.

## Источники

- [FriendlyELEC NanoPi Zero2 Wiki](https://wiki.friendlyelec.com/wiki/index.php/NanoPi_Zero2)
- [FriendlyElec kernel 6.1](https://github.com/friendlyarm/kernel-rockchip/tree/nanopi6-v6.1.y)
- [FriendlyElec sd-fuse RK3528](https://github.com/friendlyarm/sd-fuse_rk3528/tree/kernel-6.1.y)
- [Ubuntu 24.04 python3-libgpiod](https://packages.ubuntu.com/noble/python3-libgpiod)
- [Python gpiod 2.2.1](https://pypi.org/project/gpiod/2.2.1/)

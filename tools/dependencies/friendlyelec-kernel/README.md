# FriendlyElec kernel и сборка образов

[`source.lock.json`](source.lock.json) фиксирует исходники, исследованные
2026-08-01: kernel-rockchip `221af17f44d3b513b53b694d5b41614e53c5ab1b`
и sd-fuse_rk3528 `b35de9f870e0a0702ea33369154c9ec12494bcd1`.
Дата относится к исследованию исходников; checkout зависимости в Git
этого репозитория не хранится.

| Патч | Назначение |
| --- | --- |
| [official-friendlyelec-spi1.patch](official-friendlyelec-spi1.patch) | SPI1, CS0 и spidev для дисплея |
| [official-friendlyelec-spi1-touch.patch](official-friendlyelec-spi1-touch.patch) | CS0 для дисплея, CS1 и ads7846 для XPT2046, IRQ FPC4 и измеренные raw-range свойства |

Патчи взаимоисключающие: каждый применяется к чистому закреплённому DTS
NanoPi, не поверх другого патча. Автономный
[`enable_spi1.sh`](../../target/enable_spi1.sh) содержит встроенные варианты
того же изменения; отдельные файлы нужны ручной сборке.

Перед записью образа чисто собранный DTB должен совпасть с заводским,
после перепаковки все ресурсы, кроме целевого DTB, должны сохраниться.
Новый commit upstream или образ ОС требует повторной проверки применимости.
Команды и барьеры: [нативная сборка](../../../docs/guides/resource-image.md).

Исходники: [kernel на исследованном commit](https://github.com/friendlyarm/kernel-rockchip/tree/221af17f44d3b513b53b694d5b41614e53c5ab1b),
[sd-fuse на исследованном commit](https://github.com/friendlyarm/sd-fuse_rk3528/tree/b35de9f870e0a0702ea33369154c9ec12494bcd1).
SHA-256 патчей: [`tools/SHA256SUMS`](../../SHA256SUMS).

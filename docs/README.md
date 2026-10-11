# Документация NanoPi Zero2

## Руководства

| Задача | Инструкция | Граница проверки |
| --- | --- | --- |
| Включить SPI1, запустить ILI9341 и XPT2046 | [FriendlyElec Ubuntu](guides/ubuntu-spi.md) | Совместная работа на Ubuntu 24.04.3 / kernel `6.1.141 #27` |
| Подготовить DTB и resource.img вручную на плате | [Нативная сборка](guides/resource-image.md) | Сборка, запись/readback и загрузка проверены для указанного заводского образа |
| Запустить дисплей через пользовательский overlay | [Armbian SPI](guides/armbian-spi.md) | Только дисплей на указанной сборке Armbian 26.8 / Debian 13 |
| Разобрать сбой GPIO, SPI, изображения или загрузки | [Диагностика и восстановление](guides/troubleshooting.md) | Recovery-процедура описана; отдельный прогон восстановления остаётся в разработке |

## Справочник

- [Аппаратные интерфейсы, 30-pin FPC и проводка](reference/hardware.md).
- [ОС, resource.img и различия загрузочных схем](reference/boot.md).
- [ILI9341, XPT2046, Device Tree и калибровка](reference/display-and-touch.md).
- [Установщик, диагностические скрипты и контроль целостности](reference/tools.md).
- [Конфигурации, результаты и границы аппаратной проверки](reference/validation/README.md).

## Официальные источники

[Каталог FriendlyElec](vendor/README.md) содержит ссылки на wiki и схему;
оригиналы локально не сохранены. [Версии исходников и патчи](../tools/dependencies/friendlyelec-kernel/README.md)
находятся рядом с материалами программной зависимости.

## Разработка

[Сборочные варианты и незавершённая квалификация](development/README.md):
полные eFlasher Ubuntu/Debian, расширенные проверки тача, установщика,
восстановления и Armbian.

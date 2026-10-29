# Spec Delta

## Purpose

Жизненный цикл отправок и заказа: физическое движение товара со склада в ПВЗ и выдача клиенту. Определяет, когда меняются остатки и статус заказа.

## ADDED Requirements

### Requirement: Отгрузка со склада
Система SHALL переводить отправку `Planned` → `Dispatched` по `POST /api/shipments/{id}/dispatch`. При этом на складе-источнике `quantity` и `reserved` SHALL уменьшаться на количества позиций. Система SHALL записывать `dispatchedAt` и расчётное время прибытия `estimatedArrivalAt` (отправка плюс `totalMinutes`).

#### Scenario: Списание при отгрузке
- **WHEN** отправляется 3 единицы со склада с `quantity` 10 и `reserved` 3
- **THEN** `quantity` равно 7, `reserved` равно 0, отправка `Dispatched`

#### Scenario: Повторная отгрузка
- **WHEN** отправка уже `Dispatched` или `Cancelled`
- **THEN** ответ 409 с `code` равным `shipment_invalid_transition`, остатки не меняются

### Requirement: Доставка в ПВЗ
Система SHALL переводить отправку `Dispatched` → `Delivered` по `POST /api/shipments/{id}/deliver` и записывать `deliveredAt`. Из других статусов переход SHALL быть отклонён.

#### Scenario: Доставка без отгрузки
- **WHEN** отправка в статусе `Planned` получает `deliver`
- **THEN** ответ 409 с `code` равным `shipment_invalid_transition`

### Requirement: Статус заказа
Статус заказа SHALL вычисляться по отправкам: `Planned`, пока ни одна не отгружена; `InTransit`, пока хотя бы одна отгружена и не все доставлены; `ReadyForPickup`, когда все доставлены. `Cancelled` и `Completed` SHALL задаваться только отменой и выдачей.

#### Scenario: Частичная доставка
- **WHEN** у заказа две отправки, одна `Delivered`, другая `Dispatched`
- **THEN** заказ в статусе `InTransit`

#### Scenario: Все отправки доставлены
- **WHEN** последняя отправка заказа становится `Delivered`
- **THEN** заказ в статусе `ReadyForPickup`

### Requirement: Выдача заказа
Система SHALL переводить заказ `ReadyForPickup` → `Completed` по `POST /api/orders/{id}/pickup`. Из других статусов выдача SHALL быть отклонена.

#### Scenario: Успешная выдача
- **WHEN** заказ в статусе `ReadyForPickup` выдаётся клиенту
- **THEN** статус заказа `Completed`

#### Scenario: Выдача не готового заказа
- **WHEN** заказ в статусе `InTransit` выдаётся клиенту
- **THEN** ответ 409 с `code` равным `order_invalid_transition`

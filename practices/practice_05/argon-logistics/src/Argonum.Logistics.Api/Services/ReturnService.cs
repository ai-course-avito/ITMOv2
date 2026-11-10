using Argonum.Logistics.Api.Contracts;
using Argonum.Logistics.Api.Data;
using Argonum.Logistics.Api.Infrastructure;
using Argonum.Logistics.Core;
using Argonum.Logistics.Core.Entities;
using Argonum.Logistics.Core.Planning;
using Microsoft.EntityFrameworkCore;

namespace Argonum.Logistics.Api.Services;

/// <summary>
/// Отказ от товара и возвратные отправки ПВЗ → склад. Как и OrderService: всё, что трогает
/// остатки или место на складах, идёт под InventoryLock и фиксируется одним SaveChanges.
/// </summary>
public sealed class ReturnService(ArgonDbContext db, InventoryLock gate, TimeProvider time)
{
    /// <summary>Предпросмотр: куда поедет возврат. Данные не меняет, заказ не проверяет.</summary>
    public async Task<DeliveryPlan> PlanAsync(int pickupPointId, List<OrderItemRequest>? items, CancellationToken ct)
    {
        var requested = PlanningService.Normalize(items);

        var pickup = await db.PickupPoints.AsNoTracking().FirstOrDefaultAsync(p => p.Id == pickupPointId, ct)
                     ?? throw DomainException.NotFound("pickup_point_not_found", $"ПВЗ {pickupPointId} не найден.");

        var productIds = requested.Select(r => r.ProductId).ToList();
        var products = await db.Products.AsNoTracking()
            .Where(p => productIds.Contains(p.Id))
            .Select(p => new ProductRef(p.Id, p.Sku, p.Name))
            .ToListAsync(ct);
        var known = products.Select(p => p.Id).ToHashSet();
        if (productIds.Any(id => !known.Contains(id)))
            throw DomainException.NotFound("product_not_found",
                $"Товар {productIds.First(id => !known.Contains(id))} не найден.");

        return await BuildPlanAsync(pickup.Id, pickup.Name, products, requested, ct);
    }

    public Task<OrderDto> RefuseAsync(int userId, int orderId, RefusalRequest request, CancellationToken ct) =>
        gate.RunAsync(async () =>
        {
            var items = ValidateShape(request.Items);

            var order = await db.OrdersWithDetails().FirstOrDefaultAsync(o => o.Id == orderId && o.UserId == userId, ct)
                        ?? throw DomainException.NotFound("order_not_found", $"Заказ {orderId} не найден.");
            if (order.Status != OrderStatus.ReadyForPickup)
                throw DomainException.Conflict("order_not_refusable",
                    $"От товара в заказе со статусом {order.Status} отказаться нельзя: только пока он готов к выдаче.");

            var lines = order.Items.ToDictionary(i => i.ProductId);
            var v = new Validator();
            for (var i = 0; i < items.Count; i++)
                v.Check(lines.ContainsKey(items[i].ProductId), $"items[{i}].productId", "Этого товара нет в заказе.");
            v.ThrowIfInvalid();

            foreach (var item in items)
            {
                var line = lines[item.ProductId];
                var left = line.Quantity - line.RefusedQuantity;
                if (item.Quantity > left)
                    throw DomainException.Conflict("refusal_exceeds_ordered",
                        $"По товару {line.Sku} можно отказаться не больше чем от {left}: заказано {line.Quantity}, уже возвращено {line.RefusedQuantity}.");
            }

            var products = order.Items.Select(i => new ProductRef(i.ProductId, i.Sku, i.Name)).ToList();
            var requested = items.Select(i => new RequestedItem(i.ProductId, i.Quantity)).ToList();
            var plan = await BuildPlanAsync(order.PickupPointId, order.PickupPointName, products, requested, ct);

            var now = time.GetUtcNow();
            foreach (var s in plan.Shipments)
            {
                order.Returns.Add(new ReturnShipment
                {
                    PickupPointId = order.PickupPointId,
                    PickupPointName = order.PickupPointName,
                    WarehouseId = s.WarehouseId,
                    WarehouseName = s.WarehouseName,
                    Status = ReturnStatus.Planned,
                    TotalMinutes = s.TotalMinutes,
                    RouteJson = OrderMapper.Serialize(s),
                    CreatedAt = now,
                    Items = s.Items.Select(i => new ReturnShipmentItem
                    {
                        ProductId = i.ProductId,
                        Sku = i.Sku,
                        Name = i.Name,
                        Quantity = i.Quantity
                    }).ToList()
                });
            }

            foreach (var item in items) lines[item.ProductId].RefusedQuantity += item.Quantity;
            if (order.Items.All(i => i.RefusedQuantity == i.Quantity))
                order.Status = OrderStatus.Returned;

            await db.SaveChangesAsync(ct);
            return OrderMapper.ToDto(order);
        });

    public Task<OrderDto> DispatchAsync(int returnId, CancellationToken ct) =>
        gate.RunAsync(async () =>
        {
            var (order, ret) = await LoadAsync(returnId, ct);
            if (ret.Status != ReturnStatus.Planned)
                throw DomainException.Conflict("return_invalid_transition",
                    $"Возврат в статусе {ret.Status} нельзя отгрузить.");

            var now = time.GetUtcNow();
            ret.Status = ReturnStatus.Dispatched;
            ret.DispatchedAt = now;
            ret.EstimatedArrivalAt = now.AddMinutes(ret.TotalMinutes);
            await db.SaveChangesAsync(ct);
            return OrderMapper.ToDto(order);
        });

    public Task<OrderDto> DeliverAsync(int returnId, CancellationToken ct) =>
        gate.RunAsync(async () =>
        {
            var (order, ret) = await LoadAsync(returnId, ct);
            if (ret.Status != ReturnStatus.Dispatched)
                throw DomainException.Conflict("return_invalid_transition",
                    $"Возврат в статусе {ret.Status} нельзя доставить.");

            // Место под возврат уже было в «входящем»; теперь оно становится занятым.
            var productIds = ret.Items.Select(i => i.ProductId).ToList();
            var lines = (await db.Stock
                    .Where(s => s.WarehouseId == ret.WarehouseId && productIds.Contains(s.ProductId))
                    .ToListAsync(ct))
                .ToDictionary(s => s.ProductId);

            foreach (var item in ret.Items)
            {
                if (!lines.TryGetValue(item.ProductId, out var line))
                {
                    if (!await db.Products.AnyAsync(p => p.Id == item.ProductId, ct)) continue;
                    line = new StockItem { WarehouseId = ret.WarehouseId, ProductId = item.ProductId };
                    db.Stock.Add(line);
                    lines[item.ProductId] = line;
                }
                line.Quantity += item.Quantity;
            }

            ret.Status = ReturnStatus.Delivered;
            ret.DeliveredAt = time.GetUtcNow();
            await db.SaveChangesAsync(ct);
            return OrderMapper.ToDto(order);
        });

    // ---- Вспомогательное ----

    private async Task<DeliveryPlan> BuildPlanAsync(
        int pickupPointId, string pickupPointName, List<ProductRef> products, List<RequestedItem> requested, CancellationToken ct)
    {
        var space = await SpaceCalculator.LoadAsync(db, null, ct);
        var warehouses = (await db.Warehouses.AsNoTracking().Select(w => new { w.Id, w.Name, w.Capacity }).ToListAsync(ct))
            .Select(w => new WarehouseSpace(
                w.Id, w.Name, Math.Max(0, w.Capacity - space.GetValueOrDefault(w.Id).Used)))
            .ToList();
        var routes = await db.Routes.AsNoTracking()
            .Select(r => new RouteEdge(r.FromWarehouseId, r.ToWarehouseId, r.Minutes)).ToListAsync(ct);
        var links = await db.PickupLinks.AsNoTracking()
            .Where(l => l.PickupPointId == pickupPointId)
            .Select(l => new PickupEdge(l.WarehouseId, l.Minutes)).ToListAsync(ct);

        return ReturnPlanner.Build(new ReturnPlanningInput(
            pickupPointId, pickupPointName, warehouses, routes, links, products, requested));
    }

    /// <summary>Форма запроса: непустой список, количества от 1, товары без повторов.</summary>
    private static List<OrderItemRequest> ValidateShape(List<OrderItemRequest>? items)
    {
        var v = new Validator();
        v.Check(items is { Count: > 0 }, "items", "Нужна хотя бы одна позиция.");
        for (var i = 0; i < (items?.Count ?? 0); i++)
            v.Check(items![i].Quantity >= 1, $"items[{i}].quantity", "Количество не меньше 1.");
        v.Check(items is null || items.Select(i => i.ProductId).Distinct().Count() == items.Count,
            "items", "Товар не должен повторяться.");
        v.ThrowIfInvalid();
        return items!;
    }

    private async Task<(Order Order, ReturnShipment Return)> LoadAsync(int returnId, CancellationToken ct)
    {
        var order = await db.OrdersWithDetails().FirstOrDefaultAsync(o => o.Returns.Any(r => r.Id == returnId), ct)
                    ?? throw DomainException.NotFound("return_not_found", $"Возврат {returnId} не найден.");
        return (order, order.Returns.Single(r => r.Id == returnId));
    }
}

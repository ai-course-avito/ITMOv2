using Argonum.Logistics.Api.Contracts;
using Argonum.Logistics.Api.Data;
using Argonum.Logistics.Api.Infrastructure;
using Argonum.Logistics.Core;
using Argonum.Logistics.Core.Planning;
using Microsoft.EntityFrameworkCore;

namespace Argonum.Logistics.Api.Services;

/// <summary>Загружает граф и остатки из БД и отдаёт их чистому DeliveryPlanner. Данные не меняет.</summary>
public sealed class PlanningService(ArgonDbContext db)
{
    private const int MaxItems = 100;
    private const int MaxQuantityPerItem = 100_000;

    public async Task<DeliveryPlan> PlanAsync(int pickupPointId, List<OrderItemRequest>? items, CancellationToken ct)
    {
        var requested = Normalize(items);

        var pickup = await db.PickupPoints.AsNoTracking().FirstOrDefaultAsync(p => p.Id == pickupPointId, ct)
                     ?? throw DomainException.NotFound("pickup_point_not_found", $"ПВЗ {pickupPointId} не найден.");
        if (!pickup.IsActive)
            throw DomainException.Conflict("pickup_point_inactive", $"ПВЗ {pickupPointId} не принимает заказы.");

        var productIds = requested.Select(r => r.ProductId).ToList();
        var products = await db.Products.AsNoTracking()
            .Where(p => productIds.Contains(p.Id))
            .Select(p => new ProductRef(p.Id, p.Sku, p.Name))
            .ToListAsync(ct);
        var known = products.Select(p => p.Id).ToHashSet();
        if (productIds.Any(id => !known.Contains(id)))
            throw DomainException.NotFound("product_not_found",
                $"Товар {productIds.First(id => !known.Contains(id))} не найден.");

        var warehouses = await db.Warehouses.AsNoTracking()
            .Select(w => new WarehouseRef(w.Id, w.Name)).ToListAsync(ct);
        var routes = await db.Routes.AsNoTracking()
            .Select(r => new RouteEdge(r.FromWarehouseId, r.ToWarehouseId, r.Minutes)).ToListAsync(ct);
        var links = await db.PickupLinks.AsNoTracking()
            .Where(l => l.PickupPointId == pickupPointId)
            .Select(l => new PickupEdge(l.WarehouseId, l.Minutes)).ToListAsync(ct);
        var stock = await db.Stock.AsNoTracking()
            .Where(s => productIds.Contains(s.ProductId) && s.Quantity - s.Reserved > 0)
            .Select(s => new StockAvailability(s.WarehouseId, s.ProductId, s.Quantity - s.Reserved))
            .ToListAsync(ct);

        return DeliveryPlanner.Build(new PlanningInput(
            pickup.Id, pickup.Name, warehouses, routes, links, stock, products, requested));
    }

    /// <summary>Проверяет позиции и суммирует строки с одним товаром.</summary>
    public static List<RequestedItem> Normalize(List<OrderItemRequest>? items)
    {
        var v = new Validator();
        v.Check(items is { Count: > 0 }, "items", "Нужна хотя бы одна позиция.");
        v.Check(items is null || items.Count <= MaxItems, "items", $"Не более {MaxItems} позиций.");
        for (var i = 0; i < (items?.Count ?? 0); i++)
            v.Range($"items[{i}].quantity", items![i].Quantity, 1, MaxQuantityPerItem);
        v.ThrowIfInvalid();

        return items!
            .GroupBy(i => i.ProductId)
            .Select(g => new RequestedItem(g.Key, g.Sum(i => i.Quantity)))
            .ToList();
    }
}

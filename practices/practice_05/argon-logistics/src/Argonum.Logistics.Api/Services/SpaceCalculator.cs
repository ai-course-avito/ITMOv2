using Argonum.Logistics.Api.Data;
using Argonum.Logistics.Core;
using Argonum.Logistics.Core.Entities;
using Microsoft.EntityFrameworkCore;

namespace Argonum.Logistics.Api.Services;

/// <param name="Occupied">Сумма Quantity по строкам остатка (резерв место не освобождает).</param>
/// <param name="Incoming">Количество в возвратных отправках Planned/Dispatched на этот склад.</param>
public readonly record struct SpaceUsage(int Occupied, int Incoming)
{
    public int Used => Occupied + Incoming;
}

/// <summary>
/// Занятое и входящее место складов. Считается запросом, а не хранится: так нет второй точки правды.
/// Вызывать под InventoryLock, если результат нужен для записи.
/// </summary>
public static class SpaceCalculator
{
    public static async Task<Dictionary<int, SpaceUsage>> LoadAsync(ArgonDbContext db, int? warehouseId, CancellationToken ct)
    {
        var stock = db.Stock.AsNoTracking();
        var returns = db.ReturnShipments.AsNoTracking().Where(r => r.Status != ReturnStatus.Delivered);
        if (warehouseId is { } id)
        {
            stock = stock.Where(s => s.WarehouseId == id);
            returns = returns.Where(r => r.WarehouseId == id);
        }

        var occupied = (await stock
                .GroupBy(s => s.WarehouseId)
                .Select(g => new { WarehouseId = g.Key, Quantity = g.Sum(s => s.Quantity) })
                .ToListAsync(ct))
            .ToDictionary(x => x.WarehouseId, x => x.Quantity);

        var incoming = (await returns
                .Select(r => new { r.WarehouseId, Quantity = r.Items.Sum(i => i.Quantity) })
                .ToListAsync(ct))
            .GroupBy(x => x.WarehouseId)
            .ToDictionary(g => g.Key, g => g.Sum(x => x.Quantity));

        return occupied.Keys.Union(incoming.Keys)
            .ToDictionary(w => w, w => new SpaceUsage(occupied.GetValueOrDefault(w), incoming.GetValueOrDefault(w)));
    }

    public static async Task<SpaceUsage> LoadOneAsync(ArgonDbContext db, int warehouseId, CancellationToken ct) =>
        (await LoadAsync(db, warehouseId, ct)).GetValueOrDefault(warehouseId);

    /// <summary>Бросает warehouse_capacity_exceeded, если добавление не помещается.</summary>
    public static void EnsureRoom(Warehouse warehouse, SpaceUsage usage, int addQuantity)
    {
        if (addQuantity <= 0) return;
        if ((long)usage.Used + addQuantity > warehouse.Capacity)
            throw DomainException.Conflict("warehouse_capacity_exceeded",
                $"На складе «{warehouse.Name}» нет места: вместимость {warehouse.Capacity}, " +
                $"занято {usage.Occupied}, ожидается возвратов {usage.Incoming}, добавляется {addQuantity}.");
    }
}

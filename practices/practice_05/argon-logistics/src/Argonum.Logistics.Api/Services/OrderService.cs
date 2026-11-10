using Argonum.Logistics.Api.Contracts;
using Argonum.Logistics.Api.Data;
using Argonum.Logistics.Api.Infrastructure;
using Argonum.Logistics.Core;
using Argonum.Logistics.Core.Entities;
using Microsoft.EntityFrameworkCore;

namespace Argonum.Logistics.Api.Services;

/// <summary>
/// Заказы и отправки. Каждая операция, трогающая остатки, идёт под InventoryLock
/// и фиксируется одним SaveChanges, то есть одной транзакцией.
/// </summary>
public sealed class OrderService(
    ArgonDbContext db,
    PlanningService planning,
    InventoryLock gate,
    TimeProvider time)
{
    public Task<OrderDto> CreateAsync(int userId, PlanRequest request, CancellationToken ct) =>
        gate.RunAsync(async () =>
        {
            var plan = await planning.PlanAsync(request.PickupPointId, request.Items, ct);
            var pickup = await db.PickupPoints.AsNoTracking().FirstAsync(p => p.Id == request.PickupPointId, ct);

            var lines = plan.Shipments
                .SelectMany(s => s.Items.Select(i => (s.WarehouseId, i.ProductId, i.Quantity)))
                .ToList();
            var stock = await LoadStockAsync(lines.Select(l => (l.WarehouseId, l.ProductId)), ct);
            foreach (var (warehouseId, productId, quantity) in lines)
            {
                var line = stock[(warehouseId, productId)];
                line.Reserved += quantity;
                EnsureInvariant(line);
            }

            var order = new Order
            {
                UserId = userId,
                PickupPointId = pickup.Id,
                PickupPointName = pickup.Name,
                Status = OrderStatus.Planned,
                EstimatedMinutes = plan.EstimatedMinutes,
                CreatedAt = time.GetUtcNow(),
                Items = plan.Shipments
                    .SelectMany(s => s.Items)
                    .GroupBy(i => i.ProductId)
                    .Select(g => new OrderItem
                    {
                        ProductId = g.Key,
                        Sku = g.First().Sku,
                        Name = g.First().Name,
                        Quantity = g.Sum(i => i.Quantity)
                    }).ToList(),
                Shipments = plan.Shipments.Select(s => new Shipment
                {
                    WarehouseId = s.WarehouseId,
                    WarehouseName = s.WarehouseName,
                    Status = ShipmentStatus.Planned,
                    TotalMinutes = s.TotalMinutes,
                    RouteJson = OrderMapper.Serialize(s),
                    Items = s.Items.Select(i => new ShipmentItem
                    {
                        ProductId = i.ProductId,
                        Sku = i.Sku,
                        Name = i.Name,
                        Quantity = i.Quantity
                    }).ToList()
                }).ToList()
            };

            db.Orders.Add(order);
            await db.SaveChangesAsync(ct);
            return OrderMapper.ToDto(order);
        });

    public Task<OrderDto> CancelAsync(int userId, int orderId, CancellationToken ct) =>
        gate.RunAsync(async () =>
        {
            var order = await LoadOrderAsync(o => o.Id == orderId && o.UserId == userId, orderId, ct);
            if (order.Status != OrderStatus.Planned)
                throw DomainException.Conflict("order_not_cancellable",
                    $"Заказ в статусе {order.Status} нельзя отменить.");

            var lines = order.Shipments.SelectMany(s => s.Items.Select(i => (s.WarehouseId, i.ProductId, i.Quantity))).ToList();
            var stock = await LoadStockAsync(lines.Select(l => (l.WarehouseId, l.ProductId)), ct);
            foreach (var (warehouseId, productId, quantity) in lines)
            {
                var line = stock[(warehouseId, productId)];
                line.Reserved -= quantity;
                EnsureInvariant(line);
            }

            foreach (var s in order.Shipments) s.Status = ShipmentStatus.Cancelled;
            order.Status = OrderStatus.Cancelled;
            await db.SaveChangesAsync(ct);
            return OrderMapper.ToDto(order);
        });

    public Task<OrderDto> DispatchAsync(int shipmentId, CancellationToken ct) =>
        gate.RunAsync(async () =>
        {
            var order = await LoadOrderByShipmentAsync(shipmentId, ct);
            var shipment = order.Shipments.Single(s => s.Id == shipmentId);
            if (shipment.Status != ShipmentStatus.Planned)
                throw DomainException.Conflict("shipment_invalid_transition",
                    $"Отправку в статусе {shipment.Status} нельзя отгрузить.");

            var stock = await LoadStockAsync(shipment.Items.Select(i => (shipment.WarehouseId, i.ProductId)), ct);
            foreach (var item in shipment.Items)
            {
                var line = stock[(shipment.WarehouseId, item.ProductId)];
                line.Quantity -= item.Quantity;
                line.Reserved -= item.Quantity;
                EnsureInvariant(line);
            }

            var now = time.GetUtcNow();
            shipment.Status = ShipmentStatus.Dispatched;
            shipment.DispatchedAt = now;
            shipment.EstimatedArrivalAt = now.AddMinutes(shipment.TotalMinutes);
            order.RecomputeStatus();
            await db.SaveChangesAsync(ct);
            return OrderMapper.ToDto(order);
        });

    public Task<OrderDto> DeliverAsync(int shipmentId, CancellationToken ct) =>
        gate.RunAsync(async () =>
        {
            var order = await LoadOrderByShipmentAsync(shipmentId, ct);
            var shipment = order.Shipments.Single(s => s.Id == shipmentId);
            if (shipment.Status != ShipmentStatus.Dispatched)
                throw DomainException.Conflict("shipment_invalid_transition",
                    $"Отправку в статусе {shipment.Status} нельзя доставить.");

            shipment.Status = ShipmentStatus.Delivered;
            shipment.DeliveredAt = time.GetUtcNow();
            order.RecomputeStatus();
            await db.SaveChangesAsync(ct);
            return OrderMapper.ToDto(order);
        });

    public Task<OrderDto> PickupAsync(int orderId, CancellationToken ct) =>
        gate.RunAsync(async () =>
        {
            var order = await LoadOrderAsync(o => o.Id == orderId, orderId, ct);
            if (order.Status != OrderStatus.ReadyForPickup)
                throw DomainException.Conflict("order_invalid_transition",
                    $"Заказ в статусе {order.Status} нельзя выдать.");

            order.Status = OrderStatus.Completed;
            await db.SaveChangesAsync(ct);
            return OrderMapper.ToDto(order);
        });

    // ---- Чтение (без блокировки) ----

    public async Task<OrderDto> GetAsync(int orderId, int? userId, CancellationToken ct)
    {
        var order = await OrdersQuery().AsNoTracking()
            .FirstOrDefaultAsync(o => o.Id == orderId && (userId == null || o.UserId == userId), ct)
            ?? throw OrderNotFound(orderId);
        return OrderMapper.ToDto(order);
    }

    public async Task<List<OrderDto>> ListAsync(int? userId, string? status, int? pickupPointId, CancellationToken ct)
    {
        OrderStatus? parsed = null;
        if (status is not null)
        {
            if (!Enum.TryParse<OrderStatus>(status, ignoreCase: true, out var s) || !Enum.IsDefined(s))
                throw DomainException.Validation(new Dictionary<string, string[]>
                {
                    ["status"] = [$"Допустимо: {string.Join(", ", Enum.GetNames<OrderStatus>())}."]
                });
            parsed = s;
        }

        var query = OrdersQuery().AsNoTracking();
        if (userId is not null) query = query.Where(o => o.UserId == userId);
        if (parsed is not null) query = query.Where(o => o.Status == parsed);
        if (pickupPointId is not null) query = query.Where(o => o.PickupPointId == pickupPointId);

        var orders = await query.OrderBy(o => o.Id).ToListAsync(ct);
        return orders.Select(OrderMapper.ToDto).ToList();
    }

    // ---- Вспомогательное ----

    private IQueryable<Order> OrdersQuery() => db.OrdersWithDetails();

    private async Task<Order> LoadOrderAsync(
        System.Linq.Expressions.Expression<Func<Order, bool>> predicate, int orderId, CancellationToken ct) =>
        await OrdersQuery().FirstOrDefaultAsync(predicate, ct) ?? throw OrderNotFound(orderId);

    private async Task<Order> LoadOrderByShipmentAsync(int shipmentId, CancellationToken ct) =>
        await OrdersQuery().FirstOrDefaultAsync(o => o.Shipments.Any(s => s.Id == shipmentId), ct)
        ?? throw DomainException.NotFound("shipment_not_found", $"Отправка {shipmentId} не найдена.");

    private async Task<Dictionary<(int Warehouse, int Product), StockItem>> LoadStockAsync(
        IEnumerable<(int Warehouse, int Product)> keys, CancellationToken ct)
    {
        var wanted = keys.Distinct().ToList();
        var warehouseIds = wanted.Select(k => k.Warehouse).Distinct().ToList();
        var productIds = wanted.Select(k => k.Product).Distinct().ToList();
        var rows = await db.Stock
            .Where(s => warehouseIds.Contains(s.WarehouseId) && productIds.Contains(s.ProductId))
            .ToListAsync(ct);
        var map = rows.ToDictionary(s => (s.WarehouseId, s.ProductId));

        var absent = wanted.FirstOrDefault(k => !map.ContainsKey(k));
        if (absent != default)
            throw DomainException.Conflict("stock_inconsistent",
                $"Нет строки остатка: склад {absent.Warehouse}, товар {absent.Product}.");
        return map;
    }

    private static void EnsureInvariant(StockItem line)
    {
        if (line.Reserved < 0 || line.Reserved > line.Quantity)
            throw DomainException.Conflict("stock_inconsistent",
                $"Нарушен баланс остатка: склад {line.WarehouseId}, товар {line.ProductId}.");
    }

    private static DomainException OrderNotFound(int orderId) =>
        DomainException.NotFound("order_not_found", $"Заказ {orderId} не найден.");
}

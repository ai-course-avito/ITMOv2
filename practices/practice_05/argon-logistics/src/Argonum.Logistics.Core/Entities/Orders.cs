namespace Argonum.Logistics.Core.Entities;

public enum OrderStatus
{
    Planned,
    InTransit,
    ReadyForPickup,
    Completed,
    Cancelled,

    /// <summary>Клиент отказался от всех позиций, товар возвращается на склады.</summary>
    Returned
}

public enum ReturnStatus
{
    Planned,
    Dispatched,
    Delivered
}

public enum ShipmentStatus
{
    Planned,
    Dispatched,
    Delivered,
    Cancelled
}

public class User
{
    public int Id { get; set; }
    public string Name { get; set; } = "";
    public string Email { get; set; } = "";
    public string EmailKey { get; set; } = "";
}

/// <summary>Заказ хранит снимки названий и маршрутов, а не ссылки на каталог и граф.</summary>
public class Order
{
    public int Id { get; set; }
    public int UserId { get; set; }
    public int PickupPointId { get; set; }
    public string PickupPointName { get; set; } = "";
    public OrderStatus Status { get; set; }
    public int EstimatedMinutes { get; set; }
    public DateTimeOffset CreatedAt { get; set; }

    public List<OrderItem> Items { get; set; } = [];
    public List<Shipment> Shipments { get; set; } = [];
    public List<ReturnShipment> Returns { get; set; } = [];

    /// <summary>Пересчитывает статус по отправкам (кроме Completed/Cancelled/Returned).</summary>
    public void RecomputeStatus()
    {
        if (Status is OrderStatus.Completed or OrderStatus.Cancelled or OrderStatus.Returned) return;

        var live = Shipments.Where(s => s.Status != ShipmentStatus.Cancelled).ToList();
        if (live.Count > 0 && live.All(s => s.Status == ShipmentStatus.Delivered))
            Status = OrderStatus.ReadyForPickup;
        else if (live.Any(s => s.Status is ShipmentStatus.Dispatched or ShipmentStatus.Delivered))
            Status = OrderStatus.InTransit;
        else
            Status = OrderStatus.Planned;
    }
}

public class OrderItem
{
    public int Id { get; set; }
    public int OrderId { get; set; }
    public int ProductId { get; set; }
    public string Sku { get; set; } = "";
    public string Name { get; set; } = "";
    public int Quantity { get; set; }

    /// <summary>Сколько единиц клиент вернул (отказался получить), от 0 до Quantity.</summary>
    public int RefusedQuantity { get; set; }
}

public class Shipment
{
    public int Id { get; set; }
    public int OrderId { get; set; }
    public int WarehouseId { get; set; }
    public string WarehouseName { get; set; } = "";
    public ShipmentStatus Status { get; set; }
    public int TotalMinutes { get; set; }

    /// <summary>JSON-снимок маршрута: {"route":[ids],"legs":[...]}.</summary>
    public string RouteJson { get; set; } = "{}";

    public DateTimeOffset? DispatchedAt { get; set; }
    public DateTimeOffset? EstimatedArrivalAt { get; set; }
    public DateTimeOffset? DeliveredAt { get; set; }

    public List<ShipmentItem> Items { get; set; } = [];
}

public class ShipmentItem
{
    public int Id { get; set; }
    public int ShipmentId { get; set; }
    public int ProductId { get; set; }
    public string Sku { get; set; } = "";
    public string Name { get; set; } = "";
    public int Quantity { get; set; }
}

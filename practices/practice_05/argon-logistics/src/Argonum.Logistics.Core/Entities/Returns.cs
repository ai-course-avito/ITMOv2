namespace Argonum.Logistics.Core.Entities;

/// <summary>Возвратная отправка ПВЗ → склад. Место на складе резервируется с создания (входящее).</summary>
public class ReturnShipment
{
    public int Id { get; set; }
    public int OrderId { get; set; }
    public int PickupPointId { get; set; }
    public string PickupPointName { get; set; } = "";
    public int WarehouseId { get; set; }
    public string WarehouseName { get; set; } = "";
    public ReturnStatus Status { get; set; }
    public int TotalMinutes { get; set; }

    /// <summary>JSON-снимок маршрута: {"route":[ids складов],"legs":[...]}, первый участок из ПВЗ.</summary>
    public string RouteJson { get; set; } = "{}";

    public DateTimeOffset CreatedAt { get; set; }
    public DateTimeOffset? DispatchedAt { get; set; }
    public DateTimeOffset? EstimatedArrivalAt { get; set; }
    public DateTimeOffset? DeliveredAt { get; set; }

    public List<ReturnShipmentItem> Items { get; set; } = [];
}

public class ReturnShipmentItem
{
    public int Id { get; set; }
    public int ReturnShipmentId { get; set; }
    public int ProductId { get; set; }
    public string Sku { get; set; } = "";
    public string Name { get; set; } = "";
    public int Quantity { get; set; }
}

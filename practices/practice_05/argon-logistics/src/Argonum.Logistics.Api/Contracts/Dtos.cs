using Argonum.Logistics.Core.Entities;
using Argonum.Logistics.Core.Planning;

namespace Argonum.Logistics.Api.Contracts;

// ---- Запросы ----
public sealed record ProductRequest(string? Sku, string? Name, string? Description);
public sealed record WarehouseRequest(string? Name, string? Address, double? MapX = null, double? MapY = null, int? Capacity = null);
public sealed record RefusalRequest(List<OrderItemRequest>? Items);
public sealed record PickupPointRequest(string? Name, string? Address, bool? IsActive, double? MapX = null, double? MapY = null);
public sealed record PositionRequest(double X, double Y);
public sealed record AddStockRequest(int ProductId, int Quantity);
public sealed record SetStockRequest(int Quantity);
public sealed record MinutesRequest(int Minutes);
public sealed record CreateRouteRequest(int FromWarehouseId, int ToWarehouseId, int Minutes, bool Bidirectional = false);
public sealed record OrderItemRequest(int ProductId, int Quantity);
public sealed record PlanRequest(int PickupPointId, List<OrderItemRequest>? Items);
public sealed record UserRequest(string? Name, string? Email);

// ---- Ответы ----
public sealed record ProductDto(int Id, string Sku, string Name, string? Description)
{
    public static ProductDto From(Product p) => new(p.Id, p.Sku, p.Name, p.Description);
}

public sealed record WarehouseDto(int Id, string Name, string Address, double MapX, double MapY, int Capacity)
{
    public static WarehouseDto From(Warehouse w) => new(w.Id, w.Name, w.Address, w.MapX, w.MapY, w.Capacity);
}

public sealed record StockLineDto(int ProductId, string Sku, string Name, int Quantity, int Reserved, int Available);

public sealed record PickupPointDto(int Id, string Name, string Address, bool IsActive, double MapX, double MapY)
{
    public static PickupPointDto From(PickupPoint p) => new(p.Id, p.Name, p.Address, p.IsActive, p.MapX, p.MapY);
}

public sealed record PickupLinkDto(int PickupPointId, int WarehouseId, string WarehouseName, int Minutes);

public sealed record RouteDto(int Id, int FromWarehouseId, int ToWarehouseId, int Minutes, RouteDto? Reverse = null)
{
    public static RouteDto From(WarehouseRoute r, RouteDto? reverse = null) =>
        new(r.Id, r.FromWarehouseId, r.ToWarehouseId, r.Minutes, reverse);
}

public sealed record UserDto(int Id, string Name, string Email)
{
    public static UserDto From(User u) => new(u.Id, u.Name, u.Email);
}

public sealed record OrderItemDto(int ProductId, string Sku, string Name, int Quantity);

public sealed record ShipmentDto(
    int Id,
    int WarehouseId,
    string WarehouseName,
    string Status,
    int TotalMinutes,
    IReadOnlyList<int> Route,
    IReadOnlyList<PlanLeg> Legs,
    IReadOnlyList<OrderItemDto> Items,
    DateTimeOffset? DispatchedAt,
    DateTimeOffset? EstimatedArrivalAt,
    DateTimeOffset? DeliveredAt);

public sealed record OrderLineDto(int ProductId, string Sku, string Name, int Quantity, int RefusedQuantity);

/// <summary>Возвратная отправка ПВЗ → склад. В Legs первый участок начинается в узле ПВЗ.</summary>
public sealed record ReturnShipmentDto(
    int Id,
    int WarehouseId,
    string WarehouseName,
    string Status,
    int TotalMinutes,
    IReadOnlyList<int> Route,
    IReadOnlyList<PlanLeg> Legs,
    IReadOnlyList<OrderItemDto> Items,
    DateTimeOffset CreatedAt,
    DateTimeOffset? DispatchedAt,
    DateTimeOffset? EstimatedArrivalAt,
    DateTimeOffset? DeliveredAt);

public sealed record OrderDto(
    int Id,
    int UserId,
    int PickupPointId,
    string PickupPointName,
    string Status,
    int EstimatedMinutes,
    DateTimeOffset CreatedAt,
    IReadOnlyList<OrderLineDto> Items,
    IReadOnlyList<ShipmentDto> Shipments,
    IReadOnlyList<ReturnShipmentDto> Returns);

public sealed record NetworkWarehouseDto(
    int Id, string Name, string Address, double MapX, double MapY, int TotalQuantity, int TotalReserved,
    int Capacity, int IncomingQuantity);

public sealed record NetworkDto(
    IReadOnlyList<NetworkWarehouseDto> Warehouses,
    IReadOnlyList<PickupPointDto> PickupPoints,
    IReadOnlyList<RouteDto> Routes,
    IReadOnlyList<PickupLinkDto> Links);

public sealed record SimulationInfoDto(bool Enabled, double SpeedFactor, double DispatchDelaySeconds, DateTimeOffset ServerTime);

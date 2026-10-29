using System.Text.Json;
using Argonum.Logistics.Api.Contracts;
using Argonum.Logistics.Core.Entities;
using Argonum.Logistics.Core.Planning;

namespace Argonum.Logistics.Api.Services;

public sealed record RouteSnapshot(IReadOnlyList<int> Route, IReadOnlyList<PlanLeg> Legs);

public static class OrderMapper
{
    private static readonly JsonSerializerOptions Json = new(JsonSerializerDefaults.Web);

    public static string Serialize(PlanShipment s) =>
        JsonSerializer.Serialize(new RouteSnapshot(s.Route, s.Legs), Json);

    public static OrderDto ToDto(Order o) => new(
        o.Id,
        o.UserId,
        o.PickupPointId,
        o.PickupPointName,
        o.Status.ToString(),
        o.EstimatedMinutes,
        o.CreatedAt,
        o.Items.OrderBy(i => i.ProductId)
            .Select(i => new OrderLineDto(i.ProductId, i.Sku, i.Name, i.Quantity, i.RefusedQuantity)).ToList(),
        o.Shipments.OrderBy(s => s.Id).Select(ToDto).ToList(),
        o.Returns.OrderBy(r => r.Id).Select(ToDto).ToList());

    private static ReturnShipmentDto ToDto(ReturnShipment r)
    {
        var snapshot = JsonSerializer.Deserialize<RouteSnapshot>(r.RouteJson, Json)
                       ?? new RouteSnapshot([], []);
        return new ReturnShipmentDto(
            r.Id,
            r.WarehouseId,
            r.WarehouseName,
            r.Status.ToString(),
            r.TotalMinutes,
            snapshot.Route,
            snapshot.Legs,
            r.Items.OrderBy(i => i.ProductId).Select(i => new OrderItemDto(i.ProductId, i.Sku, i.Name, i.Quantity)).ToList(),
            r.CreatedAt,
            r.DispatchedAt,
            r.EstimatedArrivalAt,
            r.DeliveredAt);
    }

    private static ShipmentDto ToDto(Shipment s)
    {
        var snapshot = JsonSerializer.Deserialize<RouteSnapshot>(s.RouteJson, Json)
                       ?? new RouteSnapshot([], []);
        return new ShipmentDto(
            s.Id,
            s.WarehouseId,
            s.WarehouseName,
            s.Status.ToString(),
            s.TotalMinutes,
            snapshot.Route,
            snapshot.Legs,
            s.Items.OrderBy(i => i.ProductId).Select(i => new OrderItemDto(i.ProductId, i.Sku, i.Name, i.Quantity)).ToList(),
            s.DispatchedAt,
            s.EstimatedArrivalAt,
            s.DeliveredAt);
    }
}

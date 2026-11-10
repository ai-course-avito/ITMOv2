using Argonum.Logistics.Api.Contracts;
using Argonum.Logistics.Api.Data;
using Argonum.Logistics.Api.Services;
using Argonum.Logistics.Api.Simulation;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Options;

namespace Argonum.Logistics.Api.Endpoints;

public static class NetworkEndpoints
{
    public static void MapNetwork(this IEndpointRouteBuilder app)
    {
        // Вся сеть одним запросом: интерфейс опрашивает её каждые пару секунд.
        app.MapGet("/api/network", async (ArgonDbContext db, CancellationToken ct) =>
        {
            var totals = (await db.Stock.AsNoTracking()
                    .GroupBy(s => s.WarehouseId)
                    .Select(g => new { WarehouseId = g.Key, Quantity = g.Sum(s => s.Quantity), Reserved = g.Sum(s => s.Reserved) })
                    .ToListAsync(ct))
                .ToDictionary(t => t.WarehouseId);

            var space = await SpaceCalculator.LoadAsync(db, null, ct);

            var warehouses = (await db.Warehouses.AsNoTracking().OrderBy(w => w.Id).ToListAsync(ct))
                .Select(w => new NetworkWarehouseDto(
                    w.Id, w.Name, w.Address, w.MapX, w.MapY,
                    totals.TryGetValue(w.Id, out var t) ? t.Quantity : 0,
                    totals.TryGetValue(w.Id, out var r) ? r.Reserved : 0,
                    w.Capacity,
                    space.TryGetValue(w.Id, out var u) ? u.Incoming : 0))
                .ToList();

            var pickupPoints = await db.PickupPoints.AsNoTracking().OrderBy(p => p.Id)
                .Select(p => new PickupPointDto(p.Id, p.Name, p.Address, p.IsActive, p.MapX, p.MapY))
                .ToListAsync(ct);
            var routes = await db.Routes.AsNoTracking().OrderBy(r => r.Id)
                .Select(r => new RouteDto(r.Id, r.FromWarehouseId, r.ToWarehouseId, r.Minutes, null))
                .ToListAsync(ct);
            var links = await db.PickupLinks.AsNoTracking().OrderBy(l => l.PickupPointId).ThenBy(l => l.WarehouseId)
                .Select(l => new PickupLinkDto(l.PickupPointId, l.WarehouseId, l.Warehouse!.Name, l.Minutes))
                .ToListAsync(ct);

            return new NetworkDto(warehouses, pickupPoints, routes, links);
        }).WithTags("Network");

        app.MapGet("/api/simulation", (IOptions<SimulationOptions> options, TimeProvider time) =>
        {
            var o = options.Value;
            return new SimulationInfoDto(o.Enabled, o.EffectiveSpeedFactor, o.EffectiveDispatchDelaySeconds, time.GetUtcNow());
        }).WithTags("Simulation");
    }
}

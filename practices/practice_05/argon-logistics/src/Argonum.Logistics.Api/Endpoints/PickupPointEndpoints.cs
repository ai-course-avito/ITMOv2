using Argonum.Logistics.Api.Contracts;
using Argonum.Logistics.Api.Data;
using Argonum.Logistics.Api.Infrastructure;
using Argonum.Logistics.Core;
using Argonum.Logistics.Core.Entities;
using Microsoft.EntityFrameworkCore;

namespace Argonum.Logistics.Api.Endpoints;

public static class PickupPointEndpoints
{
    private static readonly OrderStatus[] OpenStatuses =
        [OrderStatus.Planned, OrderStatus.InTransit, OrderStatus.ReadyForPickup];

    public static void MapPickupPoints(this IEndpointRouteBuilder app)
    {
        var g = app.MapGroup("/api/pickup-points").WithTags("PickupPoints");

        g.MapGet("", async (ArgonDbContext db, CancellationToken ct) =>
            await db.PickupPoints.AsNoTracking().OrderBy(p => p.Id)
                .Select(p => new PickupPointDto(p.Id, p.Name, p.Address, p.IsActive, p.MapX, p.MapY)).ToListAsync(ct));

        g.MapGet("{id:int}", async (int id, ArgonDbContext db, CancellationToken ct) =>
            PickupPointDto.From(await Find(db, id, ct)));

        g.MapPost("", async (PickupPointRequest req, ArgonDbContext db, CancellationToken ct) =>
        {
            var (name, address) = Validate(req);
            var point = new PickupPoint
            {
                Name = name, Address = address, IsActive = req.IsActive ?? true,
                MapX = req.MapX ?? 0, MapY = req.MapY ?? 0
            };
            db.PickupPoints.Add(point);
            await db.SaveChangesAsync(ct);
            return Results.Created($"/api/pickup-points/{point.Id}", PickupPointDto.From(point));
        });

        g.MapPut("{id:int}", async (int id, PickupPointRequest req, ArgonDbContext db, CancellationToken ct) =>
        {
            var (name, address) = Validate(req);
            var point = await Find(db, id, ct);
            point.Name = name;
            point.Address = address;
            point.IsActive = req.IsActive ?? point.IsActive;
            point.MapX = req.MapX ?? point.MapX;
            point.MapY = req.MapY ?? point.MapY;
            await db.SaveChangesAsync(ct);
            return PickupPointDto.From(point);
        });

        g.MapDelete("{id:int}", async (int id, ArgonDbContext db, InventoryLock gate, CancellationToken ct) =>
        {
            await gate.RunAsync(async () =>
            {
                var point = await Find(db, id, ct);
                if (await db.Orders.AnyAsync(o => o.PickupPointId == id && OpenStatuses.Contains(o.Status), ct))
                    throw DomainException.Conflict("pickup_point_has_orders", "В ПВЗ есть незавершённые заказы.");

                db.PickupPoints.Remove(point); // привязки удаляет каскад БД
                await db.SaveChangesAsync(ct);
            });
            return Results.NoContent();
        });

        g.MapPut("{id:int}/position", async (int id, PositionRequest req, ArgonDbContext db, CancellationToken ct) =>
        {
            new Validator().MapCoordinate("x", req.X).MapCoordinate("y", req.Y).ThrowIfInvalid();
            var point = await Find(db, id, ct);
            point.MapX = req.X;
            point.MapY = req.Y;
            await db.SaveChangesAsync(ct);
            return PickupPointDto.From(point);
        });

        MapLinks(g);
    }

    private static void MapLinks(RouteGroupBuilder g)
    {
        g.MapGet("{id:int}/links", async (int id, ArgonDbContext db, CancellationToken ct) =>
        {
            await Find(db, id, ct);
            return await db.PickupLinks.AsNoTracking()
                .Where(l => l.PickupPointId == id)
                .OrderBy(l => l.WarehouseId)
                .Select(l => new PickupLinkDto(l.PickupPointId, l.WarehouseId, l.Warehouse!.Name, l.Minutes))
                .ToListAsync(ct);
        });

        g.MapPut("{id:int}/links/{warehouseId:int}", async (int id, int warehouseId, MinutesRequest req, ArgonDbContext db, CancellationToken ct) =>
        {
            new Validator().Range("minutes", req.Minutes, 1, Validator.MaxMinutes).ThrowIfInvalid();
            await Find(db, id, ct);
            var warehouse = await db.Warehouses.AsNoTracking().FirstOrDefaultAsync(w => w.Id == warehouseId, ct)
                            ?? throw DomainException.NotFound("warehouse_not_found", $"Склад {warehouseId} не найден.");

            var link = await db.PickupLinks.FindAsync([id, warehouseId], ct);
            if (link is null)
                db.PickupLinks.Add(link = new PickupPointLink { PickupPointId = id, WarehouseId = warehouseId });
            link.Minutes = req.Minutes;
            await db.SaveChangesAsync(ct);
            return new PickupLinkDto(id, warehouseId, warehouse.Name, link.Minutes);
        });

        g.MapDelete("{id:int}/links/{warehouseId:int}", async (int id, int warehouseId, ArgonDbContext db, CancellationToken ct) =>
        {
            await Find(db, id, ct);
            var link = await db.PickupLinks.FindAsync([id, warehouseId], ct)
                       ?? throw DomainException.NotFound("pickup_link_not_found", "Такой привязки нет.");
            db.PickupLinks.Remove(link);
            await db.SaveChangesAsync(ct);
            return Results.NoContent();
        });
    }

    private static (string Name, string Address) Validate(PickupPointRequest req)
    {
        new Validator()
            .Required("name", req.Name, 200, out var name)
            .Required("address", req.Address, 300, out var address)
            .MapCoordinate("mapX", req.MapX)
            .MapCoordinate("mapY", req.MapY)
            .ThrowIfInvalid();
        return (name, address);
    }

    private static async Task<PickupPoint> Find(ArgonDbContext db, int id, CancellationToken ct) =>
        await db.PickupPoints.FirstOrDefaultAsync(p => p.Id == id, ct)
        ?? throw DomainException.NotFound("pickup_point_not_found", $"ПВЗ {id} не найден.");
}

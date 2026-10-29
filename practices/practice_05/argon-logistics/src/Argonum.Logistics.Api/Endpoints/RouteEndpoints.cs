using Argonum.Logistics.Api.Contracts;
using Argonum.Logistics.Api.Data;
using Argonum.Logistics.Api.Infrastructure;
using Argonum.Logistics.Core;
using Argonum.Logistics.Core.Entities;
using Microsoft.EntityFrameworkCore;

namespace Argonum.Logistics.Api.Endpoints;

public static class RouteEndpoints
{
    public static void MapRoutes(this IEndpointRouteBuilder app)
    {
        var g = app.MapGroup("/api/routes").WithTags("Network");

        g.MapGet("", async (int? warehouseId, ArgonDbContext db, CancellationToken ct) =>
        {
            var query = db.Routes.AsNoTracking();
            if (warehouseId is not null)
                query = query.Where(r => r.FromWarehouseId == warehouseId || r.ToWarehouseId == warehouseId);
            return await query.OrderBy(r => r.Id)
                .Select(r => new RouteDto(r.Id, r.FromWarehouseId, r.ToWarehouseId, r.Minutes, null))
                .ToListAsync(ct);
        });

        g.MapGet("{id:int}", async (int id, ArgonDbContext db, CancellationToken ct) =>
            RouteDto.From(await Find(db, id, ct)));

        g.MapPost("", async (CreateRouteRequest req, ArgonDbContext db, CancellationToken ct) =>
        {
            new Validator()
                .Range("minutes", req.Minutes, 1, Validator.MaxMinutes)
                .Check(req.FromWarehouseId != req.ToWarehouseId, "toWarehouseId", "Путь не может вести в тот же склад.")
                .ThrowIfInvalid();

            foreach (var id in new[] { req.FromWarehouseId, req.ToWarehouseId })
            {
                if (!await db.Warehouses.AnyAsync(w => w.Id == id, ct))
                    throw DomainException.NotFound("warehouse_not_found", $"Склад {id} не найден.");
            }

            var forward = await NewRoute(db, req.FromWarehouseId, req.ToWarehouseId, req.Minutes, ct);
            WarehouseRoute? reverse = null;
            if (req.Bidirectional)
                reverse = await NewRoute(db, req.ToWarehouseId, req.FromWarehouseId, req.Minutes, ct);

            // Оба пути сохраняются одним SaveChanges: либо оба, либо ни одного.
            await db.SaveChangesAsync(ct);
            var dto = RouteDto.From(forward, reverse is null ? null : RouteDto.From(reverse));
            return Results.Created($"/api/routes/{forward.Id}", dto);
        });

        g.MapPut("{id:int}", async (int id, MinutesRequest req, ArgonDbContext db, CancellationToken ct) =>
        {
            new Validator().Range("minutes", req.Minutes, 1, Validator.MaxMinutes).ThrowIfInvalid();
            var route = await Find(db, id, ct);
            route.Minutes = req.Minutes;
            await db.SaveChangesAsync(ct);
            return RouteDto.From(route);
        });

        g.MapDelete("{id:int}", async (int id, ArgonDbContext db, CancellationToken ct) =>
        {
            db.Routes.Remove(await Find(db, id, ct));
            await db.SaveChangesAsync(ct);
            return Results.NoContent();
        });
    }

    private static async Task<WarehouseRoute> NewRoute(ArgonDbContext db, int from, int to, int minutes, CancellationToken ct)
    {
        if (await db.Routes.AnyAsync(r => r.FromWarehouseId == from && r.ToWarehouseId == to, ct))
            throw DomainException.Conflict("route_duplicate", $"Путь {from} → {to} уже есть.");

        var route = new WarehouseRoute { FromWarehouseId = from, ToWarehouseId = to, Minutes = minutes };
        db.Routes.Add(route);
        return route;
    }

    private static async Task<WarehouseRoute> Find(ArgonDbContext db, int id, CancellationToken ct) =>
        await db.Routes.FirstOrDefaultAsync(r => r.Id == id, ct)
        ?? throw DomainException.NotFound("route_not_found", $"Путь {id} не найден.");
}

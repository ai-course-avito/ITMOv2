using Argonum.Logistics.Api.Contracts;
using Argonum.Logistics.Api.Data;
using Argonum.Logistics.Api.Infrastructure;
using Argonum.Logistics.Api.Services;
using Argonum.Logistics.Core;
using Argonum.Logistics.Core.Entities;
using Microsoft.EntityFrameworkCore;

namespace Argonum.Logistics.Api.Endpoints;

public static class WarehouseEndpoints
{
    public static void MapWarehouses(this IEndpointRouteBuilder app)
    {
        var g = app.MapGroup("/api/warehouses").WithTags("Warehouses");

        g.MapGet("", async (ArgonDbContext db, CancellationToken ct) =>
            await db.Warehouses.AsNoTracking().OrderBy(w => w.Id)
                .Select(w => new WarehouseDto(w.Id, w.Name, w.Address, w.MapX, w.MapY, w.Capacity)).ToListAsync(ct));

        g.MapGet("{id:int}", async (int id, ArgonDbContext db, CancellationToken ct) =>
            WarehouseDto.From(await Find(db, id, ct)));

        g.MapPost("", async (WarehouseRequest req, ArgonDbContext db, CancellationToken ct) =>
        {
            var (name, address) = Validate(req);
            await EnsureNameFree(db, name, null, ct);

            var warehouse = new Warehouse
            {
                Name = name, NameKey = TextKey.Of(name), Address = address,
                MapX = req.MapX ?? 0, MapY = req.MapY ?? 0,
                Capacity = req.Capacity ?? Warehouse.DefaultCapacity
            };
            db.Warehouses.Add(warehouse);
            await db.SaveChangesAsync(ct);
            return Results.Created($"/api/warehouses/{warehouse.Id}", WarehouseDto.From(warehouse));
        });

        g.MapPut("{id:int}", async (int id, WarehouseRequest req, ArgonDbContext db, InventoryLock gate, CancellationToken ct) =>
        {
            var (name, address) = Validate(req);

            return await gate.RunAsync(async () =>
            {
                var warehouse = await Find(db, id, ct);
                await EnsureNameFree(db, name, id, ct);

                if (req.Capacity is { } capacity && capacity != warehouse.Capacity)
                {
                    var usage = await SpaceCalculator.LoadOneAsync(db, id, ct);
                    if (capacity < usage.Used)
                        throw DomainException.Conflict("capacity_below_occupied",
                            $"Вместимость {capacity} меньше занятого места: на складе {usage.Occupied}, ожидается возвратов {usage.Incoming}.");
                    warehouse.Capacity = capacity;
                }

                warehouse.Name = name;
                warehouse.NameKey = TextKey.Of(name);
                warehouse.Address = address;
                warehouse.MapX = req.MapX ?? warehouse.MapX;
                warehouse.MapY = req.MapY ?? warehouse.MapY;
                await db.SaveChangesAsync(ct);
                return WarehouseDto.From(warehouse);
            });
        });

        g.MapDelete("{id:int}", async (int id, ArgonDbContext db, InventoryLock gate, CancellationToken ct) =>
        {
            await gate.RunAsync(async () =>
            {
                var warehouse = await Find(db, id, ct);
                if (await db.Stock.AnyAsync(s => s.WarehouseId == id && s.Quantity > 0, ct))
                    throw DomainException.Conflict("warehouse_not_empty", "На складе есть товар, удалять нельзя.");
                if (await db.Shipments.AnyAsync(s => s.WarehouseId == id
                        && (s.Status == ShipmentStatus.Planned || s.Status == ShipmentStatus.Dispatched), ct))
                    throw DomainException.Conflict("warehouse_has_shipments", "Со склада есть активные отправки.");
                if (await db.ReturnShipments.AnyAsync(r => r.WarehouseId == id && r.Status != ReturnStatus.Delivered, ct))
                    throw DomainException.Conflict("warehouse_has_shipments", "На склад идут возвратные отправки.");

                // Пути, привязки к ПВЗ и нулевые остатки удаляет каскад БД.
                db.Warehouses.Remove(warehouse);
                await db.SaveChangesAsync(ct);
            });
            return Results.NoContent();
        });

        g.MapPut("{id:int}/position", async (int id, PositionRequest req, ArgonDbContext db, CancellationToken ct) =>
        {
            new Validator().MapCoordinate("x", req.X).MapCoordinate("y", req.Y).ThrowIfInvalid();
            var warehouse = await Find(db, id, ct);
            warehouse.MapX = req.X;
            warehouse.MapY = req.Y;
            await db.SaveChangesAsync(ct);
            return WarehouseDto.From(warehouse);
        });

        MapStock(g);
    }

    private static void MapStock(RouteGroupBuilder g)
    {
        g.MapGet("{id:int}/stock", async (int id, ArgonDbContext db, CancellationToken ct) =>
        {
            await Find(db, id, ct);
            return await db.Stock.AsNoTracking()
                .Where(s => s.WarehouseId == id)
                .OrderBy(s => s.ProductId)
                .Select(s => new StockLineDto(s.ProductId, s.Product!.Sku, s.Product.Name,
                    s.Quantity, s.Reserved, s.Quantity - s.Reserved))
                .ToListAsync(ct);
        });

        g.MapPost("{id:int}/stock", async (int id, AddStockRequest req, ArgonDbContext db, InventoryLock gate, CancellationToken ct) =>
        {
            new Validator().Range("quantity", req.Quantity, 1, Validator.MaxQuantity).ThrowIfInvalid();

            return await gate.RunAsync(async () =>
            {
                var warehouse = await Find(db, id, ct);
                var product = await FindProduct(db, req.ProductId, ct);
                var line = await db.Stock.FindAsync([id, req.ProductId], ct);

                var created = line is null;
                if (line is null)
                {
                    line = new StockItem { WarehouseId = id, ProductId = req.ProductId };
                    db.Stock.Add(line);
                }

                if ((long)line.Quantity + req.Quantity > Validator.MaxQuantity)
                    throw DomainException.Validation(new Dictionary<string, string[]>
                    {
                        ["quantity"] = [$"Итоговое количество не больше {Validator.MaxQuantity}."]
                    });

                SpaceCalculator.EnsureRoom(warehouse, await SpaceCalculator.LoadOneAsync(db, id, ct), req.Quantity);

                line.Quantity += req.Quantity;
                await db.SaveChangesAsync(ct);

                var dto = ToDto(line, product);
                return created
                    ? Results.Created($"/api/warehouses/{id}/stock", dto)
                    : Results.Ok(dto);
            });
        });

        g.MapPut("{id:int}/stock/{productId:int}", async (int id, int productId, SetStockRequest req, ArgonDbContext db, InventoryLock gate, CancellationToken ct) =>
        {
            new Validator().Range("quantity", req.Quantity, 0, Validator.MaxQuantity).ThrowIfInvalid();

            return await gate.RunAsync(async () =>
            {
                var warehouse = await Find(db, id, ct);
                var product = await FindProduct(db, productId, ct);
                var line = await db.Stock.FindAsync([id, productId], ct);

                SpaceCalculator.EnsureRoom(warehouse, await SpaceCalculator.LoadOneAsync(db, id, ct),
                    req.Quantity - (line?.Quantity ?? 0));

                if (line is null)
                {
                    line = new StockItem { WarehouseId = id, ProductId = productId };
                    db.Stock.Add(line);
                }
                else if (req.Quantity < line.Reserved)
                {
                    throw DomainException.Conflict("stock_below_reserved",
                        $"Нельзя задать {req.Quantity}: в резерве {line.Reserved}.");
                }

                line.Quantity = req.Quantity;
                await db.SaveChangesAsync(ct);
                return ToDto(line, product);
            });
        });

        g.MapDelete("{id:int}/stock/{productId:int}", async (int id, int productId, ArgonDbContext db, InventoryLock gate, CancellationToken ct) =>
        {
            await gate.RunAsync(async () =>
            {
                await Find(db, id, ct);
                var line = await db.Stock.FindAsync([id, productId], ct)
                           ?? throw DomainException.NotFound("stock_not_found", "Такой строки остатка нет.");
                if (line.Reserved > 0)
                    throw DomainException.Conflict("stock_reserved", $"По строке есть резерв: {line.Reserved}.");

                db.Stock.Remove(line);
                await db.SaveChangesAsync(ct);
            });
            return Results.NoContent();
        });
    }

    private static StockLineDto ToDto(StockItem s, Product p) =>
        new(s.ProductId, p.Sku, p.Name, s.Quantity, s.Reserved, s.Available);

    private static (string Name, string Address) Validate(WarehouseRequest req)
    {
        new Validator()
            .Required("name", req.Name, 200, out var name)
            .Required("address", req.Address, 300, out var address)
            .MapCoordinate("mapX", req.MapX)
            .MapCoordinate("mapY", req.MapY)
            .Capacity("capacity", req.Capacity)
            .ThrowIfInvalid();
        return (name, address);
    }

    private static async Task<Warehouse> Find(ArgonDbContext db, int id, CancellationToken ct) =>
        await db.Warehouses.FirstOrDefaultAsync(w => w.Id == id, ct)
        ?? throw DomainException.NotFound("warehouse_not_found", $"Склад {id} не найден.");

    private static async Task<Product> FindProduct(ArgonDbContext db, int id, CancellationToken ct) =>
        await db.Products.AsNoTracking().FirstOrDefaultAsync(p => p.Id == id, ct)
        ?? throw DomainException.NotFound("product_not_found", $"Товар {id} не найден.");

    private static async Task EnsureNameFree(ArgonDbContext db, string name, int? exceptId, CancellationToken ct)
    {
        if (await db.Warehouses.AnyAsync(w => w.NameKey == TextKey.Of(name) && w.Id != exceptId, ct))
            throw DomainException.Conflict("warehouse_name_duplicate", $"Склад «{name}» уже есть.");
    }
}

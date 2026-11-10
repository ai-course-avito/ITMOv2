using Argonum.Logistics.Api.Contracts;
using Argonum.Logistics.Api.Data;
using Argonum.Logistics.Api.Infrastructure;
using Argonum.Logistics.Core;
using Argonum.Logistics.Core.Entities;
using Microsoft.EntityFrameworkCore;

namespace Argonum.Logistics.Api.Endpoints;

public static class ProductEndpoints
{
    public static void MapProducts(this IEndpointRouteBuilder app)
    {
        var g = app.MapGroup("/api/products").WithTags("Catalog");

        g.MapGet("", async (ArgonDbContext db, CancellationToken ct) =>
            await db.Products.AsNoTracking().OrderBy(p => p.Id)
                .Select(p => new ProductDto(p.Id, p.Sku, p.Name, p.Description)).ToListAsync(ct));

        g.MapGet("{id:int}", async (int id, ArgonDbContext db, CancellationToken ct) =>
            ProductDto.From(await Find(db, id, ct)));

        g.MapPost("", async (ProductRequest req, ArgonDbContext db, CancellationToken ct) =>
        {
            var (sku, name, description) = Validate(req);
            await EnsureSkuFree(db, sku, null, ct);

            var product = new Product { Sku = sku, SkuKey = TextKey.Of(sku), Name = name, Description = description };
            db.Products.Add(product);
            await db.SaveChangesAsync(ct);
            return Results.Created($"/api/products/{product.Id}", ProductDto.From(product));
        });

        g.MapPut("{id:int}", async (int id, ProductRequest req, ArgonDbContext db, CancellationToken ct) =>
        {
            var (sku, name, description) = Validate(req);
            var product = await Find(db, id, ct);
            await EnsureSkuFree(db, sku, id, ct);

            product.Sku = sku;
            product.SkuKey = TextKey.Of(sku);
            product.Name = name;
            product.Description = description;
            await db.SaveChangesAsync(ct);
            return ProductDto.From(product);
        });

        g.MapDelete("{id:int}", async (int id, ArgonDbContext db, InventoryLock gate, CancellationToken ct) =>
        {
            await gate.RunAsync(async () =>
            {
                var product = await Find(db, id, ct);
                if (await db.Stock.AnyAsync(s => s.ProductId == id && s.Quantity > 0, ct))
                    throw DomainException.Conflict("product_has_stock", "Товар есть на складах, удалять нельзя.");

                db.Products.Remove(product); // нулевые строки остатков удаляет каскад БД
                await db.SaveChangesAsync(ct);
            });
            return Results.NoContent();
        });
    }

    private static (string Sku, string Name, string? Description) Validate(ProductRequest req)
    {
        var v = new Validator()
            .Required("sku", req.Sku, 64, out var sku)
            .Required("name", req.Name, 200, out var name)
            .Optional("description", req.Description, 1000, out var description);
        v.ThrowIfInvalid();
        return (sku, name, description);
    }

    private static async Task<Product> Find(ArgonDbContext db, int id, CancellationToken ct) =>
        await db.Products.FirstOrDefaultAsync(p => p.Id == id, ct)
        ?? throw DomainException.NotFound("product_not_found", $"Товар {id} не найден.");

    private static async Task EnsureSkuFree(ArgonDbContext db, string sku, int? exceptId, CancellationToken ct)
    {
        if (await db.Products.AnyAsync(p => p.SkuKey == TextKey.Of(sku) && p.Id != exceptId, ct))
            throw DomainException.Conflict("product_sku_duplicate", $"SKU «{sku}» уже занят.");
    }
}

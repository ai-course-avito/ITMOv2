using System.Net;

namespace Argonum.Logistics.Tests;

public class InventoryTests
{
    [Fact]
    public async Task Create_warehouse_and_reject_duplicate_name()
    {
        using var app = new TestApp();
        await app.Warehouse("Склад Север");

        var code = await TestApp.Code(
            await app.Post("/api/warehouses", new { name = "склад север", address = "x" }), HttpStatusCode.Conflict);

        Assert.Equal("warehouse_name_duplicate", code);
    }

    [Fact]
    public async Task Add_stock_creates_line_then_increments()
    {
        using var app = new TestApp();
        var product = await app.Product("MILK");
        var warehouse = await app.Warehouse("A");

        var created = await TestApp.Json(
            await app.Post($"/api/warehouses/{warehouse}/stock", new { productId = product, quantity = 10 }), HttpStatusCode.Created);
        Assert.Equal(10, created.GetProperty("quantity").GetInt32());
        Assert.Equal(0, created.GetProperty("reserved").GetInt32());
        Assert.Equal(10, created.GetProperty("available").GetInt32());

        var incremented = await TestApp.Json(
            await app.Post($"/api/warehouses/{warehouse}/stock", new { productId = product, quantity = 5 }), HttpStatusCode.OK);
        Assert.Equal(15, incremented.GetProperty("quantity").GetInt32());
    }

    [Fact]
    public async Task Add_stock_for_unknown_product_returns_404()
    {
        using var app = new TestApp();
        var warehouse = await app.Warehouse("A");

        var code = await TestApp.Code(
            await app.Post($"/api/warehouses/{warehouse}/stock", new { productId = 999, quantity = 1 }), HttpStatusCode.NotFound);

        Assert.Equal("product_not_found", code);
    }

    [Theory]
    [InlineData(0)]
    [InlineData(-3)]
    [InlineData(1_000_001)]
    public async Task Add_stock_rejects_out_of_range_quantity(int quantity)
    {
        using var app = new TestApp();
        var product = await app.Product("MILK");
        var warehouse = await app.Warehouse("A");

        var body = await TestApp.Json(
            await app.Post($"/api/warehouses/{warehouse}/stock", new { productId = product, quantity }), HttpStatusCode.BadRequest);

        Assert.True(body.GetProperty("errors").TryGetProperty("quantity", out _));
    }

    [Fact]
    public async Task Add_stock_cannot_exceed_line_limit()
    {
        using var app = new TestApp();
        var product = await app.Product("MILK");
        var warehouse = await app.Warehouse("A", capacity: 2_000_000);
        await app.AddStock(warehouse, product, 999_999);

        var code = await TestApp.Code(
            await app.Post($"/api/warehouses/{warehouse}/stock", new { productId = product, quantity = 2 }), HttpStatusCode.BadRequest);

        Assert.Equal("validation_failed", code);
        Assert.Equal(999_999, (await app.Stock(warehouse, product)).GetProperty("quantity").GetInt32());
    }

    [Fact]
    public async Task Available_is_quantity_minus_reserved()
    {
        using var app = new TestApp();
        var w = await app.SeedWorld(stockA: 10, stockB: 1);
        await TestApp.Json(await app.Post("/api/me/orders", w.Order(3), w.User), HttpStatusCode.Created);

        var line = await app.Stock(w.A, w.Product);

        Assert.Equal(10, line.GetProperty("quantity").GetInt32());
        Assert.Equal(3, line.GetProperty("reserved").GetInt32());
        Assert.Equal(7, line.GetProperty("available").GetInt32());
    }

    [Fact]
    public async Task Set_quantity_below_reserved_is_rejected()
    {
        using var app = new TestApp();
        var w = await app.SeedWorld(stockA: 10, stockB: 1);
        await TestApp.Json(await app.Post("/api/me/orders", w.Order(4), w.User), HttpStatusCode.Created);

        var code = await TestApp.Code(
            await app.Put($"/api/warehouses/{w.A}/stock/{w.Product}", new { quantity = 3 }), HttpStatusCode.Conflict);

        Assert.Equal("stock_below_reserved", code);
        Assert.Equal(10, (await app.Stock(w.A, w.Product)).GetProperty("quantity").GetInt32());

        var ok = await TestApp.Json(
            await app.Put($"/api/warehouses/{w.A}/stock/{w.Product}", new { quantity = 4 }), HttpStatusCode.OK);
        Assert.Equal(0, ok.GetProperty("available").GetInt32());
    }

    [Fact]
    public async Task Delete_stock_line_with_reserve_is_rejected()
    {
        using var app = new TestApp();
        var w = await app.SeedWorld();
        await TestApp.Json(await app.Post("/api/me/orders", w.Order(2), w.User), HttpStatusCode.Created);

        var code = await TestApp.Code(await app.Delete($"/api/warehouses/{w.A}/stock/{w.Product}"), HttpStatusCode.Conflict);

        Assert.Equal("stock_reserved", code);
    }

    [Fact]
    public async Task Delete_stock_line_without_reserve_succeeds()
    {
        using var app = new TestApp();
        var w = await app.SeedWorld();

        Assert.Equal(HttpStatusCode.NoContent, (await app.Delete($"/api/warehouses/{w.A}/stock/{w.Product}")).StatusCode);
        Assert.Equal(HttpStatusCode.NotFound, (await app.Delete($"/api/warehouses/{w.A}/stock/{w.Product}")).StatusCode);
    }

    [Fact]
    public async Task Cannot_delete_warehouse_with_stock()
    {
        using var app = new TestApp();
        var w = await app.SeedWorld();

        var code = await TestApp.Code(await app.Delete($"/api/warehouses/{w.A}"), HttpStatusCode.Conflict);

        Assert.Equal("warehouse_not_empty", code);
    }

    [Fact]
    public async Task Cannot_delete_warehouse_with_active_shipment_even_if_stock_is_gone()
    {
        using var app = new TestApp();
        var w = await app.SeedWorld(stockA: 5, stockB: 1);
        var order = await TestApp.Json(await app.Post("/api/me/orders", w.Order(5), w.User), HttpStatusCode.Created);
        var shipmentId = order.GetProperty("shipments")[0].GetProperty("id").GetInt32();
        await TestApp.Json(await app.Post($"/api/shipments/{shipmentId}/dispatch"), HttpStatusCode.OK);

        var code = await TestApp.Code(await app.Delete($"/api/warehouses/{w.A}"), HttpStatusCode.Conflict);

        Assert.Equal("warehouse_has_shipments", code);
    }

    [Fact]
    public async Task Delete_empty_warehouse_removes_its_routes()
    {
        using var app = new TestApp();
        var a = await app.Warehouse("A");
        var b = await app.Warehouse("B");
        await app.Route(a, b, 60, bidirectional: true);

        Assert.Equal(HttpStatusCode.NoContent, (await app.Delete($"/api/warehouses/{b}")).StatusCode);

        var routes = await TestApp.Json(await app.Get("/api/routes"), HttpStatusCode.OK);
        Assert.Equal(0, routes.GetArrayLength());
    }
}

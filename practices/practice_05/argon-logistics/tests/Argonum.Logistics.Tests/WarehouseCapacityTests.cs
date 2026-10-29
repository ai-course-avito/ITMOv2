using System.Net;

namespace Argonum.Logistics.Tests;

public class WarehouseCapacityTests
{
    [Fact]
    public async Task Create_warehouse_with_capacity()
    {
        using var app = new TestApp();

        var created = await TestApp.Json(
            await app.Post("/api/warehouses", new { name = "A", address = "x", capacity = 500 }), HttpStatusCode.Created);

        Assert.Equal(500, created.GetProperty("capacity").GetInt32());
    }

    [Fact]
    public async Task Capacity_defaults_to_100000()
    {
        using var app = new TestApp();
        var id = await app.Warehouse("A");

        var warehouse = await TestApp.Json(await app.Get($"/api/warehouses/{id}"), HttpStatusCode.OK);

        Assert.Equal(100_000, warehouse.GetProperty("capacity").GetInt32());
    }

    [Theory]
    [InlineData(0)]
    [InlineData(-5)]
    [InlineData(10_000_001)]
    public async Task Capacity_out_of_range_is_rejected(int capacity)
    {
        using var app = new TestApp();

        var body = await TestApp.Json(
            await app.Post("/api/warehouses", new { name = "A", address = "x", capacity }), HttpStatusCode.BadRequest);

        Assert.Equal("validation_failed", body.GetProperty("code").GetString());
        Assert.True(body.GetProperty("errors").TryGetProperty("capacity", out _));
    }

    [Fact]
    public async Task Update_without_capacity_keeps_it()
    {
        using var app = new TestApp();
        var id = await app.Warehouse("A", capacity: 500);

        var updated = await TestApp.Json(
            await app.Put($"/api/warehouses/{id}", new { name = "A2", address = "y" }), HttpStatusCode.OK);

        Assert.Equal(500, updated.GetProperty("capacity").GetInt32());
        Assert.Equal("A2", updated.GetProperty("name").GetString());
    }

    [Fact]
    public async Task Add_stock_over_capacity_is_rejected_and_changes_nothing()
    {
        using var app = new TestApp();
        var product = await app.Product("MILK");
        var warehouse = await app.Warehouse("A", capacity: 100);
        await app.AddStock(warehouse, product, 95);

        var code = await TestApp.Code(
            await app.Post($"/api/warehouses/{warehouse}/stock", new { productId = product, quantity = 10 }), HttpStatusCode.Conflict);

        Assert.Equal("warehouse_capacity_exceeded", code);
        Assert.Equal(95, (await app.Stock(warehouse, product)).GetProperty("quantity").GetInt32());
    }

    [Fact]
    public async Task Add_stock_up_to_the_limit_is_allowed()
    {
        using var app = new TestApp();
        var product = await app.Product("MILK");
        var warehouse = await app.Warehouse("A", capacity: 100);
        await app.AddStock(warehouse, product, 95);

        await TestApp.Json(
            await app.Post($"/api/warehouses/{warehouse}/stock", new { productId = product, quantity = 5 }), HttpStatusCode.OK);

        var network = await app.NetworkWarehouse(warehouse);
        Assert.Equal(100, network.GetProperty("totalQuantity").GetInt32());
        Assert.Equal(100, network.GetProperty("capacity").GetInt32());
    }

    [Fact]
    public async Task Capacity_is_shared_by_all_lines_of_the_warehouse()
    {
        using var app = new TestApp();
        var milk = await app.Product("MILK");
        var bread = await app.Product("BREAD");
        var warehouse = await app.Warehouse("A", capacity: 10);
        await app.AddStock(warehouse, milk, 6);

        var code = await TestApp.Code(
            await app.Post($"/api/warehouses/{warehouse}/stock", new { productId = bread, quantity = 5 }), HttpStatusCode.Conflict);

        Assert.Equal("warehouse_capacity_exceeded", code);
    }

    [Fact]
    public async Task Set_stock_over_capacity_is_rejected_but_decrease_is_allowed()
    {
        using var app = new TestApp();
        var product = await app.Product("MILK");
        var warehouse = await app.Warehouse("A", capacity: 100);
        await app.AddStock(warehouse, product, 90);

        var code = await TestApp.Code(
            await app.Put($"/api/warehouses/{warehouse}/stock/{product}", new { quantity = 101 }), HttpStatusCode.Conflict);
        Assert.Equal("warehouse_capacity_exceeded", code);

        await TestApp.Json(await app.Put($"/api/warehouses/{warehouse}/stock/{product}", new { quantity = 100 }), HttpStatusCode.OK);
        await TestApp.Json(await app.Put($"/api/warehouses/{warehouse}/stock/{product}", new { quantity = 10 }), HttpStatusCode.OK);
        Assert.Equal(10, (await app.Stock(warehouse, product)).GetProperty("quantity").GetInt32());
    }

    [Fact]
    public async Task Capacity_cannot_go_below_occupied_but_may_equal_it()
    {
        using var app = new TestApp();
        var product = await app.Product("MILK");
        var warehouse = await app.Warehouse("A", capacity: 100);
        await app.AddStock(warehouse, product, 60);

        var code = await TestApp.Code(await app.SetCapacity(warehouse, 59), HttpStatusCode.Conflict);
        Assert.Equal("capacity_below_occupied", code);

        var updated = await TestApp.Json(await app.SetCapacity(warehouse, 60), HttpStatusCode.OK);
        Assert.Equal(60, updated.GetProperty("capacity").GetInt32());
    }

    [Fact]
    public async Task Reserved_stock_still_occupies_space()
    {
        using var app = new TestApp();
        var w = await app.SeedWorld(stockA: 10, stockB: 1);
        await TestApp.Json(await app.Post("/api/me/orders", w.Order(4), w.User), HttpStatusCode.Created);

        var code = await TestApp.Code(await app.SetCapacity(w.A, 9), HttpStatusCode.Conflict);

        Assert.Equal("capacity_below_occupied", code);
    }

    [Fact]
    public async Task Network_snapshot_has_capacity_and_zero_incoming_by_default()
    {
        using var app = new TestApp();
        var product = await app.Product("MILK");
        var warehouse = await app.Warehouse("A", capacity: 250);
        await app.AddStock(warehouse, product, 40);

        var network = await app.NetworkWarehouse(warehouse);

        Assert.Equal(250, network.GetProperty("capacity").GetInt32());
        Assert.Equal(40, network.GetProperty("totalQuantity").GetInt32());
        Assert.Equal(0, network.GetProperty("incomingQuantity").GetInt32());
    }
}

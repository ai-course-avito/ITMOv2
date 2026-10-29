using System.Net;

namespace Argonum.Logistics.Tests;

public class NetworkMapTests
{
    [Fact]
    public async Task Warehouse_is_created_with_position()
    {
        using var app = new TestApp();

        var created = await TestApp.Json(await app.Post("/api/warehouses",
            new { name = "A", address = "x", mapX = 320.5, mapY = 180 }), HttpStatusCode.Created);

        Assert.Equal(320.5, created.GetProperty("mapX").GetDouble());
        Assert.Equal(180, created.GetProperty("mapY").GetDouble());
    }

    [Fact]
    public async Task Position_defaults_to_zero_for_both_kinds()
    {
        using var app = new TestApp();

        var pickup = await TestApp.Json(await app.Post("/api/pickup-points", new { name = "P", address = "x" }), HttpStatusCode.Created);
        var warehouse = await TestApp.Json(await app.Post("/api/warehouses", new { name = "W", address = "x" }), HttpStatusCode.Created);

        Assert.Equal(0, pickup.GetProperty("mapX").GetDouble());
        Assert.Equal(0, pickup.GetProperty("mapY").GetDouble());
        Assert.Equal(0, warehouse.GetProperty("mapX").GetDouble());
    }

    [Fact]
    public async Task Update_without_position_keeps_it()
    {
        using var app = new TestApp();
        var created = await TestApp.Json(await app.Post("/api/warehouses",
            new { name = "A", address = "x", mapX = 320, mapY = 180 }), HttpStatusCode.Created);
        var id = created.GetProperty("id").GetInt32();

        var updated = await TestApp.Json(await app.Put($"/api/warehouses/{id}", new { name = "A2", address = "y" }), HttpStatusCode.OK);

        Assert.Equal(320, updated.GetProperty("mapX").GetDouble());
        Assert.Equal(180, updated.GetProperty("mapY").GetDouble());
        Assert.Equal("A2", updated.GetProperty("name").GetString());
    }

    [Fact]
    public async Task Pickup_point_update_without_position_keeps_it()
    {
        using var app = new TestApp();
        var created = await TestApp.Json(await app.Post("/api/pickup-points",
            new { name = "P", address = "x", mapX = 10, mapY = 20 }), HttpStatusCode.Created);
        var id = created.GetProperty("id").GetInt32();

        var updated = await TestApp.Json(await app.Put($"/api/pickup-points/{id}", new { name = "P2", address = "y", isActive = false }), HttpStatusCode.OK);

        Assert.Equal(10, updated.GetProperty("mapX").GetDouble());
        Assert.False(updated.GetProperty("isActive").GetBoolean());
    }

    [Fact]
    public async Task Position_endpoint_moves_warehouse_and_pickup_point()
    {
        using var app = new TestApp();
        var warehouse = await app.Warehouse("A");
        var pickup = await app.PickupPoint();

        await TestApp.Json(await app.Put($"/api/warehouses/{warehouse}/position", new { x = 500, y = 250 }), HttpStatusCode.OK);
        await TestApp.Json(await app.Put($"/api/pickup-points/{pickup}/position", new { x = -40.5, y = 99 }), HttpStatusCode.OK);

        var w = await TestApp.Json(await app.Get($"/api/warehouses/{warehouse}"), HttpStatusCode.OK);
        var p = await TestApp.Json(await app.Get($"/api/pickup-points/{pickup}"), HttpStatusCode.OK);
        Assert.Equal(500, w.GetProperty("mapX").GetDouble());
        Assert.Equal(250, w.GetProperty("mapY").GetDouble());
        Assert.Equal(-40.5, p.GetProperty("mapX").GetDouble());
        // Остальные поля не тронуты.
        Assert.Equal("A", w.GetProperty("name").GetString());
    }

    [Theory]
    [InlineData(1_000_000, 0)]
    [InlineData(0, -100_001)]
    public async Task Position_out_of_range_is_rejected(double x, double y)
    {
        using var app = new TestApp();
        var warehouse = await app.Warehouse("A");

        var body = await TestApp.Json(await app.Put($"/api/warehouses/{warehouse}/position", new { x, y }), HttpStatusCode.BadRequest);

        Assert.Equal("validation_failed", body.GetProperty("code").GetString());
    }

    [Fact]
    public async Task Create_with_out_of_range_position_is_rejected()
    {
        using var app = new TestApp();

        var body = await TestApp.Json(await app.Post("/api/warehouses",
            new { name = "A", address = "x", mapX = 5_000_000 }), HttpStatusCode.BadRequest);

        Assert.True(body.GetProperty("errors").TryGetProperty("mapX", out _));
    }

    [Fact]
    public async Task Position_of_unknown_objects_returns_404()
    {
        using var app = new TestApp();

        Assert.Equal("warehouse_not_found",
            await TestApp.Code(await app.Put("/api/warehouses/999/position", new { x = 1, y = 1 }), HttpStatusCode.NotFound));
        Assert.Equal("pickup_point_not_found",
            await TestApp.Code(await app.Put("/api/pickup-points/999/position", new { x = 1, y = 1 }), HttpStatusCode.NotFound));
    }

    [Fact]
    public async Task Network_snapshot_contains_everything()
    {
        using var app = new TestApp();
        var w = await app.SeedWorld(stockA: 10, stockB: 5);
        await app.Route(w.A, w.B, 40);

        var network = await TestApp.Json(await app.Get("/api/network"), HttpStatusCode.OK);

        Assert.Equal(2, network.GetProperty("warehouses").GetArrayLength());
        Assert.Equal(1, network.GetProperty("pickupPoints").GetArrayLength());
        Assert.Equal(1, network.GetProperty("routes").GetArrayLength());
        Assert.Equal(2, network.GetProperty("links").GetArrayLength());
        var link = network.GetProperty("links")[0];
        Assert.Equal(w.Pickup, link.GetProperty("pickupPointId").GetInt32());
        Assert.Equal(30, link.GetProperty("minutes").GetInt32());
    }

    [Fact]
    public async Task Network_snapshot_sums_stock_per_warehouse()
    {
        using var app = new TestApp();
        var w = await app.SeedWorld(stockA: 10, stockB: 1);
        var bread = await app.Product("BREAD");
        await app.AddStock(w.A, bread, 5);
        await TestApp.Json(await app.Post("/api/me/orders", w.Order(3), w.User), HttpStatusCode.Created);

        var network = await TestApp.Json(await app.Get("/api/network"), HttpStatusCode.OK);

        var a = network.GetProperty("warehouses").EnumerateArray().Single(x => x.GetProperty("id").GetInt32() == w.A);
        Assert.Equal(15, a.GetProperty("totalQuantity").GetInt32());
        Assert.Equal(3, a.GetProperty("totalReserved").GetInt32());
        var b = network.GetProperty("warehouses").EnumerateArray().Single(x => x.GetProperty("id").GetInt32() == w.B);
        Assert.Equal(1, b.GetProperty("totalQuantity").GetInt32());
    }

    [Fact]
    public async Task Empty_network_is_valid()
    {
        using var app = new TestApp();

        var network = await TestApp.Json(await app.Get("/api/network"), HttpStatusCode.OK);

        Assert.Equal(0, network.GetProperty("warehouses").GetArrayLength());
        Assert.Equal(0, network.GetProperty("links").GetArrayLength());
    }
}

using System.Net;

namespace Argonum.Logistics.Tests;

public class NetworkTests
{
    [Fact]
    public async Task Create_route_and_read_it_back()
    {
        using var app = new TestApp();
        var a = await app.Warehouse("A");
        var b = await app.Warehouse("B");

        var created = await TestApp.Json(
            await app.Post("/api/routes", new { fromWarehouseId = a, toWarehouseId = b, minutes = 120 }), HttpStatusCode.Created);

        Assert.Equal(a, created.GetProperty("fromWarehouseId").GetInt32());
        Assert.Equal(b, created.GetProperty("toWarehouseId").GetInt32());
        Assert.Equal(120, created.GetProperty("minutes").GetInt32());
        // Путь направленный: обратного нет.
        var all = await TestApp.Json(await app.Get("/api/routes"), HttpStatusCode.OK);
        Assert.Equal(1, all.GetArrayLength());
    }

    [Fact]
    public async Task Route_to_same_warehouse_is_rejected()
    {
        using var app = new TestApp();
        var a = await app.Warehouse("A");

        var code = await TestApp.Code(
            await app.Post("/api/routes", new { fromWarehouseId = a, toWarehouseId = a, minutes = 5 }), HttpStatusCode.BadRequest);

        Assert.Equal("validation_failed", code);
    }

    [Theory]
    [InlineData(0)]
    [InlineData(10_081)]
    public async Task Route_minutes_must_be_in_range(int minutes)
    {
        using var app = new TestApp();
        var a = await app.Warehouse("A");
        var b = await app.Warehouse("B");

        var code = await TestApp.Code(
            await app.Post("/api/routes", new { fromWarehouseId = a, toWarehouseId = b, minutes }), HttpStatusCode.BadRequest);

        Assert.Equal("validation_failed", code);
    }

    [Fact]
    public async Task Route_with_unknown_warehouse_returns_404()
    {
        using var app = new TestApp();
        var a = await app.Warehouse("A");

        var code = await TestApp.Code(
            await app.Post("/api/routes", new { fromWarehouseId = a, toWarehouseId = 999, minutes = 5 }), HttpStatusCode.NotFound);

        Assert.Equal("warehouse_not_found", code);
    }

    [Fact]
    public async Task Duplicate_route_is_rejected()
    {
        using var app = new TestApp();
        var a = await app.Warehouse("A");
        var b = await app.Warehouse("B");
        await app.Route(a, b, 10);

        var code = await TestApp.Code(
            await app.Post("/api/routes", new { fromWarehouseId = a, toWarehouseId = b, minutes = 20 }), HttpStatusCode.Conflict);

        Assert.Equal("route_duplicate", code);
    }

    [Fact]
    public async Task Bidirectional_creates_both_directions()
    {
        using var app = new TestApp();
        var a = await app.Warehouse("A");
        var b = await app.Warehouse("B");

        var created = await TestApp.Json(
            await app.Post("/api/routes", new { fromWarehouseId = a, toWarehouseId = b, minutes = 60, bidirectional = true }),
            HttpStatusCode.Created);

        Assert.Equal(b, created.GetProperty("reverse").GetProperty("fromWarehouseId").GetInt32());
        var all = await TestApp.Json(await app.Get("/api/routes"), HttpStatusCode.OK);
        Assert.Equal(2, all.GetArrayLength());
        Assert.All(all.EnumerateArray(), r => Assert.Equal(60, r.GetProperty("minutes").GetInt32()));
    }

    [Fact]
    public async Task Bidirectional_is_atomic_when_reverse_exists()
    {
        using var app = new TestApp();
        var a = await app.Warehouse("A");
        var b = await app.Warehouse("B");
        await app.Route(b, a, 10);

        var code = await TestApp.Code(
            await app.Post("/api/routes", new { fromWarehouseId = a, toWarehouseId = b, minutes = 60, bidirectional = true }),
            HttpStatusCode.Conflict);

        Assert.Equal("route_duplicate", code);
        var all = await TestApp.Json(await app.Get("/api/routes"), HttpStatusCode.OK);
        Assert.Equal(1, all.GetArrayLength());
    }

    [Fact]
    public async Task Update_changes_minutes_only_and_filter_by_warehouse_works()
    {
        using var app = new TestApp();
        var a = await app.Warehouse("A");
        var b = await app.Warehouse("B");
        var c = await app.Warehouse("C");
        var ab = await app.Route(a, b, 10);
        await app.Route(b, c, 10);

        var updated = await TestApp.Json(await app.Put($"/api/routes/{ab}", new { minutes = 90 }), HttpStatusCode.OK);
        Assert.Equal(90, updated.GetProperty("minutes").GetInt32());
        Assert.Equal(a, updated.GetProperty("fromWarehouseId").GetInt32());

        var touchingA = await TestApp.Json(await app.Get($"/api/routes?warehouseId={a}"), HttpStatusCode.OK);
        Assert.Equal(1, touchingA.GetArrayLength());
        var touchingB = await TestApp.Json(await app.Get($"/api/routes?warehouseId={b}"), HttpStatusCode.OK);
        Assert.Equal(2, touchingB.GetArrayLength());
    }

    [Fact]
    public async Task Deleted_route_is_not_used_by_planning()
    {
        using var app = new TestApp();
        var product = await app.Product("MILK");
        var a = await app.Warehouse("A");
        var b = await app.Warehouse("B");
        var pickup = await app.PickupPoint();
        await app.AddStock(a, product, 1);
        await app.Link(pickup, b, 10);
        var route = await app.Route(a, b, 10);
        var request = new { pickupPointId = pickup, items = new[] { new { productId = product, quantity = 1 } } };

        await TestApp.Json(await app.Post("/api/plans", request), HttpStatusCode.OK);
        Assert.Equal(HttpStatusCode.NoContent, (await app.Delete($"/api/routes/{route}")).StatusCode);

        var code = await TestApp.Code(await app.Post("/api/plans", request), HttpStatusCode.Conflict);
        Assert.Equal("insufficient_stock", code);
    }

    [Fact]
    public async Task Existing_order_keeps_its_route_after_graph_changes()
    {
        using var app = new TestApp();
        var product = await app.Product("MILK");
        var a = await app.Warehouse("A");
        var b = await app.Warehouse("B");
        var pickup = await app.PickupPoint();
        var user = await app.User();
        await app.AddStock(a, product, 1);
        await app.Link(pickup, b, 10);
        var route = await app.Route(a, b, 20);

        var order = await TestApp.Json(await app.Post("/api/me/orders",
            new { pickupPointId = pickup, items = new[] { new { productId = product, quantity = 1 } } }, user), HttpStatusCode.Created);
        var orderId = order.GetProperty("id").GetInt32();

        await app.Delete($"/api/routes/{route}");

        var after = await TestApp.Json(await app.Get($"/api/me/orders/{orderId}", user), HttpStatusCode.OK);
        var shipment = after.GetProperty("shipments")[0];
        Assert.Equal(30, shipment.GetProperty("totalMinutes").GetInt32());
        Assert.Equal([a, b], shipment.GetProperty("route").EnumerateArray().Select(x => x.GetInt32()));
    }

    // ---- Привязки ПВЗ ----

    [Fact]
    public async Task Pickup_point_is_active_by_default()
    {
        using var app = new TestApp();

        var created = await TestApp.Json(
            await app.Post("/api/pickup-points", new { name = "ПВЗ", address = "ул. Мира, 1" }), HttpStatusCode.Created);

        Assert.True(created.GetProperty("isActive").GetBoolean());
    }

    [Fact]
    public async Task Link_put_is_upsert()
    {
        using var app = new TestApp();
        var warehouse = await app.Warehouse("A");
        var pickup = await app.PickupPoint();

        var first = await TestApp.Json(await app.Put($"/api/pickup-points/{pickup}/links/{warehouse}", new { minutes = 45 }), HttpStatusCode.OK);
        Assert.Equal(45, first.GetProperty("minutes").GetInt32());
        await app.Link(pickup, warehouse, 30);

        var links = await TestApp.Json(await app.Get($"/api/pickup-points/{pickup}/links"), HttpStatusCode.OK);
        Assert.Equal(1, links.GetArrayLength());
        Assert.Equal(30, links[0].GetProperty("minutes").GetInt32());
    }

    [Fact]
    public async Task Link_to_unknown_warehouse_returns_404()
    {
        using var app = new TestApp();
        var pickup = await app.PickupPoint();

        var code = await TestApp.Code(await app.Put($"/api/pickup-points/{pickup}/links/999", new { minutes = 5 }), HttpStatusCode.NotFound);

        Assert.Equal("warehouse_not_found", code);
    }

    [Fact]
    public async Task Order_to_inactive_pickup_point_is_rejected()
    {
        using var app = new TestApp();
        var w = await app.SeedWorld();
        await TestApp.Json(await app.Put($"/api/pickup-points/{w.Pickup}",
            new { name = "ПВЗ-1", address = "x", isActive = false }), HttpStatusCode.OK);

        var code = await TestApp.Code(await app.Post("/api/me/orders", w.Order(1), w.User), HttpStatusCode.Conflict);

        Assert.Equal("pickup_point_inactive", code);
    }

    [Fact]
    public async Task Cannot_delete_pickup_point_with_open_order_but_can_after_cancel()
    {
        using var app = new TestApp();
        var w = await app.SeedWorld();
        var order = await TestApp.Json(await app.Post("/api/me/orders", w.Order(1), w.User), HttpStatusCode.Created);

        var code = await TestApp.Code(await app.Delete($"/api/pickup-points/{w.Pickup}"), HttpStatusCode.Conflict);
        Assert.Equal("pickup_point_has_orders", code);

        await TestApp.Json(await app.Post($"/api/me/orders/{order.GetProperty("id").GetInt32()}/cancel", null, w.User), HttpStatusCode.OK);

        Assert.Equal(HttpStatusCode.NoContent, (await app.Delete($"/api/pickup-points/{w.Pickup}")).StatusCode);
        Assert.Equal(HttpStatusCode.NotFound, (await app.Get($"/api/pickup-points/{w.Pickup}")).StatusCode);
        Assert.Equal(HttpStatusCode.OK, (await app.Get($"/api/warehouses/{w.A}")).StatusCode);
    }
}

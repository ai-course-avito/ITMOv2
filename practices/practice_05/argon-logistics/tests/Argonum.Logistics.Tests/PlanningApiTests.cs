using System.Net;

namespace Argonum.Logistics.Tests;

public class PlanningApiTests
{
    [Fact]
    public async Task Dry_run_returns_plan_and_does_not_reserve()
    {
        using var app = new TestApp();
        var w = await app.SeedWorld();

        var plan = await TestApp.Json(await app.Post("/api/plans", w.Order(8)), HttpStatusCode.OK);

        Assert.Equal(80, plan.GetProperty("estimatedMinutes").GetInt32());
        var shipments = plan.GetProperty("shipments");
        Assert.Equal(2, shipments.GetArrayLength());
        Assert.Equal(w.A, shipments[0].GetProperty("warehouseId").GetInt32());
        Assert.Equal(5, shipments[0].GetProperty("items")[0].GetProperty("quantity").GetInt32());
        Assert.Equal(w.B, shipments[1].GetProperty("warehouseId").GetInt32());
        Assert.Equal(3, shipments[1].GetProperty("items")[0].GetProperty("quantity").GetInt32());

        Assert.Equal(0, (await app.Stock(w.A, w.Product)).GetProperty("reserved").GetInt32());
        Assert.Equal(0, (await app.Stock(w.B, w.Product)).GetProperty("reserved").GetInt32());
        var orders = await TestApp.Json(await app.Get("/api/orders"), HttpStatusCode.OK);
        Assert.Equal(0, orders.GetArrayLength());
    }

    [Fact]
    public async Task Plan_describes_route_through_intermediate_warehouse()
    {
        using var app = new TestApp();
        var product = await app.Product("MILK");
        var a = await app.Warehouse("A");
        var b = await app.Warehouse("B");
        var pickup = await app.PickupPoint("Центр");
        await app.AddStock(a, product, 1);
        await app.Link(pickup, a, 100);
        await app.Link(pickup, b, 30);
        await app.Route(a, b, 20);

        var plan = await TestApp.Json(await app.Post("/api/plans",
            new { pickupPointId = pickup, items = new[] { new { productId = product, quantity = 1 } } }), HttpStatusCode.OK);

        var shipment = plan.GetProperty("shipments")[0];
        Assert.Equal(50, shipment.GetProperty("totalMinutes").GetInt32());
        Assert.Equal([a, b], shipment.GetProperty("route").EnumerateArray().Select(x => x.GetInt32()));
        var legs = shipment.GetProperty("legs");
        Assert.Equal(2, legs.GetArrayLength());
        Assert.Equal("warehouse", legs[0].GetProperty("from").GetProperty("type").GetString());
        Assert.Equal("pickupPoint", legs[1].GetProperty("to").GetProperty("type").GetString());
        Assert.Equal("Центр", legs[1].GetProperty("to").GetProperty("name").GetString());
    }

    [Fact]
    public async Task Duplicate_lines_of_one_product_are_summed()
    {
        using var app = new TestApp();
        var w = await app.SeedWorld();

        var plan = await TestApp.Json(await app.Post("/api/plans", new
        {
            pickupPointId = w.Pickup,
            items = new[] { new { productId = w.Product, quantity = 2 }, new { productId = w.Product, quantity = 3 } }
        }), HttpStatusCode.OK);

        var shipment = Assert.Single(plan.GetProperty("shipments").EnumerateArray());
        Assert.Equal(5, shipment.GetProperty("items")[0].GetProperty("quantity").GetInt32());
    }

    [Fact]
    public async Task Empty_items_are_rejected()
    {
        using var app = new TestApp();
        var w = await app.SeedWorld();

        var code = await TestApp.Code(await app.Post("/api/plans", new { pickupPointId = w.Pickup, items = Array.Empty<object>() }),
            HttpStatusCode.BadRequest);

        Assert.Equal("validation_failed", code);
    }

    [Fact]
    public async Task Non_positive_quantity_is_rejected()
    {
        using var app = new TestApp();
        var w = await app.SeedWorld();

        var body = await TestApp.Json(await app.Post("/api/plans", w.Order(0)), HttpStatusCode.BadRequest);

        Assert.True(body.GetProperty("errors").TryGetProperty("items[0].quantity", out _));
    }

    [Fact]
    public async Task Unknown_pickup_point_and_product_return_404()
    {
        using var app = new TestApp();
        var w = await app.SeedWorld();

        var noPickup = await app.Post("/api/plans", new { pickupPointId = 999, items = new[] { new { productId = w.Product, quantity = 1 } } });
        Assert.Equal("pickup_point_not_found", await TestApp.Code(noPickup, HttpStatusCode.NotFound));

        var noProduct = await app.Post("/api/plans", new { pickupPointId = w.Pickup, items = new[] { new { productId = 999, quantity = 1 } } });
        Assert.Equal("product_not_found", await TestApp.Code(noProduct, HttpStatusCode.NotFound));

        var zeroProduct = await app.Post("/api/plans", new { pickupPointId = w.Pickup, items = new[] { new { productId = 0, quantity = 1 } } });
        Assert.Equal("product_not_found", await TestApp.Code(zeroProduct, HttpStatusCode.NotFound));
    }

    [Fact]
    public async Task Insufficient_stock_lists_only_missing_product_with_details()
    {
        using var app = new TestApp();
        var w = await app.SeedWorld(stockA: 5, stockB: 5);
        var bread = await app.Product("BREAD", "Хлеб");
        var far = await app.Warehouse("Остров"); // без путей в ПВЗ
        await app.AddStock(far, bread, 7);
        await app.AddStock(w.A, bread, 1);

        var body = await TestApp.Json(await app.Post("/api/plans", new
        {
            pickupPointId = w.Pickup,
            items = new[] { new { productId = w.Product, quantity = 2 }, new { productId = bread, quantity = 3 } }
        }), HttpStatusCode.Conflict);

        Assert.Equal("insufficient_stock", body.GetProperty("code").GetString());
        var shortage = Assert.Single(body.GetProperty("shortages").EnumerateArray());
        Assert.Equal(bread, shortage.GetProperty("productId").GetInt32());
        Assert.Equal(3, shortage.GetProperty("requested").GetInt32());
        Assert.Equal(1, shortage.GetProperty("reachableAvailable").GetInt32());
        Assert.Equal(7, shortage.GetProperty("unreachableAvailable").GetInt32());
    }

    [Fact]
    public async Task Pickup_point_without_links_is_unreachable()
    {
        using var app = new TestApp();
        var product = await app.Product("MILK");
        var warehouse = await app.Warehouse("A");
        var pickup = await app.PickupPoint();
        await app.AddStock(warehouse, product, 5);

        var code = await TestApp.Code(await app.Post("/api/plans",
            new { pickupPointId = pickup, items = new[] { new { productId = product, quantity = 1 } } }), HttpStatusCode.Conflict);

        Assert.Equal("pickup_point_unreachable", code);
    }

    [Fact]
    public async Task Inactive_pickup_point_is_rejected()
    {
        using var app = new TestApp();
        var product = await app.Product("MILK");
        var pickup = await app.PickupPoint(isActive: false);

        var code = await TestApp.Code(await app.Post("/api/plans",
            new { pickupPointId = pickup, items = new[] { new { productId = product, quantity = 1 } } }), HttpStatusCode.Conflict);

        Assert.Equal("pickup_point_inactive", code);
    }

    [Fact]
    public async Task Reserved_units_are_not_planned_again()
    {
        using var app = new TestApp();
        var w = await app.SeedWorld(stockA: 5, stockB: 5);
        await TestApp.Json(await app.Post("/api/me/orders", w.Order(4), w.User), HttpStatusCode.Created);

        var plan = await TestApp.Json(await app.Post("/api/plans", w.Order(3)), HttpStatusCode.OK);

        var fromA = plan.GetProperty("shipments").EnumerateArray().Single(s => s.GetProperty("warehouseId").GetInt32() == w.A);
        Assert.Equal(1, fromA.GetProperty("items")[0].GetProperty("quantity").GetInt32());
    }
}

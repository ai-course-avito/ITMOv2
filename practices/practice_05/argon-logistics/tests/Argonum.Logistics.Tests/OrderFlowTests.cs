using System.Net;
using System.Text.Json;

namespace Argonum.Logistics.Tests;

public class OrderFlowTests
{
    private static string Status(JsonElement order) => order.GetProperty("status").GetString()!;
    private static int ShipmentId(JsonElement order, int index) => order.GetProperty("shipments")[index].GetProperty("id").GetInt32();
    private static int OrderId(JsonElement order) => order.GetProperty("id").GetInt32();

    // ---- Пользователи ----

    [Fact]
    public async Task Register_user_and_reject_duplicate_email()
    {
        using var app = new TestApp();
        await app.User("ivan@example.com");

        var code = await TestApp.Code(await app.Post("/api/users", new { name = "Другой", email = "IVAN@example.com" }), HttpStatusCode.Conflict);

        Assert.Equal("user_email_duplicate", code);
    }

    [Fact]
    public async Task Register_user_validates_email()
    {
        using var app = new TestApp();

        var body = await TestApp.Json(await app.Post("/api/users", new { name = "Иван", email = "not-an-email" }), HttpStatusCode.BadRequest);

        Assert.True(body.GetProperty("errors").TryGetProperty("email", out _));
    }

    [Fact]
    public async Task Customer_endpoints_require_known_user()
    {
        using var app = new TestApp();

        Assert.Equal("user_unauthorized", await TestApp.Code(await app.Get("/api/me/orders"), HttpStatusCode.Unauthorized));
        Assert.Equal("user_unauthorized", await TestApp.Code(await app.Get("/api/me/orders", userId: 999), HttpStatusCode.Unauthorized));

        var request = new HttpRequestMessage(HttpMethod.Get, "/api/me/orders");
        request.Headers.Add("X-User-Id", "abc");
        Assert.Equal("user_unauthorized", await TestApp.Code(await app.Client.SendAsync(request), HttpStatusCode.Unauthorized));
    }

    // ---- Создание заказа и резерв ----

    [Fact]
    public async Task Order_from_two_warehouses_is_planned_with_two_shipments()
    {
        using var app = new TestApp();
        var w = await app.SeedWorld(stockA: 5, stockB: 10);

        var order = await TestApp.Json(await app.Post("/api/me/orders", w.Order(8), w.User), HttpStatusCode.Created);

        Assert.Equal("Planned", Status(order));
        Assert.Equal(80, order.GetProperty("estimatedMinutes").GetInt32());
        Assert.Equal(2, order.GetProperty("shipments").GetArrayLength());
        Assert.All(order.GetProperty("shipments").EnumerateArray(), s => Assert.Equal("Planned", s.GetProperty("status").GetString()));
        Assert.Equal(8, order.GetProperty("items")[0].GetProperty("quantity").GetInt32());
    }

    [Fact]
    public async Task Order_reserves_stock_without_touching_quantity()
    {
        using var app = new TestApp();
        var w = await app.SeedWorld(stockA: 10, stockB: 5);

        await TestApp.Json(await app.Post("/api/me/orders", w.Order(3), w.User), HttpStatusCode.Created);

        var line = await app.Stock(w.A, w.Product);
        Assert.Equal(10, line.GetProperty("quantity").GetInt32());
        Assert.Equal(3, line.GetProperty("reserved").GetInt32());
        Assert.Equal(7, line.GetProperty("available").GetInt32());
    }

    [Fact]
    public async Task Failed_order_changes_nothing()
    {
        using var app = new TestApp();
        var w = await app.SeedWorld(stockA: 5, stockB: 5);

        var code = await TestApp.Code(await app.Post("/api/me/orders", w.Order(11), w.User), HttpStatusCode.Conflict);

        Assert.Equal("insufficient_stock", code);
        Assert.Equal(0, (await app.Stock(w.A, w.Product)).GetProperty("reserved").GetInt32());
        Assert.Equal(0, (await app.Stock(w.B, w.Product)).GetProperty("reserved").GetInt32());
        var mine = await TestApp.Json(await app.Get("/api/me/orders", w.User), HttpStatusCode.OK);
        Assert.Equal(0, mine.GetArrayLength());
    }

    [Fact]
    public async Task Two_parallel_orders_for_last_unit_only_one_wins()
    {
        using var app = new TestApp();
        var product = await app.Product("LAST");
        var warehouse = await app.Warehouse("A");
        var pickup = await app.PickupPoint();
        var user = await app.User();
        await app.AddStock(warehouse, product, 1);
        await app.Link(pickup, warehouse, 10);
        var body = new { pickupPointId = pickup, items = new[] { new { productId = product, quantity = 1 } } };

        var responses = await Task.WhenAll(
            app.Post("/api/me/orders", body, user),
            app.Post("/api/me/orders", body, user),
            app.Post("/api/me/orders", body, user));

        Assert.Equal(1, responses.Count(r => r.StatusCode == HttpStatusCode.Created));
        Assert.Equal(2, responses.Count(r => r.StatusCode == HttpStatusCode.Conflict));
        var line = await app.Stock(warehouse, product);
        Assert.Equal(1, line.GetProperty("reserved").GetInt32());
        Assert.Equal(0, line.GetProperty("available").GetInt32());
    }

    // ---- Просмотр ----

    [Fact]
    public async Task Customer_sees_only_own_orders()
    {
        using var app = new TestApp();
        var w = await app.SeedWorld();
        var other = await app.User("petr@example.com");
        var order = await TestApp.Json(await app.Post("/api/me/orders", w.Order(1), w.User), HttpStatusCode.Created);

        var code = await TestApp.Code(await app.Get($"/api/me/orders/{OrderId(order)}", other), HttpStatusCode.NotFound);
        Assert.Equal("order_not_found", code);
        Assert.Equal(0, (await TestApp.Json(await app.Get("/api/me/orders", other), HttpStatusCode.OK)).GetArrayLength());
        Assert.Equal(1, (await TestApp.Json(await app.Get("/api/me/orders", w.User), HttpStatusCode.OK)).GetArrayLength());

        // Чужой заказ нельзя и отменить.
        Assert.Equal("order_not_found",
            await TestApp.Code(await app.Post($"/api/me/orders/{OrderId(order)}/cancel", null, other), HttpStatusCode.NotFound));
    }

    [Fact]
    public async Task Customer_can_filter_orders_by_status_and_bad_status_is_rejected()
    {
        using var app = new TestApp();
        var w = await app.SeedWorld();
        var first = await TestApp.Json(await app.Post("/api/me/orders", w.Order(1), w.User), HttpStatusCode.Created);
        await TestApp.Json(await app.Post("/api/me/orders", w.Order(1), w.User), HttpStatusCode.Created);
        await TestApp.Json(await app.Post($"/api/me/orders/{OrderId(first)}/cancel", null, w.User), HttpStatusCode.OK);

        var cancelled = await TestApp.Json(await app.Get("/api/me/orders?status=cancelled", w.User), HttpStatusCode.OK);
        Assert.Equal(1, cancelled.GetArrayLength());
        var planned = await TestApp.Json(await app.Get("/api/me/orders?status=Planned", w.User), HttpStatusCode.OK);
        Assert.Equal(1, planned.GetArrayLength());

        Assert.Equal("validation_failed", await TestApp.Code(await app.Get("/api/me/orders?status=bogus", w.User), HttpStatusCode.BadRequest));
    }

    [Fact]
    public async Task Order_keeps_snapshot_after_product_rename_and_delete()
    {
        using var app = new TestApp();
        var w = await app.SeedWorld(stockA: 5, stockB: 10);
        var order = await TestApp.Json(await app.Post("/api/me/orders", w.Order(15), w.User), HttpStatusCode.Created);
        await app.Put($"/api/products/{w.Product}", new { sku = "RENAMED", name = "Другое имя" });

        var renamed = await TestApp.Json(await app.Get($"/api/me/orders/{OrderId(order)}", w.User), HttpStatusCode.OK);
        Assert.Equal("MILK-1L", renamed.GetProperty("items")[0].GetProperty("sku").GetString());
        Assert.Equal("Молоко 1 л", renamed.GetProperty("items")[0].GetProperty("name").GetString());

        // Отгружаем всё, остатки обнуляются, и товар можно удалить.
        await TestApp.Json(await app.Post($"/api/shipments/{ShipmentId(order, 0)}/dispatch"), HttpStatusCode.OK);
        await TestApp.Json(await app.Post($"/api/shipments/{ShipmentId(order, 1)}/dispatch"), HttpStatusCode.OK);
        Assert.Equal(HttpStatusCode.NoContent, (await app.Delete($"/api/products/{w.Product}")).StatusCode);

        var afterDelete = await TestApp.Json(await app.Get($"/api/me/orders/{OrderId(order)}", w.User), HttpStatusCode.OK);
        Assert.Equal("MILK-1L", afterDelete.GetProperty("items")[0].GetProperty("sku").GetString());
    }

    [Fact]
    public async Task Operator_sees_any_order_and_can_filter()
    {
        using var app = new TestApp();
        var w = await app.SeedWorld();
        var order = await TestApp.Json(await app.Post("/api/me/orders", w.Order(1), w.User), HttpStatusCode.Created);

        var one = await TestApp.Json(await app.Get($"/api/orders/{OrderId(order)}"), HttpStatusCode.OK);
        Assert.Equal(w.User, one.GetProperty("userId").GetInt32());

        var byPickup = await TestApp.Json(await app.Get($"/api/orders?pickupPointId={w.Pickup}&status=Planned"), HttpStatusCode.OK);
        Assert.Equal(1, byPickup.GetArrayLength());
        var none = await TestApp.Json(await app.Get($"/api/orders?pickupPointId={w.Pickup + 1}"), HttpStatusCode.OK);
        Assert.Equal(0, none.GetArrayLength());
    }

    // ---- Отмена ----

    [Fact]
    public async Task Cancel_planned_order_releases_reserve()
    {
        using var app = new TestApp();
        var w = await app.SeedWorld(stockA: 5, stockB: 10);
        var order = await TestApp.Json(await app.Post("/api/me/orders", w.Order(8), w.User), HttpStatusCode.Created);

        var cancelled = await TestApp.Json(await app.Post($"/api/me/orders/{OrderId(order)}/cancel", null, w.User), HttpStatusCode.OK);

        Assert.Equal("Cancelled", Status(cancelled));
        Assert.All(cancelled.GetProperty("shipments").EnumerateArray(), s => Assert.Equal("Cancelled", s.GetProperty("status").GetString()));
        Assert.Equal(0, (await app.Stock(w.A, w.Product)).GetProperty("reserved").GetInt32());
        Assert.Equal(0, (await app.Stock(w.B, w.Product)).GetProperty("reserved").GetInt32());

        // Освобождённый товар снова доступен.
        await TestApp.Json(await app.Post("/api/me/orders", w.Order(15), w.User), HttpStatusCode.Created);
    }

    [Fact]
    public async Task Cancel_twice_or_after_dispatch_is_rejected()
    {
        using var app = new TestApp();
        var w = await app.SeedWorld(stockA: 5, stockB: 10);
        var order = await TestApp.Json(await app.Post("/api/me/orders", w.Order(8), w.User), HttpStatusCode.Created);
        await TestApp.Json(await app.Post($"/api/shipments/{ShipmentId(order, 0)}/dispatch"), HttpStatusCode.OK);

        var code = await TestApp.Code(await app.Post($"/api/me/orders/{OrderId(order)}/cancel", null, w.User), HttpStatusCode.Conflict);
        Assert.Equal("order_not_cancellable", code);
        Assert.Equal(3, (await app.Stock(w.B, w.Product)).GetProperty("reserved").GetInt32());

        var second = await TestApp.Json(await app.Post("/api/me/orders", w.Order(1), w.User), HttpStatusCode.Created);
        await TestApp.Json(await app.Post($"/api/me/orders/{OrderId(second)}/cancel", null, w.User), HttpStatusCode.OK);
        Assert.Equal("order_not_cancellable",
            await TestApp.Code(await app.Post($"/api/me/orders/{OrderId(second)}/cancel", null, w.User), HttpStatusCode.Conflict));
    }

    // ---- Отправки ----

    [Fact]
    public async Task Dispatch_writes_off_stock_and_sets_times()
    {
        using var app = new TestApp();
        var w = await app.SeedWorld(stockA: 10, stockB: 1);
        var order = await TestApp.Json(await app.Post("/api/me/orders", w.Order(3), w.User), HttpStatusCode.Created);

        var dispatched = await TestApp.Json(await app.Post($"/api/shipments/{ShipmentId(order, 0)}/dispatch"), HttpStatusCode.OK);

        var line = await app.Stock(w.A, w.Product);
        Assert.Equal(7, line.GetProperty("quantity").GetInt32());
        Assert.Equal(0, line.GetProperty("reserved").GetInt32());
        var shipment = dispatched.GetProperty("shipments")[0];
        Assert.Equal("Dispatched", shipment.GetProperty("status").GetString());
        var sent = shipment.GetProperty("dispatchedAt").GetDateTimeOffset();
        var arrival = shipment.GetProperty("estimatedArrivalAt").GetDateTimeOffset();
        Assert.Equal(TimeSpan.FromMinutes(30), arrival - sent);
        Assert.Equal("InTransit", Status(dispatched));
    }

    [Fact]
    public async Task Repeated_dispatch_does_not_write_off_twice()
    {
        using var app = new TestApp();
        var w = await app.SeedWorld(stockA: 10, stockB: 1);
        var order = await TestApp.Json(await app.Post("/api/me/orders", w.Order(3), w.User), HttpStatusCode.Created);
        var id = ShipmentId(order, 0);
        await TestApp.Json(await app.Post($"/api/shipments/{id}/dispatch"), HttpStatusCode.OK);

        var code = await TestApp.Code(await app.Post($"/api/shipments/{id}/dispatch"), HttpStatusCode.Conflict);

        Assert.Equal("shipment_invalid_transition", code);
        Assert.Equal(7, (await app.Stock(w.A, w.Product)).GetProperty("quantity").GetInt32());
    }

    [Fact]
    public async Task Dispatch_of_cancelled_shipment_is_rejected()
    {
        using var app = new TestApp();
        var w = await app.SeedWorld();
        var order = await TestApp.Json(await app.Post("/api/me/orders", w.Order(1), w.User), HttpStatusCode.Created);
        await app.Post($"/api/me/orders/{OrderId(order)}/cancel", null, w.User);

        var code = await TestApp.Code(await app.Post($"/api/shipments/{ShipmentId(order, 0)}/dispatch"), HttpStatusCode.Conflict);

        Assert.Equal("shipment_invalid_transition", code);
    }

    [Fact]
    public async Task Deliver_requires_dispatch_first()
    {
        using var app = new TestApp();
        var w = await app.SeedWorld();
        var order = await TestApp.Json(await app.Post("/api/me/orders", w.Order(1), w.User), HttpStatusCode.Created);

        var code = await TestApp.Code(await app.Post($"/api/shipments/{ShipmentId(order, 0)}/deliver"), HttpStatusCode.Conflict);

        Assert.Equal("shipment_invalid_transition", code);
    }

    [Fact]
    public async Task Unknown_shipment_returns_404()
    {
        using var app = new TestApp();

        Assert.Equal("shipment_not_found", await TestApp.Code(await app.Post("/api/shipments/999/dispatch"), HttpStatusCode.NotFound));
    }

    [Fact]
    public async Task Order_status_follows_shipments_until_pickup()
    {
        using var app = new TestApp();
        var w = await app.SeedWorld(stockA: 5, stockB: 10);
        var order = await TestApp.Json(await app.Post("/api/me/orders", w.Order(8), w.User), HttpStatusCode.Created);
        var s1 = ShipmentId(order, 0);
        var s2 = ShipmentId(order, 1);
        var orderId = OrderId(order);
        Assert.Equal("Planned", Status(order));

        Assert.Equal("InTransit", Status(await TestApp.Json(await app.Post($"/api/shipments/{s1}/dispatch"), HttpStatusCode.OK)));
        Assert.Equal("InTransit", Status(await TestApp.Json(await app.Post($"/api/shipments/{s2}/dispatch"), HttpStatusCode.OK)));
        Assert.Equal("InTransit", Status(await TestApp.Json(await app.Post($"/api/shipments/{s1}/deliver"), HttpStatusCode.OK)));

        // Не готов к выдаче, пока едет вторая отправка.
        Assert.Equal("order_invalid_transition",
            await TestApp.Code(await app.Post($"/api/orders/{orderId}/pickup"), HttpStatusCode.Conflict));

        var ready = await TestApp.Json(await app.Post($"/api/shipments/{s2}/deliver"), HttpStatusCode.OK);
        Assert.Equal("ReadyForPickup", Status(ready));
        Assert.NotEqual(JsonValueKind.Null, ready.GetProperty("shipments")[0].GetProperty("deliveredAt").ValueKind);

        var done = await TestApp.Json(await app.Post($"/api/orders/{orderId}/pickup"), HttpStatusCode.OK);
        Assert.Equal("Completed", Status(done));
        Assert.Equal("order_invalid_transition",
            await TestApp.Code(await app.Post($"/api/orders/{orderId}/pickup"), HttpStatusCode.Conflict));

        // Остатки списаны: A 5→0, B 10→7.
        Assert.Equal(0, (await app.Stock(w.A, w.Product)).GetProperty("quantity").GetInt32());
        var b = await app.Stock(w.B, w.Product);
        Assert.Equal(7, b.GetProperty("quantity").GetInt32());
        Assert.Equal(0, b.GetProperty("reserved").GetInt32());
    }

    [Fact]
    public async Task Full_scenario_across_graph_with_transit_warehouse()
    {
        using var app = new TestApp();
        var milk = await app.Product("MILK", "Молоко");
        var bread = await app.Product("BREAD", "Хлеб");
        var north = await app.Warehouse("Север");
        var hub = await app.Warehouse("Хаб");
        var south = await app.Warehouse("Юг");
        var pickup = await app.PickupPoint("Арбат");
        var user = await app.User();
        await app.AddStock(north, milk, 4);
        await app.AddStock(south, milk, 4);
        await app.AddStock(south, bread, 2);
        await app.Route(north, hub, 60);
        await app.Route(south, hub, 90, bidirectional: true);
        await app.Link(pickup, hub, 15);

        var order = await TestApp.Json(await app.Post("/api/me/orders", new
        {
            pickupPointId = pickup,
            items = new[] { new { productId = milk, quantity = 6 }, new { productId = bread, quantity = 1 } }
        }, user), HttpStatusCode.Created);

        // Север ближе (75 мин), Юг дальше (105 мин): молоко 4 + 2, хлеб 1 с Юга.
        var shipments = order.GetProperty("shipments");
        Assert.Equal(2, shipments.GetArrayLength());
        Assert.Equal(north, shipments[0].GetProperty("warehouseId").GetInt32());
        Assert.Equal(75, shipments[0].GetProperty("totalMinutes").GetInt32());
        Assert.Equal([north, hub], shipments[0].GetProperty("route").EnumerateArray().Select(x => x.GetInt32()));
        Assert.Equal(south, shipments[1].GetProperty("warehouseId").GetInt32());
        Assert.Equal(105, order.GetProperty("estimatedMinutes").GetInt32());
        Assert.Equal(2, shipments[1].GetProperty("items").GetArrayLength());
    }
}

using System.Net;
using System.Text.Json;

namespace Argonum.Logistics.Tests;

public class ReturnFlowTests
{
    private static string Status(JsonElement order) => order.GetProperty("status").GetString()!;
    private static JsonElement Returns(JsonElement order) => order.GetProperty("returns");
    private static int Quantity(JsonElement returnShipment) =>
        returnShipment.GetProperty("items").EnumerateArray().Sum(i => i.GetProperty("quantity").GetInt32());

    /// <summary>
    /// Мир для возвратов: A (30 мин от ПВЗ) и B (80 мин), путь A → B 20 мин, поэтому до B через A выходит 50.
    /// Заказ в <paramref name="ordered"/> единиц доставлен и готов к выдаче, склады почти пусты.
    /// </summary>
    private sealed record Scene(TestApp App, World World, int OrderId);

    private static async Task<Scene> Ready(TestApp app, int ordered = 5, int capacityA = 100, int capacityB = 100)
    {
        var product = await app.Product("MILK-1L", "Молоко 1 л");
        var a = await app.Warehouse("Склад A");
        var b = await app.Warehouse("Склад B");
        var pickup = await app.PickupPoint();
        await app.AddStock(a, product, ordered);
        await app.Link(pickup, a, 30);
        await app.Link(pickup, b, 80);
        await app.Route(a, b, 20);
        var world = new World(product, a, b, pickup, await app.User());
        var orderId = await app.ReadyOrder(world, ordered);

        // Вместимость задаём после заказа: пока товар лежал на складе, он должен был помещаться.
        await TestApp.Json(await app.SetCapacity(a, capacityA), HttpStatusCode.OK);
        await TestApp.Json(await app.SetCapacity(b, capacityB), HttpStatusCode.OK);
        return new Scene(app, world, orderId);
    }

    private static async Task<JsonElement> Order(TestApp app, int orderId) =>
        await TestApp.Json(await app.Get($"/api/orders/{orderId}"), HttpStatusCode.OK);

    // ---- Оформление отказа ----

    [Fact]
    public async Task Partial_refusal_returns_to_nearest_warehouse()
    {
        using var app = new TestApp();
        var s = await Ready(app, ordered: 5);

        var order = await TestApp.Json(await app.Refuse(s.OrderId, s.World.User, (s.World.Product, 2)), HttpStatusCode.Created);

        Assert.Equal("ReadyForPickup", Status(order));
        Assert.Equal(2, order.GetProperty("items")[0].GetProperty("refusedQuantity").GetInt32());
        var ret = Assert.Single(Returns(order).EnumerateArray());
        Assert.Equal(s.World.A, ret.GetProperty("warehouseId").GetInt32());
        Assert.Equal("Planned", ret.GetProperty("status").GetString());
        Assert.Equal(30, ret.GetProperty("totalMinutes").GetInt32());
        Assert.Equal(2, Quantity(ret));
        Assert.Equal("pickupPoint", ret.GetProperty("legs")[0].GetProperty("from").GetProperty("type").GetString());
        Assert.Equal(s.World.Pickup, ret.GetProperty("legs")[0].GetProperty("from").GetProperty("id").GetInt32());
    }

    [Fact]
    public async Task Refusal_reserves_space_as_incoming()
    {
        using var app = new TestApp();
        var s = await Ready(app);

        await TestApp.Json(await app.Refuse(s.OrderId, s.World.User, (s.World.Product, 3)), HttpStatusCode.Created);

        var a = await app.NetworkWarehouse(s.World.A);
        Assert.Equal(3, a.GetProperty("incomingQuantity").GetInt32());
        Assert.Equal(0, a.GetProperty("totalQuantity").GetInt32());
    }

    [Fact]
    public async Task Full_nearest_warehouse_sends_return_through_it_to_the_next_one()
    {
        using var app = new TestApp();
        var s = await Ready(app, ordered: 5, capacityA: 10);
        await app.AddStock(s.World.A, s.World.Product, 10); // A заполнен

        var order = await TestApp.Json(await app.Refuse(s.OrderId, s.World.User, (s.World.Product, 3)), HttpStatusCode.Created);

        var ret = Assert.Single(Returns(order).EnumerateArray());
        Assert.Equal(s.World.B, ret.GetProperty("warehouseId").GetInt32());
        Assert.Equal(50, ret.GetProperty("totalMinutes").GetInt32());
        Assert.Equal([s.World.A, s.World.B], ret.GetProperty("route").EnumerateArray().Select(r => r.GetInt32()));
        Assert.Equal(2, ret.GetProperty("legs").GetArrayLength());
        Assert.Equal(3, (await app.NetworkWarehouse(s.World.B)).GetProperty("incomingQuantity").GetInt32());
        Assert.Equal(0, (await app.NetworkWarehouse(s.World.A)).GetProperty("incomingQuantity").GetInt32());
    }

    [Fact]
    public async Task Return_is_split_when_the_nearest_warehouse_has_little_space()
    {
        using var app = new TestApp();
        var s = await Ready(app, ordered: 5, capacityA: 10);
        await app.AddStock(s.World.A, s.World.Product, 8); // у A свободно 2

        var order = await TestApp.Json(await app.Refuse(s.OrderId, s.World.User, (s.World.Product, 5)), HttpStatusCode.Created);

        var byWarehouse = Returns(order).EnumerateArray()
            .ToDictionary(r => r.GetProperty("warehouseId").GetInt32(), Quantity);
        Assert.Equal(2, byWarehouse[s.World.A]);
        Assert.Equal(3, byWarehouse[s.World.B]);
    }

    [Fact]
    public async Task Refusal_without_space_is_rejected_entirely()
    {
        using var app = new TestApp();
        var s = await Ready(app, ordered: 5, capacityA: 10, capacityB: 3);
        await app.AddStock(s.World.A, s.World.Product, 10);

        var body = await TestApp.Json(await app.Refuse(s.OrderId, s.World.User, (s.World.Product, 5)), HttpStatusCode.Conflict);

        Assert.Equal("return_no_capacity", body.GetProperty("code").GetString());
        Assert.Equal(5, body.GetProperty("requested").GetInt32());
        Assert.Equal(3, body.GetProperty("reachableFree").GetInt32());
        var order = await Order(app, s.OrderId);
        Assert.Empty(Returns(order).EnumerateArray());
        Assert.Equal(0, order.GetProperty("items")[0].GetProperty("refusedQuantity").GetInt32());
        Assert.Equal(0, (await app.NetworkWarehouse(s.World.B)).GetProperty("incomingQuantity").GetInt32());
    }

    [Fact]
    public async Task Second_refusal_sees_space_taken_by_the_first()
    {
        using var app = new TestApp();
        var s = await Ready(app, ordered: 8, capacityA: 5);

        await TestApp.Json(await app.Refuse(s.OrderId, s.World.User, (s.World.Product, 5)), HttpStatusCode.Created);
        var order = await TestApp.Json(await app.Refuse(s.OrderId, s.World.User, (s.World.Product, 3)), HttpStatusCode.Created);

        var returns = Returns(order).EnumerateArray().ToList();
        Assert.Equal(2, returns.Count);
        Assert.Equal(s.World.A, returns[0].GetProperty("warehouseId").GetInt32());
        Assert.Equal(s.World.B, returns[1].GetProperty("warehouseId").GetInt32());
        Assert.Equal(3, Quantity(returns[1]));
    }

    [Fact]
    public async Task Incoming_return_blocks_manual_restocking()
    {
        using var app = new TestApp();
        var s = await Ready(app, ordered: 5, capacityA: 10);
        await app.AddStock(s.World.A, s.World.Product, 3); // занято 3
        await TestApp.Json(await app.Refuse(s.OrderId, s.World.User, (s.World.Product, 5)), HttpStatusCode.Created); // входящих 5

        // Итого занято и входящее 8 из 10: 2 влезают, 3 нет.
        var code = await TestApp.Code(
            await app.Post($"/api/warehouses/{s.World.A}/stock", new { productId = s.World.Product, quantity = 3 }), HttpStatusCode.Conflict);
        Assert.Equal("warehouse_capacity_exceeded", code);
        await TestApp.Json(
            await app.Post($"/api/warehouses/{s.World.A}/stock", new { productId = s.World.Product, quantity = 2 }), HttpStatusCode.OK);
    }

    [Fact]
    public async Task Capacity_cannot_drop_below_occupied_plus_incoming()
    {
        using var app = new TestApp();
        var s = await Ready(app, ordered: 5);
        await TestApp.Json(await app.Refuse(s.OrderId, s.World.User, (s.World.Product, 5)), HttpStatusCode.Created);

        Assert.Equal("capacity_below_occupied", await TestApp.Code(await app.SetCapacity(s.World.A, 4), HttpStatusCode.Conflict));
        await TestApp.Json(await app.SetCapacity(s.World.A, 5), HttpStatusCode.OK);
    }

    [Fact]
    public async Task Warehouse_with_incoming_return_cannot_be_deleted()
    {
        using var app = new TestApp();
        var s = await Ready(app, ordered: 5);
        await TestApp.Json(await app.Refuse(s.OrderId, s.World.User, (s.World.Product, 5)), HttpStatusCode.Created);

        var code = await TestApp.Code(await app.Delete($"/api/warehouses/{s.World.A}"), HttpStatusCode.Conflict);

        Assert.Equal("warehouse_has_shipments", code);
    }

    // ---- Правила допустимости ----

    [Fact]
    public async Task Cannot_refuse_more_than_ordered_including_earlier_refusals()
    {
        using var app = new TestApp();
        var s = await Ready(app, ordered: 3);
        await TestApp.Json(await app.Refuse(s.OrderId, s.World.User, (s.World.Product, 2)), HttpStatusCode.Created);

        var code = await TestApp.Code(await app.Refuse(s.OrderId, s.World.User, (s.World.Product, 2)), HttpStatusCode.Conflict);

        Assert.Equal("refusal_exceeds_ordered", code);
        Assert.Equal(2, (await Order(app, s.OrderId)).GetProperty("items")[0].GetProperty("refusedQuantity").GetInt32());
    }

    [Theory]
    [InlineData("Planned")]
    [InlineData("InTransit")]
    [InlineData("Completed")]
    [InlineData("Cancelled")]
    public async Task Only_orders_ready_for_pickup_can_be_refused(string status)
    {
        using var app = new TestApp();
        var w = await app.SeedWorld(stockA: 5, stockB: 5);
        var order = await TestApp.Json(await app.Post("/api/me/orders", w.Order(2), w.User), HttpStatusCode.Created);
        var orderId = order.GetProperty("id").GetInt32();
        var shipmentId = order.GetProperty("shipments")[0].GetProperty("id").GetInt32();
        switch (status)
        {
            case "InTransit":
                await app.Post($"/api/shipments/{shipmentId}/dispatch");
                break;
            case "Completed":
                await app.Post($"/api/shipments/{shipmentId}/dispatch");
                await app.Post($"/api/shipments/{shipmentId}/deliver");
                await app.Post($"/api/orders/{orderId}/pickup");
                break;
            case "Cancelled":
                await app.Post($"/api/me/orders/{orderId}/cancel", userId: w.User);
                break;
        }
        Assert.Equal(status, Status(await Order(app, orderId)));

        var code = await TestApp.Code(await app.Refuse(orderId, w.User, (w.Product, 1)), HttpStatusCode.Conflict);

        Assert.Equal("order_not_refusable", code);
    }

    [Fact]
    public async Task Other_users_order_is_not_found()
    {
        using var app = new TestApp();
        var s = await Ready(app);
        var stranger = await app.User("other@example.com");

        var code = await TestApp.Code(await app.Refuse(s.OrderId, stranger, (s.World.Product, 1)), HttpStatusCode.NotFound);

        Assert.Equal("order_not_found", code);
    }

    [Fact]
    public async Task Refusal_request_is_validated()
    {
        using var app = new TestApp();
        var s = await Ready(app);
        var other = await app.Product("OTHER");

        foreach (var items in new[]
                 {
                     Array.Empty<(int, int)>(),
                     new[] { (s.World.Product, 0) },
                     new[] { (s.World.Product, -1) },
                     new[] { (s.World.Product, 1), (s.World.Product, 1) },
                     new[] { (other, 1) },
                 })
        {
            var code = await TestApp.Code(await app.Refuse(s.OrderId, s.World.User, items), HttpStatusCode.BadRequest);
            Assert.Equal("validation_failed", code);
        }

        Assert.Empty(Returns(await Order(app, s.OrderId)).EnumerateArray());
    }

    [Fact]
    public async Task Refusal_requires_a_known_user()
    {
        using var app = new TestApp();
        var s = await Ready(app);

        var code = await TestApp.Code(await app.Refuse(s.OrderId, 999, (s.World.Product, 1)), HttpStatusCode.Unauthorized);

        Assert.Equal("user_unauthorized", code);
    }

    // ---- Статус заказа ----

    [Fact]
    public async Task Refusing_everything_marks_the_order_returned()
    {
        using var app = new TestApp();
        var s = await Ready(app, ordered: 4);
        await TestApp.Json(await app.Refuse(s.OrderId, s.World.User, (s.World.Product, 1)), HttpStatusCode.Created);

        var order = await TestApp.Json(await app.Refuse(s.OrderId, s.World.User, (s.World.Product, 3)), HttpStatusCode.Created);

        Assert.Equal("Returned", Status(order));
        Assert.Equal("order_invalid_transition",
            await TestApp.Code(await app.Post($"/api/orders/{s.OrderId}/pickup"), HttpStatusCode.Conflict));
    }

    [Fact]
    public async Task Partial_refusal_then_pickup_completes_the_order()
    {
        using var app = new TestApp();
        var s = await Ready(app, ordered: 4);
        await TestApp.Json(await app.Refuse(s.OrderId, s.World.User, (s.World.Product, 1)), HttpStatusCode.Created);

        var picked = await TestApp.Json(await app.Post($"/api/orders/{s.OrderId}/pickup"), HttpStatusCode.OK);

        Assert.Equal("Completed", Status(picked));
        Assert.Single(Returns(picked).EnumerateArray());
    }

    [Fact]
    public async Task Order_without_refusals_has_empty_returns()
    {
        using var app = new TestApp();
        var s = await Ready(app);

        var order = await Order(app, s.OrderId);

        Assert.Empty(Returns(order).EnumerateArray());
        Assert.Equal(0, order.GetProperty("items")[0].GetProperty("refusedQuantity").GetInt32());
    }

    // ---- Предпросмотр ----

    [Fact]
    public async Task Return_plan_is_a_dry_run()
    {
        using var app = new TestApp();
        var s = await Ready(app, ordered: 5, capacityA: 10);
        await app.AddStock(s.World.A, s.World.Product, 9); // у A свободно 1

        var plan = await TestApp.Json(await app.Post("/api/return-plans",
            new { pickupPointId = s.World.Pickup, items = new[] { new { productId = s.World.Product, quantity = 4 } } }), HttpStatusCode.OK);

        Assert.Equal(2, plan.GetProperty("shipments").GetArrayLength());
        Assert.Equal(50, plan.GetProperty("estimatedMinutes").GetInt32());
        Assert.Equal(0, (await app.NetworkWarehouse(s.World.A)).GetProperty("incomingQuantity").GetInt32());
        Assert.Equal(0, (await app.NetworkWarehouse(s.World.B)).GetProperty("incomingQuantity").GetInt32());
        Assert.Empty(Returns(await Order(app, s.OrderId)).EnumerateArray());
    }

    [Fact]
    public async Task Return_plan_reports_planning_errors()
    {
        using var app = new TestApp();
        var s = await Ready(app, ordered: 5, capacityA: 5, capacityB: 5);
        await app.AddStock(s.World.A, s.World.Product, 5);
        var lonely = await app.PickupPoint("Без привязок");
        object Request(int pickup, int quantity) =>
            new { pickupPointId = pickup, items = new[] { new { productId = s.World.Product, quantity } } };

        Assert.Equal("return_no_capacity",
            await TestApp.Code(await app.Post("/api/return-plans", Request(s.World.Pickup, 50)), HttpStatusCode.Conflict));
        Assert.Equal("pickup_point_unreachable",
            await TestApp.Code(await app.Post("/api/return-plans", Request(lonely, 1)), HttpStatusCode.Conflict));
        Assert.Equal("pickup_point_not_found",
            await TestApp.Code(await app.Post("/api/return-plans", Request(999, 1)), HttpStatusCode.NotFound));
        Assert.Equal("validation_failed",
            await TestApp.Code(await app.Post("/api/return-plans", Request(s.World.Pickup, 0)), HttpStatusCode.BadRequest));
    }

    // ---- Жизненный цикл ----

    private static async Task<int> FirstReturnId(TestApp app, int orderId) =>
        Returns(await Order(app, orderId))[0].GetProperty("id").GetInt32();

    [Fact]
    public async Task Delivery_adds_stock_and_turns_incoming_into_occupied()
    {
        using var app = new TestApp();
        var s = await Ready(app, ordered: 5);
        await TestApp.Json(await app.Refuse(s.OrderId, s.World.User, (s.World.Product, 3)), HttpStatusCode.Created);
        var id = await FirstReturnId(app, s.OrderId);

        var dispatched = await TestApp.Json(await app.Post($"/api/returns/{id}/dispatch"), HttpStatusCode.OK);
        var ret = Returns(dispatched)[0];
        Assert.Equal("Dispatched", ret.GetProperty("status").GetString());
        Assert.NotEqual(JsonValueKind.Null, ret.GetProperty("dispatchedAt").ValueKind);
        Assert.NotEqual(JsonValueKind.Null, ret.GetProperty("estimatedArrivalAt").ValueKind);
        Assert.Equal(3, (await app.NetworkWarehouse(s.World.A)).GetProperty("incomingQuantity").GetInt32());

        var delivered = await TestApp.Json(await app.Post($"/api/returns/{id}/deliver"), HttpStatusCode.OK);

        Assert.Equal("Delivered", Returns(delivered)[0].GetProperty("status").GetString());
        var a = await app.NetworkWarehouse(s.World.A);
        Assert.Equal(3, a.GetProperty("totalQuantity").GetInt32());
        Assert.Equal(0, a.GetProperty("incomingQuantity").GetInt32());
        Assert.Equal(3, (await app.Stock(s.World.A, s.World.Product)).GetProperty("quantity").GetInt32());
    }

    [Fact]
    public async Task Delivery_tops_up_an_existing_stock_line()
    {
        using var app = new TestApp();
        var s = await Ready(app, ordered: 5);
        await app.AddStock(s.World.A, s.World.Product, 4);
        await TestApp.Json(await app.Refuse(s.OrderId, s.World.User, (s.World.Product, 2)), HttpStatusCode.Created);
        var id = await FirstReturnId(app, s.OrderId);
        await app.Post($"/api/returns/{id}/dispatch");

        await TestApp.Json(await app.Post($"/api/returns/{id}/deliver"), HttpStatusCode.OK);

        Assert.Equal(6, (await app.Stock(s.World.A, s.World.Product)).GetProperty("quantity").GetInt32());
    }

    [Fact]
    public async Task Return_transitions_are_enforced()
    {
        using var app = new TestApp();
        var s = await Ready(app);
        await TestApp.Json(await app.Refuse(s.OrderId, s.World.User, (s.World.Product, 1)), HttpStatusCode.Created);
        var id = await FirstReturnId(app, s.OrderId);

        Assert.Equal("return_invalid_transition", await TestApp.Code(await app.Post($"/api/returns/{id}/deliver"), HttpStatusCode.Conflict));
        await TestApp.Json(await app.Post($"/api/returns/{id}/dispatch"), HttpStatusCode.OK);
        Assert.Equal("return_invalid_transition", await TestApp.Code(await app.Post($"/api/returns/{id}/dispatch"), HttpStatusCode.Conflict));
        await TestApp.Json(await app.Post($"/api/returns/{id}/deliver"), HttpStatusCode.OK);
        Assert.Equal("return_invalid_transition", await TestApp.Code(await app.Post($"/api/returns/{id}/deliver"), HttpStatusCode.Conflict));
        Assert.Equal(1, (await app.Stock(s.World.A, s.World.Product)).GetProperty("quantity").GetInt32());
    }

    [Fact]
    public async Task Unknown_return_returns_404()
    {
        using var app = new TestApp();

        Assert.Equal("return_not_found", await TestApp.Code(await app.Post("/api/returns/999/dispatch"), HttpStatusCode.NotFound));
        Assert.Equal("return_not_found", await TestApp.Code(await app.Post("/api/returns/999/deliver"), HttpStatusCode.NotFound));
    }

    // ---- Конкурентность ----

    [Fact]
    public async Task Concurrent_refusals_never_overfill_the_warehouse()
    {
        using var app = new TestApp();
        var product = await app.Product("MILK-1L", "Молоко 1 л");
        var a = await app.Warehouse("Склад A", capacity: 10);
        var pickup = await app.PickupPoint();
        await app.AddStock(a, product, 10);
        await app.Link(pickup, a, 30);
        var world = new World(product, a, a, pickup, await app.User());
        var first = await app.ReadyOrder(world, 5);
        var second = await app.ReadyOrder(world, 5);
        await TestApp.Json(await app.SetCapacity(a, 5), HttpStatusCode.OK); // свободно ровно 5

        var results = await Task.WhenAll(
            app.Refuse(first, world.User, (product, 5)),
            app.Refuse(second, world.User, (product, 5)));

        Assert.Equal(1, results.Count(r => r.StatusCode == HttpStatusCode.Created));
        Assert.Equal(1, results.Count(r => r.StatusCode == HttpStatusCode.Conflict));
        var network = await app.NetworkWarehouse(a);
        Assert.True(network.GetProperty("totalQuantity").GetInt32() + network.GetProperty("incomingQuantity").GetInt32()
                    <= network.GetProperty("capacity").GetInt32());
    }

    // ---- Симуляция ----

    [Fact]
    public async Task Simulation_moves_returns_by_itself()
    {
        using var app = TestApp.WithSimulation(speedFactor: 1000, dispatchDelaySeconds: 0);
        var product = await app.Product("MILK-1L", "Молоко 1 л");
        var a = await app.Warehouse("Склад A", capacity: 100);
        var pickup = await app.PickupPoint();
        await app.AddStock(a, product, 5);
        await app.Link(pickup, a, 30);
        var world = new World(product, a, a, pickup, await app.User());
        var orderId = (await TestApp.Json(await app.Post("/api/me/orders", world.Order(5), world.User), HttpStatusCode.Created))
            .GetProperty("id").GetInt32();
        Assert.True(await TestApp.WaitUntil(async () => Status(await Order(app, orderId)) == "ReadyForPickup"));

        await TestApp.Json(await app.Refuse(orderId, world.User, (product, 5)), HttpStatusCode.Created);

        Assert.True(await TestApp.WaitUntil(async () =>
            Returns(await Order(app, orderId))[0].GetProperty("status").GetString() == "Delivered"));
        Assert.Equal("Returned", Status(await Order(app, orderId)));
        Assert.Equal(5, (await app.Stock(a, product)).GetProperty("quantity").GetInt32());
        Assert.Equal(0, (await app.NetworkWarehouse(a)).GetProperty("incomingQuantity").GetInt32());
    }

    [Fact]
    public async Task Without_simulation_return_stays_planned()
    {
        using var app = new TestApp();
        var s = await Ready(app);
        await TestApp.Json(await app.Refuse(s.OrderId, s.World.User, (s.World.Product, 1)), HttpStatusCode.Created);

        await Task.Delay(300);

        Assert.Equal("Planned", Returns(await Order(app, s.OrderId))[0].GetProperty("status").GetString());
    }
}

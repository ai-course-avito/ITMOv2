using System.Net;
using System.Text.Json;

namespace Argonum.Logistics.Tests;

public class SimulationTests
{
    private static async Task<JsonElement> GetOrder(TestApp app, int orderId) =>
        await TestApp.Json(await app.Get($"/api/orders/{orderId}"), HttpStatusCode.OK);

    private static string Status(JsonElement order) => order.GetProperty("status").GetString()!;

    [Fact]
    public async Task Simulation_is_disabled_by_default()
    {
        using var app = new TestApp();
        var info = await TestApp.Json(await app.Get("/api/simulation"), HttpStatusCode.OK);

        Assert.False(info.GetProperty("enabled").GetBoolean());
        Assert.True(info.GetProperty("speedFactor").GetDouble() > 0);
        Assert.InRange((DateTimeOffset.UtcNow - info.GetProperty("serverTime").GetDateTimeOffset()).TotalSeconds, -5, 5);

        var w = await app.SeedWorld();
        var order = await TestApp.Json(await app.Post("/api/me/orders", w.Order(1), w.User), HttpStatusCode.Created);
        await Task.Delay(700);

        Assert.Equal("Planned", Status(await GetOrder(app, order.GetProperty("id").GetInt32())));
    }

    [Fact]
    public async Task Info_reports_configured_values()
    {
        using var app = TestApp.WithSimulation(speedFactor: 3, dispatchDelaySeconds: 7);

        var info = await TestApp.Json(await app.Get("/api/simulation"), HttpStatusCode.OK);

        Assert.True(info.GetProperty("enabled").GetBoolean());
        Assert.Equal(3, info.GetProperty("speedFactor").GetDouble());
        Assert.Equal(7, info.GetProperty("dispatchDelaySeconds").GetDouble());
    }

    [Fact]
    public async Task Order_travels_to_ready_for_pickup_but_is_not_collected_automatically()
    {
        using var app = TestApp.WithSimulation(speedFactor: 1000, dispatchDelaySeconds: 0);
        var w = await app.SeedWorld(stockA: 5, stockB: 10);
        var order = await TestApp.Json(await app.Post("/api/me/orders", w.Order(8), w.User), HttpStatusCode.Created);
        var id = order.GetProperty("id").GetInt32();

        var ready = await TestApp.WaitUntil(async () => Status(await GetOrder(app, id)) == "ReadyForPickup");

        Assert.True(ready, "заказ не доехал до ReadyForPickup");
        var done = await GetOrder(app, id);
        Assert.All(done.GetProperty("shipments").EnumerateArray(), s =>
        {
            Assert.Equal("Delivered", s.GetProperty("status").GetString());
            Assert.NotEqual(JsonValueKind.Null, s.GetProperty("dispatchedAt").ValueKind);
        });
        // Остатки списаны при отгрузке: A 5→0, B 10→7.
        Assert.Equal(0, (await app.Stock(w.A, w.Product)).GetProperty("quantity").GetInt32());
        Assert.Equal(7, (await app.Stock(w.B, w.Product)).GetProperty("quantity").GetInt32());

        // Выдачу симуляция не делает.
        await Task.Delay(400);
        Assert.Equal("ReadyForPickup", Status(await GetOrder(app, id)));
        Assert.Equal("Completed", Status(await TestApp.Json(await app.Post($"/api/orders/{id}/pickup"), HttpStatusCode.OK)));
    }

    [Fact]
    public async Task Delivery_waits_for_travel_time()
    {
        // 30 минут пути при 10 мин/с: около 3 секунд в пути.
        using var app = TestApp.WithSimulation(speedFactor: 10, dispatchDelaySeconds: 0);
        var w = await app.SeedWorld(stockA: 5, stockB: 1);
        var order = await TestApp.Json(await app.Post("/api/me/orders", w.Order(2), w.User), HttpStatusCode.Created);
        var id = order.GetProperty("id").GetInt32();

        Assert.True(await TestApp.WaitUntil(async () => Status(await GetOrder(app, id)) == "InTransit", 5));
        var started = DateTimeOffset.UtcNow;
        await Task.Delay(1000);
        Assert.Equal("InTransit", Status(await GetOrder(app, id)));

        Assert.True(await TestApp.WaitUntil(async () => Status(await GetOrder(app, id)) == "ReadyForPickup", 10));
        Assert.True((DateTimeOffset.UtcNow - started).TotalSeconds > 1.5, "доставка не должна быть мгновенной");
    }

    [Fact]
    public async Task Dispatch_waits_for_configured_delay_and_cancelled_orders_are_skipped()
    {
        using var app = TestApp.WithSimulation(speedFactor: 1000, dispatchDelaySeconds: 1.5);
        var w = await app.SeedWorld(stockA: 5, stockB: 5);
        var kept = await TestApp.Json(await app.Post("/api/me/orders", w.Order(2), w.User), HttpStatusCode.Created);
        var cancelled = await TestApp.Json(await app.Post("/api/me/orders", w.Order(1), w.User), HttpStatusCode.Created);
        await TestApp.Json(await app.Post($"/api/me/orders/{cancelled.GetProperty("id").GetInt32()}/cancel", null, w.User), HttpStatusCode.OK);

        await Task.Delay(500);
        Assert.Equal("Planned", Status(await GetOrder(app, kept.GetProperty("id").GetInt32())));

        Assert.True(await TestApp.WaitUntil(async () =>
            Status(await GetOrder(app, kept.GetProperty("id").GetInt32())) is "InTransit" or "ReadyForPickup", 10));
        var untouched = await GetOrder(app, cancelled.GetProperty("id").GetInt32());
        Assert.Equal("Cancelled", Status(untouched));
        Assert.All(untouched.GetProperty("shipments").EnumerateArray(), s => Assert.Equal("Cancelled", s.GetProperty("status").GetString()));
        // Списано только по неотменённому заказу (2 единицы с ближнего склада A).
        Assert.Equal(3, (await app.Stock(w.A, w.Product)).GetProperty("quantity").GetInt32());
    }

    [Fact]
    public async Task Manual_dispatch_before_simulation_writes_off_once_and_simulation_keeps_working()
    {
        // Медленные грузовики: за время теста ничего не доедет, нам важна только отгрузка.
        using var app = TestApp.WithSimulation(speedFactor: 0.001, dispatchDelaySeconds: 1);
        var w = await app.SeedWorld(stockA: 10, stockB: 1);
        var first = await TestApp.Json(await app.Post("/api/me/orders", w.Order(3), w.User), HttpStatusCode.Created);
        var shipmentId = first.GetProperty("shipments")[0].GetProperty("id").GetInt32();
        await TestApp.Json(await app.Post($"/api/shipments/{shipmentId}/dispatch"), HttpStatusCode.OK);

        await Task.Delay(1800); // симуляция уже могла попытаться отгрузить ту же отправку
        Assert.Equal(7, (await app.Stock(w.A, w.Product)).GetProperty("quantity").GetInt32());

        var second = await TestApp.Json(await app.Post("/api/me/orders", w.Order(2), w.User), HttpStatusCode.Created);
        var secondId = second.GetProperty("id").GetInt32();
        Assert.True(await TestApp.WaitUntil(async () => Status(await GetOrder(app, secondId)) == "InTransit", 10));
        Assert.Equal(5, (await app.Stock(w.A, w.Product)).GetProperty("quantity").GetInt32());
    }
}

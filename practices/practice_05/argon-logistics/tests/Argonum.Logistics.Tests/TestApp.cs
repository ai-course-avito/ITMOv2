using System.Net;
using System.Net.Http.Json;
using System.Text.Json;
using Microsoft.AspNetCore.Hosting;
using Microsoft.AspNetCore.Mvc.Testing;

namespace Argonum.Logistics.Tests;

/// <summary>Изолированный экземпляр API с собственным SQLite-файлом.</summary>
public sealed class TestApp : WebApplicationFactory<Program>
{
    private readonly string _dbPath = Path.Combine(Path.GetTempPath(), $"argon-test-{Guid.NewGuid():N}.db");
    private readonly IReadOnlyDictionary<string, string> _settings;
    private HttpClient? _client;

    public TestApp(IReadOnlyDictionary<string, string>? settings = null) => _settings = settings ?? new Dictionary<string, string>();

    /// <summary>Приложение с включённой быстрой симуляцией движения.</summary>
    public static TestApp WithSimulation(double speedFactor = 1000, double dispatchDelaySeconds = 0) => new(new Dictionary<string, string>
    {
        ["Simulation:Enabled"] = "true",
        ["Simulation:SpeedFactor"] = speedFactor.ToString(System.Globalization.CultureInfo.InvariantCulture),
        ["Simulation:DispatchDelaySeconds"] = dispatchDelaySeconds.ToString(System.Globalization.CultureInfo.InvariantCulture),
        ["Simulation:TickMilliseconds"] = "50"
    });

    public HttpClient Client => _client ??= CreateClient();

    protected override void ConfigureWebHost(IWebHostBuilder builder)
    {
        builder.UseEnvironment("Testing");
        builder.UseSetting("ConnectionStrings:Argon", $"Data Source={_dbPath};Pooling=False");
        foreach (var (key, value) in _settings) builder.UseSetting(key, value);
    }

    protected override void Dispose(bool disposing)
    {
        base.Dispose(disposing);
        if (!disposing) return;
        foreach (var suffix in new[] { "", "-wal", "-shm" })
        {
            try { File.Delete(_dbPath + suffix); } catch (IOException) { /* best effort */ }
        }
    }

    // ---- HTTP ----

    public async Task<HttpResponseMessage> Send(HttpMethod method, string url, object? body = null, int? userId = null)
    {
        var request = new HttpRequestMessage(method, url);
        if (body is not null) request.Content = JsonContent.Create(body);
        if (userId is not null) request.Headers.Add("X-User-Id", userId.Value.ToString());
        return await Client.SendAsync(request);
    }

    public Task<HttpResponseMessage> Get(string url, int? userId = null) => Send(HttpMethod.Get, url, null, userId);
    public Task<HttpResponseMessage> Post(string url, object? body = null, int? userId = null) => Send(HttpMethod.Post, url, body ?? new { }, userId);
    public Task<HttpResponseMessage> Put(string url, object body) => Send(HttpMethod.Put, url, body);
    public Task<HttpResponseMessage> Delete(string url) => Send(HttpMethod.Delete, url);

    /// <summary>Проверяет статус и возвращает тело как JSON.</summary>
    public static async Task<JsonElement> Json(HttpResponseMessage response, HttpStatusCode expected)
    {
        var text = await response.Content.ReadAsStringAsync();
        Assert.True(expected == response.StatusCode, $"Ожидали {(int)expected}, получили {(int)response.StatusCode}: {text}");
        return text.Length == 0 ? default : JsonDocument.Parse(text).RootElement.Clone();
    }

    public static async Task<string> Code(HttpResponseMessage response, HttpStatusCode expected) =>
        (await Json(response, expected)).GetProperty("code").GetString()!;

    // ---- Заготовки данных ----

    public async Task<int> Product(string sku, string name = "Товар") =>
        (await Json(await Post("/api/products", new { sku, name }), HttpStatusCode.Created)).GetProperty("id").GetInt32();

    public async Task<int> Warehouse(string name, int? capacity = null) =>
        (await Json(await Post("/api/warehouses", new { name, address = "Адрес " + name, capacity }), HttpStatusCode.Created)).GetProperty("id").GetInt32();

    public async Task<HttpResponseMessage> SetCapacity(int warehouseId, int capacity)
    {
        var current = await Json(await Get($"/api/warehouses/{warehouseId}"), HttpStatusCode.OK);
        return await Put($"/api/warehouses/{warehouseId}", new
        {
            name = current.GetProperty("name").GetString(),
            address = current.GetProperty("address").GetString(),
            capacity
        });
    }

    /// <summary>Заказ из мира, отгруженный и доставленный в ПВЗ: готов к выдаче (отказу). Возвращает id заказа.</summary>
    public async Task<int> ReadyOrder(World w, int quantity)
    {
        var order = await Json(await Post("/api/me/orders", w.Order(quantity), w.User), HttpStatusCode.Created);
        foreach (var shipment in order.GetProperty("shipments").EnumerateArray())
        {
            var id = shipment.GetProperty("id").GetInt32();
            await Json(await Post($"/api/shipments/{id}/dispatch"), HttpStatusCode.OK);
            await Json(await Post($"/api/shipments/{id}/deliver"), HttpStatusCode.OK);
        }
        return order.GetProperty("id").GetInt32();
    }

    public Task<HttpResponseMessage> Refuse(int orderId, int userId, params (int ProductId, int Quantity)[] items) =>
        Post($"/api/me/orders/{orderId}/returns",
            new { items = items.Select(i => new { productId = i.ProductId, quantity = i.Quantity }).ToArray() }, userId);

    public async Task<JsonElement> Warehouses() =>
        (await Json(await Get("/api/network"), HttpStatusCode.OK)).GetProperty("warehouses");

    public async Task<JsonElement> NetworkWarehouse(int id) =>
        (await Warehouses()).EnumerateArray().Single(w => w.GetProperty("id").GetInt32() == id);

    public async Task<int> PickupPoint(string name = "ПВЗ-1", bool isActive = true) =>
        (await Json(await Post("/api/pickup-points", new { name, address = "Адрес " + name, isActive }), HttpStatusCode.Created)).GetProperty("id").GetInt32();

    public async Task<int> User(string email = "ivan@example.com") =>
        (await Json(await Post("/api/users", new { name = "Иван", email }), HttpStatusCode.Created)).GetProperty("id").GetInt32();

    /// <summary>Добавляет товар на склад; 201 для новой строки, 200 для пополнения существующей.</summary>
    public async Task AddStock(int warehouseId, int productId, int quantity)
    {
        var response = await Post($"/api/warehouses/{warehouseId}/stock", new { productId, quantity });
        await Json(response, response.StatusCode == HttpStatusCode.OK ? HttpStatusCode.OK : HttpStatusCode.Created);
    }

    public async Task Link(int pickupPointId, int warehouseId, int minutes) =>
        await Json(await Put($"/api/pickup-points/{pickupPointId}/links/{warehouseId}", new { minutes }), HttpStatusCode.OK);

    public async Task<int> Route(int from, int to, int minutes, bool bidirectional = false) =>
        (await Json(await Post("/api/routes", new { fromWarehouseId = from, toWarehouseId = to, minutes, bidirectional }),
            HttpStatusCode.Created)).GetProperty("id").GetInt32();

    public async Task<JsonElement> Stock(int warehouseId, int productId)
    {
        var lines = await Json(await Get($"/api/warehouses/{warehouseId}/stock"), HttpStatusCode.OK);
        return lines.EnumerateArray().Single(l => l.GetProperty("productId").GetInt32() == productId);
    }

    /// <summary>Ждёт условия, опрашивая его; нужен для фоновой симуляции.</summary>
    public static async Task<bool> WaitUntil(Func<Task<bool>> condition, double timeoutSeconds = 10)
    {
        var deadline = DateTime.UtcNow.AddSeconds(timeoutSeconds);
        while (DateTime.UtcNow < deadline)
        {
            if (await condition()) return true;
            await Task.Delay(50);
        }
        return await condition();
    }

    /// <summary>Мир по умолчанию: товар на двух складах, ПВЗ привязан к обоим (A: 30 мин, B: 80 мин).</summary>
    public async Task<World> SeedWorld(int stockA = 5, int stockB = 10)
    {
        var product = await Product("MILK-1L", "Молоко 1 л");
        var a = await Warehouse("Склад A");
        var b = await Warehouse("Склад B");
        var pickup = await PickupPoint();
        await AddStock(a, product, stockA);
        await AddStock(b, product, stockB);
        await Link(pickup, a, 30);
        await Link(pickup, b, 80);
        var user = await User();
        return new World(product, a, b, pickup, user);
    }
}

public sealed record World(int Product, int A, int B, int Pickup, int User)
{
    public object Order(int quantity) => new { pickupPointId = Pickup, items = new[] { new { productId = Product, quantity } } };
}

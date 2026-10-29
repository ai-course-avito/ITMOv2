using System.Net;

namespace Argonum.Logistics.Tests;

public class CatalogTests
{
    [Fact]
    public async Task Create_and_list_products()
    {
        using var app = new TestApp();

        var created = await TestApp.Json(
            await app.Post("/api/products", new { sku = "  MILK-1L ", name = "Молоко 1 л", description = "Свежее" }),
            HttpStatusCode.Created);
        Assert.Equal("MILK-1L", created.GetProperty("sku").GetString());
        await app.Product("BREAD", "Хлеб");

        var list = await TestApp.Json(await app.Get("/api/products"), HttpStatusCode.OK);
        Assert.Equal(2, list.GetArrayLength());
    }

    [Fact]
    public async Task Duplicate_sku_is_rejected_ignoring_case()
    {
        using var app = new TestApp();
        await app.Product("MILK-1L");

        var code = await TestApp.Code(await app.Post("/api/products", new { sku = "milk-1l", name = "Другое" }), HttpStatusCode.Conflict);
        Assert.Equal("product_sku_duplicate", code);
    }

    [Fact]
    public async Task Update_to_taken_sku_keeps_old_sku()
    {
        using var app = new TestApp();
        var a = await app.Product("A");
        await app.Product("B");

        var code = await TestApp.Code(await app.Put($"/api/products/{a}", new { sku = "B", name = "x" }), HttpStatusCode.Conflict);
        Assert.Equal("product_sku_duplicate", code);

        var product = await TestApp.Json(await app.Get($"/api/products/{a}"), HttpStatusCode.OK);
        Assert.Equal("A", product.GetProperty("sku").GetString());
    }

    [Fact]
    public async Task Update_keeping_own_sku_is_allowed()
    {
        using var app = new TestApp();
        var a = await app.Product("A");

        var updated = await TestApp.Json(await app.Put($"/api/products/{a}", new { sku = "A", name = "Новое имя" }), HttpStatusCode.OK);
        Assert.Equal("Новое имя", updated.GetProperty("name").GetString());
    }

    [Fact]
    public async Task Validation_error_names_the_field()
    {
        using var app = new TestApp();

        var body = await TestApp.Json(await app.Post("/api/products", new { sku = "A", name = "" }), HttpStatusCode.BadRequest);

        Assert.Equal("validation_failed", body.GetProperty("code").GetString());
        Assert.True(body.GetProperty("errors").TryGetProperty("name", out _));
        Assert.False(body.GetProperty("errors").TryGetProperty("sku", out _));
    }

    [Fact]
    public async Task Missing_product_returns_problem_with_code()
    {
        using var app = new TestApp();

        var response = await app.Get("/api/products/999");

        Assert.Equal("application/problem+json", response.Content.Headers.ContentType?.MediaType);
        Assert.Equal("product_not_found", await TestApp.Code(response, HttpStatusCode.NotFound));
    }

    [Fact]
    public async Task Malformed_json_returns_400_problem()
    {
        using var app = new TestApp();

        var response = await app.Client.PostAsync("/api/products",
            new StringContent("{ not json", System.Text.Encoding.UTF8, "application/json"));

        Assert.Equal("bad_request", await TestApp.Code(response, HttpStatusCode.BadRequest));
    }

    [Fact]
    public async Task Cannot_delete_product_with_stock()
    {
        using var app = new TestApp();
        var product = await app.Product("MILK");
        var warehouse = await app.Warehouse("A");
        await app.AddStock(warehouse, product, 5);

        var code = await TestApp.Code(await app.Delete($"/api/products/{product}"), HttpStatusCode.Conflict);

        Assert.Equal("product_has_stock", code);
        Assert.Equal(HttpStatusCode.OK, (await app.Get($"/api/products/{product}")).StatusCode);
    }

    [Fact]
    public async Task Delete_product_without_stock_removes_zero_lines()
    {
        using var app = new TestApp();
        var product = await app.Product("MILK");
        var warehouse = await app.Warehouse("A");
        await TestApp.Json(await app.Put($"/api/warehouses/{warehouse}/stock/{product}", new { quantity = 0 }), HttpStatusCode.OK);

        Assert.Equal(HttpStatusCode.NoContent, (await app.Delete($"/api/products/{product}")).StatusCode);

        Assert.Equal(HttpStatusCode.NotFound, (await app.Get($"/api/products/{product}")).StatusCode);
        var stock = await TestApp.Json(await app.Get($"/api/warehouses/{warehouse}/stock"), HttpStatusCode.OK);
        Assert.Equal(0, stock.GetArrayLength());
    }
}

using Argonum.Logistics.Api.Data;
using Argonum.Logistics.Api.Endpoints;
using Argonum.Logistics.Api.Infrastructure;
using Argonum.Logistics.Api.Services;
using Argonum.Logistics.Api.Simulation;
using Microsoft.AspNetCore.Http;
using Microsoft.EntityFrameworkCore;

var builder = WebApplication.CreateBuilder(args);

// Строка подключения читается лениво, чтобы тесты могли подменить её через конфигурацию хоста.
builder.Services.AddDbContext<ArgonDbContext>((sp, o) =>
    o.UseSqlite(sp.GetRequiredService<IConfiguration>().GetConnectionString("Argon") ?? "Data Source=argon.db"));

builder.Services.AddSingleton(TimeProvider.System);
builder.Services.AddSingleton<InventoryLock>();
builder.Services.AddScoped<PlanningService>();
builder.Services.AddScoped<OrderService>();
builder.Services.AddScoped<ReturnService>();

// Симуляция движения: по умолчанию выключена (секция "Simulation"), сервис сам выходит, если Enabled=false.
builder.Services.Configure<SimulationOptions>(builder.Configuration.GetSection("Simulation"));
builder.Services.AddHostedService<SimulationService>();

// Битый запрос должен проходить через наш обработчик (единый формат с code), а не только в Development.
builder.Services.Configure<RouteHandlerOptions>(o => o.ThrowOnBadRequest = true);
builder.Services.AddProblemDetails();
builder.Services.AddExceptionHandler<ProblemExceptionHandler>();
builder.Services.AddOpenApi();

var app = builder.Build();

using (var scope = app.Services.CreateScope())
{
    var db = scope.ServiceProvider.GetRequiredService<ArgonDbContext>();
    db.Database.EnsureCreated();
    db.Database.ExecuteSqlRaw("PRAGMA journal_mode=WAL;");
}

app.UseExceptionHandler();
app.UseStatusCodePages();

if (app.Environment.IsDevelopment())
    app.MapOpenApi();

app.MapGet("/", () => Results.Redirect("/openapi/v1.json")).ExcludeFromDescription();

app.MapProducts();
app.MapWarehouses();
app.MapPickupPoints();
app.MapRoutes();
app.MapNetwork();
app.MapPlanning();
app.MapUsers();
app.MapCustomerOrders();
app.MapOperations();

app.Run();

public partial class Program;

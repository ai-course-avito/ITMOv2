using Argonum.Logistics.Api.Contracts;
using Argonum.Logistics.Api.Data;
using Argonum.Logistics.Api.Infrastructure;
using Argonum.Logistics.Api.Services;
using Argonum.Logistics.Core;
using Argonum.Logistics.Core.Entities;
using Microsoft.EntityFrameworkCore;

namespace Argonum.Logistics.Api.Endpoints;

public static class OrderEndpoints
{
    private const string UserIdKey = "argon.userId";

    public static void MapPlanning(this IEndpointRouteBuilder app)
    {
        app.MapPost("/api/plans", async (PlanRequest req, PlanningService planning, CancellationToken ct) =>
            await planning.PlanAsync(req.PickupPointId, req.Items, ct))
            .WithTags("Planning");

        app.MapPost("/api/return-plans", async (PlanRequest req, ReturnService returns, CancellationToken ct) =>
            await returns.PlanAsync(req.PickupPointId, req.Items, ct))
            .WithTags("Planning");
    }

    public static void MapUsers(this IEndpointRouteBuilder app)
    {
        var g = app.MapGroup("/api/users").WithTags("Users");

        g.MapPost("", async (UserRequest req, ArgonDbContext db, CancellationToken ct) =>
        {
            new Validator()
                .Required("name", req.Name, 200, out var name)
                .Email("email", req.Email, out var email)
                .ThrowIfInvalid();

            if (await db.Users.AnyAsync(u => u.EmailKey == TextKey.Of(email), ct))
                throw DomainException.Conflict("user_email_duplicate", $"Email {email} уже зарегистрирован.");

            var user = new User { Name = name, Email = email, EmailKey = TextKey.Of(email) };
            db.Users.Add(user);
            await db.SaveChangesAsync(ct);
            return Results.Created($"/api/users/{user.Id}", UserDto.From(user));
        });

        g.MapGet("{id:int}", async (int id, ArgonDbContext db, CancellationToken ct) =>
            UserDto.From(await db.Users.AsNoTracking().FirstOrDefaultAsync(u => u.Id == id, ct)
                         ?? throw DomainException.NotFound("user_not_found", $"Пользователь {id} не найден.")));
    }

    /// <summary>Клиентская часть: заказы текущего пользователя (заголовок X-User-Id).</summary>
    public static void MapCustomerOrders(this IEndpointRouteBuilder app)
    {
        var g = app.MapGroup("/api/me/orders").WithTags("Customer");
        g.AddEndpointFilter(RequireUser);

        g.MapPost("", async (PlanRequest req, HttpContext http, OrderService orders, CancellationToken ct) =>
        {
            var order = await orders.CreateAsync(UserId(http), req, ct);
            return Results.Created($"/api/me/orders/{order.Id}", order);
        });

        g.MapGet("", async (string? status, HttpContext http, OrderService orders, CancellationToken ct) =>
            await orders.ListAsync(UserId(http), status, null, ct));

        g.MapGet("{id:int}", async (int id, HttpContext http, OrderService orders, CancellationToken ct) =>
            await orders.GetAsync(id, UserId(http), ct));

        g.MapPost("{id:int}/cancel", async (int id, HttpContext http, OrderService orders, CancellationToken ct) =>
            await orders.CancelAsync(UserId(http), id, ct));

        g.MapPost("{id:int}/returns", async (int id, RefusalRequest req, HttpContext http, ReturnService returns, CancellationToken ct) =>
        {
            var order = await returns.RefuseAsync(UserId(http), id, req, ct);
            return Results.Created($"/api/me/orders/{order.Id}", order);
        });
    }

    /// <summary>Операторская часть: все заказы, отгрузка/доставка отправок, выдача.</summary>
    public static void MapOperations(this IEndpointRouteBuilder app)
    {
        var orders = app.MapGroup("/api/orders").WithTags("Operations");

        orders.MapGet("", async (string? status, int? pickupPointId, OrderService svc, CancellationToken ct) =>
            await svc.ListAsync(null, status, pickupPointId, ct));

        orders.MapGet("{id:int}", async (int id, OrderService svc, CancellationToken ct) =>
            await svc.GetAsync(id, null, ct));

        orders.MapPost("{id:int}/pickup", async (int id, OrderService svc, CancellationToken ct) =>
            await svc.PickupAsync(id, ct));

        var shipments = app.MapGroup("/api/shipments").WithTags("Operations");

        shipments.MapPost("{id:int}/dispatch", async (int id, OrderService svc, CancellationToken ct) =>
            await svc.DispatchAsync(id, ct));

        shipments.MapPost("{id:int}/deliver", async (int id, OrderService svc, CancellationToken ct) =>
            await svc.DeliverAsync(id, ct));

        var returns = app.MapGroup("/api/returns").WithTags("Operations");

        returns.MapPost("{id:int}/dispatch", async (int id, ReturnService svc, CancellationToken ct) =>
            await svc.DispatchAsync(id, ct));

        returns.MapPost("{id:int}/deliver", async (int id, ReturnService svc, CancellationToken ct) =>
            await svc.DeliverAsync(id, ct));
    }

    private static int UserId(HttpContext http) => (int)http.Items[UserIdKey]!;

    private static async ValueTask<object?> RequireUser(EndpointFilterInvocationContext ctx, EndpointFilterDelegate next)
    {
        var http = ctx.HttpContext;
        if (!http.Request.Headers.TryGetValue("X-User-Id", out var header) || !int.TryParse(header, out var userId))
            throw new DomainException(401, "user_unauthorized", "Нужен заголовок X-User-Id с идентификатором пользователя.");

        var db = http.RequestServices.GetRequiredService<ArgonDbContext>();
        if (!await db.Users.AnyAsync(u => u.Id == userId, http.RequestAborted))
            throw new DomainException(401, "user_unauthorized", $"Пользователь {userId} не найден.");

        http.Items[UserIdKey] = userId;
        return await next(ctx);
    }
}

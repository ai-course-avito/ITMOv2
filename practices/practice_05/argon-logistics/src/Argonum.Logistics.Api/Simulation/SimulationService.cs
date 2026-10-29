using Argonum.Logistics.Api.Data;
using Argonum.Logistics.Api.Services;
using Argonum.Logistics.Core;
using Argonum.Logistics.Core.Entities;
using Microsoft.EntityFrameworkCore;
using Microsoft.Extensions.Options;

namespace Argonum.Logistics.Api.Simulation;

/// <summary>
/// Сама отгружает запланированные отправки и доставляет их в ПВЗ по времени пути (с ускорением).
/// Использует те же операции OrderService, что и ручное управление, поэтому замок и инварианты общие.
/// Выдачу клиенту не делает: это действие человека.
/// </summary>
public sealed class SimulationService(
    IServiceScopeFactory scopes,
    IOptions<SimulationOptions> options,
    TimeProvider time,
    ILogger<SimulationService> logger) : BackgroundService
{
    protected override async Task ExecuteAsync(CancellationToken stoppingToken)
    {
        var o = options.Value;
        if (!o.Enabled) return;

        logger.LogInformation("Симуляция логистики включена: x{Speed} мин/с, задержка отгрузки {Delay} с",
            o.EffectiveSpeedFactor, o.EffectiveDispatchDelaySeconds);

        using var timer = new PeriodicTimer(o.Tick);
        while (await WaitAsync(timer, stoppingToken))
        {
            try
            {
                await TickAsync(o, stoppingToken);
            }
            catch (OperationCanceledException) when (stoppingToken.IsCancellationRequested)
            {
                return;
            }
            catch (Exception e)
            {
                logger.LogError(e, "Ошибка тика симуляции");
            }
        }
    }

    private static async Task<bool> WaitAsync(PeriodicTimer timer, CancellationToken ct)
    {
        try { return await timer.WaitForNextTickAsync(ct); }
        catch (OperationCanceledException) { return false; }
    }

    private async Task TickAsync(SimulationOptions o, CancellationToken ct)
    {
        var now = time.GetUtcNow();
        List<(int Id, DateTimeOffset CreatedAt)> planned;
        List<(int Id, DateTimeOffset DispatchedAt, int TotalMinutes)> moving;
        List<(int Id, DateTimeOffset CreatedAt)> plannedReturns;
        List<(int Id, DateTimeOffset DispatchedAt, int TotalMinutes)> movingReturns;

        using (var scope = scopes.CreateScope())
        {
            var db = scope.ServiceProvider.GetRequiredService<ArgonDbContext>();

            // Времена сравниваем в памяти: SQLite плохо справляется с DateTimeOffset в запросах.
            planned = (await db.Shipments.AsNoTracking()
                    .Where(s => s.Status == ShipmentStatus.Planned)
                    .Join(db.Orders, s => s.OrderId, order => order.Id, (s, order) => new { s.Id, order.CreatedAt })
                    .ToListAsync(ct))
                .Select(x => (x.Id, x.CreatedAt)).ToList();

            moving = (await db.Shipments.AsNoTracking()
                    .Where(s => s.Status == ShipmentStatus.Dispatched && s.DispatchedAt != null)
                    .Select(s => new { s.Id, s.DispatchedAt, s.TotalMinutes })
                    .ToListAsync(ct))
                .Select(x => (x.Id, x.DispatchedAt!.Value, x.TotalMinutes)).ToList();

            plannedReturns = (await db.ReturnShipments.AsNoTracking()
                    .Where(r => r.Status == ReturnStatus.Planned)
                    .Select(r => new { r.Id, r.CreatedAt })
                    .ToListAsync(ct))
                .Select(x => (x.Id, x.CreatedAt)).ToList();

            movingReturns = (await db.ReturnShipments.AsNoTracking()
                    .Where(r => r.Status == ReturnStatus.Dispatched && r.DispatchedAt != null)
                    .Select(r => new { r.Id, r.DispatchedAt, r.TotalMinutes })
                    .ToListAsync(ct))
                .Select(x => (x.Id, x.DispatchedAt!.Value, x.TotalMinutes)).ToList();
        }

        foreach (var (id, createdAt) in planned)
        {
            if ((now - createdAt).TotalSeconds < o.EffectiveDispatchDelaySeconds) continue;
            await RunAsync(id, "отгрузка", (svc, ct2) => svc.DispatchAsync(id, ct2), ct);
        }

        foreach (var (id, dispatchedAt, totalMinutes) in moving)
        {
            if ((now - dispatchedAt).TotalSeconds * o.EffectiveSpeedFactor < totalMinutes) continue;
            await RunAsync(id, "доставка", (svc, ct2) => svc.DeliverAsync(id, ct2), ct);
        }

        // Возвраты едут так же: отгрузка после задержки, доставка по времени пути.
        foreach (var (id, createdAt) in plannedReturns)
        {
            if ((now - createdAt).TotalSeconds < o.EffectiveDispatchDelaySeconds) continue;
            await RunReturnAsync(id, "отгрузка возврата", (svc, ct2) => svc.DispatchAsync(id, ct2), ct);
        }

        foreach (var (id, dispatchedAt, totalMinutes) in movingReturns)
        {
            if ((now - dispatchedAt).TotalSeconds * o.EffectiveSpeedFactor < totalMinutes) continue;
            await RunReturnAsync(id, "доставка возврата", (svc, ct2) => svc.DeliverAsync(id, ct2), ct);
        }
    }

    private Task RunAsync(int shipmentId, string action, Func<OrderService, CancellationToken, Task> run, CancellationToken ct) =>
        RunAsync<OrderService>(shipmentId, action, run, ct);

    private Task RunReturnAsync(int returnId, string action, Func<ReturnService, CancellationToken, Task> run, CancellationToken ct) =>
        RunAsync<ReturnService>(returnId, action, run, ct);

    /// <summary>Каждое действие в своём scope. Конфликт с ручной операцией не страшен и не останавливает симуляцию.</summary>
    private async Task RunAsync<TService>(int shipmentId, string action, Func<TService, CancellationToken, Task> run, CancellationToken ct)
        where TService : notnull
    {
        try
        {
            using var scope = scopes.CreateScope();
            await run(scope.ServiceProvider.GetRequiredService<TService>(), ct);
        }
        catch (DomainException e) when (e.StatusCode is 404 or 409)
        {
            logger.LogDebug("Симуляция: {Action} отправки {Shipment} пропущена ({Code})", action, shipmentId, e.Code);
        }
    }
}

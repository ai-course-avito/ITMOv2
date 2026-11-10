namespace Argonum.Logistics.Api.Infrastructure;

/// <summary>
/// Сериализует все операции, меняющие остатки и резервы (один инстанс API).
/// Без неё два заказа на последнюю единицу могли бы оба увидеть её свободной.
/// </summary>
public sealed class InventoryLock
{
    private readonly SemaphoreSlim _gate = new(1, 1);

    public async Task<T> RunAsync<T>(Func<Task<T>> action)
    {
        await _gate.WaitAsync();
        try
        {
            return await action();
        }
        finally
        {
            _gate.Release();
        }
    }

    public Task RunAsync(Func<Task> action) =>
        RunAsync<object?>(async () =>
        {
            await action();
            return null;
        });
}

namespace Argonum.Logistics.Api.Simulation;

/// <summary>Секция конфигурации "Simulation".</summary>
public sealed class SimulationOptions
{
    /// <summary>По умолчанию симуляция выключена: статусы меняют только ручные операции.</summary>
    public bool Enabled { get; set; }

    /// <summary>Сколько минут пути проходит за одну реальную секунду.</summary>
    public double SpeedFactor { get; set; } = 1;

    /// <summary>Через сколько секунд после создания заказа отправки отгружаются.</summary>
    public double DispatchDelaySeconds { get; set; } = 5;

    public int TickMilliseconds { get; set; } = 500;

    public double EffectiveSpeedFactor => SpeedFactor > 0 && double.IsFinite(SpeedFactor) ? SpeedFactor : 1;
    public double EffectiveDispatchDelaySeconds => DispatchDelaySeconds >= 0 ? DispatchDelaySeconds : 0;
    public TimeSpan Tick => TimeSpan.FromMilliseconds(Math.Max(TickMilliseconds, 20));
}

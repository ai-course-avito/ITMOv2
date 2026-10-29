using System.Text.RegularExpressions;
using Argonum.Logistics.Core;
using Argonum.Logistics.Core.Entities;

namespace Argonum.Logistics.Api.Infrastructure;

/// <summary>Собирает ошибки полей и бросает единый validation_failed.</summary>
public sealed partial class Validator
{
    public const int MaxQuantity = 1_000_000;
    public const int MaxMinutes = 10_080;
    public const double MaxMapCoordinate = 100_000;

    private readonly Dictionary<string, List<string>> _errors = [];

    public Validator Required(string field, string? value, int maxLength, out string trimmed)
    {
        trimmed = value?.Trim() ?? "";
        if (trimmed.Length == 0) Add(field, "Поле обязательно.");
        else if (trimmed.Length > maxLength) Add(field, $"Не длиннее {maxLength} символов.");
        return this;
    }

    public Validator Optional(string field, string? value, int maxLength, out string? trimmed)
    {
        trimmed = string.IsNullOrWhiteSpace(value) ? null : value.Trim();
        if (trimmed is { } t && t.Length > maxLength) Add(field, $"Не длиннее {maxLength} символов.");
        return this;
    }

    public Validator Range(string field, int value, int min, int max)
    {
        if (value < min || value > max) Add(field, $"Значение от {min} до {max}.");
        return this;
    }

    public Validator Capacity(string field, int? value)
    {
        if (value is { } v && (v < 1 || v > Warehouse.MaxCapacity))
            Add(field, $"Значение от 1 до {Warehouse.MaxCapacity}.");
        return this;
    }

    public Validator MapCoordinate(string field, double? value)
    {
        if (value is { } v && (!double.IsFinite(v) || Math.Abs(v) > MaxMapCoordinate))
            Add(field, $"Значение от -{MaxMapCoordinate:0} до {MaxMapCoordinate:0}.");
        return this;
    }

    public Validator Email(string field, string? value, out string trimmed)
    {
        Required(field, value, 254, out trimmed);
        if (trimmed.Length > 0 && !EmailRegex().IsMatch(trimmed)) Add(field, "Некорректный email.");
        return this;
    }

    public Validator Check(bool ok, string field, string message)
    {
        if (!ok) Add(field, message);
        return this;
    }

    public void ThrowIfInvalid()
    {
        if (_errors.Count > 0)
            throw DomainException.Validation(_errors.ToDictionary(e => e.Key, e => e.Value.ToArray()));
    }

    private void Add(string field, string message)
    {
        if (!_errors.TryGetValue(field, out var list)) _errors[field] = list = [];
        list.Add(message);
    }

    [GeneratedRegex(@"^[^@\s]+@[^@\s]+\.[^@\s]+$")]
    private static partial Regex EmailRegex();
}

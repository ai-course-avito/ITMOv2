namespace Argonum.Logistics.Core;

/// <summary>
/// Ключ для уникальности без учёта регистра. Коллация NOCASE в SQLite понимает только ASCII,
/// поэтому для кириллицы сравниваем нормализованный ключ.
/// </summary>
public static class TextKey
{
    public static string Of(string value) => value.Trim().ToUpperInvariant();
}

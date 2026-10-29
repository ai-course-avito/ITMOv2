namespace Argonum.Logistics.Core;

/// <summary>Бизнес-ошибка с машинным кодом; Api превращает её в problem+json.</summary>
public sealed class DomainException : Exception
{
    public DomainException(int statusCode, string code, string detail)
        : base(detail)
    {
        StatusCode = statusCode;
        Code = code;
    }

    public int StatusCode { get; }
    public string Code { get; }
    public IDictionary<string, string[]>? Errors { get; init; }
    public IDictionary<string, object?>? Extensions { get; init; }

    public static DomainException NotFound(string code, string detail) => new(404, code, detail);
    public static DomainException Conflict(string code, string detail) => new(409, code, detail);

    public static DomainException Validation(IDictionary<string, string[]> errors) =>
        new(400, "validation_failed", "Запрос не прошёл валидацию.") { Errors = errors };
}

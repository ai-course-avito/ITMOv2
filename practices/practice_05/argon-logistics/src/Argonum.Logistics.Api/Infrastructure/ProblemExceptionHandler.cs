using Argonum.Logistics.Core;
using Microsoft.AspNetCore.Diagnostics;
using Microsoft.AspNetCore.Mvc;
using Microsoft.EntityFrameworkCore;

namespace Argonum.Logistics.Api.Infrastructure;

/// <summary>Все ошибки уходят клиенту как application/problem+json с полем code.</summary>
public sealed class ProblemExceptionHandler(ILogger<ProblemExceptionHandler> logger) : IExceptionHandler
{
    public async ValueTask<bool> TryHandleAsync(HttpContext context, Exception exception, CancellationToken ct)
    {
        var problem = exception switch
        {
            DomainException d => FromDomain(d),
            BadHttpRequestException => Create(400, "bad_request", "Некорректный запрос.", "Тело запроса не удалось разобрать."),
            DbUpdateException { InnerException.Message: var m } when m.Contains("UNIQUE", StringComparison.OrdinalIgnoreCase)
                => Create(409, "conflict", "Конфликт данных.", "Запись с такими данными уже существует."),
            _ => null
        };

        if (problem is null)
        {
            logger.LogError(exception, "Необработанная ошибка");
            problem = Create(500, "internal_error", "Внутренняя ошибка.", "Что-то пошло не так.");
        }

        context.Response.StatusCode = problem.Status!.Value;
        // Тип передаём явно, иначе поля ValidationProblemDetails (errors) не сериализуются.
        await context.Response.WriteAsJsonAsync(problem, problem.GetType(), options: null, contentType: "application/problem+json", ct);
        return true;
    }

    private static ProblemDetails FromDomain(DomainException d)
    {
        var problem = d.Errors is null
            ? new ProblemDetails()
            : new ValidationProblemDetails(new Dictionary<string, string[]>(d.Errors));

        problem.Status = d.StatusCode;
        problem.Title = d.Code;
        problem.Detail = d.Message;
        problem.Extensions["code"] = d.Code;
        if (d.Extensions is not null)
            foreach (var (key, value) in d.Extensions)
                problem.Extensions[key] = value;
        return problem;
    }

    private static ProblemDetails Create(int status, string code, string title, string detail)
    {
        var problem = new ProblemDetails { Status = status, Title = title, Detail = detail };
        problem.Extensions["code"] = code;
        return problem;
    }
}

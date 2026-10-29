using Argonum.Logistics.Api.Data;
using Argonum.Logistics.Core.Entities;
using Microsoft.EntityFrameworkCore;

namespace Argonum.Logistics.Api.Services;

public static class OrderQueries
{
    /// <summary>Заказы со всеми позициями, отправками и возвратами (для OrderMapper).</summary>
    public static IQueryable<Order> OrdersWithDetails(this ArgonDbContext db) =>
        db.Orders
            .Include(o => o.Items)
            .Include(o => o.Shipments).ThenInclude(s => s.Items)
            .Include(o => o.Returns).ThenInclude(r => r.Items)
            .AsSplitQuery();
}

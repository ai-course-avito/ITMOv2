namespace Argonum.Logistics.Core.Planning;

/// <param name="Free">Свободное место склада: вместимость минус занятое минус входящее.</param>
public sealed record WarehouseSpace(int Id, string Name, int Free);

public sealed record ReturnPlanningInput(
    int PickupPointId,
    string PickupPointName,
    IReadOnlyCollection<WarehouseSpace> Warehouses,
    IReadOnlyCollection<RouteEdge> Routes,
    IReadOnlyCollection<PickupEdge> PickupLinks,
    IReadOnlyCollection<ProductRef> Products,
    IReadOnlyCollection<RequestedItem> Items);

/// <summary>
/// Чистая логика планирования возврата (без БД и HTTP). Едем от ПВЗ: первый участок это привязка
/// склад → ПВЗ в обратную сторону с тем же временем, дальше направленные пути между складами.
/// Товар берёт ближайший склад со свободным местом, излишек едет к следующему; заполненный склад
/// может быть транзитным. Результат в формате DeliveryPlan: у отправки WarehouseId это склад-получатель,
/// Route это склады по пути (без ПВЗ), первый участок Legs начинается в узле ПВЗ.
/// </summary>
public static class ReturnPlanner
{
    // Как у DeliveryPlanner: минуты * Scale + число пересадок.
    private const long Scale = 1_000_000;
    private const int PickupMarker = -1;

    public static DeliveryPlan Build(ReturnPlanningInput input)
    {
        var spaces = input.Warehouses.ToDictionary(w => w.Id);
        var links = input.PickupLinks.Where(l => spaces.ContainsKey(l.WarehouseId)).ToList();

        if (links.Count == 0)
            throw DomainException.Conflict("pickup_point_unreachable", "У ПВЗ нет ни одной привязки к складу.");

        var routes = input.Routes
            .Where(r => spaces.ContainsKey(r.FromWarehouseId) && spaces.ContainsKey(r.ToWarehouseId))
            .ToList();
        var routeMinutes = routes.ToDictionary(r => (r.FromWarehouseId, r.ToWarehouseId), r => r.Minutes);
        var linkMinutes = links.GroupBy(l => l.WarehouseId).ToDictionary(g => g.Key, g => g.Min(l => l.Minutes));
        var outgoing = routes.GroupBy(r => r.FromWarehouseId).ToDictionary(g => g.Key, g => g.ToList());

        var (cost, previous) = ShortestFromPickup(linkMinutes, outgoing);

        var candidates = cost.Keys
            .Where(w => spaces[w].Free > 0)
            .OrderBy(w => cost[w])
            .ThenBy(w => w)
            .ToList();

        var requested = input.Items.Sum(i => (long)i.Quantity);
        var reachableFree = candidates.Sum(w => (long)spaces[w].Free);
        if (requested > reachableFree)
        {
            throw new DomainException(409, "return_no_capacity", "На достижимых складах не хватает места для возврата.")
            {
                Extensions = new Dictionary<string, object?>
                {
                    ["requested"] = requested,
                    ["reachableFree"] = reachableFree
                }
            };
        }

        var free = candidates.ToDictionary(w => w, w => spaces[w].Free);
        var allocations = new Dictionary<int, SortedDictionary<int, int>>();

        foreach (var item in input.Items.OrderBy(i => i.ProductId))
        {
            var remaining = item.Quantity;
            foreach (var w in candidates)
            {
                if (remaining == 0) break;
                var take = Math.Min(free[w], remaining);
                if (take <= 0) continue;

                if (!allocations.TryGetValue(w, out var perProduct))
                    allocations[w] = perProduct = new SortedDictionary<int, int>();
                perProduct[item.ProductId] = perProduct.GetValueOrDefault(item.ProductId) + take;
                free[w] -= take;
                remaining -= take;
            }
        }

        var products = input.Products.ToDictionary(p => p.Id);
        var pickup = new PlanNode("pickupPoint", input.PickupPointId, input.PickupPointName);
        var shipments = new List<PlanShipment>();

        foreach (var w in allocations.Keys.OrderBy(w => cost[w]).ThenBy(w => w))
        {
            var route = new List<int>();
            for (var current = w; current != PickupMarker; current = previous[current])
                route.Add(current);
            route.Reverse();

            var legs = new List<PlanLeg> { new(pickup, WarehouseNode(route[0]), linkMinutes[route[0]]) };
            for (var i = 1; i < route.Count; i++)
                legs.Add(new PlanLeg(WarehouseNode(route[i - 1]), WarehouseNode(route[i]), routeMinutes[(route[i - 1], route[i])]));

            var items = allocations[w]
                .Select(a => new PlanItem(a.Key, products[a.Key].Sku, products[a.Key].Name, a.Value))
                .ToList();

            shipments.Add(new PlanShipment(w, spaces[w].Name, legs.Sum(l => l.Minutes), route, legs, items));
        }

        return new DeliveryPlan(shipments.Max(s => s.TotalMinutes), shipments);

        PlanNode WarehouseNode(int id) => new("warehouse", id, spaces[id].Name);
    }

    /// <summary>Dijkstra от ПВЗ вперёд. Возвращает стоимость и предыдущий узел (PickupMarker для первого склада).</summary>
    private static (Dictionary<int, long> Cost, Dictionary<int, int> Previous) ShortestFromPickup(
        Dictionary<int, int> linkMinutes,
        Dictionary<int, List<RouteEdge>> outgoing)
    {
        var cost = new Dictionary<int, long>();
        var previous = new Dictionary<int, int>();
        var queue = new PriorityQueue<int, (long Cost, int Id)>();

        foreach (var (warehouse, minutes) in linkMinutes)
        {
            var c = minutes * Scale;
            cost[warehouse] = c;
            previous[warehouse] = PickupMarker;
            queue.Enqueue(warehouse, (c, warehouse));
        }

        while (queue.TryDequeue(out var u, out var priority))
        {
            if (priority.Cost > cost[u]) continue;
            if (!outgoing.TryGetValue(u, out var edges)) continue;

            foreach (var e in edges)
            {
                var v = e.ToWarehouseId;
                var candidate = cost[u] + e.Minutes * Scale + 1;

                var better = !cost.TryGetValue(v, out var current)
                             || candidate < current
                             || (candidate == current && u < previous[v]);
                if (!better) continue;

                cost[v] = candidate;
                previous[v] = u;
                queue.Enqueue(v, (candidate, v));
            }
        }

        return (cost, previous);
    }
}

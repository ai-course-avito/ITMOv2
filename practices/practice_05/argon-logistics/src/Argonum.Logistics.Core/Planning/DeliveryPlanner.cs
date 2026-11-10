namespace Argonum.Logistics.Core.Planning;

public sealed record WarehouseRef(int Id, string Name);
public sealed record ProductRef(int Id, string Sku, string Name);
public sealed record RouteEdge(int FromWarehouseId, int ToWarehouseId, int Minutes);
public sealed record PickupEdge(int WarehouseId, int Minutes);
public sealed record StockAvailability(int WarehouseId, int ProductId, int Available);
public sealed record RequestedItem(int ProductId, int Quantity);

public sealed record PlanningInput(
    int PickupPointId,
    string PickupPointName,
    IReadOnlyCollection<WarehouseRef> Warehouses,
    IReadOnlyCollection<RouteEdge> Routes,
    IReadOnlyCollection<PickupEdge> PickupLinks,
    IReadOnlyCollection<StockAvailability> Stock,
    IReadOnlyCollection<ProductRef> Products,
    IReadOnlyCollection<RequestedItem> Items);

/// <param name="Type">"warehouse" или "pickupPoint".</param>
public sealed record PlanNode(string Type, int Id, string Name);
public sealed record PlanLeg(PlanNode From, PlanNode To, int Minutes);
public sealed record PlanItem(int ProductId, string Sku, string Name, int Quantity);

public sealed record PlanShipment(
    int WarehouseId,
    string WarehouseName,
    int TotalMinutes,
    IReadOnlyList<int> Route,
    IReadOnlyList<PlanLeg> Legs,
    IReadOnlyList<PlanItem> Items);

public sealed record DeliveryPlan(int EstimatedMinutes, IReadOnlyList<PlanShipment> Shipments);

public sealed record Shortage(int ProductId, int Requested, int ReachableAvailable, int UnreachableAvailable);

/// <summary>
/// Чистая логика планирования (без БД и HTTP).
/// Кратчайшие маршруты считаются одним Dijkstra по обратному графу от ПВЗ;
/// товары берутся со складов от ближайшего к дальнему.
/// </summary>
public static class DeliveryPlanner
{
    // Стоимость маршрута кодируется как минуты * Scale + число пересадок,
    // так сравнение long даёт порядок (минуты, пересадки).
    private const long Scale = 1_000_000;
    private const int PickupMarker = -1;

    public static DeliveryPlan Build(PlanningInput input)
    {
        var names = input.Warehouses.ToDictionary(w => w.Id, w => w.Name);
        var links = input.PickupLinks.Where(l => names.ContainsKey(l.WarehouseId)).ToList();

        if (links.Count == 0)
            throw DomainException.Conflict("pickup_point_unreachable", "У ПВЗ нет ни одной привязки к складу.");

        var routes = input.Routes
            .Where(r => names.ContainsKey(r.FromWarehouseId) && names.ContainsKey(r.ToWarehouseId))
            .ToList();
        var routeMinutes = routes.ToDictionary(r => (r.FromWarehouseId, r.ToWarehouseId), r => r.Minutes);
        var linkMinutes = links.ToDictionary(l => l.WarehouseId, l => l.Minutes);
        var incoming = routes.GroupBy(r => r.ToWarehouseId).ToDictionary(g => g.Key, g => g.ToList());

        var (cost, next) = ShortestToPickup(links, incoming);

        var reachable = cost.Keys
            .OrderBy(w => cost[w] / Scale)
            .ThenBy(w => w)
            .ToList();

        var available = new Dictionary<(int Warehouse, int Product), int>();
        foreach (var s in input.Stock.Where(s => s.Available > 0))
        {
            var key = (s.WarehouseId, s.ProductId);
            available[key] = available.GetValueOrDefault(key) + s.Available;
        }

        var allocations = new Dictionary<int, SortedDictionary<int, int>>();
        var shortages = new List<Shortage>();

        foreach (var item in input.Items.OrderBy(i => i.ProductId))
        {
            var remaining = item.Quantity;
            var reachableTotal = 0;

            foreach (var w in reachable)
            {
                var have = available.GetValueOrDefault((w, item.ProductId));
                reachableTotal += have;
                var take = Math.Min(have, remaining);
                if (take <= 0) continue;

                if (!allocations.TryGetValue(w, out var perProduct))
                    allocations[w] = perProduct = new SortedDictionary<int, int>();
                perProduct[item.ProductId] = take;
                remaining -= take;
            }

            if (remaining > 0)
            {
                var unreachableTotal = available
                    .Where(a => a.Key.Product == item.ProductId && !cost.ContainsKey(a.Key.Warehouse))
                    .Sum(a => a.Value);
                shortages.Add(new Shortage(item.ProductId, item.Quantity, reachableTotal, unreachableTotal));
            }
        }

        if (shortages.Count > 0)
        {
            throw new DomainException(409, "insufficient_stock", "Недостаточно товара на достижимых складах.")
            {
                Extensions = new Dictionary<string, object?> { ["shortages"] = shortages }
            };
        }

        var products = input.Products.ToDictionary(p => p.Id);
        var pickup = new PlanNode("pickupPoint", input.PickupPointId, input.PickupPointName);
        var shipments = new List<PlanShipment>();

        foreach (var w in allocations.Keys.OrderBy(w => cost[w] / Scale).ThenBy(w => w))
        {
            var route = new List<int> { w };
            var legs = new List<PlanLeg>();
            var current = w;
            while (next[current] != PickupMarker)
            {
                var n = next[current];
                legs.Add(new PlanLeg(WarehouseNode(current), WarehouseNode(n), routeMinutes[(current, n)]));
                route.Add(n);
                current = n;
            }
            legs.Add(new PlanLeg(WarehouseNode(current), pickup, linkMinutes[current]));

            var items = allocations[w]
                .Select(a => new PlanItem(a.Key, products[a.Key].Sku, products[a.Key].Name, a.Value))
                .ToList();

            shipments.Add(new PlanShipment(w, names[w], legs.Sum(l => l.Minutes), route, legs, items));
        }

        return new DeliveryPlan(shipments.Max(s => s.TotalMinutes), shipments);

        PlanNode WarehouseNode(int id) => new("warehouse", id, names[id]);
    }

    /// <summary>
    /// Dijkstra от ПВЗ по обратным рёбрам. Возвращает стоимость и следующий узел
    /// (PickupMarker, если следующий шаг это ПВЗ) для каждого достижимого склада.
    /// </summary>
    private static (Dictionary<int, long> Cost, Dictionary<int, int> Next) ShortestToPickup(
        List<PickupEdge> links,
        Dictionary<int, List<RouteEdge>> incoming)
    {
        var cost = new Dictionary<int, long>();
        var next = new Dictionary<int, int>();
        var queue = new PriorityQueue<int, (long Cost, int Id)>();

        foreach (var l in links)
        {
            var c = l.Minutes * Scale;
            if (cost.TryGetValue(l.WarehouseId, out var existing) && existing <= c) continue;
            cost[l.WarehouseId] = c;
            next[l.WarehouseId] = PickupMarker;
            queue.Enqueue(l.WarehouseId, (c, l.WarehouseId));
        }

        while (queue.TryDequeue(out var u, out var priority))
        {
            if (priority.Cost > cost[u]) continue;
            if (!incoming.TryGetValue(u, out var edges)) continue;

            foreach (var e in edges)
            {
                var v = e.FromWarehouseId;
                var candidate = cost[u] + e.Minutes * Scale + 1;

                var better = !cost.TryGetValue(v, out var current)
                             || candidate < current
                             || (candidate == current && u < next[v]);
                if (!better) continue;

                cost[v] = candidate;
                next[v] = u;
                queue.Enqueue(v, (candidate, v));
            }
        }

        return (cost, next);
    }
}

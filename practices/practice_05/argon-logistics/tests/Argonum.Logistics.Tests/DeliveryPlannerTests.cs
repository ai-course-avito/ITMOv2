using Argonum.Logistics.Core;
using Argonum.Logistics.Core.Planning;

namespace Argonum.Logistics.Tests;

public class DeliveryPlannerTests
{
    private const int A = 1, B = 2, C = 3;
    private const int Milk = 10, Bread = 11;

    private static PlanningInput Input(
        RouteEdge[] routes,
        PickupEdge[] links,
        StockAvailability[] stock,
        RequestedItem[] items) =>
        new(
            PickupPointId: 100,
            PickupPointName: "ПВЗ-1",
            Warehouses: [new(A, "A"), new(B, "B"), new(C, "C")],
            Routes: routes,
            PickupLinks: links,
            Stock: stock,
            Products: [new(Milk, "MILK", "Молоко"), new(Bread, "BREAD", "Хлеб")],
            Items: items);

    private static DomainException Fails(PlanningInput input) =>
        Assert.Throws<DomainException>(() => DeliveryPlanner.Build(input));

    [Fact]
    public void Direct_link_gives_single_leg()
    {
        var plan = DeliveryPlanner.Build(Input([], [new(A, 25)], [new(A, Milk, 5)], [new(Milk, 2)]));

        var shipment = Assert.Single(plan.Shipments);
        Assert.Equal([A], shipment.Route);
        var leg = Assert.Single(shipment.Legs);
        Assert.Equal("pickupPoint", leg.To.Type);
        Assert.Equal(25, leg.Minutes);
        Assert.Equal(25, plan.EstimatedMinutes);
        Assert.Equal(2, shipment.Items.Single().Quantity);
    }

    [Fact]
    public void Detour_is_used_when_shorter_than_direct_link()
    {
        var plan = DeliveryPlanner.Build(Input(
            routes: [new(A, B, 20)],
            links: [new(A, 100), new(B, 30)],
            stock: [new(A, Milk, 1)],
            items: [new(Milk, 1)]));

        var shipment = Assert.Single(plan.Shipments);
        Assert.Equal([A, B], shipment.Route);
        Assert.Equal(50, shipment.TotalMinutes);
        Assert.Equal(2, shipment.Legs.Count);
    }

    [Fact]
    public void Fewer_transfers_win_on_equal_time()
    {
        var plan = DeliveryPlanner.Build(Input(
            routes: [new(A, B, 25)],
            links: [new(A, 50), new(B, 25)],
            stock: [new(A, Milk, 1)],
            items: [new(Milk, 1)]));

        Assert.Equal([A], plan.Shipments.Single().Route);
    }

    [Fact]
    public void Routes_are_directed()
    {
        // B -> A есть, A -> B нет. ПВЗ привязан к A.
        var routes = new RouteEdge[] { new(B, A, 10) };
        var links = new PickupEdge[] { new(A, 5) };

        var fromB = DeliveryPlanner.Build(Input(routes, links, [new(B, Milk, 1)], [new(Milk, 1)]));
        Assert.Equal([B, A], fromB.Shipments.Single().Route);
        Assert.Equal(15, fromB.EstimatedMinutes);

        // Обратная ситуация: путь только A -> B, а ПВЗ привязан к A, значит B недостижим.
        var ex = Fails(Input([new(A, B, 10)], links, [new(B, Milk, 4)], [new(Milk, 1)]));
        Assert.Equal("insufficient_stock", ex.Code);
        var shortage = Assert.IsType<List<Shortage>>(ex.Extensions!["shortages"]);
        Assert.Equal(0, shortage.Single().ReachableAvailable);
        Assert.Equal(4, shortage.Single().UnreachableAvailable);
    }

    [Fact]
    public void Item_is_split_between_nearest_warehouses_first()
    {
        var plan = DeliveryPlanner.Build(Input(
            routes: [],
            links: [new(A, 30), new(B, 80)],
            stock: [new(A, Milk, 5), new(B, Milk, 10)],
            items: [new(Milk, 8)]));

        Assert.Equal(2, plan.Shipments.Count);
        Assert.Equal(A, plan.Shipments[0].WarehouseId);
        Assert.Equal(5, plan.Shipments[0].Items.Single().Quantity);
        Assert.Equal(B, plan.Shipments[1].WarehouseId);
        Assert.Equal(3, plan.Shipments[1].Items.Single().Quantity);
        Assert.Equal(80, plan.EstimatedMinutes);
    }

    [Fact]
    public void Reserved_stock_is_not_planned()
    {
        // Available уже учитывает резерв: 5 на складе, 4 в резерве.
        var plan = DeliveryPlanner.Build(Input(
            routes: [],
            links: [new(A, 10), new(B, 20)],
            stock: [new(A, Milk, 1), new(B, Milk, 5)],
            items: [new(Milk, 3)]));

        Assert.Equal(1, plan.Shipments.Single(s => s.WarehouseId == A).Items.Single().Quantity);
        Assert.Equal(2, plan.Shipments.Single(s => s.WarehouseId == B).Items.Single().Quantity);
    }

    [Fact]
    public void Shipment_groups_several_products_from_one_warehouse()
    {
        var plan = DeliveryPlanner.Build(Input(
            routes: [],
            links: [new(A, 10)],
            stock: [new(A, Milk, 3), new(A, Bread, 3)],
            items: [new(Bread, 1), new(Milk, 2)]));

        var shipment = Assert.Single(plan.Shipments);
        Assert.Equal([Milk, Bread], shipment.Items.Select(i => i.ProductId));
    }

    [Fact]
    public void Shortage_lists_only_missing_products()
    {
        var ex = Fails(Input(
            routes: [],
            links: [new(A, 10)],
            stock: [new(A, Milk, 5), new(A, Bread, 1)],
            items: [new(Milk, 2), new(Bread, 3)]));

        Assert.Equal("insufficient_stock", ex.Code);
        var shortage = Assert.Single(Assert.IsType<List<Shortage>>(ex.Extensions!["shortages"]));
        Assert.Equal(Bread, shortage.ProductId);
        Assert.Equal(3, shortage.Requested);
        Assert.Equal(1, shortage.ReachableAvailable);
    }

    [Fact]
    public void Pickup_point_without_links_is_unreachable()
    {
        var ex = Fails(Input([new(A, B, 5)], [], [new(A, Milk, 5)], [new(Milk, 1)]));
        Assert.Equal("pickup_point_unreachable", ex.Code);
    }

    [Fact]
    public void Cycles_in_graph_do_not_break_planning()
    {
        var plan = DeliveryPlanner.Build(Input(
            routes: [new(A, B, 5), new(B, A, 5), new(B, C, 5), new(C, B, 5)],
            links: [new(C, 10)],
            stock: [new(A, Milk, 1)],
            items: [new(Milk, 1)]));

        var shipment = Assert.Single(plan.Shipments);
        Assert.Equal([A, B, C], shipment.Route);
        Assert.Equal(20, shipment.TotalMinutes);
    }
}

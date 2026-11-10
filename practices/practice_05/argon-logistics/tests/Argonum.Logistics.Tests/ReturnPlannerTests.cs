using Argonum.Logistics.Core;
using Argonum.Logistics.Core.Planning;

namespace Argonum.Logistics.Tests;

public class ReturnPlannerTests
{
    private static readonly ProductRef Milk = new(1, "MILK", "Молоко");
    private static readonly ProductRef Bread = new(2, "BREAD", "Хлеб");

    private static ReturnPlanningInput Input(
        (int Id, int Free)[] warehouses,
        (int From, int To, int Minutes)[] routes,
        (int Warehouse, int Minutes)[] links,
        params (ProductRef Product, int Quantity)[] items) => new(
        PickupPointId: 100,
        PickupPointName: "ПВЗ",
        Warehouses: warehouses.Select(w => new WarehouseSpace(w.Id, $"W{w.Id}", w.Free)).ToList(),
        Routes: routes.Select(r => new RouteEdge(r.From, r.To, r.Minutes)).ToList(),
        PickupLinks: links.Select(l => new PickupEdge(l.Warehouse, l.Minutes)).ToList(),
        Products: [Milk, Bread],
        Items: items.Select(i => new RequestedItem(i.Product.Id, i.Quantity)).ToList());

    [Fact]
    public void Nearest_warehouse_with_space_takes_everything()
    {
        var plan = ReturnPlanner.Build(Input(
            [(1, 100), (2, 100)], [], [(1, 15), (2, 40)], (Milk, 5)));

        var shipment = Assert.Single(plan.Shipments);
        Assert.Equal(1, shipment.WarehouseId);
        Assert.Equal(15, shipment.TotalMinutes);
        Assert.Equal(15, plan.EstimatedMinutes);
        Assert.Equal([1], shipment.Route);
        var leg = Assert.Single(shipment.Legs);
        Assert.Equal("pickupPoint", leg.From.Type);
        Assert.Equal(100, leg.From.Id);
        Assert.Equal("warehouse", leg.To.Type);
    }

    [Fact]
    public void Full_nearest_warehouse_is_transit_for_a_farther_one()
    {
        // Прямая привязка к 2 стоит 80, через заполненный 1 выходит 30 + 20 = 50.
        var plan = ReturnPlanner.Build(Input(
            [(1, 0), (2, 100)], [(1, 2, 20)], [(1, 30), (2, 80)], (Milk, 5)));

        var shipment = Assert.Single(plan.Shipments);
        Assert.Equal(2, shipment.WarehouseId);
        Assert.Equal([1, 2], shipment.Route);
        Assert.Equal(50, shipment.TotalMinutes);
        Assert.Equal([30, 20], shipment.Legs.Select(l => l.Minutes));
        Assert.Equal("pickupPoint", shipment.Legs[0].From.Type);
        Assert.Equal(1, shipment.Legs[1].From.Id);
    }

    [Fact]
    public void Overflow_goes_to_the_next_nearest_warehouse()
    {
        var plan = ReturnPlanner.Build(Input(
            [(1, 4), (2, 20)], [], [(1, 10), (2, 30)], (Milk, 10)));

        Assert.Equal(2, plan.Shipments.Count);
        Assert.Equal((1, 4), (plan.Shipments[0].WarehouseId, plan.Shipments[0].Items.Sum(i => i.Quantity)));
        Assert.Equal((2, 6), (plan.Shipments[1].WarehouseId, plan.Shipments[1].Items.Sum(i => i.Quantity)));
        Assert.Equal(30, plan.EstimatedMinutes);
    }

    [Fact]
    public void Free_space_is_shared_between_products()
    {
        // Места у ближайшего 6: молоко (id 1) занимает 4, хлебу остаётся 2, остальные 3 уезжают дальше.
        var plan = ReturnPlanner.Build(Input(
            [(1, 6), (2, 10)], [], [(1, 10), (2, 30)], (Milk, 4), (Bread, 5)));

        var near = plan.Shipments.Single(s => s.WarehouseId == 1);
        var far = plan.Shipments.Single(s => s.WarehouseId == 2);
        Assert.Equal(6, near.Items.Sum(i => i.Quantity));
        Assert.Equal(4, near.Items.Single(i => i.ProductId == 1).Quantity);
        Assert.Equal(2, near.Items.Single(i => i.ProductId == 2).Quantity);
        Assert.Equal([(2, 3)], far.Items.Select(i => (i.ProductId, i.Quantity)));
    }

    [Fact]
    public void Unreachable_warehouse_is_never_used()
    {
        // Склад 3 со свободным местом недостижим: к нему нет ни привязки, ни пути.
        var plan = ReturnPlanner.Build(Input(
            [(1, 100), (3, 1000)], [], [(1, 10)], (Milk, 5)));

        Assert.Equal([1], plan.Shipments.Select(s => s.WarehouseId));
    }

    [Fact]
    public void Routes_are_directed_so_reverse_edge_does_not_help()
    {
        var ex = Assert.Throws<DomainException>(() => ReturnPlanner.Build(Input(
            [(1, 0), (2, 100)], [(2, 1, 5)], [(1, 10)], (Milk, 5))));

        Assert.Equal("return_no_capacity", ex.Code);
    }

    [Fact]
    public void Not_enough_space_reports_requested_and_free()
    {
        var ex = Assert.Throws<DomainException>(() => ReturnPlanner.Build(Input(
            [(1, 3), (2, 4)], [], [(1, 10), (2, 20)], (Milk, 10))));

        Assert.Equal(409, ex.StatusCode);
        Assert.Equal("return_no_capacity", ex.Code);
        Assert.Equal(10L, ex.Extensions!["requested"]);
        Assert.Equal(7L, ex.Extensions["reachableFree"]);
    }

    [Fact]
    public void Pickup_without_links_is_unreachable()
    {
        var ex = Assert.Throws<DomainException>(() => ReturnPlanner.Build(Input(
            [(1, 100)], [], [], (Milk, 1))));

        Assert.Equal("pickup_point_unreachable", ex.Code);
    }

    [Fact]
    public void Equal_cost_ties_are_broken_by_warehouse_id()
    {
        var plan = ReturnPlanner.Build(Input(
            [(7, 100), (3, 100)], [], [(7, 20), (3, 20)], (Milk, 1)));

        Assert.Equal(3, Assert.Single(plan.Shipments).WarehouseId);
    }

    [Fact]
    public void Fewer_transfers_win_at_equal_minutes()
    {
        // До 2 напрямую 30 минут, либо 10 + 20 через склад 1: минуты равны, пересадок меньше у прямого.
        var plan = ReturnPlanner.Build(Input(
            [(1, 0), (2, 100)], [(1, 2, 20)], [(1, 10), (2, 30)], (Milk, 1)));

        var shipment = Assert.Single(plan.Shipments);
        Assert.Equal([2], shipment.Route);
        Assert.Equal(30, shipment.TotalMinutes);
    }

    [Fact]
    public void Plan_is_deterministic()
    {
        var input = Input([(1, 3), (2, 3), (3, 3)], [(1, 2, 5), (2, 3, 5)], [(1, 10)], (Milk, 4), (Bread, 3));

        var first = ReturnPlanner.Build(input);
        var second = ReturnPlanner.Build(input);

        Assert.Equal(
            first.Shipments.Select(s => (s.WarehouseId, s.TotalMinutes, s.Items.Sum(i => i.Quantity))),
            second.Shipments.Select(s => (s.WarehouseId, s.TotalMinutes, s.Items.Sum(i => i.Quantity))));
    }
}

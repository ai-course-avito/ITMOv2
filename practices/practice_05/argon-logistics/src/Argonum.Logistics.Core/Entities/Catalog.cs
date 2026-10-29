namespace Argonum.Logistics.Core.Entities;

public class Product
{
    public int Id { get; set; }
    public string Sku { get; set; } = "";
    public string SkuKey { get; set; } = "";
    public string Name { get; set; } = "";
    public string? Description { get; set; }
}

public class Warehouse
{
    public int Id { get; set; }
    public string Name { get; set; } = "";
    public string NameKey { get; set; } = "";
    public string Address { get; set; } = "";

    /// <summary>Положение на условной карте (не географические координаты).</summary>
    public double MapX { get; set; }
    public double MapY { get; set; }

    public const int DefaultCapacity = 100_000;
    public const int MaxCapacity = 10_000_000;

    /// <summary>Максимум суммы Quantity по всем строкам остатка склада.</summary>
    public int Capacity { get; set; } = DefaultCapacity;
}

/// <summary>Остаток товара на складе. Свободно к заказу = Quantity - Reserved.</summary>
public class StockItem
{
    public int WarehouseId { get; set; }
    public int ProductId { get; set; }
    public int Quantity { get; set; }
    public int Reserved { get; set; }

    public Warehouse? Warehouse { get; set; }
    public Product? Product { get; set; }

    public int Available => Quantity - Reserved;
}

public class PickupPoint
{
    public int Id { get; set; }
    public string Name { get; set; } = "";
    public string Address { get; set; } = "";
    public bool IsActive { get; set; } = true;
    public double MapX { get; set; }
    public double MapY { get; set; }
}

/// <summary>Направленный путь склад → склад.</summary>
public class WarehouseRoute
{
    public int Id { get; set; }
    public int FromWarehouseId { get; set; }
    public int ToWarehouseId { get; set; }
    public int Minutes { get; set; }
}

/// <summary>Направленный путь склад → ПВЗ.</summary>
public class PickupPointLink
{
    public int PickupPointId { get; set; }
    public int WarehouseId { get; set; }
    public int Minutes { get; set; }

    public Warehouse? Warehouse { get; set; }
}

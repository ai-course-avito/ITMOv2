using Argonum.Logistics.Core.Entities;
using Microsoft.EntityFrameworkCore;

namespace Argonum.Logistics.Api.Data;

public class ArgonDbContext(DbContextOptions<ArgonDbContext> options) : DbContext(options)
{
    public DbSet<Product> Products => Set<Product>();
    public DbSet<Warehouse> Warehouses => Set<Warehouse>();
    public DbSet<StockItem> Stock => Set<StockItem>();
    public DbSet<PickupPoint> PickupPoints => Set<PickupPoint>();
    public DbSet<WarehouseRoute> Routes => Set<WarehouseRoute>();
    public DbSet<PickupPointLink> PickupLinks => Set<PickupPointLink>();
    public DbSet<User> Users => Set<User>();
    public DbSet<Order> Orders => Set<Order>();
    public DbSet<Shipment> Shipments => Set<Shipment>();
    public DbSet<ReturnShipment> ReturnShipments => Set<ReturnShipment>();

    protected override void OnModelCreating(ModelBuilder b)
    {
        // Уникальность без учёта регистра держится на *Key (см. TextKey), а не на коллации.
        b.Entity<Product>(e =>
        {
            e.Property(p => p.Sku).HasMaxLength(64);
            e.Property(p => p.SkuKey).HasMaxLength(64);
            e.HasIndex(p => p.SkuKey).IsUnique();
            e.Property(p => p.Name).HasMaxLength(200);
            e.Property(p => p.Description).HasMaxLength(1000);
        });

        b.Entity<Warehouse>(e =>
        {
            e.Property(w => w.Name).HasMaxLength(200);
            e.Property(w => w.NameKey).HasMaxLength(200);
            e.HasIndex(w => w.NameKey).IsUnique();
            e.Property(w => w.Address).HasMaxLength(300);
        });

        b.Entity<StockItem>(e =>
        {
            e.HasKey(s => new { s.WarehouseId, s.ProductId });
            e.Ignore(s => s.Available);
            e.HasOne(s => s.Warehouse).WithMany().HasForeignKey(s => s.WarehouseId).OnDelete(DeleteBehavior.Cascade);
            e.HasOne(s => s.Product).WithMany().HasForeignKey(s => s.ProductId).OnDelete(DeleteBehavior.Cascade);
        });

        b.Entity<PickupPoint>(e =>
        {
            e.Property(p => p.Name).HasMaxLength(200);
            e.Property(p => p.Address).HasMaxLength(300);
        });

        b.Entity<WarehouseRoute>(e =>
        {
            e.HasIndex(r => new { r.FromWarehouseId, r.ToWarehouseId }).IsUnique();
            e.HasOne<Warehouse>().WithMany().HasForeignKey(r => r.FromWarehouseId).OnDelete(DeleteBehavior.Cascade);
            e.HasOne<Warehouse>().WithMany().HasForeignKey(r => r.ToWarehouseId).OnDelete(DeleteBehavior.Cascade);
        });

        b.Entity<PickupPointLink>(e =>
        {
            e.HasKey(l => new { l.PickupPointId, l.WarehouseId });
            e.HasOne<PickupPoint>().WithMany().HasForeignKey(l => l.PickupPointId).OnDelete(DeleteBehavior.Cascade);
            e.HasOne(l => l.Warehouse).WithMany().HasForeignKey(l => l.WarehouseId).OnDelete(DeleteBehavior.Cascade);
        });

        b.Entity<User>(e =>
        {
            e.Property(u => u.Name).HasMaxLength(200);
            e.Property(u => u.Email).HasMaxLength(254);
            e.Property(u => u.EmailKey).HasMaxLength(254);
            e.HasIndex(u => u.EmailKey).IsUnique();
        });

        // У заказа и отправок нет внешних ключей на каталог, склады и ПВЗ: это снимки истории.
        b.Entity<Order>(e =>
        {
            e.Property(o => o.Status).HasConversion<string>().HasMaxLength(20);
            e.HasOne<User>().WithMany().HasForeignKey(o => o.UserId).OnDelete(DeleteBehavior.Restrict);
            e.HasMany(o => o.Items).WithOne().HasForeignKey(i => i.OrderId).OnDelete(DeleteBehavior.Cascade);
            e.HasMany(o => o.Shipments).WithOne().HasForeignKey(s => s.OrderId).OnDelete(DeleteBehavior.Cascade);
            e.HasMany(o => o.Returns).WithOne().HasForeignKey(r => r.OrderId).OnDelete(DeleteBehavior.Cascade);
            e.HasIndex(o => o.UserId);
        });

        b.Entity<ReturnShipment>(e =>
        {
            e.Property(r => r.Status).HasConversion<string>().HasMaxLength(20);
            e.HasMany(r => r.Items).WithOne().HasForeignKey(i => i.ReturnShipmentId).OnDelete(DeleteBehavior.Cascade);
            e.HasIndex(r => r.WarehouseId);
        });

        b.Entity<Shipment>(e =>
        {
            e.Property(s => s.Status).HasConversion<string>().HasMaxLength(20);
            e.HasMany(s => s.Items).WithOne().HasForeignKey(i => i.ShipmentId).OnDelete(DeleteBehavior.Cascade);
            e.HasIndex(s => s.WarehouseId);
        });
    }
}

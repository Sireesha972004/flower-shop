using FlowerShop.AIAgent.Domain.Entities;
using Microsoft.EntityFrameworkCore;

namespace FlowerShop.AIAgent.Infrastructure.Persistence
{
    public class FlowerShopAIAgentDbContext : DbContext
    {
        public FlowerShopAIAgentDbContext(DbContextOptions<FlowerShopAIAgentDbContext> options)
            : base(options)
        {
        }

        public DbSet<Customer> Customers => Set<Customer>();
        public DbSet<Address> Addresses => Set<Address>();
        public DbSet<Product> Products => Set<Product>();
        public DbSet<CartItem> CartItems => Set<CartItem>();
        public DbSet<Order> Orders => Set<Order>();
        public DbSet<OrderItem> OrderItems => Set<OrderItem>();

        protected override void OnModelCreating(ModelBuilder builder)
        {
            base.OnModelCreating(builder);

            builder.Entity<Customer>(entity =>
            {
                entity.HasMany(c => c.Addresses).WithOne(a => a.Customer).HasForeignKey(a => a.CustomerId);
                entity.HasMany(c => c.Orders).WithOne(o => o.Customer).HasForeignKey(o => o.CustomerId);
                entity.HasMany(c => c.CartItems).WithOne(ci => ci.Customer).HasForeignKey(ci => ci.CustomerId);
                entity.Property(c => c.Email).IsRequired().HasMaxLength(256);
            });

            builder.Entity<Address>(entity =>
            {
                entity.Property(a => a.Label).HasMaxLength(60);
                entity.Property(a => a.Recipient).HasMaxLength(100);
                entity.Property(a => a.Line1).HasMaxLength(200);
                entity.Property(a => a.City).HasMaxLength(100);
                entity.Property(a => a.State).HasMaxLength(100);
                entity.Property(a => a.PostalCode).HasMaxLength(20);
                entity.Property(a => a.Country).HasMaxLength(100);
                entity.Property(a => a.Phone).HasMaxLength(40);
            });

            builder.Entity<Product>(entity =>
            {
                entity.Property(p => p.Name).IsRequired().HasMaxLength(200);
                entity.Property(p => p.Category).HasMaxLength(100);
                entity.Property(p => p.Description).HasMaxLength(2000);
                entity.Property(p => p.ImageUrl).HasMaxLength(1000);
            });

            builder.Entity<CartItem>(entity =>
            {
                entity.HasOne(ci => ci.Product).WithMany(p => p.CartItems).HasForeignKey(ci => ci.ProductId);
            });

            builder.Entity<Order>(entity =>
            {
                entity.Property(o => o.OrderNumber).IsRequired().HasMaxLength(32);
                entity.Property(o => o.Status).IsRequired().HasMaxLength(50);
                entity.HasMany(o => o.OrderItems).WithOne(oi => oi.Order).HasForeignKey(oi => oi.OrderId);
            });

            builder.Entity<OrderItem>(entity =>
            {
                entity.Property(oi => oi.ProductName).IsRequired().HasMaxLength(200);
            });
        }
    }
}
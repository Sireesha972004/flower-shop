using System;

namespace FlowerShop.AIAgent.Domain.Entities
{
    public class Product
    {
        public Guid Id { get; set; } = Guid.NewGuid();
        public string Sku { get; set; } = string.Empty;
        public string Name { get; set; } = string.Empty;
        public string Category { get; set; } = string.Empty;
        public string Description { get; set; } = string.Empty;
        public decimal Price { get; set; }
        public string ImageUrl { get; set; } = string.Empty;
        public int StockQuantity { get; set; }
        public bool IsGiftItem { get; set; }
        public bool IsActive { get; set; } = true;
        public string? OccasionTags { get; set; }
        public ICollection<CartItem> CartItems { get; set; } = new List<CartItem>();
        public ICollection<OrderItem> OrderItems { get; set; } = new List<OrderItem>();
    }
}
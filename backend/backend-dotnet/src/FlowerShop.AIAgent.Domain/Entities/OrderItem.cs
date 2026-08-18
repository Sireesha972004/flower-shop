using System;

namespace FlowerShop.AIAgent.Domain.Entities
{
    public class OrderItem
    {
        public Guid Id { get; set; } = Guid.NewGuid();
        public Guid OrderId { get; set; }
        public Order? Order { get; set; }
        public Guid ProductId { get; set; }
        public Product? Product { get; set; }
        public int Quantity { get; set; }
        public decimal Price { get; set; }
        public string ProductName { get; set; } = string.Empty;
    }
}
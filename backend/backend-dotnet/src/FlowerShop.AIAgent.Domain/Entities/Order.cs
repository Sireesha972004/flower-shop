using System;
using System.Collections.Generic;

namespace FlowerShop.AIAgent.Domain.Entities
{
    public class Order
    {
        public Guid Id { get; set; } = Guid.NewGuid();
        public Guid CustomerId { get; set; }
        public Customer? Customer { get; set; }
        public string OrderNumber { get; set; } = string.Empty;
        public decimal Total { get; set; }
        public string Status { get; set; } = "pending";
        public string DeliveryAddress { get; set; } = string.Empty;
        public DateTime? DeliveryDate { get; set; }
        public string? PaymentMethod { get; set; }
        public DateTime CreatedAt { get; set; } = DateTime.UtcNow;
        public ICollection<OrderItem> OrderItems { get; set; } = new List<OrderItem>();
    }
}
using System;

namespace FlowerShop.AIAgent.Domain.Entities
{
    public class CartItem
    {
        public Guid Id { get; set; } = Guid.NewGuid();
        public Guid CustomerId { get; set; }
        public Customer? Customer { get; set; }
        public Guid ProductId { get; set; }
        public Product? Product { get; set; }
        public int Quantity { get; set; }
    }
}
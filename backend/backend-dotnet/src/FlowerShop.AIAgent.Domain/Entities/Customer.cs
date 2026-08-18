using System;
using System.Collections.Generic;

namespace FlowerShop.AIAgent.Domain.Entities
{
    public class Customer
    {
        public Guid Id { get; set; } = Guid.NewGuid();
        public string Name { get; set; } = string.Empty;
        public string Email { get; set; } = string.Empty;
        public string? FavoriteFlowers { get; set; }
        public string? FavoriteOccasion { get; set; }
        public string? PreferredPaymentMethod { get; set; }
        public Guid? PreferredAddressId { get; set; }
        public Address? PreferredAddress { get; set; }
        public ICollection<Address> Addresses { get; set; } = new List<Address>();
        public ICollection<Order> Orders { get; set; } = new List<Order>();
        public ICollection<CartItem> CartItems { get; set; } = new List<CartItem>();
    }
}
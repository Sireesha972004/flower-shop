using System;

namespace FlowerShop.AIAgent.Domain.Entities
{
    public class Address
    {
        public Guid Id { get; set; } = Guid.NewGuid();
        public Guid CustomerId { get; set; }
        public Customer? Customer { get; set; }
        public string Label { get; set; } = string.Empty;
        public string Recipient { get; set; } = string.Empty;
        public string Line1 { get; set; } = string.Empty;
        public string? Line2 { get; set; }
        public string City { get; set; } = string.Empty;
        public string State { get; set; } = string.Empty;
        public string PostalCode { get; set; } = string.Empty;
        public string Country { get; set; } = string.Empty;
        public string Phone { get; set; } = string.Empty;
    }
}
using System;
using System.Collections.Generic;

namespace FlowerShop.AIAgent.Application.DTOs
{
    public record OrderItemDto(Guid ProductId, string ProductName, decimal Price, int Quantity);

    public record OrderDto(
        Guid Id,
        string OrderNumber,
        decimal Total,
        string Status,
        string DeliveryAddress,
        DateTime? DeliveryDate,
        string? PaymentMethod,
        DateTime CreatedAt,
        IReadOnlyCollection<OrderItemDto> Items
    );
}
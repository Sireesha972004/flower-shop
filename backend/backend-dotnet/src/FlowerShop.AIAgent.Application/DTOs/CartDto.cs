using System;
using System.Collections.Generic;

namespace FlowerShop.AIAgent.Application.DTOs
{
    public record CartItemDto(Guid ProductId, string ProductName, decimal Price, int Quantity, string ImageUrl);

    public record CartDto(IEnumerable<CartItemDto> Items, decimal Total);
}
using System;

namespace FlowerShop.AIAgent.Application.DTOs
{
    public record ProductDto(
        Guid Id,
        string Name,
        string Category,
        string Description,
        decimal Price,
        string ImageUrl,
        int StockQuantity,
        bool IsGiftItem,
        string? OccasionTags
    );
}
using System;

namespace FlowerShop.AIAgent.Application.DTOs
{
    public record CustomerDto(Guid Id, string Name, string Email, string? FavoriteFlowers, string? FavoriteOccasion, string? PreferredPaymentMethod);
}
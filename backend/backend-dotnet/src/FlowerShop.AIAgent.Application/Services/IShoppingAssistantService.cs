using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using FlowerShop.AIAgent.Application.DTOs;

namespace FlowerShop.AIAgent.Application.Services
{
    public interface IShoppingAssistantService
    {
        Task<IEnumerable<ProductDto>> SearchFlowersAsync(string occasion, decimal? budget, string? keywords, int count, CancellationToken cancellationToken);
        Task<IEnumerable<ProductDto>> RecommendFlowersAsync(string occasion, decimal budget, CancellationToken cancellationToken);
        Task<CartDto> ViewCartAsync(Guid customerId, CancellationToken cancellationToken);
        Task AddToCartAsync(Guid customerId, Guid productId, int quantity, CancellationToken cancellationToken);
        Task RemoveFromCartAsync(Guid customerId, Guid productId, CancellationToken cancellationToken);
        Task UpdateQuantityAsync(Guid customerId, Guid productId, int quantity, CancellationToken cancellationToken);
        Task<OrderDto> CreateOrderAsync(Guid customerId, string deliveryAddress, DateTime deliveryDate, string? paymentMethod, CancellationToken cancellationToken);
        Task<IEnumerable<OrderDto>> GetOrderHistoryAsync(Guid customerId, CancellationToken cancellationToken);
        Task<OrderDto?> TrackOrderAsync(Guid orderId, CancellationToken cancellationToken);
        Task CancelOrderAsync(Guid orderId, CancellationToken cancellationToken);
        Task<IEnumerable<ProductDto>> SearchGiftItemsAsync(CancellationToken cancellationToken);
        Task<IEnumerable<string>> GetDeliverySlotsAsync(DateTime requestDate, CancellationToken cancellationToken);
    }
}
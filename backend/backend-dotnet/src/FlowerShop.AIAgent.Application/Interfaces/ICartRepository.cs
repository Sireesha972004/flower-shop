using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using FlowerShop.AIAgent.Domain.Entities;

namespace FlowerShop.AIAgent.Application.Interfaces
{
    public interface ICartRepository
    {
        Task<IEnumerable<CartItem>> GetCartAsync(Guid customerId, CancellationToken cancellationToken);
        Task AddToCartAsync(CartItem item, CancellationToken cancellationToken);
        Task RemoveFromCartAsync(Guid customerId, Guid productId, CancellationToken cancellationToken);
        Task UpdateQuantityAsync(Guid customerId, Guid productId, int quantity, CancellationToken cancellationToken);
        Task ClearCartAsync(Guid customerId, CancellationToken cancellationToken);
    }
}
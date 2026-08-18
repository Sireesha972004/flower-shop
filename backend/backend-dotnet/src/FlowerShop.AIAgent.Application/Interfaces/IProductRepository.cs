using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using FlowerShop.AIAgent.Domain.Entities;

namespace FlowerShop.AIAgent.Application.Interfaces
{
    public interface IProductRepository
    {
        Task<Product?> GetByIdAsync(Guid id, CancellationToken cancellationToken);
        Task<IEnumerable<Product>> SearchAsync(string query, CancellationToken cancellationToken);
        Task<IEnumerable<Product>> GetRecommendedAsync(string occasion, decimal maxBudget, CancellationToken cancellationToken);
        Task<IEnumerable<Product>> GetGiftItemsAsync(CancellationToken cancellationToken);
        Task<bool> CheckInventoryAsync(Guid productId, int requestedQty, CancellationToken cancellationToken);
    }
}
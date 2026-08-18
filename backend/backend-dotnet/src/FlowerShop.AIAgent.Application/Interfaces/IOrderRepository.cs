using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using FlowerShop.AIAgent.Domain.Entities;

namespace FlowerShop.AIAgent.Application.Interfaces
{
    public interface IOrderRepository
    {
        Task<Order> CreateAsync(Order order, CancellationToken cancellationToken);
        Task<IEnumerable<Order>> GetOrdersAsync(Guid customerId, CancellationToken cancellationToken);
        Task<Order?> GetByIdAsync(Guid orderId, CancellationToken cancellationToken);
        Task CancelOrderAsync(Guid orderId, CancellationToken cancellationToken);
    }
}
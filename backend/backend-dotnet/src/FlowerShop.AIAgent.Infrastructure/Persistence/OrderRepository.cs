using FlowerShop.AIAgent.Application.Interfaces;
using FlowerShop.AIAgent.Domain.Entities;
using Microsoft.EntityFrameworkCore;

namespace FlowerShop.AIAgent.Infrastructure.Persistence
{
    public class OrderRepository : IOrderRepository
    {
        private readonly FlowerShopAIAgentDbContext _dbContext;

        public OrderRepository(FlowerShopAIAgentDbContext dbContext)
        {
            _dbContext = dbContext;
        }

        public async Task<Order> CreateAsync(Order order, CancellationToken cancellationToken)
        {
            await _dbContext.Orders.AddAsync(order, cancellationToken);
            await _dbContext.SaveChangesAsync(cancellationToken);
            return order;
        }

        public async Task<IEnumerable<Order>> GetOrdersAsync(Guid customerId, CancellationToken cancellationToken)
        {
            return await _dbContext.Orders
                .AsNoTracking()
                .Include(o => o.OrderItems)
                .Where(o => o.CustomerId == customerId)
                .OrderByDescending(o => o.CreatedAt)
                .ToListAsync(cancellationToken);
        }

        public async Task<Order?> GetByIdAsync(Guid orderId, CancellationToken cancellationToken)
        {
            return await _dbContext.Orders
                .AsNoTracking()
                .Include(o => o.OrderItems)
                .FirstOrDefaultAsync(o => o.Id == orderId, cancellationToken);
        }

        public async Task CancelOrderAsync(Guid orderId, CancellationToken cancellationToken)
        {
            var order = await _dbContext.Orders.FirstOrDefaultAsync(o => o.Id == orderId, cancellationToken);
            if (order is not null)
            {
                order.Status = "cancelled";
                _dbContext.Orders.Update(order);
                await _dbContext.SaveChangesAsync(cancellationToken);
            }
        }
    }
}
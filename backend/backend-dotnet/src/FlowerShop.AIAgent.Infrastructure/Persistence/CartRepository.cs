using FlowerShop.AIAgent.Application.Interfaces;
using FlowerShop.AIAgent.Domain.Entities;
using Microsoft.EntityFrameworkCore;

namespace FlowerShop.AIAgent.Infrastructure.Persistence
{
    public class CartRepository : ICartRepository
    {
        private readonly FlowerShopAIAgentDbContext _dbContext;

        public CartRepository(FlowerShopAIAgentDbContext dbContext)
        {
            _dbContext = dbContext;
        }

        public async Task<IEnumerable<CartItem>> GetCartAsync(Guid customerId, CancellationToken cancellationToken)
        {
            return await _dbContext.CartItems
                .AsNoTracking()
                .Include(ci => ci.Product)
                .Where(ci => ci.CustomerId == customerId)
                .ToListAsync(cancellationToken);
        }

        public async Task AddToCartAsync(CartItem item, CancellationToken cancellationToken)
        {
            var existing = await _dbContext.CartItems
                .FirstOrDefaultAsync(ci => ci.CustomerId == item.CustomerId && ci.ProductId == item.ProductId, cancellationToken);

            if (existing is not null)
            {
                existing.Quantity += item.Quantity;
                _dbContext.CartItems.Update(existing);
            }
            else
            {
                await _dbContext.CartItems.AddAsync(item, cancellationToken);
            }

            await _dbContext.SaveChangesAsync(cancellationToken);
        }

        public async Task RemoveFromCartAsync(Guid customerId, Guid productId, CancellationToken cancellationToken)
        {
            var existing = await _dbContext.CartItems
                .FirstOrDefaultAsync(ci => ci.CustomerId == customerId && ci.ProductId == productId, cancellationToken);

            if (existing is not null)
            {
                _dbContext.CartItems.Remove(existing);
                await _dbContext.SaveChangesAsync(cancellationToken);
            }
        }

        public async Task UpdateQuantityAsync(Guid customerId, Guid productId, int quantity, CancellationToken cancellationToken)
        {
            var existing = await _dbContext.CartItems
                .FirstOrDefaultAsync(ci => ci.CustomerId == customerId && ci.ProductId == productId, cancellationToken);

            if (existing is not null)
            {
                existing.Quantity = quantity;
                _dbContext.CartItems.Update(existing);
                await _dbContext.SaveChangesAsync(cancellationToken);
            }
        }

        public async Task ClearCartAsync(Guid customerId, CancellationToken cancellationToken)
        {
            var items = await _dbContext.CartItems.Where(ci => ci.CustomerId == customerId).ToListAsync(cancellationToken);
            _dbContext.CartItems.RemoveRange(items);
            await _dbContext.SaveChangesAsync(cancellationToken);
        }
    }
}
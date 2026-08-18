using FlowerShop.AIAgent.Application.Interfaces;
using FlowerShop.AIAgent.Domain.Entities;
using Microsoft.EntityFrameworkCore;

namespace FlowerShop.AIAgent.Infrastructure.Persistence
{
    public class ProductRepository : IProductRepository
    {
        private readonly FlowerShopAIAgentDbContext _dbContext;

        public ProductRepository(FlowerShopAIAgentDbContext dbContext)
        {
            _dbContext = dbContext;
        }

        public async Task<Product?> GetByIdAsync(Guid id, CancellationToken cancellationToken)
        {
            return await _dbContext.Products.FindAsync(new object[] { id }, cancellationToken);
        }

        public async Task<IEnumerable<Product>> SearchAsync(string query, CancellationToken cancellationToken)
        {
            return await _dbContext.Products
                .AsNoTracking()
                .Where(p => p.IsActive && (EF.Functions.ILike(p.Name, $"%{query}%") || EF.Functions.ILike(p.Description, $"%{query}%") || EF.Functions.ILike(p.Category, $"%{query}%")))
                .OrderBy(p => p.Name)
                .Take(20)
                .ToListAsync(cancellationToken);
        }

        public async Task<IEnumerable<Product>> GetRecommendedAsync(string occasion, decimal maxBudget, CancellationToken cancellationToken)
        {
            var query = _dbContext.Products.AsNoTracking().Where(p => p.IsActive);
            if (!string.IsNullOrWhiteSpace(occasion))
            {
                query = query.Where(p => EF.Functions.ILike(p.OccasionTags ?? string.Empty, $"%{occasion}%") || EF.Functions.ILike(p.Category, $"%{occasion}%"));
            }

            return await query
                .Where(p => p.Price <= maxBudget)
                .OrderBy(p => p.Price)
                .Take(10)
                .ToListAsync(cancellationToken);
        }

        public async Task<IEnumerable<Product>> GetGiftItemsAsync(CancellationToken cancellationToken)
        {
            return await _dbContext.Products
                .AsNoTracking()
                .Where(p => p.IsActive && p.IsGiftItem)
                .OrderBy(p => p.Name)
                .Take(20)
                .ToListAsync(cancellationToken);
        }

        public async Task<bool> CheckInventoryAsync(Guid productId, int requestedQty, CancellationToken cancellationToken)
        {
            var product = await _dbContext.Products.AsNoTracking().FirstOrDefaultAsync(p => p.Id == productId, cancellationToken);
            return product is not null && product.StockQuantity >= requestedQty;
        }
    }
}
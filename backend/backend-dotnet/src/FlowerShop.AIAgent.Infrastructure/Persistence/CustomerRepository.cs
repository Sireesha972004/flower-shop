using FlowerShop.AIAgent.Application.Interfaces;
using FlowerShop.AIAgent.Domain.Entities;
using Microsoft.EntityFrameworkCore;

namespace FlowerShop.AIAgent.Infrastructure.Persistence
{
    public class CustomerRepository : ICustomerRepository
    {
        private readonly FlowerShopAIAgentDbContext _dbContext;

        public CustomerRepository(FlowerShopAIAgentDbContext dbContext)
        {
            _dbContext = dbContext;
        }

        public async Task<Customer?> GetByEmailAsync(string email, CancellationToken cancellationToken)
        {
            return await _dbContext.Customers
                .AsNoTracking()
                .Include(c => c.Addresses)
                .FirstOrDefaultAsync(c => c.Email.ToLower() == email.ToLower(), cancellationToken);
        }

        public async Task<Customer> CreateAsync(Customer customer, CancellationToken cancellationToken)
        {
            await _dbContext.Customers.AddAsync(customer, cancellationToken);
            await _dbContext.SaveChangesAsync(cancellationToken);
            return customer;
        }

        public async Task UpdateAsync(Customer customer, CancellationToken cancellationToken)
        {
            _dbContext.Customers.Update(customer);
            await _dbContext.SaveChangesAsync(cancellationToken);
        }
    }
}
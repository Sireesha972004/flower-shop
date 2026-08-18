using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using FlowerShop.AIAgent.Application.Interfaces;
using FlowerShop.AIAgent.Domain.Entities;
using Microsoft.EntityFrameworkCore;

namespace FlowerShop.AIAgent.Infrastructure.Persistence
{
    public class AddressRepository : IAddressRepository
    {
        private readonly FlowerShopAIAgentDbContext _dbContext;

        public AddressRepository(FlowerShopAIAgentDbContext dbContext)
        {
            _dbContext = dbContext;
        }

        public async Task<IEnumerable<Address>> GetAddressesAsync(Guid customerId, CancellationToken cancellationToken)
        {
            return await _dbContext.Addresses
                .AsNoTracking()
                .Where(a => a.CustomerId == customerId)
                .ToListAsync(cancellationToken);
        }

        public async Task<Address> AddAddressAsync(Address address, CancellationToken cancellationToken)
        {
            await _dbContext.Addresses.AddAsync(address, cancellationToken);
            await _dbContext.SaveChangesAsync(cancellationToken);
            return address;
        }
    }
}
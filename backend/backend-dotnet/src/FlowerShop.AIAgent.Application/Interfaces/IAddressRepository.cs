using System;
using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using FlowerShop.AIAgent.Domain.Entities;

namespace FlowerShop.AIAgent.Application.Interfaces
{
    public interface IAddressRepository
    {
        Task<IEnumerable<Address>> GetAddressesAsync(Guid customerId, CancellationToken cancellationToken);
        Task<Address> AddAddressAsync(Address address, CancellationToken cancellationToken);
    }
}
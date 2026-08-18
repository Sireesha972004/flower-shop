using System;
using System.Threading;
using System.Threading.Tasks;
using FlowerShop.AIAgent.Domain.Entities;

namespace FlowerShop.AIAgent.Application.Interfaces
{
    public interface ICustomerRepository
    {
        Task<Customer?> GetByEmailAsync(string email, CancellationToken cancellationToken);
        Task<Customer> CreateAsync(Customer customer, CancellationToken cancellationToken);
        Task UpdateAsync(Customer customer, CancellationToken cancellationToken);
    }
}
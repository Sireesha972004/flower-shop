using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using FlowerShop.AIAgent.Application.Services;

namespace FlowerShop.AIAgent.Application.Interfaces
{
    public interface IAgentToolRegistry
    {
        Task<IEnumerable<AgentToolMetadata>> GetToolsAsync(CancellationToken cancellationToken);
    }
}
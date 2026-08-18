using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using FlowerShop.AIAgent.Application.Interfaces;
using FlowerShop.AIAgent.Application.Services;

namespace FlowerShop.AIAgent.Infrastructure.Persistence
{
    public class ToolRegistry : IAgentToolRegistry
    {
        public Task<IEnumerable<AgentToolMetadata>> GetToolsAsync(CancellationToken cancellationToken)
        {
            var tools = new List<AgentToolMetadata>
            {
                new("search_flowers", "Search for flower arrangements and bouquets by occasion, budget, or keywords.", OpenAiToolSchema.SearchFlowers),
                new("view_cart", "Show the customer's current shopping cart details.", OpenAiToolSchema.ViewCart),
            };
            return Task.FromResult<IEnumerable<AgentToolMetadata>>(tools);
        }
    }
}
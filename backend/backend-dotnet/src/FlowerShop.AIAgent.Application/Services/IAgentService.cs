using System.Collections.Generic;
using System.Threading;
using System.Threading.Tasks;
using FlowerShop.AIAgent.Application.Models;

namespace FlowerShop.AIAgent.Application.Services
{
    public interface IAgentService
    {
        Task<IEnumerable<AgentToolMetadata>> GetToolsAsync(CancellationToken cancellationToken);
        Task<ChatResponse> HandleChatAsync(IEnumerable<ChatMessage> messages, CancellationToken cancellationToken);
    }
}
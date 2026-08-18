using System;
using System.Collections.Generic;
using System.Linq;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using FlowerShop.AIAgent.Application.Interfaces;
using FlowerShop.AIAgent.Application.Models;
using Microsoft.Extensions.Logging;

namespace FlowerShop.AIAgent.Application.Services
{
    public class AgentService : IAgentService
    {
        private readonly IAgentToolRegistry _toolRegistry;
        private readonly IShoppingAssistantService _shoppingAssistantService;
        private readonly ILogger<AgentService> _logger;

        public AgentService(
            IAgentToolRegistry toolRegistry,
            IShoppingAssistantService shoppingAssistantService,
            ILogger<AgentService> logger)
        {
            _toolRegistry = toolRegistry;
            _shoppingAssistantService = shoppingAssistantService;
            _logger = logger;
        }

        public async Task<IEnumerable<AgentToolMetadata>> GetToolsAsync(CancellationToken cancellationToken)
        {
            return await _toolRegistry.GetToolsAsync(cancellationToken);
        }

        public async Task<ChatResponse> HandleChatAsync(IEnumerable<ChatMessage> messages, CancellationToken cancellationToken)
        {
            var userMessage = messages.LastOrDefault(m => m.Role.Equals("user", StringComparison.OrdinalIgnoreCase))?.Content ?? string.Empty;
            if (string.IsNullOrWhiteSpace(userMessage))
            {
                return new ChatResponse("Please enter a message so I can help you.", false, null, null);
            }

            if (userMessage.Contains("show tools", StringComparison.OrdinalIgnoreCase))
            {
                var tools = await GetToolsAsync(cancellationToken);
                var toolNames = string.Join(", ", tools.Select(t => t.Name));
                return new ChatResponse($"I can help with these tools: {toolNames}", false, null, null);
            }

            return new ChatResponse("I can assist with your flower shopping. Tell me what you need.", false, null, null);
        }
    }
}
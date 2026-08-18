using System;
using System.Collections.Generic;
using System.Linq;
using System.Net.Http;
using System.Net.Http.Json;
using System.Text.Json;
using System.Threading;
using System.Threading.Tasks;
using FlowerShop.AIAgent.Application.Interfaces;
using FlowerShop.AIAgent.Application.Models;
using Microsoft.Extensions.Configuration;
using Microsoft.Extensions.Logging;

namespace FlowerShop.AIAgent.Application.Services
{
    public class OpenAiAgentService : IAgentService
    {
        private readonly IAgentToolRegistry _toolRegistry;
        private readonly IShoppingAssistantService _shoppingAssistantService;
        private readonly IHttpClientFactory _httpClientFactory;
        private readonly ILogger<OpenAiAgentService> _logger;
        private readonly string _openAiApiKey;
        private readonly string _openAiModel;

        public OpenAiAgentService(
            IAgentToolRegistry toolRegistry,
            IShoppingAssistantService shoppingAssistantService,
            IHttpClientFactory httpClientFactory,
            IConfiguration configuration,
            ILogger<OpenAiAgentService> logger)
        {
            _toolRegistry = toolRegistry;
            _shoppingAssistantService = shoppingAssistantService;
            _httpClientFactory = httpClientFactory;
            _logger = logger;
            _openAiApiKey = configuration["OpenAI:ApiKey"] ?? throw new InvalidOperationException("OpenAI API key is required.");
            _openAiModel = configuration["OpenAI:Model"] ?? "gpt-4.1";
        }

        public async Task<IEnumerable<AgentToolMetadata>> GetToolsAsync(CancellationToken cancellationToken)
        {
            return await _toolRegistry.GetToolsAsync(cancellationToken);
        }

        public async Task<ChatResponse> HandleChatAsync(IEnumerable<ChatMessage> messages, CancellationToken cancellationToken)
        {
            var client = _httpClientFactory.CreateClient("openai");
            var tools = await GetToolsAsync(cancellationToken);
            var toolDefs = tools.Select(t => new
            {
                name = t.Name,
                description = t.Description,
                parameters = t.ParametersSchema
            }).ToArray();

            var requestBody = new
            {
                model = _openAiModel,
                messages = messages.Select(m => new { role = m.Role, content = m.Content }).ToArray(),
                functions = toolDefs,
                function_call = "auto"
            };

            var response = await client.PostAsJsonAsync("https://api.openai.com/v1/chat/completions", requestBody, cancellationToken);
            response.EnsureSuccessStatusCode();

            var json = await response.Content.ReadFromJsonAsync<JsonElement>(cancellationToken: cancellationToken);
            var choice = json.GetProperty("choices")[0];
            var message = choice.GetProperty("message");
            if (message.TryGetProperty("function_call", out var functionCall))
            {
                var name = functionCall.GetProperty("name").GetString();
                var argsJson = functionCall.GetProperty("arguments").GetRawText();
                return await ExecuteToolAsync(name ?? string.Empty, argsJson, cancellationToken);
            }

            var content = message.GetProperty("content").GetString() ?? string.Empty;
            return new ChatResponse(content, false, null, null);
        }

        private async Task<ChatResponse> ExecuteToolAsync(string toolName, string argsJson, CancellationToken cancellationToken)
        {
            _logger.LogInformation("Executing tool {ToolName} with args: {Arguments}", toolName, argsJson);

            try
            {
                var args = JsonSerializer.Deserialize<Dictionary<string, object>>(argsJson) ?? new Dictionary<string, object>();

                return toolName switch
                {
                    "search_flowers" => await ExecuteSearchFlowersAsync(args, cancellationToken),
                    "view_cart" => await ExecuteViewCartAsync(args, cancellationToken),
                    _ => new ChatResponse($"I could not execute the tool {toolName}.", false, null, null)
                };
            }
            catch (Exception ex)
            {
                _logger.LogError(ex, "Tool execution failed for {ToolName}", toolName);
                return new ChatResponse("Sorry, I ran into a problem while executing your request.", false, null, null);
            }
        }

        private async Task<ChatResponse> ExecuteSearchFlowersAsync(Dictionary<string, object> args, CancellationToken cancellationToken)
        {
            var occasion = args.TryGetValue("occasion", out var occasionVal) ? occasionVal?.ToString() : string.Empty;
            var budget = args.TryGetValue("budget", out var budgetVal) && decimal.TryParse(budgetVal?.ToString(), out var budgetValue) ? budgetValue : (decimal?)null;
            var keywords = args.TryGetValue("keywords", out var keywordsVal) ? keywordsVal?.ToString() : null;
            var count = args.TryGetValue("count", out var countVal) && int.TryParse(countVal?.ToString(), out var countValue) ? countValue : 5;

            var result = await _shoppingAssistantService.SearchFlowersAsync(occasion ?? string.Empty, budget, keywords, count, cancellationToken);
            return new ChatResponse("Found matching flowers.", true, "search_flowers", result);
        }

        private async Task<ChatResponse> ExecuteViewCartAsync(Dictionary<string, object> args, CancellationToken cancellationToken)
        {
            if (!args.TryGetValue("customerId", out var customerIdValue) || !Guid.TryParse(customerIdValue?.ToString(), out var customerId))
            {
                return new ChatResponse("Unable to view cart because the customer identifier is missing or invalid.", false, null, null);
            }

            var cart = await _shoppingAssistantService.ViewCartAsync(customerId, cancellationToken);
            return new ChatResponse("Here is your current cart.", true, "view_cart", cart);
        }
    }
}
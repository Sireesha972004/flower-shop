using FlowerShop.AIAgent.Application.Services;
using FlowerShop.AIAgent.Api.Models;
using Microsoft.AspNetCore.Mvc;
using ApplicationChatMessage = FlowerShop.AIAgent.Application.Models.ChatMessage;

namespace FlowerShop.AIAgent.Api.Controllers
{
    [ApiController]
    [Route("api/ai")]
    public class AiController : ControllerBase
    {
        private readonly IAgentService _agentService;

        public AiController(IAgentService agentService)
        {
            _agentService = agentService;
        }

        [HttpPost("chat")]
        public async Task<IActionResult> Chat([FromBody] IEnumerable<ChatMessage> messages, CancellationToken cancellationToken)
        {
            var applicationMessages = messages.Select(m => new ApplicationChatMessage(m.Role, m.Content));
            var response = await _agentService.HandleChatAsync(applicationMessages, cancellationToken);
            return Ok(response);
        }

        [HttpGet("tools")]
        public async Task<IActionResult> GetTools(CancellationToken cancellationToken)
        {
            var tools = await _agentService.GetToolsAsync(cancellationToken);
            return Ok(tools);
        }
    }
}
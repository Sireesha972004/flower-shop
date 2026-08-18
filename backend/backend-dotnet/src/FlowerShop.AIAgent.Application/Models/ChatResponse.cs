namespace FlowerShop.AIAgent.Application.Models
{
    public record ChatResponse(string Content, bool IsToolCall, string? ToolName, object? ToolArguments);
}
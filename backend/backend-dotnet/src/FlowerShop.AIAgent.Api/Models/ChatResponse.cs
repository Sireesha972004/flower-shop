namespace FlowerShop.AIAgent.Api.Models
{
    public record ChatResponse(string Content, bool IsToolCall, string? ToolName, object? ToolArguments);
}
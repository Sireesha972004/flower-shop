namespace FlowerShop.AIAgent.Application.Services
{
    public static class ToolDefinitions
    {
        public static readonly object SearchFlowers = new
        {
            name = "search_flowers",
            description = "Search for flower arrangements and bouquets by occasion, budget, or keywords.",
            parameters = new
            {
                type = "object",
                properties = new
                {
                    occasion = new { type = "string", description = "The occasion for the flowers." },
                    budget = new { type = "number", description = "Maximum budget in the local currency." },
                    keywords = new { type = "string", description = "Search keywords for flower products." },
                    count = new { type = "integer", description = "Number of results to return." }
                },
                required = new[] { "count" }
            }
        };

        public static readonly object ViewCart = new
        {
            name = "view_cart",
            description = "Show the customer's current cart contents.",
            parameters = new
            {
                type = "object",
                properties = new
                {
                    customerId = new { type = "string", description = "The customer's unique identifier." }
                },
                required = new[] { "customerId" }
            }
        };
    }
}
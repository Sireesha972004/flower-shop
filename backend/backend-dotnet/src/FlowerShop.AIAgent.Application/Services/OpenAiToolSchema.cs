namespace FlowerShop.AIAgent.Application.Services
{
    public static class OpenAiToolSchema
    {
        public static object SearchFlowers => new
        {
            name = "search_flowers",
            description = "Search for flower arrangements and bouquets by occasion, budget, or keywords.",
            parameters = new
            {
                type = "object",
                properties = new
                {
                    occasion = new { type = "string", description = "The occasion for the flowers." },
                    budget = new { type = "number", description = "Maximum budget for the flowers." },
                    keywords = new { type = "string", description = "Search keywords for flower products." },
                    count = new { type = "integer", description = "Number of results to return." }
                },
                required = new[] { "count" }
            }
        };

        public static object ViewCart => new
        {
            name = "view_cart",
            description = "Show the customer's current shopping cart details.",
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
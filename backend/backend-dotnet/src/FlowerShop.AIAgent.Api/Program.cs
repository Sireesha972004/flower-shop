using FlowerShop.AIAgent.Application.Interfaces;
using FlowerShop.AIAgent.Application.Services;
using FlowerShop.AIAgent.Infrastructure.Persistence;
using Microsoft.EntityFrameworkCore;

var builder = WebApplication.CreateBuilder(args);

builder.Services.AddControllers();
builder.Services.AddEndpointsApiExplorer();
builder.Services.AddSwaggerGen();

builder.Services.AddHttpClient("openai", client =>
{
    var apiKey = builder.Configuration["OpenAI:ApiKey"];
    if (!string.IsNullOrWhiteSpace(apiKey))
    {
        client.DefaultRequestHeaders.Add("Authorization", $"Bearer {apiKey}");
    }
    client.DefaultRequestHeaders.Add("Accept", "application/json");
});

builder.Services.AddDbContext<FlowerShopAIAgentDbContext>(options =>
    options.UseNpgsql(builder.Configuration.GetConnectionString("DefaultConnection")));

builder.Services.AddScoped<IProductRepository, ProductRepository>();
builder.Services.AddScoped<ICartRepository, CartRepository>();
builder.Services.AddScoped<IOrderRepository, OrderRepository>();
builder.Services.AddScoped<ICustomerRepository, CustomerRepository>();
builder.Services.AddScoped<IAddressRepository, AddressRepository>();
builder.Services.AddScoped<IAgentToolRegistry, ToolRegistry>();
builder.Services.AddScoped<IShoppingAssistantService, ShoppingAssistantService>();
builder.Services.AddScoped<IAgentService, OpenAiAgentService>();

var app = builder.Build();

if (app.Environment.IsDevelopment())
{
    app.UseSwagger();
    app.UseSwaggerUI();
}

app.UseHttpsRedirection();
app.UseAuthorization();
app.MapControllers();
app.Run();
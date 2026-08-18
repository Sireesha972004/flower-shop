using System;
using System.Collections.Generic;
using System.Linq;
using System.Threading;
using System.Threading.Tasks;
using FlowerShop.AIAgent.Application.DTOs;
using FlowerShop.AIAgent.Application.Interfaces;
using FlowerShop.AIAgent.Domain.Entities;

namespace FlowerShop.AIAgent.Application.Services
{
    public class ShoppingAssistantService : IShoppingAssistantService
    {
        private readonly IProductRepository _productRepository;
        private readonly ICartRepository _cartRepository;
        private readonly IOrderRepository _orderRepository;
        private readonly ICustomerRepository _customerRepository;

        public ShoppingAssistantService(
            IProductRepository productRepository,
            ICartRepository cartRepository,
            IOrderRepository orderRepository,
            ICustomerRepository customerRepository)
        {
            _productRepository = productRepository;
            _cartRepository = cartRepository;
            _orderRepository = orderRepository;
            _customerRepository = customerRepository;
        }

        public async Task AddToCartAsync(Guid customerId, Guid productId, int quantity, CancellationToken cancellationToken)
        {
            var product = await _productRepository.GetByIdAsync(productId, cancellationToken);
            if (product is null)
            {
                throw new InvalidOperationException("Product not found.");
            }

            if (!await _productRepository.CheckInventoryAsync(productId, quantity, cancellationToken))
            {
                throw new InvalidOperationException("Insufficient stock for the requested product.");
            }

            await _cartRepository.AddToCartAsync(new CartItem
            {
                CustomerId = customerId,
                ProductId = productId,
                Quantity = quantity
            }, cancellationToken);
        }

        public async Task<IEnumerable<ProductDto>> RecommendFlowersAsync(string occasion, decimal budget, CancellationToken cancellationToken)
        {
            var recommended = await _productRepository.GetRecommendedAsync(occasion, budget, cancellationToken);
            return recommended.Select(ToProductDto);
        }

        public async Task<IEnumerable<ProductDto>> SearchFlowersAsync(string occasion, decimal? budget, string? keywords, int count, CancellationToken cancellationToken)
        {
            var query = string.Join(' ', new[] { occasion, keywords }.Where(x => !string.IsNullOrWhiteSpace(x)));
            var searchResults = await _productRepository.SearchAsync(query, cancellationToken);
            if (budget.HasValue)
            {
                searchResults = searchResults.Where(p => p.Price <= budget.Value);
            }
            return searchResults.Take(count).Select(ToProductDto);
        }

        public async Task<IEnumerable<ProductDto>> SearchGiftItemsAsync(CancellationToken cancellationToken)
        {
            var gifts = await _productRepository.GetGiftItemsAsync(cancellationToken);
            return gifts.Select(ToProductDto);
        }

        public async Task<CartDto> ViewCartAsync(Guid customerId, CancellationToken cancellationToken)
        {
            var items = await _cartRepository.GetCartAsync(customerId, cancellationToken);
            var cartItems = items.Select(ci => new CartItemDto(ci.ProductId, ci.Product?.Name ?? string.Empty, ci.Product?.Price ?? 0m, ci.Quantity, ci.Product?.ImageUrl ?? string.Empty)).ToList();
            var total = cartItems.Sum(item => item.Price * item.Quantity);
            return new CartDto(cartItems, total);
        }

        public async Task RemoveFromCartAsync(Guid customerId, Guid productId, CancellationToken cancellationToken)
        {
            await _cartRepository.RemoveFromCartAsync(customerId, productId, cancellationToken);
        }

        public async Task UpdateQuantityAsync(Guid customerId, Guid productId, int quantity, CancellationToken cancellationToken)
        {
            await _cartRepository.UpdateQuantityAsync(customerId, productId, quantity, cancellationToken);
        }

        public async Task<IEnumerable<OrderDto>> GetOrderHistoryAsync(Guid customerId, CancellationToken cancellationToken)
        {
            var orders = await _orderRepository.GetOrdersAsync(customerId, cancellationToken);
            return orders.Select(ToOrderDto);
        }

        public async Task<OrderDto?> TrackOrderAsync(Guid orderId, CancellationToken cancellationToken)
        {
            var order = await _orderRepository.GetByIdAsync(orderId, cancellationToken);
            return order is null ? null : ToOrderDto(order);
        }

        public async Task<OrderDto> CreateOrderAsync(Guid customerId, string deliveryAddress, DateTime deliveryDate, string? paymentMethod, CancellationToken cancellationToken)
        {
            var cartItems = await _cartRepository.GetCartAsync(customerId, cancellationToken);
            if (!cartItems.Any())
            {
                throw new InvalidOperationException("Cart is empty.");
            }

            var order = new Order
            {
                CustomerId = customerId,
                OrderNumber = $"FS-{DateTime.UtcNow:yyyyMMddHHmmss}",
                DeliveryAddress = deliveryAddress,
                DeliveryDate = deliveryDate,
                PaymentMethod = paymentMethod,
                Status = "confirmed",
                Total = cartItems.Sum(ci => (ci.Product?.Price ?? 0m) * ci.Quantity),
                OrderItems = cartItems.Select(ci => new OrderItem
                {
                    ProductId = ci.ProductId,
                    ProductName = ci.Product?.Name ?? string.Empty,
                    Price = ci.Product?.Price ?? 0m,
                    Quantity = ci.Quantity
                }).ToList()
            };

            var created = await _orderRepository.CreateAsync(order, cancellationToken);
            await _cartRepository.ClearCartAsync(customerId, cancellationToken);
            return ToOrderDto(created);
        }

        public async Task CancelOrderAsync(Guid orderId, CancellationToken cancellationToken)
        {
            await _orderRepository.CancelOrderAsync(orderId, cancellationToken);
        }

        public async Task<IEnumerable<string>> GetDeliverySlotsAsync(DateTime requestDate, CancellationToken cancellationToken)
        {
            var slots = new List<string>();
            var localDate = requestDate.Date;
            for (var hour = 9; hour < 20; hour += 2)
            {
                slots.Add($"{localDate:yyyy-MM-dd}T{hour:00}:00");
            }
            return await Task.FromResult(slots);
        }

        private static ProductDto ToProductDto(Product product)
        {
            return new ProductDto(product.Id, product.Name, product.Category, product.Description, product.Price, product.ImageUrl, product.StockQuantity, product.IsGiftItem, product.OccasionTags);
        }

        private static OrderDto ToOrderDto(Order order)
        {
            var items = order.OrderItems.Select(oi => new OrderItemDto(oi.ProductId, oi.ProductName, oi.Price, oi.Quantity)).ToArray();
            return new OrderDto(order.Id, order.OrderNumber, order.Total, order.Status, order.DeliveryAddress, order.DeliveryDate, order.PaymentMethod, order.CreatedAt, items);
        }
    }
}
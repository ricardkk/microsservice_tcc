package order;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.List;
final class OrderContracts {
 record CreateOrder(@NotNull @Positive Long userId, @NotEmpty @Size(max = 100) List<@NotNull @Valid ItemInput> items) {}
 record ItemInput(@NotNull @Positive Long productId, @NotNull @Min(1) @Max(10000) Integer quantity) {}
 record ItemResponse(Long id, Long productId, Integer quantity, BigDecimal unitPrice, BigDecimal subtotal) {}
 record OrderResponse(Long id, Long userId, BigDecimal total, String status, Instant createdAt, List<ItemResponse> items) {
  static OrderResponse from(OrderEntity o) {
   return new OrderResponse(o.id, o.userId, o.total, o.status, o.createdAt, o.items.stream()
     .map(i -> new ItemResponse(i.id, i.productId, i.quantity, i.unitPrice, i.subtotal)).toList());
  }
 }
}

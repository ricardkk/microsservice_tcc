package order;
import jakarta.persistence.*;
import java.math.BigDecimal;
@Entity @Table(name = "order_items")
public class OrderItemEntity {
 @Id @GeneratedValue(strategy = GenerationType.IDENTITY) Long id;
 @ManyToOne(fetch = FetchType.LAZY, optional = false) @JoinColumn(name = "order_id") OrderEntity order;
 @Column(name = "product_id", nullable = false) Long productId;
 @Column(nullable = false) Integer quantity;
 @Column(name = "unit_price", nullable = false, precision = 12, scale = 2) BigDecimal unitPrice;
 @Column(nullable = false, precision = 20, scale = 2) BigDecimal subtotal;
 protected OrderItemEntity() {}
 OrderItemEntity(OrderEntity order, Long productId, int quantity, BigDecimal price) {
  this.order = order; this.productId = productId; this.quantity = quantity; this.unitPrice = price;
  this.subtotal = price.multiply(BigDecimal.valueOf(quantity));
 }
}

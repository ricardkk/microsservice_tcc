package order;
import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.Instant;
import java.util.ArrayList;
import java.util.List;
@Entity @Table(name = "orders")
public class OrderEntity {
 @Id @GeneratedValue(strategy = GenerationType.IDENTITY) Long id;
 @Column(name = "user_id", nullable = false) Long userId;
 @Column(nullable = false, precision = 20, scale = 2) BigDecimal total;
 @Column(nullable = false, length = 20) String status;
 @Column(name = "created_at", nullable = false) Instant createdAt;
 @OneToMany(mappedBy = "order", cascade = CascadeType.ALL, orphanRemoval = true)
 @OrderBy("id") List<OrderItemEntity> items = new ArrayList<>();
 protected OrderEntity() {}
 OrderEntity(Long userId) { this.userId = userId; this.status = "CREATED"; this.createdAt = Instant.now(); this.total = BigDecimal.ZERO; }
 void add(Long productId, int quantity, BigDecimal price) {
  var item = new OrderItemEntity(this, productId, quantity, price); items.add(item); total = total.add(item.subtotal);
 }
}

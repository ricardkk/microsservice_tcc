package product;
import jakarta.persistence.*;
import java.math.BigDecimal;
import java.time.Instant;
@Entity @Table(name = "products")
public class ProductEntity {
 @Id @GeneratedValue(strategy = GenerationType.IDENTITY) Long id;
 @Column(nullable = false, length = 120) String name;
 @Column(nullable = false, length = 1000) String description;
 @Column(nullable = false, precision = 12, scale = 2) BigDecimal price;
 @Column(nullable = false) Integer stock;
 @Column(name = "created_at", nullable = false) Instant createdAt;
 protected ProductEntity() {}
 ProductEntity(String name, String description, BigDecimal price, Integer stock) {
  this.name = name; this.description = description; this.price = price; this.stock = stock; this.createdAt = Instant.now();
 }
}

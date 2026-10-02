package user;
import jakarta.persistence.*;
import java.time.Instant;
@Entity @Table(name = "users")
public class UserEntity {
 @Id @GeneratedValue(strategy = GenerationType.IDENTITY) Long id;
 @Column(nullable = false, length = 120) String name;
 @Column(nullable = false, unique = true, length = 254) String email;
 @Column(name = "created_at", nullable = false) Instant createdAt;
 protected UserEntity() {}
 UserEntity(String name, String email) { this.name = name; this.email = email; this.createdAt = Instant.now(); }
}

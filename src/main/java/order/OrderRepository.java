package order;
import java.util.List;
import org.springframework.data.jpa.repository.JpaRepository;
interface OrderRepository extends JpaRepository<OrderEntity, Long> {
 List<OrderEntity> findByUserIdOrderByIdAsc(Long userId);
}

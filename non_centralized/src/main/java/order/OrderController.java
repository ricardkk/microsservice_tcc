package order;
import jakarta.validation.Valid;
import java.net.URI;
import java.util.List;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;
import static order.OrderContracts.*;
@RestController @RequestMapping("/orders")
class OrderController {
 private final OrderService orders;
 OrderController(OrderService orders) { this.orders = orders; }
 @PostMapping ResponseEntity<OrderResponse> create(@Valid @RequestBody CreateOrder input) {
  var order = orders.create(input);
  return ResponseEntity.created(URI.create("/orders/" + order.id())).body(order);
 }
 @GetMapping("/{id}") OrderResponse get(@PathVariable Long id) { return orders.get(id); }
 @GetMapping List<OrderResponse> list(@RequestParam(required = false) Long userId) { return orders.list(userId); }
}

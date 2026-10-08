package order;

import common.ApiFailure;
import java.util.HashSet;
import java.util.List;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.domain.Sort;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import static order.OrderContracts.*;

@Service
class OrderService {
 private static final Logger log = LoggerFactory.getLogger(OrderService.class);
 private final OrderRepository orders;
 private final CatalogClient catalog;
 OrderService(OrderRepository orders, CatalogClient catalog) { this.orders = orders; this.catalog = catalog; }
 @Transactional
 public OrderResponse create(CreateOrder input) {
  var seen = new HashSet<Long>();
  for (var item : input.items()) if (!seen.add(item.productId()))
   throw new ApiFailure(400, "DUPLICATE_PRODUCT", "Each product must appear only once in a request");
  org.slf4j.MDC.put("operation", "createOrder");
  log.atInfo().addKeyValue("userId", input.userId()).log("Creating order");
  catalog.validateUser(input.userId());
  var order = new OrderEntity(input.userId());
  for (var item : input.items()) {
   var product = catalog.product(item.productId());
   if (product.stock() < item.quantity()) {
    log.atWarn().addKeyValue("productId", item.productId()).addKeyValue("requestedQuantity", item.quantity())
      .addKeyValue("availableStock", product.stock()).log("Insufficient stock");
    throw new ApiFailure(422, "INSUFFICIENT_STOCK", "Insufficient stock for product " + item.productId());
   }
   order.add(item.productId(), item.quantity(), product.price());
  }
  orders.saveAndFlush(order);
  org.slf4j.MDC.put("operation", "createOrder");
  log.atInfo().addKeyValue("orderId", order.id)
    .addKeyValue("total", order.total).log("Order persisted");
  return OrderResponse.from(order);
 }
 @Transactional(readOnly = true)
 public OrderResponse get(Long id) {
  var order = orders.findById(id).orElseThrow(() -> new ApiFailure(404, "ORDER_NOT_FOUND", "Order does not exist"));
  org.slf4j.MDC.put("operation", "getOrder");
  log.atInfo().addKeyValue("orderId", id).log("Order retrieved");
  return OrderResponse.from(order);
 }
 @Transactional(readOnly = true)
 public List<OrderResponse> list(Long userId) {
  var result = userId == null ? orders.findAll(Sort.by("id")) : orders.findByUserIdOrderByIdAsc(userId);
  return result.stream().map(OrderResponse::from).toList();
 }
}

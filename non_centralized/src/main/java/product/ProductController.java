package product;

import common.ApiFailure;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import java.math.BigDecimal;
import java.net.URI;
import java.time.Instant;
import java.util.List;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.domain.Sort;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController @RequestMapping("/products")
class ProductController {
 private static final Logger log = LoggerFactory.getLogger(ProductController.class);
 private final ProductRepository products;
 ProductController(ProductRepository products) { this.products = products; }
 record CreateProduct(@NotBlank @Size(max = 120) String name, @NotNull @Size(max = 1000) String description,
   @NotNull @DecimalMin("0.01") @Digits(integer = 10, fraction = 2) BigDecimal price,
   @NotNull @Min(0) Integer stock) {}
 record ProductResponse(Long id, String name, String description, BigDecimal price, Integer stock, Instant createdAt) {
  static ProductResponse from(ProductEntity p) { return new ProductResponse(p.id, p.name, p.description, p.price, p.stock, p.createdAt); }
 }
 record Availability(Long productId, Integer stock, boolean available) {}
 @PostMapping ResponseEntity<ProductResponse> create(@Valid @RequestBody CreateProduct input) {
  var product = products.saveAndFlush(new ProductEntity(input.name().trim(), input.description(), input.price(), input.stock()));
  org.slf4j.MDC.put("operation", "createProduct");
  log.atInfo().addKeyValue("productId", product.id).log("Product created");
  return ResponseEntity.created(URI.create("/products/" + product.id)).body(ProductResponse.from(product));
 }
 private ProductEntity find(Long id) {
  return products.findById(id).orElseThrow(() -> new ApiFailure(404, "PRODUCT_NOT_FOUND", "Product does not exist"));
 }
 @GetMapping("/{id}") ProductResponse get(@PathVariable Long id) {
  var product = find(id);
  org.slf4j.MDC.put("operation", "getProduct");
  log.atInfo().addKeyValue("productId", id).log("Product retrieved");
  return ProductResponse.from(product);
 }
 @GetMapping List<ProductResponse> list() {
  return products.findAll(Sort.by("id")).stream().map(ProductResponse::from).toList();
 }
 @GetMapping("/{id}/availability") Availability availability(@PathVariable Long id) {
  var p = find(id); return new Availability(p.id, p.stock, p.stock > 0);
 }
}

package order;

import common.*;
import java.math.BigDecimal;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Component;
import org.springframework.web.client.*;

@Component
class CatalogClient {
 @com.fasterxml.jackson.annotation.JsonIgnoreProperties(ignoreUnknown = true)
 record User(Long id) {}
 @com.fasterxml.jackson.annotation.JsonIgnoreProperties(ignoreUnknown = true)
 record Product(Long id, BigDecimal price, Integer stock) {}
 private final RestClient users;
 private final RestClient products;
 CatalogClient(HttpClients clients, @Value("${services.user-url}") String userUrl, @Value("${services.product-url}") String productUrl) {
  users = clients.create(userUrl); products = clients.create(productUrl);
 }
 void validateUser(Long id) {
  User user = get(users, "/users/{id}", id, User.class, "user-service", "USER_NOT_FOUND");
  if (user == null || !id.equals(user.id())) throw invalid("user-service");
 }
 Product product(Long id) {
  Product p = get(products, "/products/{id}", id, Product.class, "product-service", "PRODUCT_NOT_FOUND");
  if (p == null || !id.equals(p.id()) || p.price() == null || p.price().signum() <= 0 || p.price().scale() > 2
    || p.price().compareTo(new BigDecimal("9999999999.99")) > 0 || p.stock() == null || p.stock() < 0) throw invalid("product-service");
  return p;
 }
 private ApiFailure invalid(String service) { return new ApiFailure(502, "INVALID_DOWNSTREAM_RESPONSE", "Invalid resource returned by " + service); }
 private <T> T get(RestClient client, String path, Long id, Class<T> type, String service, String missingCode) {
  try { return client.get().uri(path, id).retrieve().body(type); }
  catch (RestClientResponseException e) {
   if (e.getStatusCode().value() == 404) throw new ApiFailure(422, missingCode, "Referenced resource does not exist in " + service, e);
   throw new ApiFailure(502, "DOWNSTREAM_ERROR", service + " returned HTTP " + e.getStatusCode().value(), e);
  } catch (ResourceAccessException e) { throw CommunicationErrors.map(e, service); }
  catch (RestClientException e) { throw new ApiFailure(502, "INVALID_DOWNSTREAM_RESPONSE", "Could not decode response from " + service, e); }
 }
}

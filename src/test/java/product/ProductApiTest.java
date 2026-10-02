package product;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import static org.assertj.core.api.Assertions.assertThat;
@SpringBootTest(useMainMethod = SpringBootTest.UseMainMethod.ALWAYS, webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT, properties = {
 "spring.datasource.url=jdbc:h2:mem:products;MODE=PostgreSQL;DB_CLOSE_DELAY=-1", "spring.datasource.driver-class-name=org.h2.Driver", "fault.enabled=true", "fault.delay-ms=10"})
class ProductApiTest extends HttpTestSupport {
 @Test void createsProductAndChecksAvailability() throws Exception {
  var created = request("POST", "/products", "{\"name\":\"Livro\",\"description\":\"Teste\",\"price\":19.95,\"stock\":10}");
  assertThat(created.statusCode()).isEqualTo(201);
  long id = tree(created).get("id").asLong();
  assertThat(request("GET", "/products/" + id, null).statusCode()).isEqualTo(200);
  assertThat(tree(request("GET", "/products/" + id + "/availability", null)).get("available").asBoolean()).isTrue();
 }
 @Test void rejectsInvalidPriceAndStock() throws Exception {
  assertThat(request("POST", "/products", "{\"name\":\"Livro\",\"description\":\"\",\"price\":-1,\"stock\":-1}").statusCode()).isEqualTo(400);
  assertThat(request("POST", "/products", "{\"name\":\"Livro\",\"description\":\"\",\"price\":1.999,\"stock\":1}").statusCode()).isEqualTo(400);
 }
 @Test void faultsAreDeterministicAndRequestScoped() throws Exception {
  for (String type : new String[]{"internal-error", "database", "timeout", "not-found", "invalid-response"}) {
   var response = request("GET", "/products", null, "X-Fault-Service", "product-service", "X-Fault-Type", type);
   int expected = switch(type) { case "internal-error" -> 500; case "database" -> 503; case "timeout" -> 504; case "not-found" -> 404; default -> 200; };
   assertThat(response.statusCode()).isEqualTo(expected);
   assertThat(request("GET", "/products", null).statusCode()).isEqualTo(200);
  }
 }
}

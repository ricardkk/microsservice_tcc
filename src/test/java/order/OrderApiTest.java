package order;

import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import java.util.concurrent.Executors;
import java.util.concurrent.ExecutorService;
import org.junit.jupiter.api.*;
import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(useMainMethod = SpringBootTest.UseMainMethod.ALWAYS, webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT, properties = {
 "spring.datasource.url=jdbc:h2:mem:orders;MODE=PostgreSQL;DB_CLOSE_DELAY=-1", "spring.datasource.driver-class-name=org.h2.Driver",
 "http.read-timeout-ms=600", "fault.enabled=true", "fault.delay-ms=10"})
class OrderApiTest extends HttpTestSupport {
 static HttpServer downstream;
 static ExecutorService executor = Executors.newCachedThreadPool();
 static volatile String mode = "ok", userTrace, productTrace, faultService, faultType;
 static {
  try {
   downstream = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
   downstream.setExecutor(executor);
   downstream.createContext("/", exchange -> {
    boolean user = exchange.getRequestURI().getPath().startsWith("/users");
    if (user) userTrace = exchange.getRequestHeaders().getFirst("X-Trace-Id");
    else {
     productTrace = exchange.getRequestHeaders().getFirst("X-Trace-Id");
     faultService = exchange.getRequestHeaders().getFirst("X-Fault-Service");
     faultType = exchange.getRequestHeaders().getFirst("X-Fault-Type");
    }
    String current = mode;
    int status = 200;
    String body = user ? "{\"id\":1,\"name\":\"User\",\"email\":\"u@example.com\"}" : "{\"id\":10,\"price\":19.95,\"stock\":10,\"name\":\"Livro\"}";
    if (!user) {
     if (current.equals("missing")) { status = 404; body = "{}"; }
     if (current.equals("error")) { status = 500; body = "{}"; }
     if (current.equals("invalid")) body = "{\"invalid\":true}";
     if (current.equals("malformed")) body = "broken-json";
     if (current.equals("timeout")) try { Thread.sleep(1200); } catch (InterruptedException e) { Thread.currentThread().interrupt(); }
    } else if (current.equals("missing-user")) { status = 404; body = "{}"; }
    byte[] bytes = body.getBytes(StandardCharsets.UTF_8);
    exchange.getResponseHeaders().set("Content-Type", "application/json");
    try { exchange.sendResponseHeaders(status, bytes.length); exchange.getResponseBody().write(bytes); }
    catch (java.io.IOException ignored) { /* caller intentionally timed out */ }
    finally { exchange.close(); }
   });
   downstream.start();
  } catch (Exception e) { throw new ExceptionInInitializerError(e); }
 }
 @DynamicPropertySource static void urls(DynamicPropertyRegistry props) {
  String url = "http://127.0.0.1:" + downstream.getAddress().getPort();
  props.add("services.user-url", () -> url); props.add("services.product-url", () -> url);
 }
 @AfterAll static void stop() { downstream.stop(0); executor.shutdownNow(); }
 @BeforeEach void reset() { mode = "ok"; userTrace = productTrace = null; }
 @Autowired OrderRepository repository;
 private String input(int quantity) { return "{\"userId\":1,\"items\":[{\"productId\":10,\"quantity\":" + quantity + "}]}"; }
 @Test void distributedCreationPropagatesTraceAndPersistsPriceSnapshot() throws Exception {
  var response = request("POST", "/orders", input(2), "X-Fault-Service", "unmatched-service", "X-Fault-Type", "internal-error");
  assertThat(response.statusCode()).isEqualTo(201);
  assertThat(tree(response).get("total").decimalValue()).isEqualByComparingTo("39.90");
  assertThat(userTrace).isEqualTo("test-trace-123"); assertThat(productTrace).isEqualTo(userTrace);
  assertThat(faultService).isEqualTo("unmatched-service"); assertThat(faultType).isEqualTo("internal-error");
  long id = tree(response).get("id").asLong();
  mode = "error"; // reads of existing orders must not consult catalog again
  var saved = request("GET", "/orders/" + id, null);
  assertThat(saved.statusCode()).isEqualTo(200);
  assertThat(tree(saved).get("items").get(0).get("subtotal").decimalValue()).isEqualByComparingTo("39.90");
  assertThat(tree(request("GET", "/orders?userId=1", null)).size()).isPositive();
 }
 @Test void downstreamFailuresNeverPersistPartialOrders() throws Exception {
  for (String scenario : new String[]{"missing", "missing-user", "error", "invalid", "malformed", "timeout"}) {
   mode = scenario; long before = repository.count();
   var response = request("POST", "/orders", input(2));
   int expected = scenario.startsWith("missing") ? 422 : scenario.equals("timeout") ? 504 : 502;
   assertThat(response.statusCode()).as(scenario + ": " + response.body()).isEqualTo(expected);
   assertThat(tree(response).get("traceId").asText()).isEqualTo("test-trace-123");
   assertThat(repository.count()).isEqualTo(before);
  }
 }
 @Test void validationStockAndInjectedErrorsDoNotWriteOrders() throws Exception {
  long before = repository.count();
  assertThat(request("POST", "/orders", input(0)).statusCode()).isEqualTo(400);
  assertThat(request("POST", "/orders", input(11)).statusCode()).isEqualTo(422);
  assertThat(request("POST", "/orders", "{\"userId\":1,\"items\":[null]}").statusCode()).isEqualTo(400);
  assertThat(request("POST", "/orders", "{\"userId\":1,\"items\":[]}").statusCode()).isEqualTo(400);
  assertThat(request("POST", "/orders", "{\"userId\":1,\"items\":[{\"productId\":10,\"quantity\":1},{\"productId\":10,\"quantity\":1}]}").statusCode()).isEqualTo(400);
  assertThat(request("POST", "/orders", input(2), "X-Fault-Service", "order-service", "X-Fault-Type", "internal-error").statusCode()).isEqualTo(500);
  assertThat(repository.count()).isEqualTo(before);
 }
}

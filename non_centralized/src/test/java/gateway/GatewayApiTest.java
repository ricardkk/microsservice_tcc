package gateway;

import com.sun.net.httpserver.HttpServer;
import java.net.InetSocketAddress;
import java.nio.charset.StandardCharsets;
import org.junit.jupiter.api.*;
import org.springframework.boot.test.context.SpringBootTest;
import org.springframework.test.context.DynamicPropertyRegistry;
import org.springframework.test.context.DynamicPropertySource;
import static org.assertj.core.api.Assertions.assertThat;

@SpringBootTest(useMainMethod = SpringBootTest.UseMainMethod.ALWAYS, webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT)
class GatewayApiTest extends HttpTestSupport {
 static HttpServer downstream;
 static volatile String path, trace, body, fault;
 static volatile int status = 200;
 static {
  try {
   downstream = HttpServer.create(new InetSocketAddress("127.0.0.1", 0), 0);
   downstream.createContext("/", exchange -> {
    path = exchange.getRequestURI().toString();
    trace = exchange.getRequestHeaders().getFirst("X-Trace-Id");
    fault = exchange.getRequestHeaders().getFirst("X-Fault-Service");
    body = new String(exchange.getRequestBody().readAllBytes(), StandardCharsets.UTF_8);
    byte[] bytes = "{\"example\":true}".getBytes(StandardCharsets.UTF_8);
    exchange.getResponseHeaders().set("Content-Type", "application/json");
    exchange.getResponseHeaders().set("Location", "/orders/42");
    exchange.sendResponseHeaders(status, bytes.length); exchange.getResponseBody().write(bytes); exchange.close();
   });
   downstream.start();
  } catch (Exception e) { throw new ExceptionInInitializerError(e); }
 }
 @DynamicPropertySource static void urls(DynamicPropertyRegistry props) {
  String url = "http://127.0.0.1:" + downstream.getAddress().getPort();
  props.add("services.user-url", () -> url); props.add("services.product-url", () -> url); props.add("services.order-url", () -> url);
 }
 @AfterAll static void stop() { downstream.stop(0); }
 @BeforeEach void reset() { status = 200; }
 @Test void routesQueriesAndPreservesUpstreamErrors() throws Exception {
  for (String resource : new String[]{"users", "products", "orders"}) {
   status = 422;
   var response = request("GET", "/api/" + resource + "?userId=1", null);
   assertThat(response.statusCode()).isEqualTo(422);
   assertThat(response.body()).isEqualTo("{\"example\":true}");
   assertThat(path).isEqualTo("/" + resource + "?userId=1");
   assertThat(trace).isEqualTo("test-trace-123");
  }
 }
 @Test void forwardsRequestBodyFaultAndLocation() throws Exception {
  status = 201;
  var response = request("POST", "/api/orders", "{\"userId\":1}", "X-Fault-Service", "product-service", "X-Fault-Type", "timeout");
  assertThat(response.statusCode()).isEqualTo(201);
  assertThat(body).isEqualTo("{\"userId\":1}");
  assertThat(fault).isEqualTo("product-service");
  assertThat(response.headers().firstValue("Location")).contains("/api/orders/42");
  assertThat(response.headers().firstValue("X-Trace-Id")).contains("test-trace-123");
 }
}

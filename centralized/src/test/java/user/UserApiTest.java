package user;
import org.junit.jupiter.api.Test;
import org.springframework.boot.test.context.SpringBootTest;
import static org.assertj.core.api.Assertions.assertThat;
@SpringBootTest(useMainMethod = SpringBootTest.UseMainMethod.ALWAYS, webEnvironment = SpringBootTest.WebEnvironment.RANDOM_PORT, properties = {
 "spring.datasource.url=jdbc:h2:mem:users;MODE=PostgreSQL;DB_CLOSE_DELAY=-1", "spring.datasource.driver-class-name=org.h2.Driver"})
@org.junit.jupiter.api.extension.ExtendWith(org.springframework.boot.test.system.OutputCaptureExtension.class)
class UserApiTest extends HttpTestSupport {
 @Test void createsReadsAndRejectsDuplicateEmail(org.springframework.boot.test.system.CapturedOutput output) throws Exception {
  String input = "{\"name\":\"Ricardo\",\"email\":\"RICARDO@example.com\"}";
  var created = request("POST", "/users", input);
  assertThat(created.statusCode()).isEqualTo(201);
  assertThat(created.headers().firstValue("X-Trace-Id")).contains("test-trace-123");
  long id = tree(created).get("id").asLong();
  var found = request("GET", "/users/" + id, null);
  assertThat(tree(found).get("email").asText()).isEqualTo("ricardo@example.com");
  assertThat(request("GET", "/users", null).statusCode()).isEqualTo(200);
  assertThat(request("POST", "/users", input).statusCode()).isEqualTo(409);
  var event = output.getAll().lines().filter(line -> line.startsWith("{") && line.contains("User created")).findFirst().orElseThrow();
  var logEntry = json.readTree(event);
  assertThat(logEntry.has("timestamp")).isTrue();
  assertThat(logEntry.get("service").asText()).isEqualTo("user-service");
  assertThat(logEntry.get("traceId").asText()).isEqualTo("test-trace-123");
  assertThat(logEntry.get("operation").asText()).isEqualTo("createUser");
 }
 @Test void invalidAndMissingResourcesHaveCorrelatedErrors() throws Exception {
  assertThat(request("POST", "/users", "{\"name\":\"\",\"email\":\"invalid\"}").statusCode()).isEqualTo(400);
  var missing = request("GET", "/users/999999", null);
  assertThat(missing.statusCode()).isEqualTo(404);
  assertThat(tree(missing).get("traceId").asText()).isEqualTo("test-trace-123");
  assertThat(request("GET", "/users/no-number", null).statusCode()).isEqualTo(400);
  assertThat(request("PUT", "/users", "{}").statusCode()).isEqualTo(405);
 }
 @Test void faultHeadersDoNothingWhenDisabled() throws Exception {
  assertThat(request("GET", "/users", null, "X-Fault-Service", "user-service", "X-Fault-Type", "internal-error").statusCode()).isEqualTo(200);
 }
}

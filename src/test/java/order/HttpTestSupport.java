package order;
import java.net.URI;
import java.net.http.*;
import java.time.Duration;
import tools.jackson.databind.JsonNode;
import tools.jackson.databind.json.JsonMapper;
import org.springframework.boot.test.web.server.LocalServerPort;
abstract class HttpTestSupport {
 @LocalServerPort int port;
 final JsonMapper json = JsonMapper.builder().build();
 final HttpClient client = HttpClient.newBuilder().connectTimeout(Duration.ofSeconds(2)).build();
 HttpResponse<String> request(String method, String path, String body, String... headers) throws Exception {
  var builder = HttpRequest.newBuilder(URI.create("http://localhost:" + port + path)).timeout(Duration.ofSeconds(5));
  builder.header("Content-Type", "application/json");
  builder.header("X-Trace-Id", "test-trace-123");
  if (headers.length > 0) builder.headers(headers);
  builder.method(method, body == null ? HttpRequest.BodyPublishers.noBody() : HttpRequest.BodyPublishers.ofString(body));
  return client.send(builder.build(), HttpResponse.BodyHandlers.ofString());
 }
 JsonNode tree(HttpResponse<String> response) { return json.readTree(response.body()); }
}

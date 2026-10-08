package gateway;

import common.*;
import jakarta.servlet.http.HttpServletRequest;
import java.net.URI;
import java.util.Map;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.beans.factory.annotation.Value;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.client.ResourceAccessException;
import org.springframework.web.client.RestClient;

@RestController
class GatewayController {
 private static final Logger log = LoggerFactory.getLogger(GatewayController.class);
 private final Map<String, RestClient> clients;
 private final Map<String, String> urls;
 GatewayController(HttpClients http, @Value("${services.user-url}") String users,
   @Value("${services.product-url}") String products, @Value("${services.order-url}") String orders) {
  urls = Map.of("users", users, "products", products, "orders", orders);
  clients = Map.of("users", http.create(users), "products", http.create(products), "orders", http.create(orders));
 }
 @RequestMapping(value = {"/api/{resource:users|products|orders}", "/api/{resource:users|products|orders}/**"},
   method = {RequestMethod.GET, RequestMethod.POST})
 ResponseEntity<byte[]> proxy(@PathVariable String resource, HttpServletRequest request,
   @RequestBody(required = false) byte[] body) {
  String path = request.getRequestURI().substring(4);
  String query = request.getQueryString();
  URI target = URI.create(urls.get(resource) + path + (query == null ? "" : "?" + query));
  var outgoing = clients.get(resource).method(HttpMethod.valueOf(request.getMethod())).uri(target);
  for (String header : new String[]{HttpHeaders.CONTENT_TYPE, HttpHeaders.ACCEPT}) {
   String value = request.getHeader(header);
   if (value != null) outgoing.header(header, value);
  }
  if (body != null && body.length > 0) outgoing.body(body);
  try {
   return outgoing.exchange((sent, received) -> {
    var headers = new HttpHeaders();
    MediaType contentType = received.getHeaders().getContentType();
    if (contentType != null) headers.setContentType(contentType);
    URI location = received.getHeaders().getLocation();
    if (location != null) headers.setLocation(URI.create("/api" + location.getRawPath()));
    int status = received.getStatusCode().value();
    log.atInfo().addKeyValue("route", resource).addKeyValue("downstreamStatus", status).log("Response forwarded");
    return new ResponseEntity<>(received.getBody().readAllBytes(), headers, received.getStatusCode());
   });
  } catch (ResourceAccessException e) { throw CommunicationErrors.map(e, resource + " service"); }
 }
}

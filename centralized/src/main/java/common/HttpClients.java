package common;

import java.net.http.HttpClient;
import java.time.Duration;
import java.util.List;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.http.client.JdkClientHttpRequestFactory;
import org.springframework.web.client.RestClient;
import org.springframework.web.context.request.RequestContextHolder;
import org.springframework.web.context.request.ServletRequestAttributes;

public class HttpClients {
 private static final Logger log = LoggerFactory.getLogger(HttpClients.class);
 private final JdkClientHttpRequestFactory factory;
 public HttpClients(long connectMs, long readMs) {
  if (connectMs <= 0 || readMs <= 0) throw new IllegalArgumentException("HTTP timeouts must be positive");
  HttpClient client = HttpClient.newBuilder().connectTimeout(Duration.ofMillis(connectMs))
    .followRedirects(HttpClient.Redirect.NEVER).build();
  factory = new JdkClientHttpRequestFactory(client);
  factory.setReadTimeout(Duration.ofMillis(readMs));
 }
 public RestClient create(String baseUrl) {
  return RestClient.builder().baseUrl(baseUrl).requestFactory(factory)
    .requestInterceptor((request, body, execution) -> {
     String trace = MDC.get("traceId");
     if (trace != null) request.getHeaders().set(TraceFilter.HEADER, trace);
     if (RequestContextHolder.getRequestAttributes() instanceof ServletRequestAttributes attrs) {
      for (String name : List.of("X-Fault-Service", "X-Fault-Type")) {
       String value = attrs.getRequest().getHeader(name);
       if (value != null) request.getHeaders().set(name, value);
      }
     }
     long start = System.nanoTime();
     log.atInfo().addKeyValue("downstream", baseUrl).addKeyValue("method", request.getMethod())
       .addKeyValue("path", request.getURI().getPath()).log("Downstream request started");
     try {
      var response = execution.execute(request, body);
      log.atInfo().addKeyValue("downstream", baseUrl).addKeyValue("downstreamStatus", response.getStatusCode().value())
        .addKeyValue("durationMs", (System.nanoTime() - start) / 1_000_000).log("Downstream response received");
      return response;
     } catch (java.io.IOException e) {
      log.atError().addKeyValue("downstream", baseUrl).setCause(e).log("Downstream communication failed");
      throw e;
     }
    }).build();
 }
}

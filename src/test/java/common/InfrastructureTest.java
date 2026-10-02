package common;

import java.net.ConnectException;
import java.net.http.HttpTimeoutException;
import org.junit.jupiter.api.Test;
import org.slf4j.MDC;
import org.springframework.mock.web.MockHttpServletRequest;
import org.springframework.mock.web.MockHttpServletResponse;
import org.springframework.web.client.ResourceAccessException;
import static org.assertj.core.api.Assertions.*;

class InfrastructureTest {
 @Test void generatedTraceIsReturnedAndMdcClearedEvenOnException() throws Exception {
  var request = new MockHttpServletRequest("GET", "/users/1");
  var response = new MockHttpServletResponse();
  request.addHeader("X-Trace-Id", "unsafe trace!");
  assertThatThrownBy(() -> new TraceFilter().doFilter(request, response, (req, res) -> {
   assertThat(MDC.get("traceId")).matches("[0-9a-f-]{36}");
   throw new jakarta.servlet.ServletException("test");
  })).isInstanceOf(jakarta.servlet.ServletException.class);
  assertThat(response.getHeader("X-Trace-Id")).matches("[0-9a-f-]{36}");
  assertThat(MDC.get("traceId")).isNull();
 }
 @Test void connectionRefusalAndTimeoutHaveDistinctDiagnosticCodes() {
  assertThat(CommunicationErrors.map(new ResourceAccessException("timeout", new HttpTimeoutException("test")), "product-service").status()).isEqualTo(504);
  assertThat(CommunicationErrors.map(new ResourceAccessException("refused", new ConnectException("test")), "product-service").code()).isEqualTo("DOWNSTREAM_UNAVAILABLE");
 }
 @Test void invalidFaultConfigurationFailsEarly() {
  assertThatThrownBy(() -> new FaultInterceptor(true, "user-service", 0)).isInstanceOf(IllegalArgumentException.class);
 }
}

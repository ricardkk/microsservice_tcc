package common;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.util.Set;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.web.servlet.HandlerInterceptor;

/** Request-scoped faults: no persistent switches or mutations. */
public class FaultInterceptor implements HandlerInterceptor {
 private static final Set<String> TYPES = Set.of("internal-error", "database", "timeout", "not-found", "invalid-response");
 private final boolean enabled;
 private final String service;
 private final long delayMs;
 public FaultInterceptor(boolean enabled, String service, long delayMs) {
  if (delayMs < 1 || delayMs > 60000) throw new IllegalArgumentException("fault.delay-ms must be between 1 and 60000");
  this.enabled = enabled; this.service = service; this.delayMs = delayMs;
 }
 @Override
 public boolean preHandle(HttpServletRequest request, HttpServletResponse response, Object handler) throws Exception {
  if (!enabled || !service.equals(request.getHeader("X-Fault-Service"))) return true;
  String type = request.getHeader("X-Fault-Type");
  if (!TYPES.contains(type == null ? "" : type)) throw new ApiFailure(400, "INVALID_FAULT", "Unknown X-Fault-Type");
  switch (type) {
   case "internal-error" -> throw new IllegalStateException("Resource processing failed");
   case "database" -> throw new DataAccessResourceFailureException("Database connection unavailable");
   case "not-found" -> throw new ApiFailure(404, "RESOURCE_NOT_FOUND", "Resource does not exist");
   case "timeout" -> {
    if (!request.getMethod().equals("GET")) throw new ApiFailure(400, "INVALID_FAULT", "Delay requires GET");
    try { Thread.sleep(delayMs); }
    catch (InterruptedException e) { Thread.currentThread().interrupt(); throw new ApiFailure(503, "PROCESSING_INTERRUPTED", "Request processing interrupted", e); }
    // A read completes normally; the caller's HTTP deadline produces the timeout.
    return true;
   }
   case "invalid-response" -> {
    if (!request.getMethod().equals("GET")) throw new ApiFailure(400, "INVALID_FAULT", "invalid-response requires GET");
    response.setContentType("application/json");
    response.getWriter().write("{\"invalid\":true}");
    return false;
   }
   default -> throw new IllegalStateException("Unexpected fault");
  }
 }
}

package common;

import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.util.Set;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.dao.DataAccessResourceFailureException;
import org.springframework.web.servlet.HandlerInterceptor;

/** Request-scoped faults: no persistent switches or mutations. */
public class FaultInterceptor implements HandlerInterceptor {
 private static final Logger log = LoggerFactory.getLogger(FaultInterceptor.class);
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
  MDC.put("faultId", service + ":" + type);
  log.atWarn().addKeyValue("faultType", type).log("Experimental fault injected");
  switch (type) {
   case "internal-error" -> throw new ApiFailure(500, "INJECTED_INTERNAL_ERROR", "Injected internal error");
   case "database" -> throw new DataAccessResourceFailureException("Simulated database failure (no real disconnection)");
   case "not-found" -> throw new ApiFailure(404, "INJECTED_NOT_FOUND", "Injected missing resource");
   case "timeout" -> {
    try { Thread.sleep(delayMs); }
    catch (InterruptedException e) { Thread.currentThread().interrupt(); throw new ApiFailure(503, "FAULT_INTERRUPTED", "Fault delay interrupted", e); }
    // Never continue to a write after the caller has timed out.
    throw new ApiFailure(504, "INJECTED_TIMEOUT", "Injected delay exceeded response deadline");
   }
   case "invalid-response" -> {
    if (!request.getMethod().equals("GET")) throw new ApiFailure(400, "INVALID_FAULT", "invalid-response requires GET");
    log.error("Returning deliberately invalid resource representation");
    response.setContentType("application/json");
    response.getWriter().write("{\"invalid\":true}");
    return false;
   }
   default -> throw new IllegalStateException("Unexpected fault");
  }
 }
}

package common;

import jakarta.servlet.FilterChain;
import jakarta.servlet.ServletException;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.UUID;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.web.filter.OncePerRequestFilter;

public class TraceFilter extends OncePerRequestFilter {
 public static final String HEADER = "X-Trace-Id";
 private static final Logger log = LoggerFactory.getLogger(TraceFilter.class);
 @Override
 protected void doFilterInternal(HttpServletRequest request, HttpServletResponse response, FilterChain chain)
   throws ServletException, IOException {
  String trace = request.getHeader(HEADER);
  if (trace == null || !trace.matches("[A-Za-z0-9._-]{1,64}")) trace = UUID.randomUUID().toString();
  long start = System.nanoTime();
  MDC.put("traceId", trace);
  MDC.put("operation", request.getMethod() + " " + request.getRequestURI());
  response.setHeader(HEADER, trace);
  try {
   log.info("Request started");
   chain.doFilter(request, response);
  } finally {
   log.atInfo().addKeyValue("status", response.getStatus())
     .addKeyValue("durationMs", (System.nanoTime() - start) / 1_000_000).log("Request completed");
   MDC.clear();
  }
 }
}

package common;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.web.servlet.config.annotation.InterceptorRegistry;
import org.springframework.web.servlet.config.annotation.WebMvcConfigurer;

@Configuration
public class InfrastructureConfiguration implements WebMvcConfigurer {
 private final FaultInterceptor faults;
 public InfrastructureConfiguration(@Value("${fault.enabled:false}") boolean enabled,
   @Value("${spring.application.name}") String service, @Value("${fault.delay-ms:5000}") long delay) {
  faults = new FaultInterceptor(enabled, service, delay);
 }
 @Bean TraceFilter traceFilter() { return new TraceFilter(); }
 @Bean ApiExceptionHandler apiExceptionHandler() { return new ApiExceptionHandler(); }
 @Bean HttpClients httpClients(@Value("${http.connect-timeout-ms:1000}") long connect,
   @Value("${http.read-timeout-ms:2000}") long read) { return new HttpClients(connect, read); }
 @Override public void addInterceptors(InterceptorRegistry registry) {
  registry.addInterceptor(faults).addPathPatterns("/users/**", "/products/**", "/orders/**", "/api/**");
 }
}

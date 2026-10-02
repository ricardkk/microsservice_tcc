package gateway;
import common.InfrastructureConfiguration;
import java.util.Map;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Import;
@SpringBootApplication
@Import(InfrastructureConfiguration.class)
public class GatewayApplication {
 public static void main(String[] args) {
  var application = new SpringApplication(GatewayApplication.class);
  application.setDefaultProperties(Map.of("spring.config.additional-location", "classpath:/services/gateway/"));
  application.run(args);
 }
}

package order;
import common.InfrastructureConfiguration;
import java.util.Map;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Import;
@SpringBootApplication
@Import(InfrastructureConfiguration.class)
public class OrderApplication {
 public static void main(String[] args) {
  var application = new SpringApplication(OrderApplication.class);
  application.setDefaultProperties(Map.of("spring.config.additional-location", "classpath:/services/order-service/"));
  application.run(args);
 }
}

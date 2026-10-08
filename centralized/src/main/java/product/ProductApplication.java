package product;
import common.InfrastructureConfiguration;
import java.util.Map;
import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;
import org.springframework.context.annotation.Import;
@SpringBootApplication
@Import(InfrastructureConfiguration.class)
public class ProductApplication {
 public static void main(String[] args) {
  var application = new SpringApplication(ProductApplication.class);
  application.setDefaultProperties(Map.of("spring.config.additional-location", "classpath:/services/product-service/"));
  application.run(args);
 }
}

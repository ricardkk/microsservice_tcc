package user;

import common.ApiFailure;
import jakarta.validation.Valid;
import jakarta.validation.constraints.*;
import java.net.URI;
import java.time.Instant;
import java.util.List;
import java.util.Locale;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.springframework.data.domain.Sort;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

@RestController @RequestMapping("/users")
class UserController {
 private static final Logger log = LoggerFactory.getLogger(UserController.class);
 private final UserRepository users;
 UserController(UserRepository users) { this.users = users; }
 record CreateUser(@NotBlank @Size(max = 120) String name, @NotBlank @Email @Size(max = 254) String email) {}
 record UserResponse(Long id, String name, String email, Instant createdAt) {
  static UserResponse from(UserEntity u) { return new UserResponse(u.id, u.name, u.email, u.createdAt); }
 }
 @PostMapping ResponseEntity<UserResponse> create(@Valid @RequestBody CreateUser input) {
  var user = users.saveAndFlush(new UserEntity(input.name().trim(), input.email().trim().toLowerCase(Locale.ROOT)));
  org.slf4j.MDC.put("operation", "createUser");
  log.atInfo().addKeyValue("userId", user.id).log("User created");
  return ResponseEntity.created(URI.create("/users/" + user.id)).body(UserResponse.from(user));
 }
 @GetMapping("/{id}") UserResponse get(@PathVariable Long id) {
  var user = users.findById(id).orElseThrow(() -> new ApiFailure(404, "USER_NOT_FOUND", "User does not exist"));
  org.slf4j.MDC.put("operation", "getUser");
  log.atInfo().addKeyValue("userId", id).log("User retrieved");
  return UserResponse.from(user);
 }
 @GetMapping List<UserResponse> list() {
  return users.findAll(Sort.by("id")).stream().map(UserResponse::from).toList();
 }
}

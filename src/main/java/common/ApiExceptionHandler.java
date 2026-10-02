package common;

import java.time.Instant;
import java.util.List;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;
import org.slf4j.MDC;
import org.springframework.dao.DataAccessException;
import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.ResponseEntity;
import org.springframework.http.converter.HttpMessageNotReadableException;
import org.springframework.web.bind.MethodArgumentNotValidException;
import org.springframework.web.bind.annotation.ExceptionHandler;
import org.springframework.web.bind.annotation.RestControllerAdvice;
import org.springframework.web.method.annotation.MethodArgumentTypeMismatchException;

@RestControllerAdvice
public class ApiExceptionHandler {
 private static final Logger log = LoggerFactory.getLogger(ApiExceptionHandler.class);
 public record ErrorBody(Instant timestamp, int status, String code, String message, String traceId, List<String> details) {}
 @ExceptionHandler(ApiFailure.class)
 ResponseEntity<ErrorBody> failure(ApiFailure e) { return error(e.status(), e.code(), e.getMessage(), List.of(), e); }
 @ExceptionHandler(MethodArgumentNotValidException.class)
 ResponseEntity<ErrorBody> validation(MethodArgumentNotValidException e) {
  List<String> details = e.getBindingResult().getFieldErrors().stream()
    .map(f -> f.getField() + ": " + f.getDefaultMessage()).sorted().toList();
  return error(400, "VALIDATION_ERROR", "Request validation failed", details, e);
 }
 @ExceptionHandler({HttpMessageNotReadableException.class, MethodArgumentTypeMismatchException.class})
 ResponseEntity<ErrorBody> malformed(Exception e) { return error(400, "INVALID_REQUEST", "Invalid JSON or parameter", List.of(), e); }
 @ExceptionHandler(DataIntegrityViolationException.class)
 ResponseEntity<ErrorBody> conflict(DataIntegrityViolationException e) {
  return error(409, "DATA_CONFLICT", "Data violates a uniqueness or integrity constraint", List.of(), e);
 }
 @ExceptionHandler({DataAccessException.class, org.springframework.transaction.CannotCreateTransactionException.class})
 ResponseEntity<ErrorBody> database(Exception e) {
  return error(503, "DATABASE_UNAVAILABLE", "Database operation failed", List.of(), e);
 }
 @ExceptionHandler(Exception.class)
 ResponseEntity<ErrorBody> unexpected(Exception e) {
  if (e instanceof org.springframework.web.ErrorResponse httpError)
   return error(httpError.getStatusCode().value(), "HTTP_ERROR", "Request could not be handled", List.of(), e);
  return error(500, "INTERNAL_ERROR", "Unexpected processing error", List.of(), e);
 }
 private ResponseEntity<ErrorBody> error(int status, String code, String message, List<String> details, Exception cause) {
  if (status >= 500) log.atError().addKeyValue("errorCode", code).addKeyValue("status", status).setCause(cause).log(message);
  else log.atWarn().addKeyValue("errorCode", code).addKeyValue("status", status).log(message);
  return ResponseEntity.status(status).body(new ErrorBody(Instant.now(), status, code, message, MDC.get("traceId"), details));
 }
}

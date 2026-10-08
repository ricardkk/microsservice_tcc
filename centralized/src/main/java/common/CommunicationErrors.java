package common;

import java.net.http.HttpTimeoutException;
import org.springframework.web.client.ResourceAccessException;

public final class CommunicationErrors {
 private CommunicationErrors() {}
 public static ApiFailure map(ResourceAccessException error, String service) {
  for (Throwable cause = error; cause != null; cause = cause.getCause()) {
   if (cause instanceof HttpTimeoutException || cause instanceof java.net.SocketTimeoutException)
    return new ApiFailure(504, "DOWNSTREAM_TIMEOUT", "Timeout calling " + service, error);
  }
  return new ApiFailure(502, "DOWNSTREAM_UNAVAILABLE", "Could not connect to " + service, error);
 }
}

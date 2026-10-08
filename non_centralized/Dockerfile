FROM maven:3.9.15-eclipse-temurin-21 AS build
WORKDIR /workspace
COPY . .
RUN mvn -B -DskipTests package

FROM eclipse-temurin:21-jre-jammy
RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/* \
    && groupadd --system tcc && useradd --system --gid tcc tcc
WORKDIR /app
ARG SERVICE
COPY --from=build /workspace/target/microservices-1.0.0-SNAPSHOT-${SERVICE}.jar app.jar
USER tcc
EXPOSE 8080
ENTRYPOINT ["java", "-jar", "/app/app.jar"]

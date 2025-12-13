FROM maven:3.9.6-eclipse-temurin-17 AS build
WORKDIR /app
COPY pom.xml .
COPY src ./src
RUN mvn clean package -DskipTests

# Use JDK instead of JRE for javac
FROM eclipse-temurin:17-jdk-alpine
WORKDIR /app
COPY --from=build /app/target/analysis-engine-0.0.1-SNAPSHOT.jar app.jar

# Install wget and tar for downloading SpotBugs
RUN apk add --no-cache wget tar

# Install SpotBugs
ENV SPOTBUGS_VERSION=4.8.3
RUN wget https://github.com/spotbugs/spotbugs/releases/download/${SPOTBUGS_VERSION}/spotbugs-${SPOTBUGS_VERSION}.tgz && \
    tar -xzf spotbugs-${SPOTBUGS_VERSION}.tgz && \
    rm spotbugs-${SPOTBUGS_VERSION}.tgz && \
    mv spotbugs-${SPOTBUGS_VERSION} /opt/spotbugs

# Add SpotBugs to PATH
ENV PATH="/opt/spotbugs/bin:${PATH}"

EXPOSE 8080
ENTRYPOINT ["java", "-jar", "app.jar"]

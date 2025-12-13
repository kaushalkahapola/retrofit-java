# Local Development Guide

This guide explains how to run the Backporting Tool components locally without using Docker.

## Prerequisites

*   **Java 17+**: Required for the Analysis Engine.
*   **Maven**: Required to build the Analysis Engine.
*   **Python 3.10+**: Required for the Orchestrator.
*   **pip**: Python package manager.

## 1. Analysis Engine (Java)

The Analysis Engine is a Spring Boot application that exposes tools via MCP over SSE.

### Build and Run

1.  Navigate to the `analysis-engine` directory:
    ```bash
    cd analysis-engine
    ```

2.  Run the application using Maven:
    ```bash
    mvn spring-boot:run
    ```
    Alternatively, you can build the JAR and run it:
    ```bash
    mvn clean package
    java -jar target/analysis-engine-0.0.1-SNAPSHOT.jar
    ```

3.  **Verify**: The server should start on port `8080`. You can check the SSE endpoint at `http://localhost:8080/mcp/sse` (it will hang waiting for events, which is normal).

## 2. Orchestrator (Python)

The Orchestrator is a Python application that connects to the Analysis Engine.

### Setup

1.  Navigate to the `agents-backend` directory:
    ```bash
    cd agents-backend
    ```

2.  Create a virtual environment (optional but recommended):
    ```bash
    python -m venv venv
    # Windows
    venv\Scripts\activate
    # Linux/Mac
    source venv/bin/activate
    ```

3.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

### Run

1.  Ensure the Analysis Engine is running on `http://localhost:8080`.

2.  Run the Orchestrator:
    ```bash
    # The script defaults to http://localhost:8080/mcp/sse
    python src/main.py
    ```

    If you need to change the URL, set the `MCP_SERVER_URL` environment variable:
    ```bash
    # Windows (PowerShell)
    $env:MCP_SERVER_URL="http://localhost:9090/mcp/sse"
    python src/main.py
    ```

## Troubleshooting

*   **Connection Refused**: Ensure the Analysis Engine is fully started before running the Orchestrator.
*   **Port Conflicts**: If port 8080 is in use, change `server.port` in `analysis-engine/src/main/resources/application.properties` (create the file if it doesn't exist) and update the URL in the Orchestrator.

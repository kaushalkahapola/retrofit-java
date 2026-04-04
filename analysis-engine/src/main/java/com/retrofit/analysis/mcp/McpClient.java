package com.retrofit.analysis.mcp;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.springframework.stereotype.Component;
import java.io.IOException;
import java.net.URI;
import java.net.http.HttpClient;
import java.net.http.HttpRequest;
import java.net.http.HttpResponse;
import java.time.Duration;
import java.util.concurrent.*;

/**
 * MCP Client for communicating with the MCP server.
 * Provides methods for calling MCP tools with connection pooling and caching.
 */
@Component
public class McpClient {
    
    private final HttpClient httpClient;
    private final ObjectMapper objectMapper;
    private final String mcpServerUrl;
    private final ExecutorService executorService;
    private final ConcurrentHashMap<String, Object> responseCache;
    private final int cacheExpirationSeconds;

    public McpClient(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
        this.mcpServerUrl = System.getenv("MCP_SERVER_URL");
        
        // Create HTTP client with connection pooling
        this.httpClient = HttpClient.newBuilder()
            .version(HttpClient.Version.HTTP_2)
            .connectTimeout(Duration.ofSeconds(30))
            .executor(Executors.newFixedThreadPool(10))
            .build();
        
        this.executorService = Executors.newFixedThreadPool(5);
        this.responseCache = new ConcurrentHashMap<>();
        this.cacheExpirationSeconds = 300; // 5 minutes
    }

    /**
     * Call an MCP tool synchronously.
     * 
     * @param toolName Name of the MCP tool
     * @param arguments Tool arguments as JsonNode
     * @return Response from the tool
     */
    public JsonNode callTool(String toolName, JsonNode arguments) throws IOException, InterruptedException {
        // Check cache first
        String cacheKey = generateCacheKey(toolName, arguments);
        if (responseCache.containsKey(cacheKey)) {
            return (JsonNode) responseCache.get(cacheKey);
        }

        String requestId = java.util.UUID.randomUUID().toString();
        ObjectMapper mapper = new ObjectMapper();
        
        // Build MCP request
        var request = mapper.createObjectNode();
        request.put("jsonrpc", "2.0");
        request.put("id", requestId);
        request.put("method", "tools/call");
        
        var params = request.putObject("params");
        params.put("name", toolName);
        params.set("arguments", arguments);

        String requestBody = mapper.writeValueAsString(request);

        // Send request
        HttpRequest httpRequest = HttpRequest.newBuilder()
            .uri(URI.create(mcpServerUrl + "/mcp/sync/call"))
            .header("Content-Type", "application/json")
            .POST(HttpRequest.BodyPublishers.ofString(requestBody))
            .timeout(Duration.ofSeconds(60))
            .build();

        HttpResponse<String> response = httpClient.send(httpRequest, HttpResponse.BodyHandlers.ofString());

        if (response.statusCode() != 200) {
            throw new IOException("MCP server returned status " + response.statusCode());
        }

        JsonNode responseNode = mapper.readTree(response.body());
        
        // Cache the response
        if (responseNode.has("result")) {
            responseCache.put(cacheKey, responseNode.get("result"));
        }

        return responseNode;
    }

    /**
     * Call an MCP tool asynchronously.
     * 
     * @param toolName Name of the MCP tool
     * @param arguments Tool arguments as JsonNode
     * @return CompletableFuture with the response
     */
    public CompletableFuture<JsonNode> callToolAsync(String toolName, JsonNode arguments) {
        return CompletableFuture.supplyAsync(() -> {
            try {
                return callTool(toolName, arguments);
            } catch (Exception e) {
                throw new RuntimeException(e);
            }
        }, executorService);
    }

    /**
     * Generate a cache key for a tool call.
     */
    private String generateCacheKey(String toolName, JsonNode arguments) {
        try {
            return toolName + ":" + objectMapper.writeValueAsString(arguments);
        } catch (Exception e) {
            return toolName + ":" + arguments.toString();
        }
    }

    /**
     * Clear the response cache.
     */
    public void clearCache() {
        responseCache.clear();
    }

    /**
     * Shutdown the client and release resources.
     */
    public void shutdown() {
        executorService.shutdown();
        try {
            if (!executorService.awaitTermination(30, TimeUnit.SECONDS)) {
                executorService.shutdownNow();
            }
        } catch (InterruptedException e) {
            executorService.shutdownNow();
        }
    }

    /**
     * Check if the MCP server is reachable.
     */
    public boolean isHealthy() {
        try {
            HttpRequest request = HttpRequest.newBuilder()
                .uri(URI.create(mcpServerUrl + "/mcp/sync/call"))
                .timeout(Duration.ofSeconds(5))
                .HEAD()
                .build();
            HttpResponse<Void> response = httpClient.send(request, HttpResponse.BodyHandlers.discarding());
            return response.statusCode() >= 200 && response.statusCode() < 300;
        } catch (Exception e) {
            return false;
        }
    }
}

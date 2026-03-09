package com.retrofit.analysis.mcp;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.fasterxml.jackson.databind.node.ArrayNode;
import com.fasterxml.jackson.databind.node.ObjectNode;
import com.retrofit.analysis.tools.GetDependencyTool;
import com.retrofit.analysis.tools.GetClassContextTool;
import com.retrofit.analysis.tools.GetJavaVersionTool;
import com.retrofit.analysis.tools.CompileTool;
import com.retrofit.analysis.tools.SpotBugsTool;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.servlet.mvc.method.annotation.SseEmitter;

import java.util.ArrayList;
import java.util.List;
import java.util.Map;
import java.util.concurrent.ConcurrentHashMap;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;

@RestController
@RequestMapping("/mcp")
public class McpServer {

    private final GetJavaVersionTool getJavaVersionTool;
    private final GetDependencyTool getDependencyTool;
    private final GetClassContextTool getClassContextTool;
    private final CompileTool compileTool;
    private final SpotBugsTool spotBugsTool;
    private final ObjectMapper objectMapper;
    private final Map<String, SseEmitter> emitters = new ConcurrentHashMap<>();
    private final ExecutorService executor = Executors.newCachedThreadPool();

    public McpServer(GetJavaVersionTool getJavaVersionTool, GetDependencyTool getDependencyTool,
            GetClassContextTool getClassContextTool, CompileTool compileTool, SpotBugsTool spotBugsTool,
            ObjectMapper objectMapper) {
        this.getJavaVersionTool = getJavaVersionTool;
        this.getDependencyTool = getDependencyTool;
        this.getClassContextTool = getClassContextTool;
        this.compileTool = compileTool;
        this.spotBugsTool = spotBugsTool;
        this.objectMapper = objectMapper;
    }

    @GetMapping(value = "/sse", produces = org.springframework.http.MediaType.TEXT_EVENT_STREAM_VALUE)
    public SseEmitter handleSse() {
        SseEmitter emitter = new SseEmitter(Long.MAX_VALUE);
        String id = java.util.UUID.randomUUID().toString();
        emitters.put(id, emitter);

        System.out.println("SSE Connection initiated: " + id);

        emitter.onCompletion(() -> {
            System.out.println("SSE Completed: " + id);
            emitters.remove(id);
        });
        emitter.onTimeout(() -> {
            System.out.println("SSE Timeout: " + id);
            emitters.remove(id);
        });
        emitter.onError((e) -> {
            System.out.println("SSE Error [" + id + "]: " + e.getMessage());
            emitters.remove(id);
        });

        executor.submit(() -> {
            try {
                // Wait a bit to ensure connection is established
                Thread.sleep(500);
                String endpointUri = "/mcp/messages?sessionId=" + id;
                System.out.println("Sending endpoint event to " + id + ": " + endpointUri);
                emitter.send(SseEmitter.event().name("endpoint").data(endpointUri));
            } catch (Exception e) {
                System.out.println("Error sending endpoint event to " + id + ": " + e.getMessage());
                emitters.remove(id);
            }
        });

        return emitter;
    }

    @PostMapping("/sync/call")
    public JsonNode handleSyncCall(@RequestBody JsonNode request) {
        System.out.println("Received SYNC request");
        return processRequest(request);
    }

    @SuppressWarnings("null")
    @PostMapping("/messages")
    public void handleMessage(@RequestParam String sessionId, @RequestBody JsonNode request) {
        SseEmitter emitter = emitters.get(sessionId);
        if (emitter == null) {
            System.out.println("Session not found for message: " + sessionId);
            throw new IllegalArgumentException("Session not found: " + sessionId);
        }

        executor.submit(() -> {
            try {
                JsonNode response = processRequest(request);
                // Send response via SSE
                String responseString = objectMapper.writeValueAsString(response);
                System.out.println("Sending response [" + sessionId + "]");
                emitter.send(SseEmitter.event().name("message").data(responseString));
            } catch (Exception e) {
                System.out.println("Error handling request for " + sessionId + ": " + e.getMessage());
                e.printStackTrace();
            }
        });
    }

    private JsonNode processRequest(JsonNode request) {
        if (!request.has("id")) {
            System.out.println("Received notification (ignoring for sync)");
            return objectMapper.createObjectNode();
        }

        String id = request.get("id").asText();
        String method = request.get("method").asText();

        if ("initialize".equals(method)) {
            ObjectNode response = objectMapper.createObjectNode();
            response.put("jsonrpc", "2.0");
            response.put("id", id);
            ObjectNode result = response.putObject("result");
            result.put("protocolVersion", "2024-11-05");
            ObjectNode capabilities = result.putObject("capabilities");
            capabilities.putObject("tools");
            ObjectNode serverInfo = result.putObject("serverInfo");
            serverInfo.put("name", "analysis-engine");
            serverInfo.put("version", "0.1.0");
            return response;
        } else if ("tools/list".equals(method)) {
            return createToolsListResponse(id);
        } else if ("tools/call".equals(method)) {
            return handleToolCall(request);
        } else {
            return createErrorResponse(id, -32601, "Method not found");
        }
    }

    private JsonNode createToolsListResponse(String id) {
        ObjectNode response = objectMapper.createObjectNode();
        response.put("jsonrpc", "2.0");
        response.put("id", id);

        ObjectNode result = response.putObject("result");
        ArrayNode tools = result.putArray("tools");

        // Tool: get_java_version
        ObjectNode tool1 = tools.addObject();
        tool1.put("name", "get_java_version");
        tool1.put("description", "Returns the Java version of the analysis engine");
        tool1.putObject("inputSchema").put("type", "object");

        // Tool: get_dependency_graph
        ObjectNode depTool = tools.addObject();
        depTool.put("name", "get_dependency_graph");
        depTool.put("description", "Analyzes dependencies between a list of Java files.");
        ObjectNode depSchema = depTool.putObject("inputSchema");
        depSchema.put("type", "object");
        ObjectNode depProps = depSchema.putObject("properties");
        depProps.putObject("target_repo_path").put("type", "string");
        depProps.putObject("file_paths").put("type", "array").putObject("items").put("type", "string");
        depProps.putObject("explore_neighbors").put("type", "boolean").put("description",
                "If true, also analyzes files in the same directory as the input files.");
        ArrayNode depRequired = depSchema.putArray("required");
        depRequired.add("target_repo_path");
        depRequired.add("file_paths");

        // Tool: get_class_context
        ObjectNode ctxTool = tools.addObject();
        ctxTool.put("name", "get_class_context");
        ctxTool.put("description", "Reads a Java file and returns a skeleton view with focused method body");
        ObjectNode ctxSchema = ctxTool.putObject("inputSchema");
        ctxSchema.put("type", "object");
        ObjectNode ctxProps = ctxSchema.putObject("properties");
        ctxProps.putObject("target_repo_path").put("type", "string");
        ctxProps.putObject("file_path").put("type", "string");
        ctxProps.putObject("focus_method").put("type", "string");
        ArrayNode ctxRequired = ctxSchema.putArray("required");
        ctxRequired.add("target_repo_path");
        ctxRequired.add("file_path");

        // Tool: compile
        ObjectNode compTool = tools.addObject();
        compTool.put("name", "compile");
        compTool.put("description", "Compiles Java files using javac -Xlint");
        ObjectNode compSchema = compTool.putObject("inputSchema");
        compSchema.put("type", "object");
        ObjectNode compProps = compSchema.putObject("properties");
        compProps.putObject("target_repo_path").put("type", "string");
        compProps.putObject("file_paths").put("type", "array").putObject("items").put("type", "string");
        ArrayNode compRequired = compSchema.putArray("required");
        compRequired.add("target_repo_path");
        compRequired.add("file_paths");

        // Tool: spotbugs
        ObjectNode sbTool = tools.addObject();
        sbTool.put("name", "spotbugs");
        sbTool.put("description", "Runs SpotBugs on compiled classes");
        ObjectNode sbSchema = sbTool.putObject("inputSchema");
        sbSchema.put("type", "object");
        ObjectNode sbProps = sbSchema.putObject("properties");
        sbProps.putObject("compiled_classes_path").put("type", "string");
        sbProps.putObject("source_path").put("type", "string");
        ArrayNode sbRequired = sbSchema.putArray("required");
        sbRequired.add("compiled_classes_path");

        return response;
    }

    private JsonNode handleToolCall(JsonNode request) {
        String id = request.get("id").asText();
        JsonNode params = request.get("params");
        String toolName = params.get("name").asText();
        JsonNode arguments = params.get("arguments");

        try {
            if ("get_java_version".equals(toolName)) {
                return createToolResponse(id, getJavaVersionTool.execute());
            } else if ("get_dependency_graph".equals(toolName)) {
                String repoPath = arguments.get("target_repo_path").asText();
                List<String> filePaths = new ArrayList<>();
                if (arguments.has("file_paths")) {
                    arguments.get("file_paths").forEach(node -> filePaths.add(node.asText()));
                }
                boolean exploreNeighbors = arguments.has("explore_neighbors")
                        && arguments.get("explore_neighbors").asBoolean();

                Map<String, Object> graph = getDependencyTool.execute(repoPath, filePaths, exploreNeighbors);
                return createToolResponse(id, graph);
            } else if ("get_class_context".equals(toolName)) {
                String repoPath = arguments.get("target_repo_path").asText();
                String filePath = arguments.get("file_path").asText();
                String focusMethod = arguments.has("focus_method") ? arguments.get("focus_method").asText() : null;

                Map<String, Object> context = getClassContextTool.execute(repoPath, filePath, focusMethod);
                return createToolResponse(id, context);
            } else if ("compile".equals(toolName)) {
                String repoPath = arguments.get("target_repo_path").asText();
                List<String> filePaths = new ArrayList<>();
                if (arguments.has("file_paths")) {
                    arguments.get("file_paths").forEach(node -> filePaths.add(node.asText()));
                }
                Map<String, Object> result = compileTool.execute(repoPath, filePaths);
                return createToolResponse(id, result);
            } else if ("spotbugs".equals(toolName)) {
                String compiledClassesPath = arguments.get("compiled_classes_path").asText();
                String sourcePath = arguments.has("source_path") ? arguments.get("source_path").asText() : null;
                Map<String, Object> result = spotBugsTool.execute(compiledClassesPath, sourcePath);
                return createToolResponse(id, result);
            } else {
                return createErrorResponse(id, -32601, "Tool not found: " + toolName);
            }
        } catch (Exception e) {
            return createErrorResponse(id, -32603, "Internal error: " + e.getMessage());
        }
    }

    private JsonNode createErrorResponse(String id, int code, String message) {
        ObjectNode response = objectMapper.createObjectNode();
        response.put("jsonrpc", "2.0");
        response.put("id", id);
        ObjectNode error = response.putObject("error");
        error.put("code", code);
        error.put("message", message);
        return response;
    }

    private JsonNode createToolResponse(String id, Object resultData) {
        ObjectNode response = objectMapper.createObjectNode();
        response.put("jsonrpc", "2.0");
        response.put("id", id);
        try {
            ObjectNode result = response.putObject("result");
            var contentArray = result.putArray("content");
            var textContent = contentArray.addObject();
            textContent.put("type", "text");
            textContent.put("text", objectMapper.writeValueAsString(resultData));
        } catch (Exception e) {
            return createErrorResponse(id, -32603, "Serialization error: " + e.getMessage());
        }
        return response;
    }
}

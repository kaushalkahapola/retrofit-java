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
import com.retrofit.analysis.tools.GetStructuralAnalysisTool;
import com.retrofit.analysis.tools.ReplaceMethodBodyTool;
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
    private final GetStructuralAnalysisTool getStructuralAnalysisTool;
    private final ReplaceMethodBodyTool replaceMethodBodyTool;
    private final ObjectMapper objectMapper;
    private final Map<String, SseEmitter> emitters = new ConcurrentHashMap<>();
    private final ExecutorService executor = Executors.newCachedThreadPool();

    public McpServer(GetJavaVersionTool getJavaVersionTool, GetDependencyTool getDependencyTool,
            GetClassContextTool getClassContextTool, CompileTool compileTool, SpotBugsTool spotBugsTool,
            GetStructuralAnalysisTool getStructuralAnalysisTool, ReplaceMethodBodyTool replaceMethodBodyTool,
            ObjectMapper objectMapper) {
        this.getJavaVersionTool = getJavaVersionTool;
        this.getDependencyTool = getDependencyTool;
        this.getClassContextTool = getClassContextTool;
        this.compileTool = compileTool;
        this.spotBugsTool = spotBugsTool;
        this.getStructuralAnalysisTool = getStructuralAnalysisTool;
        this.replaceMethodBodyTool = replaceMethodBodyTool;
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
        sbProps.putObject("compiled_classes_paths").put("type", "array").putObject("items").put("type", "string");
        sbProps.putObject("source_path").put("type", "string");
        sbProps.putObject("aux_classpath").put("type", "array").putObject("items").put("type", "string");
        ArrayNode sbRequired = sbSchema.putArray("required");
        sbRequired.add("compiled_classes_paths");

        // Tool: get_structural_analysis
        ObjectNode strTool = tools.addObject();
        strTool.put("name", "get_structural_analysis");
        strTool.put("description", "Analyzes the structural properties of a Java file including classes, methods, fields, and call relationships");
        ObjectNode strSchema = strTool.putObject("inputSchema");
        strSchema.put("type", "object");
        ObjectNode strProps = strSchema.putObject("properties");
        strProps.putObject("target_repo_path").put("type", "string");
        strProps.putObject("file_path").put("type", "string");
        ArrayNode strRequired = strSchema.putArray("required");
        strRequired.add("target_repo_path");
        strRequired.add("file_path");

        // Tool: replace_method_body (AST-based, immune to line drift)
        ObjectNode replaceTool = tools.addObject();
        replaceTool.put("name", "replace_method_body");
        replaceTool.put("description", "Replace the body of a method or constructor using AST-based approach. Immune to line number drift. Matches method by signature.");
        ObjectNode replaceSchema = replaceTool.putObject("inputSchema");
        replaceSchema.put("type", "object");
        ObjectNode replaceProps = replaceSchema.putObject("properties");
        replaceProps.putObject("target_repo_path").put("type", "string").put("description", "Root path of the repository");
        replaceProps.putObject("file_path").put("type", "string").put("description", "Relative path to the Java file");
        replaceProps.putObject("method_signature").put("type", "string").put("description", "Method/constructor signature (e.g., 'doSomething(String arg1, int arg2)' or 'ClassName(Type param)')");
        replaceProps.putObject("new_body").put("type", "string").put("description", "Complete method body code (without curly braces)");
        ArrayNode replaceRequired = replaceSchema.putArray("required");
        replaceRequired.add("target_repo_path");
        replaceRequired.add("file_path");
        replaceRequired.add("method_signature");
        replaceRequired.add("new_body");

        // Tool: get_method_boundaries (returns exact line numbers)
        ObjectNode boundariesTool = tools.addObject();
        boundariesTool.put("name", "get_method_boundaries");
        boundariesTool.put("description", "Get the exact line number boundaries of a method or constructor without line drift issues");
        ObjectNode boundariesSchema = boundariesTool.putObject("inputSchema");
        boundariesSchema.put("type", "object");
        ObjectNode boundariesProps = boundariesSchema.putObject("properties");
        boundariesProps.putObject("target_repo_path").put("type", "string");
        boundariesProps.putObject("file_path").put("type", "string");
        boundariesProps.putObject("method_signature").put("type", "string").put("description", "Method/constructor signature to locate");
        ArrayNode boundariesRequired = boundariesSchema.putArray("required");
        boundariesRequired.add("target_repo_path");
        boundariesRequired.add("file_path");
        boundariesRequired.add("method_signature");

        // Tool: replace_field (full implementation for field replacement)
        ObjectNode replaceFieldTool = tools.addObject();
        replaceFieldTool.put("name", "replace_field");
        replaceFieldTool.put("description", "Replace a field declaration in a Java file using AST-based approach");
        ObjectNode replaceFieldSchema = replaceFieldTool.putObject("inputSchema");
        replaceFieldSchema.put("type", "object");
        ObjectNode replaceFieldProps = replaceFieldSchema.putObject("properties");
        replaceFieldProps.putObject("target_repo_path").put("type", "string");
        replaceFieldProps.putObject("file_path").put("type", "string");
        replaceFieldProps.putObject("field_name").put("type", "string").put("description", "Name of the field to replace");
        replaceFieldProps.putObject("new_declaration").put("type", "string").put("description", "Complete field declaration");
        ArrayNode replaceFieldRequired = replaceFieldSchema.putArray("required");
        replaceFieldRequired.add("target_repo_path");
        replaceFieldRequired.add("file_path");
        replaceFieldRequired.add("field_name");
        replaceFieldRequired.add("new_declaration");

        // Tool: insert_import (AST-based import management)
        ObjectNode insertImportTool = tools.addObject();
        insertImportTool.put("name", "insert_import");
        insertImportTool.put("description", "Insert an import statement into a Java file. Automatically avoids duplicates.");
        ObjectNode insertImportSchema = insertImportTool.putObject("inputSchema");
        insertImportSchema.put("type", "object");
        ObjectNode insertImportProps = insertImportSchema.putObject("properties");
        insertImportProps.putObject("target_repo_path").put("type", "string");
        insertImportProps.putObject("file_path").put("type", "string");
        insertImportProps.putObject("import_statement").put("type", "string").put("description", "Import statement (e.g., 'java.util.List' or 'java.util.*')");
        ArrayNode insertImportRequired = insertImportSchema.putArray("required");
        insertImportRequired.add("target_repo_path");
        insertImportRequired.add("file_path");
        insertImportRequired.add("import_statement");

        // Tool: remove_method (AST-based method deletion)
        ObjectNode removeMethodTool = tools.addObject();
        removeMethodTool.put("name", "remove_method");
        removeMethodTool.put("description", "Remove a method from a Java file using AST-based approach");
        ObjectNode removeMethodSchema = removeMethodTool.putObject("inputSchema");
        removeMethodSchema.put("type", "object");
        ObjectNode removeMethodProps = removeMethodSchema.putObject("properties");
        removeMethodProps.putObject("target_repo_path").put("type", "string");
        removeMethodProps.putObject("file_path").put("type", "string");
        removeMethodProps.putObject("method_signature").put("type", "string").put("description", "Method signature to remove (supports wildcards like 'method(...)')");
        ArrayNode removeMethodRequired = removeMethodSchema.putArray("required");
        removeMethodRequired.add("target_repo_path");
        removeMethodRequired.add("file_path");
        removeMethodRequired.add("method_signature");

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
                List<String> compiledClassesPaths = new ArrayList<>();
                if (arguments.has("compiled_classes_paths")) {
                    arguments.get("compiled_classes_paths").forEach(node -> compiledClassesPaths.add(node.asText()));
                }
                String sourcePath = arguments.has("source_path") ? arguments.get("source_path").asText() : null;
                List<String> auxClasspath = new ArrayList<>();
                if (arguments.has("aux_classpath")) {
                    arguments.get("aux_classpath").forEach(node -> auxClasspath.add(node.asText()));
                }
                Map<String, Object> result = spotBugsTool.execute(compiledClassesPaths, sourcePath, auxClasspath);
                return createToolResponse(id, result);
            } else if ("get_structural_analysis".equals(toolName)) {
                String repoPath = arguments.get("target_repo_path").asText();
                String filePath = arguments.get("file_path").asText();
                Map<String, Object> result = getStructuralAnalysisTool.execute(repoPath, filePath);
                return createToolResponse(id, result);
            } else if ("replace_method_body".equals(toolName)) {
                String repoPath = arguments.get("target_repo_path").asText();
                String filePath = arguments.get("file_path").asText();
                String methodSignature = arguments.get("method_signature").asText();
                String newBody = arguments.get("new_body").asText();
                Map<String, Object> result = replaceMethodBodyTool.execute(repoPath, filePath, methodSignature, newBody);
                return createToolResponse(id, result);
            } else if ("get_method_boundaries".equals(toolName)) {
                String repoPath = arguments.get("target_repo_path").asText();
                String filePath = arguments.get("file_path").asText();
                String methodSignature = arguments.get("method_signature").asText();
                Map<String, Object> result = replaceMethodBodyTool.executeGetMethodBoundaries(repoPath, filePath, methodSignature);
                return createToolResponse(id, result);
            } else if ("replace_field".equals(toolName)) {
                String repoPath = arguments.get("target_repo_path").asText();
                String filePath = arguments.get("file_path").asText();
                String fieldName = arguments.get("field_name").asText();
                String newDeclaration = arguments.get("new_declaration").asText();
                Map<String, Object> result = replaceMethodBodyTool.executeReplaceField(repoPath, filePath, fieldName, newDeclaration);
                return createToolResponse(id, result);
            } else if ("insert_import".equals(toolName)) {
                String repoPath = arguments.get("target_repo_path").asText();
                String filePath = arguments.get("file_path").asText();
                String importStatement = arguments.get("import_statement").asText();
                Map<String, Object> result = replaceMethodBodyTool.executeInsertImport(repoPath, filePath, importStatement);
                return createToolResponse(id, result);
            } else if ("remove_method".equals(toolName)) {
                String repoPath = arguments.get("target_repo_path").asText();
                String filePath = arguments.get("file_path").asText();
                String methodSignature = arguments.get("method_signature").asText();
                Map<String, Object> result = replaceMethodBodyTool.executeRemoveMethod(repoPath, filePath, methodSignature);
                return createToolResponse(id, result);
            } else {
                return createErrorResponse(id, -32601, "Tool not found: " + toolName);
            }
        } catch (Throwable t) {
            return createErrorResponse(id, -32603, "Internal error: " + t.getMessage());
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

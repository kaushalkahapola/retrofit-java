package com.retrofit.analysis.tools;

import org.springframework.stereotype.Component;
import spoon.Launcher;
import spoon.reflect.CtModel;
import spoon.reflect.declaration.*;
import spoon.reflect.visitor.filter.TypeFilter;

import java.io.File;
import java.util.*;

@Component
public class GetClassContextTool {

    public Map<String, Object> execute(String targetRepoPath, String filePath, String focusMethod) {
        Launcher launcher = new Launcher();
        launcher.getEnvironment().setNoClasspath(true);
        launcher.getEnvironment().setCommentEnabled(true);
        launcher.getEnvironment().setIgnoreSyntaxErrors(true);
        launcher.getEnvironment().setComplianceLevel(17);

        File repoRoot = new File(targetRepoPath);
        File targetFile = new File(repoRoot, filePath);

        if (!targetFile.exists()) {
            return Map.of("error", "File not found: " + filePath);
        }

        launcher.addInputResource(targetFile.getAbsolutePath());

        try {
            launcher.buildModel();
        } catch (Exception e) {
            return Map.of("error", "Failed to parse file: " + e.getMessage());
        }

        CtModel model = launcher.getModel();
        Collection<CtType<?>> types = model.getElements(new TypeFilter<>(CtType.class));

        if (types.isEmpty()) {
            return Map.of("error", "No types found in file.");
        }

        StringBuilder contextBuilder = new StringBuilder();
        // Container to track line numbers of focused method
        Map<String, Object> lineInfo = new HashMap<>();
        lineInfo.put("start_line", null);
        lineInfo.put("end_line", null);

        // 1. Package & Imports (Approximation: Spoon doesn't easily give raw imports in
        // no-classpath mode,
        // so we print the package and rely on the fact that we are showing the
        // structure)
        // A better way for imports is to read the first few lines of the file, but
        // let's stick to AST for now.
        // Actually, let's just print the package.

        for (CtType<?> type : types) {
            if (!type.isTopLevel())
                continue;

            CtPackage pack = type.getPackage();
            if (pack != null && !pack.isUnnamedPackage()) {
                contextBuilder.append("package ").append(pack.getQualifiedName()).append(";\n\n");
            }

            // 2. Class Structure
            printTypeStructure(type, focusMethod, contextBuilder, "", lineInfo);
        }

        // Build result with line numbers as separate fields
        Map<String, Object> result = new HashMap<>();
        result.put("context", contextBuilder.toString());
        result.put("file_path", filePath);
        
        // Include line numbers if they were found
        if (lineInfo.get("start_line") != null) {
            result.put("start_line", lineInfo.get("start_line"));
            result.put("end_line", lineInfo.get("end_line"));
            result.put("method_name", focusMethod);
        }
        
        return result;
    }

    private void printTypeStructure(CtType<?> type, String focusMethod, StringBuilder sb, String indent, Map<String, Object> lineInfo) {
        // Annotations
        for (spoon.reflect.declaration.CtAnnotation<?> annotation : type.getAnnotations()) {
            sb.append(indent).append(annotation.toString()).append("\n");
        }

        // Signature
        if (type.getPosition().isValidPosition()) {
            sb.append(indent).append("// Line ").append(type.getPosition().getLine()).append("\n");
        }
        sb.append(indent);
        if (type.isPublic())
            sb.append("public ");
        if (type.isProtected())
            sb.append("protected ");
        if (type.isPrivate())
            sb.append("private ");
        if (type.isAbstract() && !type.isInterface())
            sb.append("abstract ");
        if (type.isStatic())
            sb.append("static ");
        if (type.isInterface())
            sb.append("interface ");
        else if (type.isEnum())
            sb.append("enum ");
        else
            sb.append("class ");

        sb.append(type.getSimpleName());

        if (type.getSuperclass() != null) {
            sb.append(" extends ").append(type.getSuperclass().getSimpleName());
        }

        if (!type.getSuperInterfaces().isEmpty()) {
            sb.append(" implements ");
            Iterator<spoon.reflect.reference.CtTypeReference<?>> it = type.getSuperInterfaces().iterator();
            while (it.hasNext()) {
                sb.append(it.next().getSimpleName());
                if (it.hasNext())
                    sb.append(", ");
            }
        }

        sb.append(" {\n");

        String childIndent = indent + "    ";

        // Fields
        for (CtField<?> field : type.getFields()) {
            if (field.getPosition().isValidPosition()) {
                sb.append(childIndent).append("// Line ").append(field.getPosition().getLine()).append(": ");
            } else {
                sb.append(childIndent);
            }
            sb.append(field.toString()).append("\n");
        }
        if (!type.getFields().isEmpty())
            sb.append("\n");

        // Methods
        for (CtMethod<?> method : type.getMethods()) {
            boolean isFocus = focusMethod != null && method.getSimpleName().equals(focusMethod);

            if (isFocus) {
                // Print FULL body with line numbers
                int startLine = method.getPosition().isValidPosition() ? method.getPosition().getLine() : -1;
                int endLine = method.getPosition().isValidPosition() ? method.getPosition().getEndLine() : -1;

                // STORE line info for return to caller
                lineInfo.put("start_line", startLine);
                lineInfo.put("end_line", endLine);

                sb.append(childIndent).append("// [FOCUS] Full Body (Lines ").append(startLine).append("-")
                        .append(endLine).append(")\n");

                // Get original source if possible to preserve formatting and provide exact
                // lines
                if (method.getPosition().isValidPosition()) {
                    String originalContent = method.getPosition().getCompilationUnit().getOriginalSourceCode();
                    // We need to extract lines manually because offsets might be tricky with
                    // newlines
                    // But we can just use the provided lines.
                    String[] allLines = originalContent.split("\\r?\\n");
                    for (int i = startLine; i <= endLine; i++) {
                        if (i > 0 && i <= allLines.length) {
                            sb.append(String.format("%4d: ", i)).append(allLines[i - 1]).append("\n");
                        }
                    }
                } else {
                    sb.append(childIndent).append(method.toString()).append("\n");
                }
            } else {
                // Print Signature ONLY
                int line = method.getPosition().isValidPosition() ? method.getPosition().getLine() : -1;
                sb.append(childIndent).append("// Line ").append(line).append(": ");

                // Modifiers
                if (method.isPublic())
                    sb.append("public ");
                if (method.isProtected())
                    sb.append("protected ");
                if (method.isPrivate())
                    sb.append("private ");
                if (method.isStatic())
                    sb.append("static ");
                if (method.isAbstract())
                    sb.append("abstract ");

                // Return type
                sb.append(method.getType().getSimpleName()).append(" ");
                // Name
                sb.append(method.getSimpleName()).append("(");
                // Parameters
                List<CtParameter<?>> params = method.getParameters();
                for (int i = 0; i < params.size(); i++) {
                    CtParameter<?> param = params.get(i);
                    sb.append(param.getType().getSimpleName()).append(" ").append(param.getSimpleName());
                    if (i < params.size() - 1)
                        sb.append(", ");
                }
                sb.append(")");

                if (method.isAbstract() || type.isInterface()) {
                    sb.append(";\n");
                } else {
                    sb.append(" { /* ... */ }\n");
                }
            }
        }

        // Inner Types
        for (CtType<?> innerType : type.getNestedTypes()) {
            sb.append("\n");
            printTypeStructure(innerType, focusMethod, sb, childIndent, lineInfo);
        }

        sb.append(indent).append("}\n");
    }
}

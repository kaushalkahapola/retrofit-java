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
            printTypeStructure(type, focusMethod, contextBuilder, "");
        }

        return Map.of("context", contextBuilder.toString());
    }

    private void printTypeStructure(CtType<?> type, String focusMethod, StringBuilder sb, String indent) {
        // Annotations
        for (spoon.reflect.declaration.CtAnnotation<?> annotation : type.getAnnotations()) {
            sb.append(indent).append(annotation.toString()).append("\n");
        }

        // Signature
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
            sb.append(childIndent).append(field.toString()).append("\n");
        }
        if (!type.getFields().isEmpty())
            sb.append("\n");

        // Methods
        for (CtMethod<?> method : type.getMethods()) {
            boolean isFocus = focusMethod != null && method.getSimpleName().equals(focusMethod);

            if (isFocus) {
                // Print FULL body
                sb.append(childIndent).append("// [FOCUS] Full Body\n");
                // Split by lines to add indentation
                String body = method.toString();
                for (String line : body.split("\n")) {
                    sb.append(childIndent).append(line).append("\n");
                }
            } else {
                // Print Signature ONLY
                sb.append(childIndent);
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
            printTypeStructure(innerType, focusMethod, sb, childIndent);
        }

        sb.append(indent).append("}\n");
    }
}

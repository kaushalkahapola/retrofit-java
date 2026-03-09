package com.retrofit.analysis.tools;

import org.springframework.stereotype.Component;
import spoon.Launcher;
import spoon.reflect.CtModel;
import spoon.reflect.declaration.CtType;
import spoon.reflect.reference.CtTypeReference;
import spoon.reflect.visitor.filter.TypeFilter;

import java.io.File;
import java.util.*;

@Component
public class GetDependencyTool {

    public Map<String, Object> execute(String targetRepoPath, List<String> filePaths, boolean exploreNeighbors) {
        Launcher launcher = new Launcher();
        launcher.getEnvironment().setNoClasspath(true);
        launcher.getEnvironment().setCommentEnabled(false);
        launcher.getEnvironment().setIgnoreSyntaxErrors(true);
        launcher.getEnvironment().setComplianceLevel(17);

        Set<String> filesToAnalyze = new HashSet<>();
        File repoRoot = new File(targetRepoPath);

        for (String path : filePaths) {
            File f = new File(repoRoot, path);
            if (f.exists()) {
                filesToAnalyze.add(f.getAbsolutePath());

                if (exploreNeighbors) {
                    File parentDir = f.getParentFile();
                    if (parentDir != null && parentDir.isDirectory()) {
                        File[] siblings = parentDir.listFiles((dir, name) -> name.endsWith(".java"));
                        if (siblings != null) {
                            for (File sibling : siblings) {
                                filesToAnalyze.add(sibling.getAbsolutePath());
                            }
                        }
                    }
                }
            }
        }

        if (filesToAnalyze.isEmpty()) {
            return Map.of("error", "No valid files found to analyze.");
        }

        for (String absPath : filesToAnalyze) {
            launcher.addInputResource(absPath);
        }

        try {
            launcher.buildModel();
        } catch (Exception e) {
            return Map.of("error", "Failed to parse files: " + e.getMessage());
        }

        CtModel model = launcher.getModel();
        Collection<CtType<?>> types = model.getElements(new TypeFilter<>(CtType.class));

        List<Map<String, Object>> nodes = new ArrayList<>();
        List<Map<String, Object>> edges = new ArrayList<>();
        Set<String> analyzedTypes = new HashSet<>();

        // First pass: Collect all types being analyzed
        for (CtType<?> type : types) {
            if (type.getPosition().isValidPosition()) {
                analyzedTypes.add(type.getQualifiedName());
            }
        }

        for (CtType<?> type : types) {
            if (!type.isTopLevel())
                continue;

            String typeName = type.getQualifiedName();

            // Extract methods and their calls
            List<Map<String, Object>> methods = new ArrayList<>();
            for (spoon.reflect.declaration.CtMethod<?> method : type.getMethods()) {
                List<String> calls = new ArrayList<>();
                List<spoon.reflect.code.CtInvocation<?>> invocations = method
                        .getElements(new TypeFilter<>(spoon.reflect.code.CtInvocation.class));

                for (spoon.reflect.code.CtInvocation<?> invocation : invocations) {
                    try {
                        CtTypeReference<?> declaringType = invocation.getExecutable().getDeclaringType();
                        if (declaringType != null) {
                            String targetType = declaringType.getQualifiedName();
                            String targetMethod = invocation.getExecutable().getSignature();
                            calls.add(targetType + "." + targetMethod);

                            // Add edge if target is in analyzed set
                            if (analyzedTypes.contains(targetType) && !targetType.equals(typeName)) {
                                edges.add(Map.of(
                                        "source", typeName,
                                        "target", targetType,
                                        "relation", "calls",
                                        "details", method.getSignature() + " -> " + targetMethod));
                            }
                        }
                    } catch (Exception e) {
                        // Ignore resolution errors
                    }
                }

                methods.add(Map.of(
                        "signature", method.getSignature(),
                        "simpleName", method.getSimpleName(),
                        "calls", calls));
            }

            nodes.add(Map.of(
                    "id", typeName,
                    "simpleName", type.getSimpleName(),
                    "methods", methods));

            // Class-level Dependencies (Inheritance/Interfaces)
            Set<String> dependencies = new HashSet<>();

            if (type.getSuperclass() != null)
                dependencies.add(type.getSuperclass().getQualifiedName());
            for (CtTypeReference<?> iface : type.getSuperInterfaces())
                dependencies.add(iface.getQualifiedName());
            type.getReferencedTypes().forEach(ref -> dependencies.add(ref.getQualifiedName()));

            for (String dep : dependencies) {
                if (analyzedTypes.contains(dep) && !dep.equals(typeName)) {
                    edges.add(Map.of("source", typeName, "target", dep, "relation", "depends_on"));
                }
            }
        }

        return Map.of("nodes", nodes, "edges", edges);
    }
}

package com.retrofit.analysis.tools;

import org.springframework.stereotype.Component;
import spoon.Launcher;
import spoon.reflect.CtModel;
import spoon.reflect.declaration.*;
import spoon.reflect.reference.CtTypeReference;
import spoon.reflect.visitor.filter.TypeFilter;
import spoon.reflect.code.CtInvocation;

import java.io.File;
import java.util.*;

@Component
public class GetStructuralAnalysisTool {

    public Map<String, Object> execute(String targetRepoPath, String filePath) {
        Launcher launcher = new Launcher();
        launcher.getEnvironment().setNoClasspath(true);
        launcher.getEnvironment().setCommentEnabled(false);
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

        List<Map<String, Object>> classes = new ArrayList<>();

        for (CtType<?> type : types) {
            if (!type.isTopLevel())
                continue;

            Map<String, Object> classData = new HashMap<>();
            classData.put("className", type.getQualifiedName());
            classData.put("simpleName", type.getSimpleName());

            // Inheritance
            if (type.getSuperclass() != null) {
                classData.put("superclass", type.getSuperclass().getQualifiedName());
            }

            List<String> interfaces = new ArrayList<>();
            for (CtTypeReference<?> iface : type.getSuperInterfaces()) {
                interfaces.add(iface.getQualifiedName());
            }
            classData.put("interfaces", interfaces);

            // Fields
            List<Map<String, String>> fields = new ArrayList<>();
            for (CtField<?> field : type.getFields()) {
                Map<String, String> fieldData = new HashMap<>();
                fieldData.put("name", field.getSimpleName());
                fieldData.put("type", field.getType().getQualifiedName());
                fields.add(fieldData);
            }
            classData.put("fields", fields);

            // Methods & Outgoing Calls
            List<Map<String, Object>> methodsData = new ArrayList<>();
            Set<String> allOutgoingCalls = new HashSet<>();

            for (CtMethod<?> method : type.getMethods()) {
                Map<String, Object> methodInfo = new HashMap<>();
                methodInfo.put("signature", method.getSignature());

                Set<String> localCalls = new HashSet<>();

                // Capture all invocations within this method
                List<CtInvocation<?>> invocations = method.getElements(new TypeFilter<>(CtInvocation.class));
                for (CtInvocation<?> invocation : invocations) {
                    try {
                        if (invocation.getExecutable() != null
                                && invocation.getExecutable().getDeclaringType() != null) {
                            String targetType = invocation.getExecutable().getDeclaringType().getQualifiedName();
                            String targetMethod = invocation.getExecutable().getSignature();
                            String callSig = targetType + "." + targetMethod;

                            localCalls.add(callSig);
                            allOutgoingCalls.add(callSig); // Add to class-level aggregate
                        }
                    } catch (Exception e) {
                        // Ignore resolution issues in no-classpath mode
                    }
                }
                methodInfo.put("outgoingCalls", new ArrayList<>(localCalls));
                methodsData.add(methodInfo);
            }
            classData.put("methods", methodsData);
            classData.put("outgoingCalls", new ArrayList<>(allOutgoingCalls));

            classes.add(classData);
        }

        return Map.of("classes", classes);
    }
}

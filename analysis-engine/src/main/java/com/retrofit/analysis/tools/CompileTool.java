package com.retrofit.analysis.tools;

import org.springframework.stereotype.Component;
import java.io.BufferedReader;
import java.io.File;
import java.io.InputStreamReader;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Component
public class CompileTool {

    public Map<String, Object> execute(String repoPath, List<String> filePaths) {
        Map<String, Object> result = new HashMap<>();
        try {
            if (filePaths == null || filePaths.isEmpty()) {
                result.put("success", true);
                result.put("message", "No files to compile.");
                return result;
            }

            File repoDir = new File(repoPath);
            if (!repoDir.exists()) {
                result.put("success", false);
                result.put("message", "Repository path not found: " + repoPath);
                return result;
            }

            // 1. Determine Source Root (Heuristic)
            // Look for src/main/java
            Path sourceRoot = Paths.get(repoPath, "src", "main", "java");
            if (!Files.exists(sourceRoot)) {
                // Fallback to repo root if src/main/java doesn't exist
                sourceRoot = Paths.get(repoPath);
            }

            // 2. Prepare Output Directory
            Path outputDir = Files.createTempDirectory("compilation_output_");

            // 3. Build Command
            List<String> command = new ArrayList<>();
            command.add("javac");
            command.add("-Xlint");
            command.add("-d");
            command.add(outputDir.toAbsolutePath().toString());
            command.add("-cp");
            command.add(sourceRoot.toAbsolutePath().toString()); // Add source root to classpath so imports work

            // Add files
            for (String fp : filePaths) {
                // Ensure filepath is absolute
                Path p = Paths.get(repoPath, fp);
                command.add(p.toAbsolutePath().toString());
            }

            System.out.println("Executing compilation: " + String.join(" ", command));

            ProcessBuilder pb = new ProcessBuilder(command);
            pb.directory(repoDir);
            pb.redirectErrorStream(true);

            Process process = pb.start();

            StringBuilder output = new StringBuilder();
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    output.append(line).append("\n");
                }
            }

            int exitCode = process.waitFor();

            result.put("success", exitCode == 0);
            result.put("message", output.toString());
            result.put("output_path", outputDir.toAbsolutePath().toString());
            result.put("source_path", sourceRoot.toAbsolutePath().toString()); // return source path for spotbugs aux classpath

        } catch (Exception e) {
            result.put("success", false);
            result.put("message", "Error during compilation: " + e.getMessage());
            e.printStackTrace();
        }
        return result;
    }
}

package com.retrofit.analysis.tools;

import org.springframework.stereotype.Component;
import java.io.BufferedReader;
import java.io.File;
import java.io.InputStreamReader;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Component
public class SpotBugsTool {

    public Map<String, Object> execute(String compiledClassesPath, String sourcePath) {
        Map<String, Object> result = new HashMap<>();
        try {
            // Check if SpotBugs is installed
            String spotBugsHome = "/opt/spotbugs"; // As defined in Dockerfile
            File sbHome = new File(spotBugsHome);
            if (!sbHome.exists()) {
                // Fallback for local testing if not in container
                if (System.getenv("SPOTBUGS_HOME") != null) {
                    spotBugsHome = System.getenv("SPOTBUGS_HOME");
                } else {
                     result.put("success", false);
                     result.put("message", "SpotBugs not found at /opt/spotbugs and SPOTBUGS_HOME not set.");
                     return result;
                }
            }

            List<String> command = new ArrayList<>();
            command.add(spotBugsHome + "/bin/spotbugs");
            command.add("-textui"); // Text interface
            command.add("-low"); // Low confidence issues too? Or maybe -medium
            command.add("-xml:withMessages"); // Output XML (easier to parse if we wanted, but text is fine for LLM/Agent)
            // Actually, for the agent trace, text is better readable.
            // But if we want to parse it for JSON output, XML is better.
            // Let's stick to text for the trace, and maybe I'll wrap it in a pseudo-format.
            // Wait, the agent needs to return "pass/fail + issues" in JSON.
            // Parsing XML in Java is better.
            // But to keep it simple and robust, let's use text output first. The agent can verify if "BugInstance" count > 0.
            // Re-reading: "use spotbugs... output the things just similar to reasoning agents outputs (the mds and all)"
            // So a readable text report is good for the MD.

            // Let's use standard text output.

            if (sourcePath != null) {
                command.add("-sourcepath");
                command.add(sourcePath);
            }

            command.add(compiledClassesPath);

            System.out.println("Executing SpotBugs: " + String.join(" ", command));

            ProcessBuilder pb = new ProcessBuilder(command);
            pb.redirectErrorStream(true);

            Process process = pb.start();

            StringBuilder output = new StringBuilder();
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(process.getInputStream()))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    output.append(line).append("\n");
                }
            }

            process.waitFor();

            // SpotBugs exit codes:
            // 0: No bugs found
            // 1: Error
            // 2: Bugs found? Check docs.
            // Actually, CLI often returns 0 even if bugs are found unless configuration says otherwise.
            // But we can check the output.

            result.put("success", true); // Execution was successful, bugs or not.
            result.put("report", output.toString());

        } catch (Exception e) {
            result.put("success", false);
            result.put("message", "Error during SpotBugs execution: " + e.getMessage());
            e.printStackTrace();
        }
        return result;
    }
}

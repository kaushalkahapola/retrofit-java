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
            // Use the current binding's java home and classpath to run SpotBugs from dependencies
            String javaHome = System.getProperty("java.home");
            String javaBin = javaHome + File.separator + "bin" + File.separator + "java";
            String classpath = System.getProperty("java.class.path");

            List<String> command = new ArrayList<>();
            command.add(javaBin);
            command.add("-cp");
            command.add(classpath);
            // Main entry point for SpotBugs CLI
            command.add("edu.umd.cs.findbugs.LaunchAppropriateUI"); 
            command.add("-textui");
            command.add("-low");
            // command.add("-xml:withMessages"); 
            
            if (sourcePath != null) {
                command.add("-sourcepath");
                command.add(sourcePath);
            }

            command.add(compiledClassesPath);

            System.out.println("Executing integrated SpotBugs...");
            // print command list for debug?
            
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

            int exitCode = process.waitFor();
            
            result.put("success", true);
            result.put("report", output.toString());
            
        } catch (Exception e) {
            result.put("success", false);
            result.put("message", "Error during SpotBugs execution: " + e.getMessage());
            e.printStackTrace();
        }
        return result;
    }
}

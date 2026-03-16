package com.retrofit.analysis.tools;

import edu.umd.cs.findbugs.FindBugs2;
import edu.umd.cs.findbugs.Project;
import edu.umd.cs.findbugs.TextUIBugReporter;
import edu.umd.cs.findbugs.Priorities;
import org.springframework.stereotype.Component;

import java.io.ByteArrayOutputStream;
import java.io.File;
import java.io.PrintStream;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

@Component
public class SpotBugsTool {

    public Map<String, Object> execute(List<String> compiledClassesPaths, String sourcePath) {
        Map<String, Object> result = new HashMap<>();
        StringBuilder debugLog = new StringBuilder();
        try {
            Project project = new Project();
            project.setProjectName("AnalysisEngineProject");
            
            if (compiledClassesPaths == null || compiledClassesPaths.isEmpty()) {
                result.put("success", false);
                result.put("message", "No compiled classes paths provided.");
                return result;
            }

            for (String path : compiledClassesPaths) {
                File file = new File(path);
                if (file.exists()) {
                    project.addFile(path);
                }
            }
            
            if (sourcePath != null && new File(sourcePath).exists()) {
                project.addSourceDir(sourcePath);
            }
            
            // Trigger static initialization of DetectorFactoryCollection with more debug info
            debugLog.append("  SpotBugs: Checking DetectorFactoryCollection initialization...\n");
            edu.umd.cs.findbugs.DetectorFactoryCollection dfc = null;
            try {
                dfc = edu.umd.cs.findbugs.DetectorFactoryCollection.instance();
                if (dfc == null) {
                    debugLog.append("  SpotBugs: DetectorFactoryCollection.instance() is null, resetting...\n");
                    dfc = new edu.umd.cs.findbugs.DetectorFactoryCollection();
                    edu.umd.cs.findbugs.DetectorFactoryCollection.resetInstance(dfc);
                }
                debugLog.append("  SpotBugs: DetectorFactoryCollection initialized.\n");
            } catch (Throwable t) {
                debugLog.append("  SpotBugs Error: DetectorFactoryCollection initialization failed: ").append(t.getMessage()).append("\n");
                dfc = new edu.umd.cs.findbugs.DetectorFactoryCollection();
            }
            
            FindBugs2 findBugs = new FindBugs2();
            findBugs.setProject(project);
            if (dfc != null) {
                findBugs.setDetectorFactoryCollection(dfc);
            }
            // Fix NullPointerException: UserPreferences must be set
            findBugs.setUserPreferences(edu.umd.cs.findbugs.config.UserPreferences.createDefaultUserPreferences());
            findBugs.finishSettings();
            
            // Check if detectors were loaded
            try {
                int detectorCount = 0;
                var it = edu.umd.cs.findbugs.DetectorFactoryCollection.instance().pluginIterator();
                while (it.hasNext()) {
                    it.next();
                    detectorCount++;
                }
                debugLog.append("  SpotBugs: Loaded ").append(detectorCount).append(" plugins.\n");
            } catch (Throwable t) {
                debugLog.append("  SpotBugs Error: Failed to iterate plugins: ").append(t.getMessage()).append("\n");
            }
            
            // Use a collection to store bugs
            edu.umd.cs.findbugs.SortedBugCollection bugCollection = new edu.umd.cs.findbugs.SortedBugCollection();
            // PrintingBugReporter is concrete and useful
            edu.umd.cs.findbugs.PrintingBugReporter reporter = new edu.umd.cs.findbugs.PrintingBugReporter();
            reporter.setPriorityThreshold(Priorities.LOW_PRIORITY);
            
            findBugs.setBugReporter(reporter);
            
            debugLog.append("Executing SpotBugs programmatically on: ").append(String.join(", ", compiledClassesPaths)).append("\n");
            findBugs.execute();
            
            // Actually, FindBugs2.execute() might not be enough if we don't capture the bugs.
            // Let's use BugCollection directly.
            edu.umd.cs.findbugs.BugCollection bugs = findBugs.getBugReporter().getBugCollection();
            
            ByteArrayOutputStream out = new ByteArrayOutputStream();
            PrintStream ps = new PrintStream(out);
            
            // Print summarized findings to the output stream
            for (edu.umd.cs.findbugs.BugInstance bug : bugs.getCollection()) {
                ps.println(bug.getBugPattern().getType() + ": " + bug.getMessage());
                ps.println("  at " + bug.getPrimarySourceLineAnnotation());
                ps.println();
            }
            
            if (bugs.getCollection().isEmpty()) {
                ps.println("No bugs found.");
            }
            
            result.put("success", true);
            result.put("report", out.toString());
            result.put("debug_log", debugLog.toString());
            
        } catch (Throwable t) {
            result.put("success", false);
            result.put("message", "Error during SpotBugs programmatic execution: " + t.getMessage() + "\nDebug Log:\n" + debugLog.toString());
            t.printStackTrace();
        }
        return result;
    }
}

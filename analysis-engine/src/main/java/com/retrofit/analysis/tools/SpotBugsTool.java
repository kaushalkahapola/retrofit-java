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

    public Map<String, Object> execute(List<String> compiledClassesPaths, String sourcePath, List<String> auxClasspath) {
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
            
            if (auxClasspath != null) {
                for (String path : auxClasspath) {
                    if (new File(path).exists()) {
                        project.addAuxClasspathEntry(path);
                    }
                }
            }
            
            if (sourcePath != null && new File(sourcePath).exists()) {
                project.addSourceDir(sourcePath);
            }
            
            // Trigger static initialization of DetectorFactoryCollection with more debug info
            debugLog.append("  SpotBugs: Checking DetectorFactoryCollection initialization...\n");
            edu.umd.cs.findbugs.DetectorFactoryCollection dfc = null;
            try {
                // Force loading of plugins before getting instance
                dfc = edu.umd.cs.findbugs.DetectorFactoryCollection.instance();
                debugLog.append("  SpotBugs: DetectorFactoryCollection initialized.\n");
            } catch (Throwable t) {
                debugLog.append("  SpotBugs Error: DetectorFactoryCollection initialization failed: ").append(t.getMessage()).append("\n");
                // Try manual initialization if instance() fails
                try {
                    dfc = new edu.umd.cs.findbugs.DetectorFactoryCollection();
                    edu.umd.cs.findbugs.DetectorFactoryCollection.resetInstance(dfc);
                    debugLog.append("  SpotBugs: DetectorFactoryCollection reset manually.\n");
                } catch (Throwable t2) {
                    debugLog.append("  SpotBugs Error: Manual reset failed: ").append(t2.getMessage()).append("\n");
                }
            }
            
            // Critical: AnalysisContext needs to be initialized. 
            // Usually, FindBugs2.execute() handles this, but let's be safe.
            
            FindBugs2 findBugs = new FindBugs2();
            findBugs.setProject(project);
            
            // Allow analysis to continue even if some classes are missing
            findBugs.setNoClassOk(true);
            
            // Critical: FindBugs2 needs a DetectorFactoryCollection
            if (dfc != null) {
                findBugs.setDetectorFactoryCollection(dfc);
            } else {
                // Try one more time to get the instance
                try {
                    findBugs.setDetectorFactoryCollection(edu.umd.cs.findbugs.DetectorFactoryCollection.instance());
                } catch (Throwable t) {
                    debugLog.append("  SpotBugs Warning: Final attempt to set DetectorFactoryCollection failed.\n");
                }
            }
            
            // Fix NullPointerException: UserPreferences must be set
            edu.umd.cs.findbugs.config.UserPreferences prefs = edu.umd.cs.findbugs.config.UserPreferences.createDefaultUserPreferences();
            // Set some basic effort
            prefs.setEffort(edu.umd.cs.findbugs.config.UserPreferences.EFFORT_DEFAULT);
            findBugs.setUserPreferences(prefs);
            
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
            java.io.StringWriter sw = new java.io.StringWriter();
            java.io.PrintWriter pw = new java.io.PrintWriter(sw);
            t.printStackTrace(pw);
            String stackTrace = sw.toString();
            
            result.put("success", false);
            result.put("message", "Error during SpotBugs programmatic execution: " + t.getMessage() + "\nDebug Log:\n" + debugLog.toString());
            result.put("stack_trace", stackTrace);
            t.printStackTrace();
        }
        return result;
    }
}

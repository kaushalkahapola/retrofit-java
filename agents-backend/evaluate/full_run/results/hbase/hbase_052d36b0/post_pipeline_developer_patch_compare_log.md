# Post-Pipeline Developer Patch Comparison

**Exact Developer Patch (code-only)**: True

**Comparison Method**: file_state

## File State Comparison
- Compared files: ['hbase-mapreduce/src/main/java/org/apache/hadoop/hbase/mapreduce/WALInputFormat.java']
- Mismatched files: []
- Error: None

## Hunk-by-Hunk Comparison

### hbase-mapreduce/src/main/java/org/apache/hadoop/hbase/mapreduce/WALInputFormat.java

#### Hunk 1

Developer
```diff
@@ -318,7 +318,7 @@
     for (Path inputPath : inputPaths) {
       FileSystem fs = inputPath.getFileSystem(conf);
       try {
-        List<FileStatus> files = getFiles(fs, inputPath, startTime, endTime);
+        List<FileStatus> files = getFiles(fs, inputPath, startTime, endTime, conf);
         allFiles.addAll(files);
       } catch (FileNotFoundException e) {
         if (ignoreMissing) {

```

Generated
```diff
@@ -318,7 +318,7 @@
     for (Path inputPath : inputPaths) {
       FileSystem fs = inputPath.getFileSystem(conf);
       try {
-        List<FileStatus> files = getFiles(fs, inputPath, startTime, endTime);
+        List<FileStatus> files = getFiles(fs, inputPath, startTime, endTime, conf);
         allFiles.addAll(files);
       } catch (FileNotFoundException e) {
         if (ignoreMissing) {

```

Developer -> Generated (Unified Diff)
```diff
(No textual difference)

```

#### Hunk 2

Developer
```diff
@@ -349,11 +349,11 @@
    *                  equal to this value else we will filter out the file. If name does not seem to
    *                  have a timestamp, we will just return it w/o filtering.
    */
-  private List<FileStatus> getFiles(FileSystem fs, Path dir, long startTime, long endTime)
-    throws IOException {
+  private List<FileStatus> getFiles(FileSystem fs, Path dir, long startTime, long endTime,
+    Configuration conf) throws IOException {
     List<FileStatus> result = new ArrayList<>();
     LOG.debug("Scanning " + dir.toString() + " for WAL files");
-    RemoteIterator<LocatedFileStatus> iter = fs.listLocatedStatus(dir);
+    RemoteIterator<LocatedFileStatus> iter = listLocatedFileStatus(fs, dir, conf);
     if (!iter.hasNext()) {
       return Collections.emptyList();
     }

```

Generated
```diff
@@ -349,11 +349,11 @@
    *                  equal to this value else we will filter out the file. If name does not seem to
    *                  have a timestamp, we will just return it w/o filtering.
    */
-  private List<FileStatus> getFiles(FileSystem fs, Path dir, long startTime, long endTime)
-    throws IOException {
+  private List<FileStatus> getFiles(FileSystem fs, Path dir, long startTime, long endTime,
+    Configuration conf) throws IOException {
     List<FileStatus> result = new ArrayList<>();
     LOG.debug("Scanning " + dir.toString() + " for WAL files");
-    RemoteIterator<LocatedFileStatus> iter = fs.listLocatedStatus(dir);
+    RemoteIterator<LocatedFileStatus> iter = listLocatedFileStatus(fs, dir, conf);
     if (!iter.hasNext()) {
       return Collections.emptyList();
     }

```

Developer -> Generated (Unified Diff)
```diff
(No textual difference)

```

#### Hunk 3

Developer
```diff
@@ -361,7 +361,7 @@
       LocatedFileStatus file = iter.next();
       if (file.isDirectory()) {
         // Recurse into sub directories
-        result.addAll(getFiles(fs, file.getPath(), startTime, endTime));
+        result.addAll(getFiles(fs, file.getPath(), startTime, endTime, conf));
       } else {
         addFile(result, file, startTime, endTime);
       }

```

Generated
```diff
@@ -361,7 +361,7 @@
       LocatedFileStatus file = iter.next();
       if (file.isDirectory()) {
         // Recurse into sub directories
-        result.addAll(getFiles(fs, file.getPath(), startTime, endTime));
+        result.addAll(getFiles(fs, file.getPath(), startTime, endTime, conf));
       } else {
         addFile(result, file, startTime, endTime);
       }

```

Developer -> Generated (Unified Diff)
```diff
(No textual difference)

```

#### Hunk 4

Developer
```diff
@@ -396,4 +396,28 @@
     TaskAttemptContext context) throws IOException, InterruptedException {
     return new WALKeyRecordReader();
   }
+
+  /**
+   * Attempts to return the {@link LocatedFileStatus} for the given directory. If the directory does
+   * not exist, it will check if the directory is an archived log file and try to find it
+   */
+  private static RemoteIterator<LocatedFileStatus> listLocatedFileStatus(FileSystem fs, Path dir,
+    Configuration conf) throws IOException {
+    try {
+      return fs.listLocatedStatus(dir);
+    } catch (FileNotFoundException e) {
+      if (AbstractFSWALProvider.isArchivedLogFile(dir)) {
+        throw e;
+      }
+
+      LOG.warn("Log file {} not found, trying to find it in archive directory.", dir);
+      Path archiveFile = AbstractFSWALProvider.findArchivedLog(dir, conf);
+      if (archiveFile == null) {
+        LOG.error("Did not find archive file for {}", dir);
+        throw e;
+      }
+
+      return fs.listLocatedStatus(archiveFile);
+    }
+  }
 }

```

Generated
```diff
@@ -396,4 +396,28 @@
     TaskAttemptContext context) throws IOException, InterruptedException {
     return new WALKeyRecordReader();
   }
+
+  /**
+   * Attempts to return the {@link LocatedFileStatus} for the given directory. If the directory does
+   * not exist, it will check if the directory is an archived log file and try to find it
+   */
+  private static RemoteIterator<LocatedFileStatus> listLocatedFileStatus(FileSystem fs, Path dir,
+    Configuration conf) throws IOException {
+    try {
+      return fs.listLocatedStatus(dir);
+    } catch (FileNotFoundException e) {
+      if (AbstractFSWALProvider.isArchivedLogFile(dir)) {
+        throw e;
+      }
+
+      LOG.warn("Log file {} not found, trying to find it in archive directory.", dir);
+      Path archiveFile = AbstractFSWALProvider.findArchivedLog(dir, conf);
+      if (archiveFile == null) {
+        LOG.error("Did not find archive file for {}", dir);
+        throw e;
+      }
+
+      return fs.listLocatedStatus(archiveFile);
+    }
+  }
 }

```

Developer -> Generated (Unified Diff)
```diff
(No textual difference)

```


### hbase-mapreduce/src/test/java/org/apache/hadoop/hbase/mapreduce/TestWALInputFormat.java

#### Hunk 1

Developer
```diff
*No hunk*
```

Generated
```diff
@@ -21,24 +21,43 @@
 
 import java.util.ArrayList;
 import java.util.List;
+import org.apache.hadoop.conf.Configuration;
 import org.apache.hadoop.fs.FileStatus;
 import org.apache.hadoop.fs.LocatedFileStatus;
 import org.apache.hadoop.fs.Path;
 import org.apache.hadoop.hbase.HBaseClassTestRule;
+import org.apache.hadoop.hbase.HBaseTestingUtility;
+import org.apache.hadoop.hbase.HConstants;
+import org.apache.hadoop.hbase.regionserver.HRegionServer;
+import org.apache.hadoop.hbase.regionserver.wal.AbstractFSWAL;
 import org.apache.hadoop.hbase.testclassification.MapReduceTests;
-import org.apache.hadoop.hbase.testclassification.SmallTests;
+import org.apache.hadoop.hbase.testclassification.MediumTests;
+import org.apache.hadoop.hbase.util.CommonFSUtils;
 import org.apache.hadoop.hbase.util.EnvironmentEdgeManager;
+import org.apache.hadoop.mapreduce.InputSplit;
+import org.apache.hadoop.mapreduce.Job;
+import org.apache.hadoop.mapreduce.JobContext;
+import org.apache.hadoop.mapreduce.lib.input.FileInputFormat;
+import org.junit.BeforeClass;
 import org.junit.ClassRule;
 import org.junit.Test;
 import org.junit.experimental.categories.Category;
 import org.mockito.Mockito;
 
-@Category({ MapReduceTests.class, SmallTests.class })
+@Category({ MapReduceTests.class, MediumTests.class })
 public class TestWALInputFormat {
+  private static final HBaseTestingUtility TEST_UTIL = new HBaseTestingUtility();
+
   @ClassRule
   public static final HBaseClassTestRule CLASS_RULE =
     HBaseClassTestRule.forClass(TestWALInputFormat.class);
 
+  @BeforeClass
+  public static void setupClass() throws Exception {
+    TEST_UTIL.startMiniCluster();
+    TEST_UTIL.createWALRootDir();
+  }
+
   /**
    * Test the primitive start/end time filtering.
    */

```

Developer -> Generated (Unified Diff)
```diff
--- developer+++ generated@@ -1 +1,46 @@-*No hunk*+@@ -21,24 +21,43 @@
+ 
+ import java.util.ArrayList;
+ import java.util.List;
++import org.apache.hadoop.conf.Configuration;
+ import org.apache.hadoop.fs.FileStatus;
+ import org.apache.hadoop.fs.LocatedFileStatus;
+ import org.apache.hadoop.fs.Path;
+ import org.apache.hadoop.hbase.HBaseClassTestRule;
++import org.apache.hadoop.hbase.HBaseTestingUtility;
++import org.apache.hadoop.hbase.HConstants;
++import org.apache.hadoop.hbase.regionserver.HRegionServer;
++import org.apache.hadoop.hbase.regionserver.wal.AbstractFSWAL;
+ import org.apache.hadoop.hbase.testclassification.MapReduceTests;
+-import org.apache.hadoop.hbase.testclassification.SmallTests;
++import org.apache.hadoop.hbase.testclassification.MediumTests;
++import org.apache.hadoop.hbase.util.CommonFSUtils;
+ import org.apache.hadoop.hbase.util.EnvironmentEdgeManager;
++import org.apache.hadoop.mapreduce.InputSplit;
++import org.apache.hadoop.mapreduce.Job;
++import org.apache.hadoop.mapreduce.JobContext;
++import org.apache.hadoop.mapreduce.lib.input.FileInputFormat;
++import org.junit.BeforeClass;
+ import org.junit.ClassRule;
+ import org.junit.Test;
+ import org.junit.experimental.categories.Category;
+ import org.mockito.Mockito;
+ 
+-@Category({ MapReduceTests.class, SmallTests.class })
++@Category({ MapReduceTests.class, MediumTests.class })
+ public class TestWALInputFormat {
++  private static final HBaseTestingUtility TEST_UTIL = new HBaseTestingUtility();
++
+   @ClassRule
+   public static final HBaseClassTestRule CLASS_RULE =
+     HBaseClassTestRule.forClass(TestWALInputFormat.class);
+ 
++  @BeforeClass
++  public static void setupClass() throws Exception {
++    TEST_UTIL.startMiniCluster();
++    TEST_UTIL.createWALRootDir();
++  }
++
+   /**
+    * Test the primitive start/end time filtering.
+    */

```

#### Hunk 2

Developer
```diff
*No hunk*
```

Generated
```diff
@@ -74,4 +93,36 @@
     WALInputFormat.addFile(lfss, lfs, now, now);
     assertEquals(8, lfss.size());
   }
+
+  @Test
+  public void testHandlesArchivedWALFiles() throws Exception {
+    Configuration conf = TEST_UTIL.getConfiguration();
+    JobContext ctx = Mockito.mock(JobContext.class);
+    Mockito.when(ctx.getConfiguration()).thenReturn(conf);
+    Job job = Job.getInstance(conf);
+    TableMapReduceUtil.initCredentialsForCluster(job, conf);
+    Mockito.when(ctx.getCredentials()).thenReturn(job.getCredentials());
+
+    // Setup WAL file, then archive it
+    HRegionServer rs = TEST_UTIL.getHBaseCluster().getRegionServer(0);
+    AbstractFSWAL wal = (AbstractFSWAL) rs.getWALs().get(0);
+    Path walPath = wal.getCurrentFileName();
+    TEST_UTIL.getConfiguration().set(FileInputFormat.INPUT_DIR, walPath.toString());
+    TEST_UTIL.getConfiguration().set(WALPlayer.INPUT_FILES_SEPARATOR_KEY, ";");
+
+    Path rootDir = CommonFSUtils.getWALRootDir(conf);
+    Path archiveWal = new Path(rootDir, HConstants.HREGION_OLDLOGDIR_NAME);
+    archiveWal = new Path(archiveWal, walPath.getName());
+    TEST_UTIL.getTestFileSystem().delete(walPath, true);
+    TEST_UTIL.getTestFileSystem().mkdirs(archiveWal.getParent());
+    TEST_UTIL.getTestFileSystem().create(archiveWal).close();
+
+    // Test for that we can read from the archived WAL file
+    WALInputFormat wif = new WALInputFormat();
+    List<InputSplit> splits = wif.getSplits(ctx);
+    assertEquals(1, splits.size());
+    WALInputFormat.WALSplit split = (WALInputFormat.WALSplit) splits.get(0);
+    assertEquals(archiveWal.toString(), split.getLogFileName());
+  }
+
 }

```

Developer -> Generated (Unified Diff)
```diff
--- developer+++ generated@@ -1 +1,37 @@-*No hunk*+@@ -74,4 +93,36 @@
+     WALInputFormat.addFile(lfss, lfs, now, now);
+     assertEquals(8, lfss.size());
+   }
++
++  @Test
++  public void testHandlesArchivedWALFiles() throws Exception {
++    Configuration conf = TEST_UTIL.getConfiguration();
++    JobContext ctx = Mockito.mock(JobContext.class);
++    Mockito.when(ctx.getConfiguration()).thenReturn(conf);
++    Job job = Job.getInstance(conf);
++    TableMapReduceUtil.initCredentialsForCluster(job, conf);
++    Mockito.when(ctx.getCredentials()).thenReturn(job.getCredentials());
++
++    // Setup WAL file, then archive it
++    HRegionServer rs = TEST_UTIL.getHBaseCluster().getRegionServer(0);
++    AbstractFSWAL wal = (AbstractFSWAL) rs.getWALs().get(0);
++    Path walPath = wal.getCurrentFileName();
++    TEST_UTIL.getConfiguration().set(FileInputFormat.INPUT_DIR, walPath.toString());
++    TEST_UTIL.getConfiguration().set(WALPlayer.INPUT_FILES_SEPARATOR_KEY, ";");
++
++    Path rootDir = CommonFSUtils.getWALRootDir(conf);
++    Path archiveWal = new Path(rootDir, HConstants.HREGION_OLDLOGDIR_NAME);
++    archiveWal = new Path(archiveWal, walPath.getName());
++    TEST_UTIL.getTestFileSystem().delete(walPath, true);
++    TEST_UTIL.getTestFileSystem().mkdirs(archiveWal.getParent());
++    TEST_UTIL.getTestFileSystem().create(archiveWal).close();
++
++    // Test for that we can read from the archived WAL file
++    WALInputFormat wif = new WALInputFormat();
++    List<InputSplit> splits = wif.getSplits(ctx);
++    assertEquals(1, splits.size());
++    WALInputFormat.WALSplit split = (WALInputFormat.WALSplit) splits.get(0);
++    assertEquals(archiveWal.toString(), split.getLogFileName());
++  }
++
+ }

```



## Full Generated Patch (code-only)
```diff
diff --git a/hbase-mapreduce/src/main/java/org/apache/hadoop/hbase/mapreduce/WALInputFormat.java b/hbase-mapreduce/src/main/java/org/apache/hadoop/hbase/mapreduce/WALInputFormat.java
--- a/hbase-mapreduce/src/main/java/org/apache/hadoop/hbase/mapreduce/WALInputFormat.java
+++ b/hbase-mapreduce/src/main/java/org/apache/hadoop/hbase/mapreduce/WALInputFormat.java
@@ -318,7 +318,7 @@
     for (Path inputPath : inputPaths) {
       FileSystem fs = inputPath.getFileSystem(conf);
       try {
-        List<FileStatus> files = getFiles(fs, inputPath, startTime, endTime);
+        List<FileStatus> files = getFiles(fs, inputPath, startTime, endTime, conf);
         allFiles.addAll(files);
       } catch (FileNotFoundException e) {
         if (ignoreMissing) {
@@ -349,11 +349,11 @@
    *                  equal to this value else we will filter out the file. If name does not seem to
    *                  have a timestamp, we will just return it w/o filtering.
    */
-  private List<FileStatus> getFiles(FileSystem fs, Path dir, long startTime, long endTime)
-    throws IOException {
+  private List<FileStatus> getFiles(FileSystem fs, Path dir, long startTime, long endTime,
+    Configuration conf) throws IOException {
     List<FileStatus> result = new ArrayList<>();
     LOG.debug("Scanning " + dir.toString() + " for WAL files");
-    RemoteIterator<LocatedFileStatus> iter = fs.listLocatedStatus(dir);
+    RemoteIterator<LocatedFileStatus> iter = listLocatedFileStatus(fs, dir, conf);
     if (!iter.hasNext()) {
       return Collections.emptyList();
     }
@@ -361,7 +361,7 @@
       LocatedFileStatus file = iter.next();
       if (file.isDirectory()) {
         // Recurse into sub directories
-        result.addAll(getFiles(fs, file.getPath(), startTime, endTime));
+        result.addAll(getFiles(fs, file.getPath(), startTime, endTime, conf));
       } else {
         addFile(result, file, startTime, endTime);
       }
@@ -396,4 +396,28 @@
     TaskAttemptContext context) throws IOException, InterruptedException {
     return new WALKeyRecordReader();
   }
+
+  /**
+   * Attempts to return the {@link LocatedFileStatus} for the given directory. If the directory does
+   * not exist, it will check if the directory is an archived log file and try to find it
+   */
+  private static RemoteIterator<LocatedFileStatus> listLocatedFileStatus(FileSystem fs, Path dir,
+    Configuration conf) throws IOException {
+    try {
+      return fs.listLocatedStatus(dir);
+    } catch (FileNotFoundException e) {
+      if (AbstractFSWALProvider.isArchivedLogFile(dir)) {
+        throw e;
+      }
+
+      LOG.warn("Log file {} not found, trying to find it in archive directory.", dir);
+      Path archiveFile = AbstractFSWALProvider.findArchivedLog(dir, conf);
+      if (archiveFile == null) {
+        LOG.error("Did not find archive file for {}", dir);
+        throw e;
+      }
+
+      return fs.listLocatedStatus(archiveFile);
+    }
+  }
 }
diff --git a/hbase-mapreduce/src/test/java/org/apache/hadoop/hbase/mapreduce/TestWALInputFormat.java b/hbase-mapreduce/src/test/java/org/apache/hadoop/hbase/mapreduce/TestWALInputFormat.java
--- a/hbase-mapreduce/src/test/java/org/apache/hadoop/hbase/mapreduce/TestWALInputFormat.java
+++ b/hbase-mapreduce/src/test/java/org/apache/hadoop/hbase/mapreduce/TestWALInputFormat.java
@@ -21,24 +21,43 @@
 
 import java.util.ArrayList;
 import java.util.List;
+import org.apache.hadoop.conf.Configuration;
 import org.apache.hadoop.fs.FileStatus;
 import org.apache.hadoop.fs.LocatedFileStatus;
 import org.apache.hadoop.fs.Path;
 import org.apache.hadoop.hbase.HBaseClassTestRule;
+import org.apache.hadoop.hbase.HBaseTestingUtility;
+import org.apache.hadoop.hbase.HConstants;
+import org.apache.hadoop.hbase.regionserver.HRegionServer;
+import org.apache.hadoop.hbase.regionserver.wal.AbstractFSWAL;
 import org.apache.hadoop.hbase.testclassification.MapReduceTests;
-import org.apache.hadoop.hbase.testclassification.SmallTests;
+import org.apache.hadoop.hbase.testclassification.MediumTests;
+import org.apache.hadoop.hbase.util.CommonFSUtils;
 import org.apache.hadoop.hbase.util.EnvironmentEdgeManager;
+import org.apache.hadoop.mapreduce.InputSplit;
+import org.apache.hadoop.mapreduce.Job;
+import org.apache.hadoop.mapreduce.JobContext;
+import org.apache.hadoop.mapreduce.lib.input.FileInputFormat;
+import org.junit.BeforeClass;
 import org.junit.ClassRule;
 import org.junit.Test;
 import org.junit.experimental.categories.Category;
 import org.mockito.Mockito;
 
-@Category({ MapReduceTests.class, SmallTests.class })
+@Category({ MapReduceTests.class, MediumTests.class })
 public class TestWALInputFormat {
+  private static final HBaseTestingUtility TEST_UTIL = new HBaseTestingUtility();
+
   @ClassRule
   public static final HBaseClassTestRule CLASS_RULE =
     HBaseClassTestRule.forClass(TestWALInputFormat.class);
 
+  @BeforeClass
+  public static void setupClass() throws Exception {
+    TEST_UTIL.startMiniCluster();
+    TEST_UTIL.createWALRootDir();
+  }
+
   /**
    * Test the primitive start/end time filtering.
    */
@@ -74,4 +93,36 @@
     WALInputFormat.addFile(lfss, lfs, now, now);
     assertEquals(8, lfss.size());
   }
+
+  @Test
+  public void testHandlesArchivedWALFiles() throws Exception {
+    Configuration conf = TEST_UTIL.getConfiguration();
+    JobContext ctx = Mockito.mock(JobContext.class);
+    Mockito.when(ctx.getConfiguration()).thenReturn(conf);
+    Job job = Job.getInstance(conf);
+    TableMapReduceUtil.initCredentialsForCluster(job, conf);
+    Mockito.when(ctx.getCredentials()).thenReturn(job.getCredentials());
+
+    // Setup WAL file, then archive it
+    HRegionServer rs = TEST_UTIL.getHBaseCluster().getRegionServer(0);
+    AbstractFSWAL wal = (AbstractFSWAL) rs.getWALs().get(0);
+    Path walPath = wal.getCurrentFileName();
+    TEST_UTIL.getConfiguration().set(FileInputFormat.INPUT_DIR, walPath.toString());
+    TEST_UTIL.getConfiguration().set(WALPlayer.INPUT_FILES_SEPARATOR_KEY, ";");
+
+    Path rootDir = CommonFSUtils.getWALRootDir(conf);
+    Path archiveWal = new Path(rootDir, HConstants.HREGION_OLDLOGDIR_NAME);
+    archiveWal = new Path(archiveWal, walPath.getName());
+    TEST_UTIL.getTestFileSystem().delete(walPath, true);
+    TEST_UTIL.getTestFileSystem().mkdirs(archiveWal.getParent());
+    TEST_UTIL.getTestFileSystem().create(archiveWal).close();
+
+    // Test for that we can read from the archived WAL file
+    WALInputFormat wif = new WALInputFormat();
+    List<InputSplit> splits = wif.getSplits(ctx);
+    assertEquals(1, splits.size());
+    WALInputFormat.WALSplit split = (WALInputFormat.WALSplit) splits.get(0);
+    assertEquals(archiveWal.toString(), split.getLogFileName());
+  }
+
 }

```
## Full Developer Backport Patch (full commit diff)
```diff
diff --git a/hbase-mapreduce/src/main/java/org/apache/hadoop/hbase/mapreduce/WALInputFormat.java b/hbase-mapreduce/src/main/java/org/apache/hadoop/hbase/mapreduce/WALInputFormat.java
index 7362f585d3..03d3250f54 100644
--- a/hbase-mapreduce/src/main/java/org/apache/hadoop/hbase/mapreduce/WALInputFormat.java
+++ b/hbase-mapreduce/src/main/java/org/apache/hadoop/hbase/mapreduce/WALInputFormat.java
@@ -318,7 +318,7 @@ public class WALInputFormat extends InputFormat<WALKey, WALEdit> {
     for (Path inputPath : inputPaths) {
       FileSystem fs = inputPath.getFileSystem(conf);
       try {
-        List<FileStatus> files = getFiles(fs, inputPath, startTime, endTime);
+        List<FileStatus> files = getFiles(fs, inputPath, startTime, endTime, conf);
         allFiles.addAll(files);
       } catch (FileNotFoundException e) {
         if (ignoreMissing) {
@@ -349,11 +349,11 @@ public class WALInputFormat extends InputFormat<WALKey, WALEdit> {
    *                  equal to this value else we will filter out the file. If name does not seem to
    *                  have a timestamp, we will just return it w/o filtering.
    */
-  private List<FileStatus> getFiles(FileSystem fs, Path dir, long startTime, long endTime)
-    throws IOException {
+  private List<FileStatus> getFiles(FileSystem fs, Path dir, long startTime, long endTime,
+    Configuration conf) throws IOException {
     List<FileStatus> result = new ArrayList<>();
     LOG.debug("Scanning " + dir.toString() + " for WAL files");
-    RemoteIterator<LocatedFileStatus> iter = fs.listLocatedStatus(dir);
+    RemoteIterator<LocatedFileStatus> iter = listLocatedFileStatus(fs, dir, conf);
     if (!iter.hasNext()) {
       return Collections.emptyList();
     }
@@ -361,7 +361,7 @@ public class WALInputFormat extends InputFormat<WALKey, WALEdit> {
       LocatedFileStatus file = iter.next();
       if (file.isDirectory()) {
         // Recurse into sub directories
-        result.addAll(getFiles(fs, file.getPath(), startTime, endTime));
+        result.addAll(getFiles(fs, file.getPath(), startTime, endTime, conf));
       } else {
         addFile(result, file, startTime, endTime);
       }
@@ -396,4 +396,28 @@ public class WALInputFormat extends InputFormat<WALKey, WALEdit> {
     TaskAttemptContext context) throws IOException, InterruptedException {
     return new WALKeyRecordReader();
   }
+
+  /**
+   * Attempts to return the {@link LocatedFileStatus} for the given directory. If the directory does
+   * not exist, it will check if the directory is an archived log file and try to find it
+   */
+  private static RemoteIterator<LocatedFileStatus> listLocatedFileStatus(FileSystem fs, Path dir,
+    Configuration conf) throws IOException {
+    try {
+      return fs.listLocatedStatus(dir);
+    } catch (FileNotFoundException e) {
+      if (AbstractFSWALProvider.isArchivedLogFile(dir)) {
+        throw e;
+      }
+
+      LOG.warn("Log file {} not found, trying to find it in archive directory.", dir);
+      Path archiveFile = AbstractFSWALProvider.findArchivedLog(dir, conf);
+      if (archiveFile == null) {
+        LOG.error("Did not find archive file for {}", dir);
+        throw e;
+      }
+
+      return fs.listLocatedStatus(archiveFile);
+    }
+  }
 }
diff --git a/hbase-mapreduce/src/test/java/org/apache/hadoop/hbase/mapreduce/TestWALInputFormat.java b/hbase-mapreduce/src/test/java/org/apache/hadoop/hbase/mapreduce/TestWALInputFormat.java
index 70602a3716..6fdfb2bb8e 100644
--- a/hbase-mapreduce/src/test/java/org/apache/hadoop/hbase/mapreduce/TestWALInputFormat.java
+++ b/hbase-mapreduce/src/test/java/org/apache/hadoop/hbase/mapreduce/TestWALInputFormat.java
@@ -21,24 +21,43 @@ import static org.junit.Assert.assertEquals;
 
 import java.util.ArrayList;
 import java.util.List;
+import org.apache.hadoop.conf.Configuration;
 import org.apache.hadoop.fs.FileStatus;
 import org.apache.hadoop.fs.LocatedFileStatus;
 import org.apache.hadoop.fs.Path;
 import org.apache.hadoop.hbase.HBaseClassTestRule;
+import org.apache.hadoop.hbase.HBaseTestingUtility;
+import org.apache.hadoop.hbase.HConstants;
+import org.apache.hadoop.hbase.regionserver.HRegionServer;
+import org.apache.hadoop.hbase.regionserver.wal.AbstractFSWAL;
 import org.apache.hadoop.hbase.testclassification.MapReduceTests;
-import org.apache.hadoop.hbase.testclassification.SmallTests;
+import org.apache.hadoop.hbase.testclassification.MediumTests;
+import org.apache.hadoop.hbase.util.CommonFSUtils;
 import org.apache.hadoop.hbase.util.EnvironmentEdgeManager;
+import org.apache.hadoop.mapreduce.InputSplit;
+import org.apache.hadoop.mapreduce.Job;
+import org.apache.hadoop.mapreduce.JobContext;
+import org.apache.hadoop.mapreduce.lib.input.FileInputFormat;
+import org.junit.BeforeClass;
 import org.junit.ClassRule;
 import org.junit.Test;
 import org.junit.experimental.categories.Category;
 import org.mockito.Mockito;
 
-@Category({ MapReduceTests.class, SmallTests.class })
+@Category({ MapReduceTests.class, MediumTests.class })
 public class TestWALInputFormat {
+  private static final HBaseTestingUtility TEST_UTIL = new HBaseTestingUtility();
+
   @ClassRule
   public static final HBaseClassTestRule CLASS_RULE =
     HBaseClassTestRule.forClass(TestWALInputFormat.class);
 
+  @BeforeClass
+  public static void setupClass() throws Exception {
+    TEST_UTIL.startMiniCluster();
+    TEST_UTIL.createWALRootDir();
+  }
+
   /**
    * Test the primitive start/end time filtering.
    */
@@ -74,4 +93,36 @@ public class TestWALInputFormat {
     WALInputFormat.addFile(lfss, lfs, now, now);
     assertEquals(8, lfss.size());
   }
+
+  @Test
+  public void testHandlesArchivedWALFiles() throws Exception {
+    Configuration conf = TEST_UTIL.getConfiguration();
+    JobContext ctx = Mockito.mock(JobContext.class);
+    Mockito.when(ctx.getConfiguration()).thenReturn(conf);
+    Job job = Job.getInstance(conf);
+    TableMapReduceUtil.initCredentialsForCluster(job, conf);
+    Mockito.when(ctx.getCredentials()).thenReturn(job.getCredentials());
+
+    // Setup WAL file, then archive it
+    HRegionServer rs = TEST_UTIL.getHBaseCluster().getRegionServer(0);
+    AbstractFSWAL wal = (AbstractFSWAL) rs.getWALs().get(0);
+    Path walPath = wal.getCurrentFileName();
+    TEST_UTIL.getConfiguration().set(FileInputFormat.INPUT_DIR, walPath.toString());
+    TEST_UTIL.getConfiguration().set(WALPlayer.INPUT_FILES_SEPARATOR_KEY, ";");
+
+    Path rootDir = CommonFSUtils.getWALRootDir(conf);
+    Path archiveWal = new Path(rootDir, HConstants.HREGION_OLDLOGDIR_NAME);
+    archiveWal = new Path(archiveWal, walPath.getName());
+    TEST_UTIL.getTestFileSystem().delete(walPath, true);
+    TEST_UTIL.getTestFileSystem().mkdirs(archiveWal.getParent());
+    TEST_UTIL.getTestFileSystem().create(archiveWal).close();
+
+    // Test for that we can read from the archived WAL file
+    WALInputFormat wif = new WALInputFormat();
+    List<InputSplit> splits = wif.getSplits(ctx);
+    assertEquals(1, splits.size());
+    WALInputFormat.WALSplit split = (WALInputFormat.WALSplit) splits.get(0);
+    assertEquals(archiveWal.toString(), split.getLogFileName());
+  }
+
 }

```

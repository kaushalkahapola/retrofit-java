# Post-Pipeline Developer Patch Comparison

**Exact Developer Patch (code-only)**: False

**Comparison Method**: file_state

## File State Comparison
- Compared files: []
- Mismatched files: []
- Error: Failed to apply generated patch in temporary index: error: dev/null: does not exist in index


error: dev/null: does not exist in index


## Hunk-by-Hunk Comparison

### docs/ingestion/supervisor.md

#### Hunk 1

Developer
```diff
@@ -96,6 +96,7 @@
 |`scaleActionPeriodMillis`|The frequency in milliseconds to check if a scale action is triggered.|No|60000|
 |`scaleInStep`|The number of tasks to reduce at once when scaling down.|No|1|
 |`scaleOutStep`|The number of tasks to add at once when scaling out.|No|2|
+|`lagAggregate`|The aggregate function used to compute the lag metric for scaling decisions. Possible values are `MAX`, `SUM` and `AVERAGE`. |No|`SUM`|
 
 The following example shows a supervisor spec with `lagBased` autoscaler:
 

```

Generated
```diff
*No hunk*
```

Developer -> Generated (Unified Diff)
```diff
--- developer+++ generated@@ -1,8 +1 @@-@@ -96,6 +96,7 @@
- |`scaleActionPeriodMillis`|The frequency in milliseconds to check if a scale action is triggered.|No|60000|
- |`scaleInStep`|The number of tasks to reduce at once when scaling down.|No|1|
- |`scaleOutStep`|The number of tasks to add at once when scaling out.|No|2|
-+|`lagAggregate`|The aggregate function used to compute the lag metric for scaling decisions. Possible values are `MAX`, `SUM` and `AVERAGE`. |No|`SUM`|
- 
- The following example shows a supervisor spec with `lagBased` autoscaler:
- 
+*No hunk*
```


### extensions-core/kinesis-indexing-service/src/main/java/org/apache/druid/indexing/kinesis/supervisor/KinesisSupervisor.java

#### Hunk 1

Developer
```diff
@@ -427,13 +427,6 @@
     );
   }
 
-  @Override
-  public long computeLagForAutoScaler()
-  {
-    LagStats lagStats = computeLagStats();
-    return lagStats == null ? 0L : lagStats.getMaxLag();
-  }
-
   private SeekableStreamDataSourceMetadata<String, String> createDataSourceMetadataWithClosedOrExpiredPartitions(
       SeekableStreamDataSourceMetadata<String, String> currentMetadata,
       Set<String> terminatedPartitionIds,

```

Generated
```diff
@@ -431,13 +431,6 @@
     );
   }
 
-  @Override
-  public long computeLagForAutoScaler()
-  {
-    LagStats lagStats = computeLagStats();
-    return lagStats == null ? 0L : lagStats.getMaxLag();
-  }
-
   private SeekableStreamDataSourceMetadata<String, String> createDataSourceMetadataWithClosedOrExpiredPartitions(
       SeekableStreamDataSourceMetadata<String, String> currentMetadata,
       Set<String> terminatedPartitionIds,

```

Developer -> Generated (Unified Diff)
```diff
--- developer+++ generated@@ -1,4 +1,4 @@-@@ -427,13 +427,6 @@
+@@ -431,13 +431,6 @@
      );
    }
  

```


### indexing-service/src/main/java/org/apache/druid/indexing/seekablestream/supervisor/autoscaler/LagBasedAutoScaler.java

#### Hunk 1

Developer
```diff
@@ -21,6 +21,8 @@
 
 import org.apache.commons.collections4.queue.CircularFifoQueue;
 import org.apache.druid.indexing.overlord.supervisor.SupervisorSpec;
+import org.apache.druid.indexing.overlord.supervisor.autoscaler.AggregateFunction;
+import org.apache.druid.indexing.overlord.supervisor.autoscaler.LagStats;
 import org.apache.druid.indexing.overlord.supervisor.autoscaler.SupervisorTaskAutoScaler;
 import org.apache.druid.indexing.seekablestream.supervisor.SeekableStreamSupervisor;
 import org.apache.druid.java.util.common.StringUtils;

```

Generated
```diff
@@ -21,6 +21,8 @@
 
 import org.apache.commons.collections4.queue.CircularFifoQueue;
 import org.apache.druid.indexing.overlord.supervisor.SupervisorSpec;
+import org.apache.druid.indexing.overlord.supervisor.autoscaler.AggregateFunction;
+import org.apache.druid.indexing.overlord.supervisor.autoscaler.LagStats;
 import org.apache.druid.indexing.overlord.supervisor.autoscaler.SupervisorTaskAutoScaler;
 import org.apache.druid.indexing.seekablestream.supervisor.SeekableStreamSupervisor;
 import org.apache.druid.java.util.common.StringUtils;

```

Developer -> Generated (Unified Diff)
```diff
(No textual difference)

```

#### Hunk 2

Developer
```diff
@@ -154,8 +156,17 @@
       LOCK.lock();
       try {
         if (!spec.isSuspended()) {
-          long lag = supervisor.computeLagForAutoScaler();
-          lagMetricsQueue.offer(lag > 0 ? lag : 0L);
+          LagStats lagStats = supervisor.computeLagStats();
+
+          if (lagStats != null) {
+            AggregateFunction aggregate = lagBasedAutoScalerConfig.getLagAggregate() == null ?
+                                          lagStats.getAggregateForScaling() :
+                                          lagBasedAutoScalerConfig.getLagAggregate();
+            long lag = lagStats.getMetric(aggregate);
+            lagMetricsQueue.offer(lag > 0 ? lag : 0L);
+          } else {
+            lagMetricsQueue.offer(0L);
+          }
           log.debug("Current lags for dataSource[%s] are [%s].", dataSource, lagMetricsQueue);
         } else {
           log.warn("[%s] supervisor is suspended, skipping lag collection", dataSource);

```

Generated
```diff
@@ -151,8 +151,17 @@
       LOCK.lock();
       try {
         if (!spec.isSuspended()) {
-          long lag = supervisor.computeLagForAutoScaler();
-          lagMetricsQueue.offer(lag > 0 ? lag : 0L);
+          LagStats lagStats = supervisor.computeLagStats();
+
+          if (lagStats != null) {
+            AggregateFunction aggregate = lagBasedAutoScalerConfig.getLagAggregate() == null ?
+                                          lagStats.getAggregateForScaling() :
+                                          lagBasedAutoScalerConfig.getLagAggregate();
+            long lag = lagStats.getMetric(aggregate);
+            lagMetricsQueue.offer(lag > 0 ? lag : 0L);
+          } else {
+            lagMetricsQueue.offer(0L);
+          }
           log.debug("Current lags for dataSource[%s] are [%s].", dataSource, lagMetricsQueue);
         } else {
           log.warn("[%s] supervisor is suspended, skipping lag collection", dataSource);

```

Developer -> Generated (Unified Diff)
```diff
--- developer+++ generated@@ -1,4 +1,4 @@-@@ -154,8 +156,17 @@
+@@ -151,8 +151,17 @@
        LOCK.lock();
        try {
          if (!spec.isSuspended()) {

```


### indexing-service/src/main/java/org/apache/druid/indexing/seekablestream/supervisor/autoscaler/LagBasedAutoScalerConfig.java

#### Hunk 1

Developer
```diff
@@ -23,6 +23,7 @@
 import com.fasterxml.jackson.annotation.JsonProperty;
 import org.apache.druid.indexing.overlord.supervisor.Supervisor;
 import org.apache.druid.indexing.overlord.supervisor.SupervisorSpec;
+import org.apache.druid.indexing.overlord.supervisor.autoscaler.AggregateFunction;
 import org.apache.druid.indexing.overlord.supervisor.autoscaler.SupervisorTaskAutoScaler;
 import org.apache.druid.indexing.seekablestream.supervisor.SeekableStreamSupervisor;
 import org.apache.druid.java.util.emitter.service.ServiceEmitter;

```

Generated
```diff
@@ -23,6 +23,7 @@
 import com.fasterxml.jackson.annotation.JsonProperty;
 import org.apache.druid.indexing.overlord.supervisor.Supervisor;
 import org.apache.druid.indexing.overlord.supervisor.SupervisorSpec;
+import org.apache.druid.indexing.overlord.supervisor.autoscaler.AggregateFunction;
 import org.apache.druid.indexing.overlord.supervisor.autoscaler.SupervisorTaskAutoScaler;
 import org.apache.druid.indexing.seekablestream.supervisor.SeekableStreamSupervisor;
 import org.apache.druid.java.util.emitter.service.ServiceEmitter;

```

Developer -> Generated (Unified Diff)
```diff
(No textual difference)

```

#### Hunk 2

Developer
```diff
@@ -45,6 +46,7 @@
   private final int scaleOutStep;
   private final boolean enableTaskAutoScaler;
   private final long minTriggerScaleActionFrequencyMillis;
+  private final AggregateFunction lagAggregate;
 
   @JsonCreator
   public LagBasedAutoScalerConfig(

```

Generated
```diff
@@ -18,6 +18,7 @@
   private final int scaleOutStep;
   private final boolean enableTaskAutoScaler;
   private final long minTriggerScaleActionFrequencyMillis;
+private final AggregateFunction lagAggregate;
 
   @JsonCreator
   public LagBasedAutoScalerConfig(

```

Developer -> Generated (Unified Diff)
```diff
--- developer+++ generated@@ -1,8 +1,8 @@-@@ -45,6 +46,7 @@
+@@ -18,6 +18,7 @@
    private final int scaleOutStep;
    private final boolean enableTaskAutoScaler;
    private final long minTriggerScaleActionFrequencyMillis;
-+  private final AggregateFunction lagAggregate;
++private final AggregateFunction lagAggregate;
  
    @JsonCreator
    public LagBasedAutoScalerConfig(

```

#### Hunk 3

Developer
```diff
@@ -61,7 +63,8 @@
           @Nullable @JsonProperty("scaleInStep") Integer scaleInStep,
           @Nullable @JsonProperty("scaleOutStep") Integer scaleOutStep,
           @Nullable @JsonProperty("enableTaskAutoScaler") Boolean enableTaskAutoScaler,
-          @Nullable @JsonProperty("minTriggerScaleActionFrequencyMillis") Long minTriggerScaleActionFrequencyMillis
+          @Nullable @JsonProperty("minTriggerScaleActionFrequencyMillis") Long minTriggerScaleActionFrequencyMillis,
+          @Nullable @JsonProperty("lagAggregate") AggregateFunction lagAggregate
   )
   {
     this.enableTaskAutoScaler = enableTaskAutoScaler != null ? enableTaskAutoScaler : false;

```

Generated
```diff
@@ -20,7 +20,8 @@
           @Nullable @JsonProperty("scaleInStep") Integer scaleInStep,
           @Nullable @JsonProperty("scaleOutStep") Integer scaleOutStep,
           @Nullable @JsonProperty("enableTaskAutoScaler") Boolean enableTaskAutoScaler,
-          @Nullable @JsonProperty("minTriggerScaleActionFrequencyMillis") Long minTriggerScaleActionFrequencyMillis
+          @Nullable @JsonProperty("minTriggerScaleActionFrequencyMillis") Long minTriggerScaleActionFrequencyMillis,
+          @Nullable @JsonProperty("lagAggregate") AggregateFunction lagAggregate
   )
   {
     this.enableTaskAutoScaler = enableTaskAutoScaler != null ? enableTaskAutoScaler : false;

```

Developer -> Generated (Unified Diff)
```diff
--- developer+++ generated@@ -1,4 +1,4 @@-@@ -61,7 +63,8 @@
+@@ -20,7 +20,8 @@
            @Nullable @JsonProperty("scaleInStep") Integer scaleInStep,
            @Nullable @JsonProperty("scaleOutStep") Integer scaleOutStep,
            @Nullable @JsonProperty("enableTaskAutoScaler") Boolean enableTaskAutoScaler,

```

#### Hunk 4

Developer
```diff
@@ -73,6 +76,7 @@
     this.scaleInThreshold = scaleInThreshold != null ? scaleInThreshold : 1000000;
     this.triggerScaleOutFractionThreshold = triggerScaleOutFractionThreshold != null ? triggerScaleOutFractionThreshold : 0.3;
     this.triggerScaleInFractionThreshold = triggerScaleInFractionThreshold != null ? triggerScaleInFractionThreshold : 0.9;
+    this.lagAggregate = lagAggregate;
 
     // Only do taskCountMax and taskCountMin check when autoscaler is enabled. So that users left autoConfig empty{} will not throw any exception and autoscaler is disabled.
     // If autoscaler is disabled, no matter what configs are set, they are not used.

```

Generated
```diff
@@ -49,6 +49,7 @@
     this.scaleInThreshold = scaleInThreshold != null ? scaleInThreshold : 1000000;
     this.triggerScaleOutFractionThreshold = triggerScaleOutFractionThreshold != null ? triggerScaleOutFractionThreshold : 0.3;
     this.triggerScaleInFractionThreshold = triggerScaleInFractionThreshold != null ? triggerScaleInFractionThreshold : 0.9;
+this.lagAggregate = lagAggregate;
 
     // Only do taskCountMax and taskCountMin check when autoscaler is enabled. So that users left autoConfig empty{} will not throw any exception and autoscaler is disabled.
     // If autoscaler is disabled, no matter what configs are set, they are not used.

```

Developer -> Generated (Unified Diff)
```diff
--- developer+++ generated@@ -1,8 +1,8 @@-@@ -73,6 +76,7 @@
+@@ -49,6 +49,7 @@
      this.scaleInThreshold = scaleInThreshold != null ? scaleInThreshold : 1000000;
      this.triggerScaleOutFractionThreshold = triggerScaleOutFractionThreshold != null ? triggerScaleOutFractionThreshold : 0.3;
      this.triggerScaleInFractionThreshold = triggerScaleInFractionThreshold != null ? triggerScaleInFractionThreshold : 0.9;
-+    this.lagAggregate = lagAggregate;
++this.lagAggregate = lagAggregate;
  
      // Only do taskCountMax and taskCountMin check when autoscaler is enabled. So that users left autoConfig empty{} will not throw any exception and autoscaler is disabled.
      // If autoscaler is disabled, no matter what configs are set, they are not used.

```

#### Hunk 5

Developer
```diff
@@ -186,6 +190,13 @@
     return minTriggerScaleActionFrequencyMillis;
   }
 
+  @JsonProperty
+  @Nullable
+  public AggregateFunction getLagAggregate()
+  {
+    return lagAggregate;
+  }
+
   @Override
   public String toString()
   {

```

Generated
```diff
@@ -190,6 +190,13 @@
     return minTriggerScaleActionFrequencyMillis;
   }
 
+  @com.fasterxml.jackson.annotation.JsonProperty
+  @javax.annotation.Nullable
+  public AggregateFunction getLagAggregate()
+  {
+    return lagAggregate;
+  }
+
   @Override
   public String toString()
   {

```

Developer -> Generated (Unified Diff)
```diff
--- developer+++ generated@@ -1,9 +1,9 @@-@@ -186,6 +190,13 @@
+@@ -190,6 +190,13 @@
      return minTriggerScaleActionFrequencyMillis;
    }
  
-+  @JsonProperty
-+  @Nullable
++  @com.fasterxml.jackson.annotation.JsonProperty
++  @javax.annotation.Nullable
 +  public AggregateFunction getLagAggregate()
 +  {
 +    return lagAggregate;

```

#### Hunk 6

Developer
```diff
@@ -204,6 +215,7 @@
             ", scaleActionPeriodMillis=" + scaleActionPeriodMillis +
             ", scaleInStep=" + scaleInStep +
             ", scaleOutStep=" + scaleOutStep +
+            ", lagAggregate=" + lagAggregate +
             '}';
   }
 }

```

Generated
```diff
@@ -190,6 +190,7 @@
             ", scaleActionPeriodMillis=" + scaleActionPeriodMillis +
             ", scaleInStep=" + scaleInStep +
             ", scaleOutStep=" + scaleOutStep +
+            ", lagAggregate=" + lagAggregate +
             '}';
   }
 }

```

Developer -> Generated (Unified Diff)
```diff
--- developer+++ generated@@ -1,4 +1,4 @@-@@ -204,6 +215,7 @@
+@@ -190,6 +190,7 @@
              ", scaleActionPeriodMillis=" + scaleActionPeriodMillis +
              ", scaleInStep=" + scaleInStep +
              ", scaleOutStep=" + scaleOutStep +

```


### server/src/main/java/org/apache/druid/indexing/overlord/supervisor/Supervisor.java

#### Hunk 1

Developer
```diff
@@ -92,14 +92,5 @@
    */
   LagStats computeLagStats();
 
-  /**
-   * Used by AutoScaler to make scaling decisions.
-   */
-  default long computeLagForAutoScaler()
-  {
-    LagStats lagStats = computeLagStats();
-    return lagStats == null ? 0L : lagStats.getTotalLag();
-  }
-
   int getActiveTaskGroupsCount();
 }

```

Generated
```diff
@@ -98,14 +98,5 @@
    */
   LagStats computeLagStats();
 
-  /**
-   * Used by AutoScaler to make scaling decisions.
-   */
-  default long computeLagForAutoScaler()
-  {
-    LagStats lagStats = computeLagStats();
-    return lagStats == null ? 0L : lagStats.getTotalLag();
-  }
-
   int getActiveTaskGroupsCount();
 }

```

Developer -> Generated (Unified Diff)
```diff
--- developer+++ generated@@ -1,4 +1,4 @@-@@ -92,14 +92,5 @@
+@@ -98,14 +98,5 @@
     */
    LagStats computeLagStats();
  

```


### server/src/main/java/org/apache/druid/indexing/overlord/supervisor/autoscaler/AggregateFunction.java

#### Hunk 1

Developer
```diff
@@ -0,0 +1,27 @@
+/*
+ * Licensed to the Apache Software Foundation (ASF) under one
+ * or more contributor license agreements.  See the NOTICE file
+ * distributed with this work for additional information
+ * regarding copyright ownership.  The ASF licenses this file
+ * to you under the Apache License, Version 2.0 (the
+ * "License"); you may not use this file except in compliance
+ * with the License.  You may obtain a copy of the License at
+ *
+ *   http://www.apache.org/licenses/LICENSE-2.0
+ *
+ * Unless required by applicable law or agreed to in writing,
+ * software distributed under the License is distributed on an
+ * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
+ * KIND, either express or implied.  See the License for the
+ * specific language governing permissions and limitations
+ * under the License.
+ */
+
+package org.apache.druid.indexing.overlord.supervisor.autoscaler;
+
+public enum AggregateFunction
+{
+  MAX,
+  SUM,
+  AVERAGE
+}

```

Generated
```diff
@@ -1,1 +1,27 @@
+/*
+ * Licensed to the Apache Software Foundation (ASF) under one
+ * or more contributor license agreements.  See the NOTICE file
+ * distributed with this work for additional information
+ * regarding copyright ownership.  The ASF licenses this file
+ * to you under the Apache License, Version 2.0 (the
+ * "License"); you may not use this file except in compliance
+ * with the License.  You may obtain a copy of the License at
+ *
+ *   http://www.apache.org/licenses/LICENSE-2.0
+ *
+ * Unless required by applicable law or agreed to in writing,
+ * software distributed under the License is distributed on an
+ * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
+ * KIND, either express or implied.  See the License for the
+ * specific language governing permissions and limitations
+ * under the License.
+ */
+
+package org.apache.druid.indexing.overlord.supervisor.autoscaler;
+
+public enum AggregateFunction
+{
+  MAX,
+  SUM,
+  AVERAGE
+}

```

Developer -> Generated (Unified Diff)
```diff
--- developer+++ generated@@ -1,4 +1,4 @@-@@ -0,0 +1,27 @@
+@@ -1,1 +1,27 @@
 +/*
 + * Licensed to the Apache Software Foundation (ASF) under one
 + * or more contributor license agreements.  See the NOTICE file

```


### server/src/main/java/org/apache/druid/indexing/overlord/supervisor/autoscaler/LagStats.java

#### Hunk 1

Developer
```diff
@@ -24,12 +24,19 @@
   private final long maxLag;
   private final long totalLag;
   private final long avgLag;
+  private final AggregateFunction aggregateForScaling;
 
   public LagStats(long maxLag, long totalLag, long avgLag)
+  {
+    this(maxLag, totalLag, avgLag, AggregateFunction.SUM);
+  }
+
+  public LagStats(long maxLag, long totalLag, long avgLag, AggregateFunction aggregateForScaling)
   {
     this.maxLag = maxLag;
     this.totalLag = totalLag;
     this.avgLag = avgLag;
+    this.aggregateForScaling = aggregateForScaling == null ? AggregateFunction.SUM : aggregateForScaling;
   }
 
   public long getMaxLag()

```

Generated
```diff
@@ -6,12 +6,19 @@
   private final long maxLag;
   private final long totalLag;
   private final long avgLag;
+  private final AggregateFunction aggregateForScaling;
 
   public LagStats(long maxLag, long totalLag, long avgLag)
+  {
+    this(maxLag, totalLag, avgLag, AggregateFunction.SUM);
+  }
+
+  public LagStats(long maxLag, long totalLag, long avgLag, AggregateFunction aggregateForScaling)
   {
     this.maxLag = maxLag;
     this.totalLag = totalLag;
     this.avgLag = avgLag;
+    this.aggregateForScaling = aggregateForScaling == null ? AggregateFunction.SUM : aggregateForScaling;
   }
 
   public long getMaxLag()

```

Developer -> Generated (Unified Diff)
```diff
--- developer+++ generated@@ -1,4 +1,4 @@-@@ -24,12 +24,19 @@
+@@ -6,12 +6,19 @@
    private final long maxLag;
    private final long totalLag;
    private final long avgLag;

```

#### Hunk 2

Developer
```diff
@@ -46,4 +53,26 @@
   {
     return avgLag;
   }
+
+  /**
+   * The preferred scaling metric that supervisor may specify to be used.
+   * This could be overrided by the autscaler.
+   */
+  public AggregateFunction getAggregateForScaling()
+  {
+    return aggregateForScaling;
+  }
+
+  public long getMetric(AggregateFunction metric)
+  {
+    switch (metric) {
+      case MAX:
+        return getMaxLag();
+      case SUM:
+        return getTotalLag();
+      case AVERAGE:
+        return getAvgLag();
+    }
+    throw new IllegalStateException("Unknown scale metric");
+  }
 }

```

Generated
```diff
@@ -53,4 +53,26 @@
   {
     return avgLag;
   }
+
+  /**
+   * The preferred scaling metric that supervisor may specify to be used.
+   * This could be overrided by the autscaler.
+   */
+  public AggregateFunction getAggregateForScaling()
+  {
+    return aggregateForScaling;
+  }
+
+  public long getMetric(AggregateFunction metric)
+  {
+    switch (metric) {
+      case MAX:
+        return getMaxLag();
+      case SUM:
+        return getTotalLag();
+      case AVERAGE:
+        return getAvgLag();
+    }
+    throw new IllegalStateException("Unknown scale metric");
+  }
 }

```

Developer -> Generated (Unified Diff)
```diff
--- developer+++ generated@@ -1,4 +1,4 @@-@@ -46,4 +53,26 @@
+@@ -53,4 +53,26 @@
    {
      return avgLag;
    }

```



## Full Generated Patch (code-only)
```diff
diff --git a/extensions-core/kinesis-indexing-service/src/main/java/org/apache/druid/indexing/kinesis/supervisor/KinesisSupervisor.java b/extensions-core/kinesis-indexing-service/src/main/java/org/apache/druid/indexing/kinesis/supervisor/KinesisSupervisor.java
--- a/extensions-core/kinesis-indexing-service/src/main/java/org/apache/druid/indexing/kinesis/supervisor/KinesisSupervisor.java
+++ b/extensions-core/kinesis-indexing-service/src/main/java/org/apache/druid/indexing/kinesis/supervisor/KinesisSupervisor.java
@@ -431,13 +431,6 @@
     );
   }
 
-  @Override
-  public long computeLagForAutoScaler()
-  {
-    LagStats lagStats = computeLagStats();
-    return lagStats == null ? 0L : lagStats.getMaxLag();
-  }
-
   private SeekableStreamDataSourceMetadata<String, String> createDataSourceMetadataWithClosedOrExpiredPartitions(
       SeekableStreamDataSourceMetadata<String, String> currentMetadata,
       Set<String> terminatedPartitionIds,
diff --git a/indexing-service/src/main/java/org/apache/druid/indexing/seekablestream/supervisor/autoscaler/LagBasedAutoScaler.java b/indexing-service/src/main/java/org/apache/druid/indexing/seekablestream/supervisor/autoscaler/LagBasedAutoScaler.java
--- a/indexing-service/src/main/java/org/apache/druid/indexing/seekablestream/supervisor/autoscaler/LagBasedAutoScaler.java
+++ b/indexing-service/src/main/java/org/apache/druid/indexing/seekablestream/supervisor/autoscaler/LagBasedAutoScaler.java
@@ -21,6 +21,8 @@
 
 import org.apache.commons.collections4.queue.CircularFifoQueue;
 import org.apache.druid.indexing.overlord.supervisor.SupervisorSpec;
+import org.apache.druid.indexing.overlord.supervisor.autoscaler.AggregateFunction;
+import org.apache.druid.indexing.overlord.supervisor.autoscaler.LagStats;
 import org.apache.druid.indexing.overlord.supervisor.autoscaler.SupervisorTaskAutoScaler;
 import org.apache.druid.indexing.seekablestream.supervisor.SeekableStreamSupervisor;
 import org.apache.druid.java.util.common.StringUtils;
@@ -151,8 +151,17 @@
       LOCK.lock();
       try {
         if (!spec.isSuspended()) {
-          long lag = supervisor.computeLagForAutoScaler();
-          lagMetricsQueue.offer(lag > 0 ? lag : 0L);
+          LagStats lagStats = supervisor.computeLagStats();
+
+          if (lagStats != null) {
+            AggregateFunction aggregate = lagBasedAutoScalerConfig.getLagAggregate() == null ?
+                                          lagStats.getAggregateForScaling() :
+                                          lagBasedAutoScalerConfig.getLagAggregate();
+            long lag = lagStats.getMetric(aggregate);
+            lagMetricsQueue.offer(lag > 0 ? lag : 0L);
+          } else {
+            lagMetricsQueue.offer(0L);
+          }
           log.debug("Current lags for dataSource[%s] are [%s].", dataSource, lagMetricsQueue);
         } else {
           log.warn("[%s] supervisor is suspended, skipping lag collection", dataSource);
diff --git a/indexing-service/src/main/java/org/apache/druid/indexing/seekablestream/supervisor/autoscaler/LagBasedAutoScalerConfig.java b/indexing-service/src/main/java/org/apache/druid/indexing/seekablestream/supervisor/autoscaler/LagBasedAutoScalerConfig.java
--- a/indexing-service/src/main/java/org/apache/druid/indexing/seekablestream/supervisor/autoscaler/LagBasedAutoScalerConfig.java
+++ b/indexing-service/src/main/java/org/apache/druid/indexing/seekablestream/supervisor/autoscaler/LagBasedAutoScalerConfig.java
@@ -23,6 +23,7 @@
 import com.fasterxml.jackson.annotation.JsonProperty;
 import org.apache.druid.indexing.overlord.supervisor.Supervisor;
 import org.apache.druid.indexing.overlord.supervisor.SupervisorSpec;
+import org.apache.druid.indexing.overlord.supervisor.autoscaler.AggregateFunction;
 import org.apache.druid.indexing.overlord.supervisor.autoscaler.SupervisorTaskAutoScaler;
 import org.apache.druid.indexing.seekablestream.supervisor.SeekableStreamSupervisor;
 import org.apache.druid.java.util.emitter.service.ServiceEmitter;
@@ -18,6 +18,7 @@
   private final int scaleOutStep;
   private final boolean enableTaskAutoScaler;
   private final long minTriggerScaleActionFrequencyMillis;
+private final AggregateFunction lagAggregate;
 
   @JsonCreator
   public LagBasedAutoScalerConfig(
@@ -20,7 +20,8 @@
           @Nullable @JsonProperty("scaleInStep") Integer scaleInStep,
           @Nullable @JsonProperty("scaleOutStep") Integer scaleOutStep,
           @Nullable @JsonProperty("enableTaskAutoScaler") Boolean enableTaskAutoScaler,
-          @Nullable @JsonProperty("minTriggerScaleActionFrequencyMillis") Long minTriggerScaleActionFrequencyMillis
+          @Nullable @JsonProperty("minTriggerScaleActionFrequencyMillis") Long minTriggerScaleActionFrequencyMillis,
+          @Nullable @JsonProperty("lagAggregate") AggregateFunction lagAggregate
   )
   {
     this.enableTaskAutoScaler = enableTaskAutoScaler != null ? enableTaskAutoScaler : false;
@@ -49,6 +49,7 @@
     this.scaleInThreshold = scaleInThreshold != null ? scaleInThreshold : 1000000;
     this.triggerScaleOutFractionThreshold = triggerScaleOutFractionThreshold != null ? triggerScaleOutFractionThreshold : 0.3;
     this.triggerScaleInFractionThreshold = triggerScaleInFractionThreshold != null ? triggerScaleInFractionThreshold : 0.9;
+this.lagAggregate = lagAggregate;
 
     // Only do taskCountMax and taskCountMin check when autoscaler is enabled. So that users left autoConfig empty{} will not throw any exception and autoscaler is disabled.
     // If autoscaler is disabled, no matter what configs are set, they are not used.
@@ -190,6 +190,13 @@
     return minTriggerScaleActionFrequencyMillis;
   }
 
+  @com.fasterxml.jackson.annotation.JsonProperty
+  @javax.annotation.Nullable
+  public AggregateFunction getLagAggregate()
+  {
+    return lagAggregate;
+  }
+
   @Override
   public String toString()
   {
@@ -190,6 +190,7 @@
             ", scaleActionPeriodMillis=" + scaleActionPeriodMillis +
             ", scaleInStep=" + scaleInStep +
             ", scaleOutStep=" + scaleOutStep +
+            ", lagAggregate=" + lagAggregate +
             '}';
   }
 }
diff --git a/server/src/main/java/org/apache/druid/indexing/overlord/supervisor/Supervisor.java b/server/src/main/java/org/apache/druid/indexing/overlord/supervisor/Supervisor.java
--- a/server/src/main/java/org/apache/druid/indexing/overlord/supervisor/Supervisor.java
+++ b/server/src/main/java/org/apache/druid/indexing/overlord/supervisor/Supervisor.java
@@ -98,14 +98,5 @@
    */
   LagStats computeLagStats();
 
-  /**
-   * Used by AutoScaler to make scaling decisions.
-   */
-  default long computeLagForAutoScaler()
-  {
-    LagStats lagStats = computeLagStats();
-    return lagStats == null ? 0L : lagStats.getTotalLag();
-  }
-
   int getActiveTaskGroupsCount();
 }
diff --git a/server/src/main/java/org/apache/druid/indexing/overlord/supervisor/autoscaler/AggregateFunction.java b/server/src/main/java/org/apache/druid/indexing/overlord/supervisor/autoscaler/AggregateFunction.java
--- /dev/null
+++ b/server/src/main/java/org/apache/druid/indexing/overlord/supervisor/autoscaler/AggregateFunction.java
@@ -0,0 +1,27 @@
+/*
+ * Licensed to the Apache Software Foundation (ASF) under one
+ * or more contributor license agreements.  See the NOTICE file
+ * distributed with this work for additional information
+ * regarding copyright ownership.  The ASF licenses this file
+ * to you under the Apache License, Version 2.0 (the
+ * "License"); you may not use this file except in compliance
+ * with the License.  You may obtain a copy of the License at
+ *
+ *   http://www.apache.org/licenses/LICENSE-2.0
+ *
+ * Unless required by applicable law or agreed to in writing,
+ * software distributed under the License is distributed on an
+ * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
+ * KIND, either express or implied.  See the License for the
+ * specific language governing permissions and limitations
+ * under the License.
+ */
+
+package org.apache.druid.indexing.overlord.supervisor.autoscaler;
+
+public enum AggregateFunction
+{
+  MAX,
+  SUM,
+  AVERAGE
+}
diff --git a/server/src/main/java/org/apache/druid/indexing/overlord/supervisor/autoscaler/LagStats.java b/server/src/main/java/org/apache/druid/indexing/overlord/supervisor/autoscaler/LagStats.java
--- a/server/src/main/java/org/apache/druid/indexing/overlord/supervisor/autoscaler/LagStats.java
+++ b/server/src/main/java/org/apache/druid/indexing/overlord/supervisor/autoscaler/LagStats.java
@@ -6,12 +6,19 @@
   private final long maxLag;
   private final long totalLag;
   private final long avgLag;
+  private final AggregateFunction aggregateForScaling;
 
   public LagStats(long maxLag, long totalLag, long avgLag)
+  {
+    this(maxLag, totalLag, avgLag, AggregateFunction.SUM);
+  }
+
+  public LagStats(long maxLag, long totalLag, long avgLag, AggregateFunction aggregateForScaling)
   {
     this.maxLag = maxLag;
     this.totalLag = totalLag;
     this.avgLag = avgLag;
+    this.aggregateForScaling = aggregateForScaling == null ? AggregateFunction.SUM : aggregateForScaling;
   }
 
   public long getMaxLag()
@@ -53,4 +53,26 @@
   {
     return avgLag;
   }
+
+  /**
+   * The preferred scaling metric that supervisor may specify to be used.
+   * This could be overrided by the autscaler.
+   */
+  public AggregateFunction getAggregateForScaling()
+  {
+    return aggregateForScaling;
+  }
+
+  public long getMetric(AggregateFunction metric)
+  {
+    switch (metric) {
+      case MAX:
+        return getMaxLag();
+      case SUM:
+        return getTotalLag();
+      case AVERAGE:
+        return getAvgLag();
+    }
+    throw new IllegalStateException("Unknown scale metric");
+  }
 }

```
## Full Developer Backport Patch (full commit diff)
```diff
diff --git a/docs/ingestion/supervisor.md b/docs/ingestion/supervisor.md
index 76dd1cc4a7..9320c39a02 100644
--- a/docs/ingestion/supervisor.md
+++ b/docs/ingestion/supervisor.md
@@ -96,6 +96,7 @@ The following table outlines the configuration properties related to the `lagBas
 |`scaleActionPeriodMillis`|The frequency in milliseconds to check if a scale action is triggered.|No|60000|
 |`scaleInStep`|The number of tasks to reduce at once when scaling down.|No|1|
 |`scaleOutStep`|The number of tasks to add at once when scaling out.|No|2|
+|`lagAggregate`|The aggregate function used to compute the lag metric for scaling decisions. Possible values are `MAX`, `SUM` and `AVERAGE`. |No|`SUM`|
 
 The following example shows a supervisor spec with `lagBased` autoscaler:
 
diff --git a/extensions-core/kinesis-indexing-service/src/main/java/org/apache/druid/indexing/kinesis/supervisor/KinesisSupervisor.java b/extensions-core/kinesis-indexing-service/src/main/java/org/apache/druid/indexing/kinesis/supervisor/KinesisSupervisor.java
index 365a9135e3..a142f41476 100644
--- a/extensions-core/kinesis-indexing-service/src/main/java/org/apache/druid/indexing/kinesis/supervisor/KinesisSupervisor.java
+++ b/extensions-core/kinesis-indexing-service/src/main/java/org/apache/druid/indexing/kinesis/supervisor/KinesisSupervisor.java
@@ -427,13 +427,6 @@ public class KinesisSupervisor extends SeekableStreamSupervisor<String, String,
     );
   }
 
-  @Override
-  public long computeLagForAutoScaler()
-  {
-    LagStats lagStats = computeLagStats();
-    return lagStats == null ? 0L : lagStats.getMaxLag();
-  }
-
   private SeekableStreamDataSourceMetadata<String, String> createDataSourceMetadataWithClosedOrExpiredPartitions(
       SeekableStreamDataSourceMetadata<String, String> currentMetadata,
       Set<String> terminatedPartitionIds,
diff --git a/indexing-service/src/main/java/org/apache/druid/indexing/seekablestream/supervisor/autoscaler/LagBasedAutoScaler.java b/indexing-service/src/main/java/org/apache/druid/indexing/seekablestream/supervisor/autoscaler/LagBasedAutoScaler.java
index f8618b06f7..ec81c5f9f9 100644
--- a/indexing-service/src/main/java/org/apache/druid/indexing/seekablestream/supervisor/autoscaler/LagBasedAutoScaler.java
+++ b/indexing-service/src/main/java/org/apache/druid/indexing/seekablestream/supervisor/autoscaler/LagBasedAutoScaler.java
@@ -21,6 +21,8 @@ package org.apache.druid.indexing.seekablestream.supervisor.autoscaler;
 
 import org.apache.commons.collections4.queue.CircularFifoQueue;
 import org.apache.druid.indexing.overlord.supervisor.SupervisorSpec;
+import org.apache.druid.indexing.overlord.supervisor.autoscaler.AggregateFunction;
+import org.apache.druid.indexing.overlord.supervisor.autoscaler.LagStats;
 import org.apache.druid.indexing.overlord.supervisor.autoscaler.SupervisorTaskAutoScaler;
 import org.apache.druid.indexing.seekablestream.supervisor.SeekableStreamSupervisor;
 import org.apache.druid.java.util.common.StringUtils;
@@ -154,8 +156,17 @@ public class LagBasedAutoScaler implements SupervisorTaskAutoScaler
       LOCK.lock();
       try {
         if (!spec.isSuspended()) {
-          long lag = supervisor.computeLagForAutoScaler();
-          lagMetricsQueue.offer(lag > 0 ? lag : 0L);
+          LagStats lagStats = supervisor.computeLagStats();
+
+          if (lagStats != null) {
+            AggregateFunction aggregate = lagBasedAutoScalerConfig.getLagAggregate() == null ?
+                                          lagStats.getAggregateForScaling() :
+                                          lagBasedAutoScalerConfig.getLagAggregate();
+            long lag = lagStats.getMetric(aggregate);
+            lagMetricsQueue.offer(lag > 0 ? lag : 0L);
+          } else {
+            lagMetricsQueue.offer(0L);
+          }
           log.debug("Current lags for dataSource[%s] are [%s].", dataSource, lagMetricsQueue);
         } else {
           log.warn("[%s] supervisor is suspended, skipping lag collection", dataSource);
diff --git a/indexing-service/src/main/java/org/apache/druid/indexing/seekablestream/supervisor/autoscaler/LagBasedAutoScalerConfig.java b/indexing-service/src/main/java/org/apache/druid/indexing/seekablestream/supervisor/autoscaler/LagBasedAutoScalerConfig.java
index e03242de27..068e7cc4f8 100644
--- a/indexing-service/src/main/java/org/apache/druid/indexing/seekablestream/supervisor/autoscaler/LagBasedAutoScalerConfig.java
+++ b/indexing-service/src/main/java/org/apache/druid/indexing/seekablestream/supervisor/autoscaler/LagBasedAutoScalerConfig.java
@@ -23,6 +23,7 @@ import com.fasterxml.jackson.annotation.JsonCreator;
 import com.fasterxml.jackson.annotation.JsonProperty;
 import org.apache.druid.indexing.overlord.supervisor.Supervisor;
 import org.apache.druid.indexing.overlord.supervisor.SupervisorSpec;
+import org.apache.druid.indexing.overlord.supervisor.autoscaler.AggregateFunction;
 import org.apache.druid.indexing.overlord.supervisor.autoscaler.SupervisorTaskAutoScaler;
 import org.apache.druid.indexing.seekablestream.supervisor.SeekableStreamSupervisor;
 import org.apache.druid.java.util.emitter.service.ServiceEmitter;
@@ -45,6 +46,7 @@ public class LagBasedAutoScalerConfig implements AutoScalerConfig
   private final int scaleOutStep;
   private final boolean enableTaskAutoScaler;
   private final long minTriggerScaleActionFrequencyMillis;
+  private final AggregateFunction lagAggregate;
 
   @JsonCreator
   public LagBasedAutoScalerConfig(
@@ -61,7 +63,8 @@ public class LagBasedAutoScalerConfig implements AutoScalerConfig
           @Nullable @JsonProperty("scaleInStep") Integer scaleInStep,
           @Nullable @JsonProperty("scaleOutStep") Integer scaleOutStep,
           @Nullable @JsonProperty("enableTaskAutoScaler") Boolean enableTaskAutoScaler,
-          @Nullable @JsonProperty("minTriggerScaleActionFrequencyMillis") Long minTriggerScaleActionFrequencyMillis
+          @Nullable @JsonProperty("minTriggerScaleActionFrequencyMillis") Long minTriggerScaleActionFrequencyMillis,
+          @Nullable @JsonProperty("lagAggregate") AggregateFunction lagAggregate
   )
   {
     this.enableTaskAutoScaler = enableTaskAutoScaler != null ? enableTaskAutoScaler : false;
@@ -73,6 +76,7 @@ public class LagBasedAutoScalerConfig implements AutoScalerConfig
     this.scaleInThreshold = scaleInThreshold != null ? scaleInThreshold : 1000000;
     this.triggerScaleOutFractionThreshold = triggerScaleOutFractionThreshold != null ? triggerScaleOutFractionThreshold : 0.3;
     this.triggerScaleInFractionThreshold = triggerScaleInFractionThreshold != null ? triggerScaleInFractionThreshold : 0.9;
+    this.lagAggregate = lagAggregate;
 
     // Only do taskCountMax and taskCountMin check when autoscaler is enabled. So that users left autoConfig empty{} will not throw any exception and autoscaler is disabled.
     // If autoscaler is disabled, no matter what configs are set, they are not used.
@@ -186,6 +190,13 @@ public class LagBasedAutoScalerConfig implements AutoScalerConfig
     return minTriggerScaleActionFrequencyMillis;
   }
 
+  @JsonProperty
+  @Nullable
+  public AggregateFunction getLagAggregate()
+  {
+    return lagAggregate;
+  }
+
   @Override
   public String toString()
   {
@@ -204,6 +215,7 @@ public class LagBasedAutoScalerConfig implements AutoScalerConfig
             ", scaleActionPeriodMillis=" + scaleActionPeriodMillis +
             ", scaleInStep=" + scaleInStep +
             ", scaleOutStep=" + scaleOutStep +
+            ", lagAggregate=" + lagAggregate +
             '}';
   }
 }
diff --git a/server/src/main/java/org/apache/druid/indexing/overlord/supervisor/Supervisor.java b/server/src/main/java/org/apache/druid/indexing/overlord/supervisor/Supervisor.java
index b1fb439184..bcfc5ebe81 100644
--- a/server/src/main/java/org/apache/druid/indexing/overlord/supervisor/Supervisor.java
+++ b/server/src/main/java/org/apache/druid/indexing/overlord/supervisor/Supervisor.java
@@ -92,14 +92,5 @@ public interface Supervisor
    */
   LagStats computeLagStats();
 
-  /**
-   * Used by AutoScaler to make scaling decisions.
-   */
-  default long computeLagForAutoScaler()
-  {
-    LagStats lagStats = computeLagStats();
-    return lagStats == null ? 0L : lagStats.getTotalLag();
-  }
-
   int getActiveTaskGroupsCount();
 }
diff --git a/server/src/main/java/org/apache/druid/indexing/overlord/supervisor/autoscaler/AggregateFunction.java b/server/src/main/java/org/apache/druid/indexing/overlord/supervisor/autoscaler/AggregateFunction.java
new file mode 100644
index 0000000000..247c05180b
--- /dev/null
+++ b/server/src/main/java/org/apache/druid/indexing/overlord/supervisor/autoscaler/AggregateFunction.java
@@ -0,0 +1,27 @@
+/*
+ * Licensed to the Apache Software Foundation (ASF) under one
+ * or more contributor license agreements.  See the NOTICE file
+ * distributed with this work for additional information
+ * regarding copyright ownership.  The ASF licenses this file
+ * to you under the Apache License, Version 2.0 (the
+ * "License"); you may not use this file except in compliance
+ * with the License.  You may obtain a copy of the License at
+ *
+ *   http://www.apache.org/licenses/LICENSE-2.0
+ *
+ * Unless required by applicable law or agreed to in writing,
+ * software distributed under the License is distributed on an
+ * "AS IS" BASIS, WITHOUT WARRANTIES OR CONDITIONS OF ANY
+ * KIND, either express or implied.  See the License for the
+ * specific language governing permissions and limitations
+ * under the License.
+ */
+
+package org.apache.druid.indexing.overlord.supervisor.autoscaler;
+
+public enum AggregateFunction
+{
+  MAX,
+  SUM,
+  AVERAGE
+}
diff --git a/server/src/main/java/org/apache/druid/indexing/overlord/supervisor/autoscaler/LagStats.java b/server/src/main/java/org/apache/druid/indexing/overlord/supervisor/autoscaler/LagStats.java
index 7b6e5fd0ba..2240585680 100644
--- a/server/src/main/java/org/apache/druid/indexing/overlord/supervisor/autoscaler/LagStats.java
+++ b/server/src/main/java/org/apache/druid/indexing/overlord/supervisor/autoscaler/LagStats.java
@@ -24,12 +24,19 @@ public class LagStats
   private final long maxLag;
   private final long totalLag;
   private final long avgLag;
+  private final AggregateFunction aggregateForScaling;
 
   public LagStats(long maxLag, long totalLag, long avgLag)
+  {
+    this(maxLag, totalLag, avgLag, AggregateFunction.SUM);
+  }
+
+  public LagStats(long maxLag, long totalLag, long avgLag, AggregateFunction aggregateForScaling)
   {
     this.maxLag = maxLag;
     this.totalLag = totalLag;
     this.avgLag = avgLag;
+    this.aggregateForScaling = aggregateForScaling == null ? AggregateFunction.SUM : aggregateForScaling;
   }
 
   public long getMaxLag()
@@ -46,4 +53,26 @@ public class LagStats
   {
     return avgLag;
   }
+
+  /**
+   * The preferred scaling metric that supervisor may specify to be used.
+   * This could be overrided by the autscaler.
+   */
+  public AggregateFunction getAggregateForScaling()
+  {
+    return aggregateForScaling;
+  }
+
+  public long getMetric(AggregateFunction metric)
+  {
+    switch (metric) {
+      case MAX:
+        return getMaxLag();
+      case SUM:
+        return getTotalLag();
+      case AVERAGE:
+        return getAvgLag();
+    }
+    throw new IllegalStateException("Unknown scale metric");
+  }
 }
diff --git a/server/src/test/java/org/apache/druid/indexing/overlord/supervisor/SupervisorTest.java b/server/src/test/java/org/apache/druid/indexing/overlord/supervisor/LagStatsTest.java
similarity index 69%
rename from server/src/test/java/org/apache/druid/indexing/overlord/supervisor/SupervisorTest.java
rename to server/src/test/java/org/apache/druid/indexing/overlord/supervisor/LagStatsTest.java
index 79811079d3..5799d8c5e8 100644
--- a/server/src/test/java/org/apache/druid/indexing/overlord/supervisor/SupervisorTest.java
+++ b/server/src/test/java/org/apache/druid/indexing/overlord/supervisor/LagStatsTest.java
@@ -19,22 +19,21 @@
 
 package org.apache.druid.indexing.overlord.supervisor;
 
+import org.apache.druid.indexing.overlord.supervisor.autoscaler.AggregateFunction;
 import org.apache.druid.indexing.overlord.supervisor.autoscaler.LagStats;
 import org.junit.Assert;
 import org.junit.Test;
-import org.mockito.Mockito;
 
-public class SupervisorTest
+public class LagStatsTest
 {
   @Test
   public void testAutoScalerLagComputation()
   {
-    Supervisor supervisor = Mockito.spy(Supervisor.class);
+    LagStats lagStats = new LagStats(1, 2, 3);
 
-    Mockito.when(supervisor.computeLagStats()).thenReturn(new LagStats(1, 2, 3));
-    Assert.assertEquals(2, supervisor.computeLagForAutoScaler());
-
-    Mockito.when(supervisor.computeLagStats()).thenReturn(null);
-    Assert.assertEquals(0, supervisor.computeLagForAutoScaler());
+    Assert.assertEquals(1, lagStats.getMetric(AggregateFunction.MAX));
+    Assert.assertEquals(2, lagStats.getMetric(AggregateFunction.SUM));
+    Assert.assertEquals(3, lagStats.getMetric(AggregateFunction.AVERAGE));
+    Assert.assertEquals(AggregateFunction.SUM, lagStats.getAggregateForScaling());
   }
 }

```

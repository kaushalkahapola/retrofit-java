# Post-Pipeline Developer Patch Comparison

**Exact Developer Patch (code-only)**: False

**Comparison Method**: file_state

## Commit Pair Consistency
- Pair mismatch: False
- Reason: scope_overlap_ok
- Mainline Java files: ['server/src/main/java/io/crate/execution/engine/distribution/DistributingConsumer.java', 'server/src/main/java/io/crate/execution/engine/distribution/DistributingConsumerFactory.java', 'server/src/main/java/io/crate/execution/engine/distribution/TransportDistributedResultAction.java']
- Developer Java files: ['server/src/main/java/io/crate/execution/engine/distribution/DistributingConsumer.java', 'server/src/main/java/io/crate/execution/engine/distribution/DistributingConsumerFactory.java', 'server/src/main/java/io/crate/execution/engine/distribution/TransportDistributedResultAction.java']
- Overlap Java files: ['server/src/main/java/io/crate/execution/engine/distribution/DistributingConsumer.java', 'server/src/main/java/io/crate/execution/engine/distribution/DistributingConsumerFactory.java', 'server/src/main/java/io/crate/execution/engine/distribution/TransportDistributedResultAction.java']
- Overlap ratio (mainline): 1.0
- Compare files scope used: ['server/src/main/java/io/crate/execution/engine/distribution/DistributingConsumer.java', 'server/src/main/java/io/crate/execution/engine/distribution/DistributingConsumerFactory.java', 'server/src/main/java/io/crate/execution/engine/distribution/TransportDistributedResultAction.java']

## File State Comparison
- Compared files: ['server/src/main/java/io/crate/execution/engine/distribution/DistributingConsumer.java', 'server/src/main/java/io/crate/execution/engine/distribution/DistributingConsumerFactory.java', 'server/src/main/java/io/crate/execution/engine/distribution/TransportDistributedResultAction.java']
- Mismatched files: ['server/src/main/java/io/crate/execution/engine/distribution/DistributingConsumer.java', 'server/src/main/java/io/crate/execution/engine/distribution/DistributingConsumerFactory.java', 'server/src/main/java/io/crate/execution/engine/distribution/TransportDistributedResultAction.java']
- Error: None

## Comparison Scope
- Agent-only patch: code hunks produced by Agent 3
- Final effective patch: agent code hunks + developer auxiliary hunks (still code-only for this report)

## Agent-Only Hunk Comparison (code files)

### server/src/main/java/io/crate/execution/engine/distribution/DistributingConsumer.java

- Developer hunks: 6
- Generated hunks: 0

#### Hunk 1

Developer
```diff
@@ -21,6 +21,8 @@
 
 package io.crate.execution.engine.distribution;
 
+import static io.crate.execution.engine.distribution.TransportDistributedResultAction.broadcastKill;
+
 import java.util.ArrayList;
 import java.util.Collection;
 import java.util.List;

```

Generated
```diff
*No hunk*
```

Developer -> Generated (Unified Diff)
```diff
--- developer+++ generated@@ -1,9 +1 @@-@@ -21,6 +21,8 @@
- 
- package io.crate.execution.engine.distribution;
- 
-+import static io.crate.execution.engine.distribution.TransportDistributedResultAction.broadcastKill;
-+
- import java.util.ArrayList;
- import java.util.Collection;
- import java.util.List;
+*No hunk*
```

#### Hunk 2

Developer
```diff
@@ -40,6 +42,8 @@
 import io.crate.data.Row;
 import io.crate.data.RowConsumer;
 import io.crate.exceptions.SQLExceptions;
+import io.crate.execution.jobs.kill.KillJobsNodeRequest;
+import io.crate.execution.jobs.kill.KillResponse;
 import io.crate.execution.support.ActionExecutor;
 import io.crate.execution.support.NodeRequest;
 

```

Generated
```diff
*No hunk*
```

Developer -> Generated (Unified Diff)
```diff
--- developer+++ generated@@ -1,9 +1 @@-@@ -40,6 +42,8 @@
- import io.crate.data.Row;
- import io.crate.data.RowConsumer;
- import io.crate.exceptions.SQLExceptions;
-+import io.crate.execution.jobs.kill.KillJobsNodeRequest;
-+import io.crate.execution.jobs.kill.KillResponse;
- import io.crate.execution.support.ActionExecutor;
- import io.crate.execution.support.NodeRequest;
- 
+*No hunk*
```

#### Hunk 3

Developer
```diff
@@ -75,6 +79,9 @@
 
     private volatile Throwable failure;
 
+    private final ActionExecutor<KillJobsNodeRequest, KillResponse> killNodeAction;
+    private final String localNodeId;
+
     public DistributingConsumer(Executor responseExecutor,
                                 UUID jobId,
                                 MultiBucketBuilder multiBucketBuilder,

```

Generated
```diff
*No hunk*
```

Developer -> Generated (Unified Diff)
```diff
--- developer+++ generated@@ -1,10 +1 @@-@@ -75,6 +79,9 @@
- 
-     private volatile Throwable failure;
- 
-+    private final ActionExecutor<KillJobsNodeRequest, KillResponse> killNodeAction;
-+    private final String localNodeId;
-+
-     public DistributingConsumer(Executor responseExecutor,
-                                 UUID jobId,
-                                 MultiBucketBuilder multiBucketBuilder,
+*No hunk*
```

#### Hunk 4

Developer
```diff
@@ -83,6 +90,8 @@
                                 int bucketIdx,
                                 Collection<String> downstreamNodeIds,
                                 ActionExecutor<NodeRequest<DistributedResultRequest>, DistributedResultResponse> distributedResultAction,
+                                ActionExecutor<KillJobsNodeRequest, KillResponse> killNodeAction,
+                                String localNodeId,
                                 int pageSize) {
         this.traceEnabled = LOGGER.isTraceEnabled();
         this.responseExecutor = responseExecutor;

```

Generated
```diff
*No hunk*
```

Developer -> Generated (Unified Diff)
```diff
--- developer+++ generated@@ -1,9 +1 @@-@@ -83,6 +90,8 @@
-                                 int bucketIdx,
-                                 Collection<String> downstreamNodeIds,
-                                 ActionExecutor<NodeRequest<DistributedResultRequest>, DistributedResultResponse> distributedResultAction,
-+                                ActionExecutor<KillJobsNodeRequest, KillResponse> killNodeAction,
-+                                String localNodeId,
-                                 int pageSize) {
-         this.traceEnabled = LOGGER.isTraceEnabled();
-         this.responseExecutor = responseExecutor;
+*No hunk*
```

#### Hunk 5

Developer
```diff
@@ -92,6 +101,8 @@
         this.inputId = inputId;
         this.bucketIdx = bucketIdx;
         this.distributedResultAction = distributedResultAction;
+        this.killNodeAction = killNodeAction;
+        this.localNodeId = localNodeId;
         this.pageSize = pageSize;
         this.buckets = new StreamBucket[downstreamNodeIds.size()];
         this.completionFuture = new CompletableFuture<>();

```

Generated
```diff
*No hunk*
```

Developer -> Generated (Unified Diff)
```diff
--- developer+++ generated@@ -1,9 +1 @@-@@ -92,6 +101,8 @@
-         this.inputId = inputId;
-         this.bucketIdx = bucketIdx;
-         this.distributedResultAction = distributedResultAction;
-+        this.killNodeAction = killNodeAction;
-+        this.localNodeId = localNodeId;
-         this.pageSize = pageSize;
-         this.buckets = new StreamBucket[downstreamNodeIds.size()];
-         this.completionFuture = new CompletableFuture<>();
+*No hunk*
```

#### Hunk 6

Developer
```diff
@@ -227,10 +238,11 @@
                                 downstream.nodeId,
                                 t
                             );
-                            failure = t;
-                            downstream.needsMoreData = false;
-                            // continue because it's necessary to send something to downstreams still waiting for data
-                            countdownAndMaybeContinue(it, numActiveRequests, false);
+                            failure = SQLExceptions.unwrap(t);
+                            String reason = "An error was encountered: " + failure;
+                            broadcastKill(killNodeAction, jobId, localNodeId, reason);
+                            it.close();
+                            completionFuture.completeExceptionally(failure);
                         }
                     }
                 );

```

Generated
```diff
*No hunk*
```

Developer -> Generated (Unified Diff)
```diff
--- developer+++ generated@@ -1,16 +1 @@-@@ -227,10 +238,11 @@
-                                 downstream.nodeId,
-                                 t
-                             );
--                            failure = t;
--                            downstream.needsMoreData = false;
--                            // continue because it's necessary to send something to downstreams still waiting for data
--                            countdownAndMaybeContinue(it, numActiveRequests, false);
-+                            failure = SQLExceptions.unwrap(t);
-+                            String reason = "An error was encountered: " + failure;
-+                            broadcastKill(killNodeAction, jobId, localNodeId, reason);
-+                            it.close();
-+                            completionFuture.completeExceptionally(failure);
-                         }
-                     }
-                 );
+*No hunk*
```


### server/src/main/java/io/crate/execution/engine/distribution/DistributingConsumerFactory.java

- Developer hunks: 4
- Generated hunks: 1

#### Hunk 1

Developer
```diff
@@ -37,6 +37,9 @@
 import io.crate.execution.dsl.phases.ExecutionPhases;
 import io.crate.execution.dsl.phases.NodeOperation;
 import io.crate.execution.jobs.PageBucketReceiver;
+import io.crate.execution.jobs.kill.KillJobsNodeAction;
+import io.crate.execution.jobs.kill.KillJobsNodeRequest;
+import io.crate.execution.jobs.kill.KillResponse;
 import io.crate.execution.support.ActionExecutor;
 import io.crate.execution.support.NodeRequest;
 import io.crate.planner.distribution.DistributionInfo;

```

Generated
```diff
@@ -49,14 +49,17 @@
     private final ClusterService clusterService;
     private final Executor responseExecutor;
     private final ActionExecutor<NodeRequest<DistributedResultRequest>, DistributedResultResponse> distributedResultAction;
+    private final ActionExecutor<KillJobsNodeRequest, KillResponse> killNodeAction;
 
     @Inject
     public DistributingConsumerFactory(ClusterService clusterService,
                                        ThreadPool threadPool,
-                                       Node node) {
+                                       Node node,
+                                       ActionExecutor<KillJobsNodeRequest, KillResponse> killNodeAction) {
         this.clusterService = clusterService;
         this.responseExecutor = threadPool.executor(RESPONSE_EXECUTOR_NAME);
         this.distributedResultAction = req -> node.client().execute(DistributedResultAction.INSTANCE, req);
+        this.killNodeAction = killNodeAction;
     }
 
     public DistributingConsumer create(NodeOperation nodeOperation,

```

Developer -> Generated (Unified Diff)
```diff
--- developer+++ generated@@ -1,10 +1,19 @@-@@ -37,6 +37,9 @@
- import io.crate.execution.dsl.phases.ExecutionPhases;
- import io.crate.execution.dsl.phases.NodeOperation;
- import io.crate.execution.jobs.PageBucketReceiver;
-+import io.crate.execution.jobs.kill.KillJobsNodeAction;
-+import io.crate.execution.jobs.kill.KillJobsNodeRequest;
-+import io.crate.execution.jobs.kill.KillResponse;
- import io.crate.execution.support.ActionExecutor;
- import io.crate.execution.support.NodeRequest;
- import io.crate.planner.distribution.DistributionInfo;
+@@ -49,14 +49,17 @@
+     private final ClusterService clusterService;
+     private final Executor responseExecutor;
+     private final ActionExecutor<NodeRequest<DistributedResultRequest>, DistributedResultResponse> distributedResultAction;
++    private final ActionExecutor<KillJobsNodeRequest, KillResponse> killNodeAction;
+ 
+     @Inject
+     public DistributingConsumerFactory(ClusterService clusterService,
+                                        ThreadPool threadPool,
+-                                       Node node) {
++                                       Node node,
++                                       ActionExecutor<KillJobsNodeRequest, KillResponse> killNodeAction) {
+         this.clusterService = clusterService;
+         this.responseExecutor = threadPool.executor(RESPONSE_EXECUTOR_NAME);
+         this.distributedResultAction = req -> node.client().execute(DistributedResultAction.INSTANCE, req);
++        this.killNodeAction = killNodeAction;
+     }
+ 
+     public DistributingConsumer create(NodeOperation nodeOperation,

```

#### Hunk 2

Developer
```diff
@@ -49,6 +52,7 @@
     private final ClusterService clusterService;
     private final Executor responseExecutor;
     private final ActionExecutor<NodeRequest<DistributedResultRequest>, DistributedResultResponse> distributedResultAction;
+    private final ActionExecutor<KillJobsNodeRequest, KillResponse> killNodeAction;
 
     @Inject
     public DistributingConsumerFactory(ClusterService clusterService,

```

Generated
```diff
*No hunk*
```

Developer -> Generated (Unified Diff)
```diff
--- developer+++ generated@@ -1,8 +1 @@-@@ -49,6 +52,7 @@
-     private final ClusterService clusterService;
-     private final Executor responseExecutor;
-     private final ActionExecutor<NodeRequest<DistributedResultRequest>, DistributedResultResponse> distributedResultAction;
-+    private final ActionExecutor<KillJobsNodeRequest, KillResponse> killNodeAction;
- 
-     @Inject
-     public DistributingConsumerFactory(ClusterService clusterService,
+*No hunk*
```

#### Hunk 3

Developer
```diff
@@ -57,6 +61,7 @@
         this.clusterService = clusterService;
         this.responseExecutor = threadPool.executor(RESPONSE_EXECUTOR_NAME);
         this.distributedResultAction = req -> node.client().execute(DistributedResultAction.INSTANCE, req);
+        this.killNodeAction = req -> node.client().execute(KillJobsNodeAction.INSTANCE, req);
     }
 
     public DistributingConsumer create(NodeOperation nodeOperation,

```

Generated
```diff
*No hunk*
```

Developer -> Generated (Unified Diff)
```diff
--- developer+++ generated@@ -1,8 +1 @@-@@ -57,6 +61,7 @@
-         this.clusterService = clusterService;
-         this.responseExecutor = threadPool.executor(RESPONSE_EXECUTOR_NAME);
-         this.distributedResultAction = req -> node.client().execute(DistributedResultAction.INSTANCE, req);
-+        this.killNodeAction = req -> node.client().execute(KillJobsNodeAction.INSTANCE, req);
-     }
- 
-     public DistributingConsumer create(NodeOperation nodeOperation,
+*No hunk*
```

#### Hunk 4

Developer
```diff
@@ -110,6 +115,8 @@
             bucketIdx,
             nodeOperation.downstreamNodes(),
             distributedResultAction,
+            killNodeAction,
+            clusterService.localNode().getId(),
             pageSize
         );
     }

```

Generated
```diff
*No hunk*
```

Developer -> Generated (Unified Diff)
```diff
--- developer+++ generated@@ -1,9 +1 @@-@@ -110,6 +115,8 @@
-             bucketIdx,
-             nodeOperation.downstreamNodes(),
-             distributedResultAction,
-+            killNodeAction,
-+            clusterService.localNode().getId(),
-             pageSize
-         );
-     }
+*No hunk*
```


### server/src/main/java/io/crate/execution/engine/distribution/TransportDistributedResultAction.java

- Developer hunks: 3
- Generated hunks: 0

#### Hunk 1

Developer
```diff
@@ -25,6 +25,7 @@
 import java.util.Iterator;
 import java.util.List;
 import java.util.Locale;
+import java.util.UUID;
 import java.util.concurrent.CompletableFuture;
 import java.util.concurrent.ScheduledExecutorService;
 import java.util.concurrent.TimeUnit;

```

Generated
```diff
*No hunk*
```

Developer -> Generated (Unified Diff)
```diff
--- developer+++ generated@@ -1,8 +1 @@-@@ -25,6 +25,7 @@
- import java.util.Iterator;
- import java.util.List;
- import java.util.Locale;
-+import java.util.UUID;
- import java.util.concurrent.CompletableFuture;
- import java.util.concurrent.ScheduledExecutorService;
- import java.util.concurrent.TimeUnit;
+*No hunk*
```

#### Hunk 2

Developer
```diff
@@ -110,10 +111,7 @@
             DistributedResultAction.NAME,
             ThreadPool.Names.SAME, // <- we will dispatch later at the nodeOperation on non failures
             true,
-            // Don't trip breaker on transport layer, but instead depend on ram-accounting in PageBucketReceivers
-            // We need to always handle requests to avoid jobs from getting stuck.
-            // (If we receive a request, but don't handle it, a task would remain open indefinitely)
-            false,
+            true,
             DistributedResultRequest::new,
             new NodeActionRequestHandler<>(nodeAction));
     }

```

Generated
```diff
*No hunk*
```

Developer -> Generated (Unified Diff)
```diff
--- developer+++ generated@@ -1,12 +1 @@-@@ -110,10 +111,7 @@
-             DistributedResultAction.NAME,
-             ThreadPool.Names.SAME, // <- we will dispatch later at the nodeOperation on non failures
-             true,
--            // Don't trip breaker on transport layer, but instead depend on ram-accounting in PageBucketReceivers
--            // We need to always handle requests to avoid jobs from getting stuck.
--            // (If we receive a request, but don't handle it, a task would remain open indefinitely)
--            false,
-+            true,
-             DistributedResultRequest::new,
-             new NodeActionRequestHandler<>(nodeAction));
-     }
+*No hunk*
```

#### Hunk 3

Developer
```diff
@@ -204,33 +202,43 @@
             if (LOGGER.isTraceEnabled()) {
                 LOGGER.trace("Received a result for job={} but couldn't find a RootTask for it", request.jobId());
             }
-            List<String> excludedNodeIds = Collections.singletonList(clusterService.localNode().getId());
             /* The upstream (DistributingConsumer) forwards failures to other downstreams and eventually considers its job done.
              * But it cannot inform the handler-merge about a failure because the JobResponse is sent eagerly.
              *
              * The handler local-merge would get stuck if not all its upstreams send their requests, so we need to invoke
              * a kill to make sure that doesn't happen.
              */
-            KillJobsNodeRequest killRequest = new KillJobsNodeRequest(
-                excludedNodeIds,
-                List.of(request.jobId()),
-                Role.CRATE_USER.name(),
-                "Received data for job=" + request.jobId() + " but there is no job context present. " +
-                "This can happen due to bad network latency or if individual nodes are unresponsive due to high load"
-            );
-            killNodeAction
-                .execute(killRequest)
-                .whenComplete(
-                    (resp, t) -> {
-                        if (t != null) {
-                            LOGGER.debug("Could not kill " + request.jobId(), t);
-                        }
-                    }
-                );
+            String reason = "Received data for job=" + request.jobId() + " but there is no job context present. " +
+                "This can happen due to bad network latency or if individual nodes are unresponsive due to high load";
+            broadcastKill(killNodeAction, request.jobId(), clusterService.localNode().getId(), reason);
             return CompletableFuture.failedFuture(new TaskMissing(TaskMissing.Type.ROOT, request.jobId()));
         }
     }
 
+    /**
+     * Sends KILL request to all nodes (excluding sender node).
+     */
+    public static void broadcastKill(ActionExecutor<KillJobsNodeRequest, KillResponse> killNodeAction,
+                                     UUID jobId,
+                                     String localNodeId,
+                                     String reason) {
+        List<String> excludedNodeIds = Collections.singletonList(localNodeId);
+
+        KillJobsNodeRequest killRequest = new KillJobsNodeRequest(
+            excludedNodeIds,
+            List.of(jobId),
+            Role.CRATE_USER.name(),
+            reason
+        );
+        killNodeAction
+            .execute(killRequest)
+            .whenComplete((_, t) -> {
+                if (t != null) {
+                    LOGGER.debug("Could not kill " + jobId, t);
+                }
+            });
+    }
+
     private static class SendResponsePageResultListener implements PageResultListener {
         private final CompletableFuture<DistributedResultResponse> future = new CompletableFuture<>();
 

```

Generated
```diff
*No hunk*
```

Developer -> Generated (Unified Diff)
```diff
--- developer+++ generated@@ -1,61 +1 @@-@@ -204,33 +202,43 @@
-             if (LOGGER.isTraceEnabled()) {
-                 LOGGER.trace("Received a result for job={} but couldn't find a RootTask for it", request.jobId());
-             }
--            List<String> excludedNodeIds = Collections.singletonList(clusterService.localNode().getId());
-             /* The upstream (DistributingConsumer) forwards failures to other downstreams and eventually considers its job done.
-              * But it cannot inform the handler-merge about a failure because the JobResponse is sent eagerly.
-              *
-              * The handler local-merge would get stuck if not all its upstreams send their requests, so we need to invoke
-              * a kill to make sure that doesn't happen.
-              */
--            KillJobsNodeRequest killRequest = new KillJobsNodeRequest(
--                excludedNodeIds,
--                List.of(request.jobId()),
--                Role.CRATE_USER.name(),
--                "Received data for job=" + request.jobId() + " but there is no job context present. " +
--                "This can happen due to bad network latency or if individual nodes are unresponsive due to high load"
--            );
--            killNodeAction
--                .execute(killRequest)
--                .whenComplete(
--                    (resp, t) -> {
--                        if (t != null) {
--                            LOGGER.debug("Could not kill " + request.jobId(), t);
--                        }
--                    }
--                );
-+            String reason = "Received data for job=" + request.jobId() + " but there is no job context present. " +
-+                "This can happen due to bad network latency or if individual nodes are unresponsive due to high load";
-+            broadcastKill(killNodeAction, request.jobId(), clusterService.localNode().getId(), reason);
-             return CompletableFuture.failedFuture(new TaskMissing(TaskMissing.Type.ROOT, request.jobId()));
-         }
-     }
- 
-+    /**
-+     * Sends KILL request to all nodes (excluding sender node).
-+     */
-+    public static void broadcastKill(ActionExecutor<KillJobsNodeRequest, KillResponse> killNodeAction,
-+                                     UUID jobId,
-+                                     String localNodeId,
-+                                     String reason) {
-+        List<String> excludedNodeIds = Collections.singletonList(localNodeId);
-+
-+        KillJobsNodeRequest killRequest = new KillJobsNodeRequest(
-+            excludedNodeIds,
-+            List.of(jobId),
-+            Role.CRATE_USER.name(),
-+            reason
-+        );
-+        killNodeAction
-+            .execute(killRequest)
-+            .whenComplete((_, t) -> {
-+                if (t != null) {
-+                    LOGGER.debug("Could not kill " + jobId, t);
-+                }
-+            });
-+    }
-+
-     private static class SendResponsePageResultListener implements PageResultListener {
-         private final CompletableFuture<DistributedResultResponse> future = new CompletableFuture<>();
- 
+*No hunk*
```



## Full Generated Patch (Agent-Only, code-only)
```diff
diff --git a/server/src/main/java/io/crate/execution/engine/distribution/DistributingConsumerFactory.java b/server/src/main/java/io/crate/execution/engine/distribution/DistributingConsumerFactory.java
index 3dc1921a76..40461e0351 100644
--- a/server/src/main/java/io/crate/execution/engine/distribution/DistributingConsumerFactory.java
+++ b/server/src/main/java/io/crate/execution/engine/distribution/DistributingConsumerFactory.java
@@ -49,14 +49,17 @@ public class DistributingConsumerFactory {
     private final ClusterService clusterService;
     private final Executor responseExecutor;
     private final ActionExecutor<NodeRequest<DistributedResultRequest>, DistributedResultResponse> distributedResultAction;
+    private final ActionExecutor<KillJobsNodeRequest, KillResponse> killNodeAction;
 
     @Inject
     public DistributingConsumerFactory(ClusterService clusterService,
                                        ThreadPool threadPool,
-                                       Node node) {
+                                       Node node,
+                                       ActionExecutor<KillJobsNodeRequest, KillResponse> killNodeAction) {
         this.clusterService = clusterService;
         this.responseExecutor = threadPool.executor(RESPONSE_EXECUTOR_NAME);
         this.distributedResultAction = req -> node.client().execute(DistributedResultAction.INSTANCE, req);
+        this.killNodeAction = killNodeAction;
     }
 
     public DistributingConsumer create(NodeOperation nodeOperation,

```

## Full Generated Patch (Final Effective, code-only)
```diff
diff --git a/server/src/main/java/io/crate/execution/engine/distribution/DistributingConsumerFactory.java b/server/src/main/java/io/crate/execution/engine/distribution/DistributingConsumerFactory.java
index 3dc1921a76..40461e0351 100644
--- a/server/src/main/java/io/crate/execution/engine/distribution/DistributingConsumerFactory.java
+++ b/server/src/main/java/io/crate/execution/engine/distribution/DistributingConsumerFactory.java
@@ -49,14 +49,17 @@ public class DistributingConsumerFactory {
     private final ClusterService clusterService;
     private final Executor responseExecutor;
     private final ActionExecutor<NodeRequest<DistributedResultRequest>, DistributedResultResponse> distributedResultAction;
+    private final ActionExecutor<KillJobsNodeRequest, KillResponse> killNodeAction;
 
     @Inject
     public DistributingConsumerFactory(ClusterService clusterService,
                                        ThreadPool threadPool,
-                                       Node node) {
+                                       Node node,
+                                       ActionExecutor<KillJobsNodeRequest, KillResponse> killNodeAction) {
         this.clusterService = clusterService;
         this.responseExecutor = threadPool.executor(RESPONSE_EXECUTOR_NAME);
         this.distributedResultAction = req -> node.client().execute(DistributedResultAction.INSTANCE, req);
+        this.killNodeAction = killNodeAction;
     }
 
     public DistributingConsumer create(NodeOperation nodeOperation,

```
## Full Developer Backport Patch (full commit diff)
```diff
diff --git a/server/src/main/java/io/crate/execution/engine/distribution/DistributingConsumer.java b/server/src/main/java/io/crate/execution/engine/distribution/DistributingConsumer.java
index 12171a4a54..203889b1e5 100644
--- a/server/src/main/java/io/crate/execution/engine/distribution/DistributingConsumer.java
+++ b/server/src/main/java/io/crate/execution/engine/distribution/DistributingConsumer.java
@@ -21,6 +21,8 @@
 
 package io.crate.execution.engine.distribution;
 
+import static io.crate.execution.engine.distribution.TransportDistributedResultAction.broadcastKill;
+
 import java.util.ArrayList;
 import java.util.Collection;
 import java.util.List;
@@ -40,6 +42,8 @@ import io.crate.data.Paging;
 import io.crate.data.Row;
 import io.crate.data.RowConsumer;
 import io.crate.exceptions.SQLExceptions;
+import io.crate.execution.jobs.kill.KillJobsNodeRequest;
+import io.crate.execution.jobs.kill.KillResponse;
 import io.crate.execution.support.ActionExecutor;
 import io.crate.execution.support.NodeRequest;
 
@@ -75,6 +79,9 @@ public class DistributingConsumer implements RowConsumer {
 
     private volatile Throwable failure;
 
+    private final ActionExecutor<KillJobsNodeRequest, KillResponse> killNodeAction;
+    private final String localNodeId;
+
     public DistributingConsumer(Executor responseExecutor,
                                 UUID jobId,
                                 MultiBucketBuilder multiBucketBuilder,
@@ -83,6 +90,8 @@ public class DistributingConsumer implements RowConsumer {
                                 int bucketIdx,
                                 Collection<String> downstreamNodeIds,
                                 ActionExecutor<NodeRequest<DistributedResultRequest>, DistributedResultResponse> distributedResultAction,
+                                ActionExecutor<KillJobsNodeRequest, KillResponse> killNodeAction,
+                                String localNodeId,
                                 int pageSize) {
         this.traceEnabled = LOGGER.isTraceEnabled();
         this.responseExecutor = responseExecutor;
@@ -92,6 +101,8 @@ public class DistributingConsumer implements RowConsumer {
         this.inputId = inputId;
         this.bucketIdx = bucketIdx;
         this.distributedResultAction = distributedResultAction;
+        this.killNodeAction = killNodeAction;
+        this.localNodeId = localNodeId;
         this.pageSize = pageSize;
         this.buckets = new StreamBucket[downstreamNodeIds.size()];
         this.completionFuture = new CompletableFuture<>();
@@ -227,10 +238,11 @@ public class DistributingConsumer implements RowConsumer {
                                 downstream.nodeId,
                                 t
                             );
-                            failure = t;
-                            downstream.needsMoreData = false;
-                            // continue because it's necessary to send something to downstreams still waiting for data
-                            countdownAndMaybeContinue(it, numActiveRequests, false);
+                            failure = SQLExceptions.unwrap(t);
+                            String reason = "An error was encountered: " + failure;
+                            broadcastKill(killNodeAction, jobId, localNodeId, reason);
+                            it.close();
+                            completionFuture.completeExceptionally(failure);
                         }
                     }
                 );
diff --git a/server/src/main/java/io/crate/execution/engine/distribution/DistributingConsumerFactory.java b/server/src/main/java/io/crate/execution/engine/distribution/DistributingConsumerFactory.java
index 3dc1921a76..ee47d15116 100644
--- a/server/src/main/java/io/crate/execution/engine/distribution/DistributingConsumerFactory.java
+++ b/server/src/main/java/io/crate/execution/engine/distribution/DistributingConsumerFactory.java
@@ -37,6 +37,9 @@ import io.crate.data.breaker.RamAccounting;
 import io.crate.execution.dsl.phases.ExecutionPhases;
 import io.crate.execution.dsl.phases.NodeOperation;
 import io.crate.execution.jobs.PageBucketReceiver;
+import io.crate.execution.jobs.kill.KillJobsNodeAction;
+import io.crate.execution.jobs.kill.KillJobsNodeRequest;
+import io.crate.execution.jobs.kill.KillResponse;
 import io.crate.execution.support.ActionExecutor;
 import io.crate.execution.support.NodeRequest;
 import io.crate.planner.distribution.DistributionInfo;
@@ -49,6 +52,7 @@ public class DistributingConsumerFactory {
     private final ClusterService clusterService;
     private final Executor responseExecutor;
     private final ActionExecutor<NodeRequest<DistributedResultRequest>, DistributedResultResponse> distributedResultAction;
+    private final ActionExecutor<KillJobsNodeRequest, KillResponse> killNodeAction;
 
     @Inject
     public DistributingConsumerFactory(ClusterService clusterService,
@@ -57,6 +61,7 @@ public class DistributingConsumerFactory {
         this.clusterService = clusterService;
         this.responseExecutor = threadPool.executor(RESPONSE_EXECUTOR_NAME);
         this.distributedResultAction = req -> node.client().execute(DistributedResultAction.INSTANCE, req);
+        this.killNodeAction = req -> node.client().execute(KillJobsNodeAction.INSTANCE, req);
     }
 
     public DistributingConsumer create(NodeOperation nodeOperation,
@@ -110,6 +115,8 @@ public class DistributingConsumerFactory {
             bucketIdx,
             nodeOperation.downstreamNodes(),
             distributedResultAction,
+            killNodeAction,
+            clusterService.localNode().getId(),
             pageSize
         );
     }
diff --git a/server/src/main/java/io/crate/execution/engine/distribution/TransportDistributedResultAction.java b/server/src/main/java/io/crate/execution/engine/distribution/TransportDistributedResultAction.java
index 4d64814dd5..d34fc3eb6a 100644
--- a/server/src/main/java/io/crate/execution/engine/distribution/TransportDistributedResultAction.java
+++ b/server/src/main/java/io/crate/execution/engine/distribution/TransportDistributedResultAction.java
@@ -25,6 +25,7 @@ import java.util.Collections;
 import java.util.Iterator;
 import java.util.List;
 import java.util.Locale;
+import java.util.UUID;
 import java.util.concurrent.CompletableFuture;
 import java.util.concurrent.ScheduledExecutorService;
 import java.util.concurrent.TimeUnit;
@@ -110,10 +111,7 @@ public class TransportDistributedResultAction extends TransportAction<NodeReques
             DistributedResultAction.NAME,
             ThreadPool.Names.SAME, // <- we will dispatch later at the nodeOperation on non failures
             true,
-            // Don't trip breaker on transport layer, but instead depend on ram-accounting in PageBucketReceivers
-            // We need to always handle requests to avoid jobs from getting stuck.
-            // (If we receive a request, but don't handle it, a task would remain open indefinitely)
-            false,
+            true,
             DistributedResultRequest::new,
             new NodeActionRequestHandler<>(nodeAction));
     }
@@ -204,33 +202,43 @@ public class TransportDistributedResultAction extends TransportAction<NodeReques
             if (LOGGER.isTraceEnabled()) {
                 LOGGER.trace("Received a result for job={} but couldn't find a RootTask for it", request.jobId());
             }
-            List<String> excludedNodeIds = Collections.singletonList(clusterService.localNode().getId());
             /* The upstream (DistributingConsumer) forwards failures to other downstreams and eventually considers its job done.
              * But it cannot inform the handler-merge about a failure because the JobResponse is sent eagerly.
              *
              * The handler local-merge would get stuck if not all its upstreams send their requests, so we need to invoke
              * a kill to make sure that doesn't happen.
              */
-            KillJobsNodeRequest killRequest = new KillJobsNodeRequest(
-                excludedNodeIds,
-                List.of(request.jobId()),
-                Role.CRATE_USER.name(),
-                "Received data for job=" + request.jobId() + " but there is no job context present. " +
-                "This can happen due to bad network latency or if individual nodes are unresponsive due to high load"
-            );
-            killNodeAction
-                .execute(killRequest)
-                .whenComplete(
-                    (resp, t) -> {
-                        if (t != null) {
-                            LOGGER.debug("Could not kill " + request.jobId(), t);
-                        }
-                    }
-                );
+            String reason = "Received data for job=" + request.jobId() + " but there is no job context present. " +
+                "This can happen due to bad network latency or if individual nodes are unresponsive due to high load";
+            broadcastKill(killNodeAction, request.jobId(), clusterService.localNode().getId(), reason);
             return CompletableFuture.failedFuture(new TaskMissing(TaskMissing.Type.ROOT, request.jobId()));
         }
     }
 
+    /**
+     * Sends KILL request to all nodes (excluding sender node).
+     */
+    public static void broadcastKill(ActionExecutor<KillJobsNodeRequest, KillResponse> killNodeAction,
+                                     UUID jobId,
+                                     String localNodeId,
+                                     String reason) {
+        List<String> excludedNodeIds = Collections.singletonList(localNodeId);
+
+        KillJobsNodeRequest killRequest = new KillJobsNodeRequest(
+            excludedNodeIds,
+            List.of(jobId),
+            Role.CRATE_USER.name(),
+            reason
+        );
+        killNodeAction
+            .execute(killRequest)
+            .whenComplete((_, t) -> {
+                if (t != null) {
+                    LOGGER.debug("Could not kill " + jobId, t);
+                }
+            });
+    }
+
     private static class SendResponsePageResultListener implements PageResultListener {
         private final CompletableFuture<DistributedResultResponse> future = new CompletableFuture<>();
 
diff --git a/server/src/test/java/io/crate/execution/engine/distribution/DistributingConsumerTest.java b/server/src/test/java/io/crate/execution/engine/distribution/DistributingConsumerTest.java
index 290cc91397..4ff0ea3e27 100644
--- a/server/src/test/java/io/crate/execution/engine/distribution/DistributingConsumerTest.java
+++ b/server/src/test/java/io/crate/execution/engine/distribution/DistributingConsumerTest.java
@@ -172,6 +172,10 @@ public class DistributingConsumerTest extends ESTestCase {
             0,
             Collections.singletonList("n1"),
             distributedResultAction::execute,
+            // killAction and localNodeId are irrelevant for those tests,
+            // They are relevant for the test_dist_result_request_tripped_by_cb_no_stuck_jobs
+            null,
+            null,
             2 // pageSize
         );
     }
diff --git a/server/src/test/java/io/crate/integrationtests/GroupByAggregateTest.java b/server/src/test/java/io/crate/integrationtests/GroupByAggregateTest.java
index b285aa1eec..2065e5d661 100644
--- a/server/src/test/java/io/crate/integrationtests/GroupByAggregateTest.java
+++ b/server/src/test/java/io/crate/integrationtests/GroupByAggregateTest.java
@@ -26,18 +26,28 @@ import static io.crate.protocols.postgres.PGErrorStatus.INTERNAL_ERROR;
 import static io.crate.testing.Asserts.assertThat;
 import static io.crate.testing.TestingHelpers.printedTable;
 import static io.netty.handler.codec.http.HttpResponseStatus.BAD_REQUEST;
+import static org.assertj.core.api.Assertions.assertThatThrownBy;
 import static org.assertj.core.api.Assertions.fail;
 
 import java.util.Arrays;
+import java.util.Collection;
 import java.util.List;
 import java.util.stream.Stream;
 
 import org.assertj.core.data.Percentage;
+import org.elasticsearch.common.breaker.CircuitBreakingException;
+import org.elasticsearch.plugins.Plugin;
 import org.elasticsearch.test.IntegTestCase;
+import org.elasticsearch.test.transport.MockTransportService;
+import org.elasticsearch.transport.TransportService;
 import org.junit.Before;
 import org.junit.Test;
 
+import io.crate.common.collections.Lists;
+import io.crate.common.unit.TimeValue;
 import io.crate.data.Paging;
+import io.crate.exceptions.JobKilledException;
+import io.crate.execution.engine.distribution.DistributedResultAction;
 import io.crate.testing.Asserts;
 import io.crate.testing.SQLResponse;
 import io.crate.testing.UseJdbc;
@@ -48,11 +58,43 @@ public class GroupByAggregateTest extends IntegTestCase {
 
     private final Setup setup = new Setup(sqlExecutor);
 
+
     @Before
     public void initTestData() {
         setup.setUpEmployees();
     }
 
+    @Override
+    protected Collection<Class<? extends Plugin>> nodePlugins() {
+        return Lists.concat(super.nodePlugins(), MockTransportService.TestPlugin.class);
+    }
+
+
+    @Test
+    @UseJdbc(value = 0) // To avoid wrapping into PSQLException
+    public void test_dist_result_request_tripped_by_cb_no_stuck_jobs() throws Exception {
+        this.setup.groupBySetup("integer");
+        for (TransportService transportService : cluster().getDataOrMasterNodeInstances(TransportService.class)) {
+            MockTransportService mockTransportService = (MockTransportService) transportService;
+            mockTransportService.addRequestHandlingBehavior(DistributedResultAction.NAME, (handler, request, channel) -> {
+                throw new CircuitBreakingException("dummy");
+            });
+        }
+
+        // Using assertBusy to avoid flakiness.
+        // Sometimes a single select doesn't throw CBE, because of non-distributed execution.
+        // Depends on data distribution and which node out of 2 is selected to be a handler.
+        assertBusy(() -> {
+            try (var session = sqlExecutor.newSession()) {
+                // Timeout defeats the purpose of this test, ensure it's not applied.
+                session.sessionSettings().statementTimeout(TimeValue.ZERO);
+                assertThatThrownBy(() ->
+                    execute("select min(age) as minage, gender from characters group by gender order by gender", session)
+                ).isInstanceOfAny(JobKilledException.class, CircuitBreakingException.class);
+            }
+        });
+    }
+
     @Test
     public void selectGroupByAggregateMinInteger() throws Exception {
         this.setup.groupBySetup("integer");

```

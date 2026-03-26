#!/bin/bash
# Runs targeted Elasticsearch tests inside Docker.
# Compatible with evaluate_full_workflow.py — uses the same IMAGE_TAG and volumes
# as run_build.sh so compiled Gradle outputs are reused.
set -e

echo "=== Running Elasticsearch Tests for ${COMMIT_SHA:0:7} ==="
echo "Target: ${TEST_TARGETS}"

IMAGE_TAG="${IMAGE_TAG:-retrofit-elasticsearch-builder:local}"

echo "--- Using Docker Image: ${IMAGE_TAG} ---"

# 1. Determine Gradle test command from TEST_TARGETS.
#
# TEST_TARGETS format (set by ValidationToolkit.run_relevant_tests):
#   "module:ClassName"   →  e.g. "server:org.elasticsearch.index.FooTests"
#   Space-separated for multiple targets.
#   "ALL"  — run everything
#   "NONE" — skip
#
if [ "${TEST_TARGETS:-}" == "ALL" ]; then
    GRADLE_ARGS="test --no-daemon -Dbuild.docker=false"
elif [ "${TEST_TARGETS:-}" == "NONE" ]; then
    echo "No relevant test targets. Skipping tests."
    exit 0
elif [ -n "${TEST_TARGETS:-}" ]; then
    # Build a list of Gradle task args: ":module:test --tests ClassName" per target.
    GRADLE_ARGS=""
    for target in ${TEST_TARGETS}; do
        # target is "module:FullClassName"
        module="${target%%:*}"
        cls="${target#*:}"
        # Convert Maven-style module path (with /) to Gradle project path (:).
        gradle_module=":${module//\///:}"
        # Strip leading double-colon if module starts with /.
        gradle_module="${gradle_module//::/:}"
        if [ -n "${GRADLE_ARGS}" ]; then
            GRADLE_ARGS="${GRADLE_ARGS} ${gradle_module}:test"
        else
            GRADLE_ARGS="${gradle_module}:test"
        fi
        GRADLE_ARGS="${GRADLE_ARGS} --tests \"${cls}\""
    done
    GRADLE_ARGS="${GRADLE_ARGS} --no-daemon -Dbuild.docker=false -DfailIfNoTests=false"
elif [ -n "${TEST_MODULES:-}" ]; then
    # Module-level fallback — run all tests in the module.
    GRADLE_ARGS=""
    IFS=',' read -ra MODS <<< "${TEST_MODULES}"
    for mod in "${MODS[@]}"; do
        gradle_module=":${mod//\///:}"
        gradle_module="${gradle_module//::/:}"
        GRADLE_ARGS="${GRADLE_ARGS} ${gradle_module}:test"
    done
    GRADLE_ARGS="${GRADLE_ARGS} --no-daemon -Dbuild.docker=false"
else
    echo "No TEST_TARGETS or TEST_MODULES set. Skipping tests."
    exit 0
fi

DOCKER_CMD="docker"
if ! docker info > /dev/null 2>&1; then
    if sudo docker info > /dev/null 2>&1; then
        echo "Docker requires sudo. Using 'sudo docker'."
        DOCKER_CMD="sudo docker"
    else
        echo "Warning: Docker not accessible. Proceeding anyway."
    fi
fi

${DOCKER_CMD} volume create gradle-cache-es 2>/dev/null || true
${DOCKER_CMD} volume create gradle-wrapper-es 2>/dev/null || true

GRADLE_CMD="./gradlew ${GRADLE_ARGS}"
echo "--- Executing: ${GRADLE_CMD} ---"

if ${DOCKER_CMD} run --rm \
    --dns=8.8.8.8 \
    -u 1000:1000 \
    -v "gradle-cache-es:/home/gradle/.gradle/caches" \
    -v "gradle-wrapper-es:/home/gradle/.gradle/wrapper" \
    -v "${PROJECT_DIR}:/repo" \
    -w /repo \
    "${IMAGE_TAG}" \
    bash -c "git config --global --add safe.directory /repo && \
    ${GRADLE_CMD}; \
    GRADLE_EXIT=\$?; \
    echo '--- Test results are available in build/test-results/ ---'; \
    exit \$GRADLE_EXIT"; then
    echo "✅ Tests Passed"
    exit 0
else
    echo "❌ Tests Failed"
    exit 1
fi
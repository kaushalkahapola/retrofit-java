#!/bin/bash
# Runs targeted Elasticsearch tests inside Docker.
# Compatible with evaluate_full_workflow.py — uses the same IMAGE_TAG and volumes
# as run_build.sh so compiled Gradle outputs are reused.
set -e

echo "=== Running Elasticsearch Tests for ${COMMIT_SHA:0:7} ==="
echo "Target: ${TEST_TARGETS}"

HOST_UID="${HOST_UID:-$(id -u)}"
HOST_GID="${HOST_GID:-$(id -g)}"
echo "--- Container user: ${HOST_UID}:${HOST_GID} ---"

IMAGE_TAG="${IMAGE_TAG:-retrofit-elasticsearch-builder:local}"

MAX_CPU="${MAX_CPU:-$(getconf _NPROCESSORS_ONLN 2>/dev/null || nproc 2>/dev/null || echo 1)}"
echo "--- Using Docker Image: ${IMAGE_TAG} ---"
echo "CPU detected: ${MAX_CPU}"

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
elif [ -n "${TEST_TARGETS:-}" ] && [ "${TEST_TARGETS}" != "NONE" ]; then
    # Build a list of Gradle task args per target.
    # Prefer source-set specific tasks when detectable from changed file hints:
    # - src/internalClusterTest -> :module:internalClusterTest --tests Class
    # - src/test                -> :module:test --tests Class
    GRADLE_ARGS=""
    TEST_TARGET_FILES_LIST=()
    if [ -n "${TEST_TARGET_FILES:-}" ]; then
        IFS=',' read -ra TEST_TARGET_FILES_LIST <<< "${TEST_TARGET_FILES}"
    fi

    resolve_test_tasks() {
        local module="$1"
        local cls="$2"
        local class_file
        class_file="${cls//./\/}.java"

        local file
        for file in "${TEST_TARGET_FILES_LIST[@]}"; do
            [ -z "${file}" ] && continue
            if [[ "${file}" == *"${class_file}" ]]; then
                if [[ "${file}" == */src/internalClusterTest/* ]]; then
                    echo "internalClusterTest"
                    return
                fi
                if [[ "${file}" == */src/test/* ]]; then
                    echo "test"
                    return
                fi
            fi
        done

        # Unknown source-set mapping: run both tasks to avoid silently skipping
        # internalClusterTest classes when only class names are provided.
        echo "test,internalClusterTest"
    }

    for target in ${TEST_TARGETS}; do
        # target is "module:FullClassName"
        module="${target%%:*}"
        cls="${target#*:}"
        # Convert Maven-style module path (with /) to Gradle project path (:).
        gradle_module=":${module//\//:}"
        # Strip leading double-colon if module starts with /.
        gradle_module="${gradle_module//::/:}"
        test_tasks_csv="$(resolve_test_tasks "${module}" "${cls}")"
        IFS=',' read -ra TEST_TASKS <<< "${test_tasks_csv}"
        for test_task in "${TEST_TASKS[@]}"; do
            [ -z "${test_task}" ] && continue
            if [ -n "${GRADLE_ARGS}" ]; then
                GRADLE_ARGS="${GRADLE_ARGS} ${gradle_module}:${test_task}"
            else
                GRADLE_ARGS="${gradle_module}:${test_task}"
            fi
            GRADLE_ARGS="${GRADLE_ARGS} --tests \"${cls}\""
        done
    done
    GRADLE_ARGS="${GRADLE_ARGS} --no-daemon -Dbuild.docker=false -DfailIfNoTests=false"
elif [ -n "${TEST_MODULES:-}" ]; then
    # Module-level fallback — run all tests in the module.
    GRADLE_ARGS=""
    IFS=',' read -ra MODS <<< "${TEST_MODULES}"
    for mod in "${MODS[@]}"; do
        gradle_module=":${mod//\//:}"
        gradle_module="${gradle_module//::/:}"
        GRADLE_ARGS="${GRADLE_ARGS} ${gradle_module}:test"
    done
    GRADLE_ARGS="${GRADLE_ARGS} --no-daemon -Dbuild.docker=false"
elif [ "${TEST_TARGETS:-}" == "NONE" ]; then
    echo "No relevant test targets. Skipping tests."
    exit 0
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

echo "--- Setting cache permissions ---"
${DOCKER_CMD} run --rm -u root \
    -v "gradle-cache-es:/home/gradle/.gradle/caches" \
    -v "gradle-wrapper-es:/home/gradle/.gradle/wrapper" \
    "${IMAGE_TAG}" \
    chown -R "${HOST_UID}:${HOST_GID}" /home/gradle/.gradle

GRADLE_CMD="./gradlew ${GRADLE_ARGS} --max-workers=${MAX_CPU} --project-cache-dir /tmp/gradle-project-cache"
echo "--- Executing: ${GRADLE_CMD} ---"

if ${DOCKER_CMD} run --rm \
    --dns=8.8.8.8 \
    -e HOME=/tmp \
    -e XDG_CONFIG_HOME=/tmp \
    -u "${HOST_UID}:${HOST_GID}" \
    -v "gradle-cache-es:/home/gradle/.gradle/caches" \
    -v "gradle-wrapper-es:/home/gradle/.gradle/wrapper" \
    -v "${PROJECT_DIR}:/repo" \
    -w /repo \
    "${IMAGE_TAG}" \
    bash -c "git config --global --add safe.directory /repo || true; \
    export GRADLE_OPTS=\"\${GRADLE_OPTS:-} -XX:ActiveProcessorCount=${MAX_CPU}\"; \
    mkdir -p /tmp/gradle-project-cache && \
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

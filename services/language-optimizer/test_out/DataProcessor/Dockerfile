# ── GraalVM Polyglot Optimizer — Auto-generated Dockerfile ─────────────────
# Stage 1: compile C/C++ to LLVM bitcode
FROM ubuntu:22.04 AS builder
RUN apt-get update -q && apt-get install -y -q clang && rm -rf /var/lib/apt/lists/*
WORKDIR /build
COPY native/ ./native/
RUN for f in native/*.c; do \
        [ -f "$f" ] || continue; \
        name=$(basename "$f" .c); \
        clang -O2 -emit-llvm -c "$f" -o "native/$name.bc" \
        --target=x86_64-unknown-linux-gnu \
        && echo "OK $name.bc" || echo "FAIL $f"; \
    done
RUN for f in native/*.cpp; do \
        [ -f "$f" ] || continue; \
        name=$(basename "$f" .cpp); \
        clang++ -O2 -emit-llvm -c "$f" -o "native/$name.bc" \
        --target=x86_64-unknown-linux-gnu \
        && echo "OK $name.bc" || echo "FAIL $f"; \
    done

# Stage 2: GraalVM CE 22.3.3 runtime
FROM ubuntu:20.04 AS runtime
ENV DEBIAN_FRONTEND=noninteractive GRAALVM_HOME=/opt/graalvm
RUN apt-get update -q && apt-get install -y -q curl tar && rm -rf /var/lib/apt/lists/*
RUN curl -sL \
    https://github.com/graalvm/graalvm-ce-builds/releases/download/vm-22.3.3/graalvm-ce-java17-linux-amd64-22.3.3.tar.gz \
    | tar -xz -C /opt && mv /opt/graalvm-ce-java17-22.3.3 /opt/graalvm
ENV PATH="/opt/graalvm/bin:$PATH" JAVA_HOME="/opt/graalvm"
RUN gu install llvm llvm-toolchain
RUN mkdir -p /app/out
WORKDIR /app
COPY . .
COPY --from=builder /build/native/*.bc ./native/

# Stage 3: compile and run test suite
FROM runtime AS tester
RUN mkdir -p /app/out/com/example && \
    cp /app/DataProcessor.java /app/out/com/example/DataProcessor.java && \
    javac -encoding UTF-8 -d /app/out /app/out/com/example/DataProcessor.java /app/TestSuite.java && \
    java -cp /app/out \
         -Dpolyglot.engine.WarnInterpreterOnly=false \
         -Dpolyglot.llvm.verifyBitcode=false \
         -Dnative.dir=/app/native \
         TestSuite

# Stage 4: final image -- only reachable if Stage 3 tests passed
FROM tester AS final
# Original command: java DataProcessor.java
ENTRYPOINT ["bash", "run.sh"]
CMD []

# heartcube/Dockerfile
# Builds cube from source with Data Model IDE modifications
# Based on dev.Dockerfile — Rust build skipped (uses pre-built cubestore binary)

# ── Stage 1: TypeScript + Vite build ─────────────────────────────────────────
FROM node:22.22.0-bookworm-slim AS builder

ENV CUBESTORE_SKIP_POST_INSTALL=true
ENV NODE_ENV=development
ENV CI=0

RUN apt-get update && apt-get install -y --no-install-recommends \
    python3 python3.11 libpython3.11-dev gcc g++ make cmake \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /cubejs

RUN yarn policies set-version v1.22.22 && \
    yarn config set network-timeout 120000 -g

# ── Layer: workspace manifests (changes rarely → good cache hit) ──────────────
COPY package.json lerna.json yarn.lock tsconfig.base.json rollup.config.js ./
COPY packages/cubejs-linter/ packages/cubejs-linter/

# Copy package.json files only first (for dependency-layer caching)
COPY packages/cubejs-backend-shared/package.json      packages/cubejs-backend-shared/package.json
COPY packages/cubejs-base-driver/package.json          packages/cubejs-base-driver/package.json
COPY packages/cubejs-api-gateway/package.json          packages/cubejs-api-gateway/package.json
COPY packages/cubejs-backend-cloud/package.json        packages/cubejs-backend-cloud/package.json
COPY packages/cubejs-backend-native/package.json       packages/cubejs-backend-native/package.json
COPY packages/cubejs-cli/package.json                  packages/cubejs-cli/package.json
COPY packages/cubejs-client-core/package.json          packages/cubejs-client-core/package.json
COPY packages/cubejs-client-react/package.json         packages/cubejs-client-react/package.json
COPY packages/cubejs-client-vue3/package.json          packages/cubejs-client-vue3/package.json
COPY packages/cubejs-client-ngx/package.json           packages/cubejs-client-ngx/package.json
COPY packages/cubejs-client-ws-transport/package.json  packages/cubejs-client-ws-transport/package.json
COPY packages/cubejs-cubestore-driver/package.json     packages/cubejs-cubestore-driver/package.json
COPY packages/cubejs-dbt-schema-extension/package.json packages/cubejs-dbt-schema-extension/package.json
COPY packages/cubejs-playground/package.json           packages/cubejs-playground/package.json
COPY packages/cubejs-postgres-driver/package.json      packages/cubejs-postgres-driver/package.json
COPY packages/cubejs-query-orchestrator/package.json   packages/cubejs-query-orchestrator/package.json
COPY packages/cubejs-schema-compiler/package.json      packages/cubejs-schema-compiler/package.json
COPY packages/cubejs-server/package.json               packages/cubejs-server/package.json
COPY packages/cubejs-server-core/package.json          packages/cubejs-server-core/package.json
COPY packages/cubejs-templates/package.json            packages/cubejs-templates/package.json
COPY packages/cubejs-testing-shared/package.json       packages/cubejs-testing-shared/package.json
COPY rust/cubestore/package.json                       rust/cubestore/package.json
COPY rust/cubestore/bin                                rust/cubestore/bin
COPY rust/cubesql/package.json                         rust/cubesql/package.json

RUN yarn install

# ── Layer: source files (changes often) ──────────────────────────────────────
COPY packages/cubejs-backend-shared/      packages/cubejs-backend-shared/
COPY packages/cubejs-base-driver/          packages/cubejs-base-driver/
COPY packages/cubejs-api-gateway/          packages/cubejs-api-gateway/
COPY packages/cubejs-backend-cloud/        packages/cubejs-backend-cloud/
COPY packages/cubejs-backend-native/       packages/cubejs-backend-native/
COPY packages/cubejs-cli/                  packages/cubejs-cli/
COPY packages/cubejs-client-core/          packages/cubejs-client-core/
COPY packages/cubejs-client-react/         packages/cubejs-client-react/
COPY packages/cubejs-client-vue3/          packages/cubejs-client-vue3/
COPY packages/cubejs-client-ngx/           packages/cubejs-client-ngx/
COPY packages/cubejs-client-ws-transport/  packages/cubejs-client-ws-transport/
COPY packages/cubejs-cubestore-driver/     packages/cubejs-cubestore-driver/
COPY packages/cubejs-dbt-schema-extension/ packages/cubejs-dbt-schema-extension/
COPY packages/cubejs-playground/           packages/cubejs-playground/
COPY packages/cubejs-postgres-driver/      packages/cubejs-postgres-driver/
COPY packages/cubejs-query-orchestrator/   packages/cubejs-query-orchestrator/
COPY packages/cubejs-schema-compiler/      packages/cubejs-schema-compiler/
COPY packages/cubejs-server/               packages/cubejs-server/
COPY packages/cubejs-server-core/          packages/cubejs-server-core/
COPY packages/cubejs-templates/            packages/cubejs-templates/
COPY packages/cubejs-testing-shared/       packages/cubejs-testing-shared/
COPY rust/cubestore/                       rust/cubestore/
COPY rust/cubesql/                         rust/cubesql/

# Step 1: build client-core + Rollup bundles for @cubejs-client/react etc.
# (mirrors dev.Dockerfile: yarn build = lerna run build:client-core && rollup -c)
RUN yarn build

# Step 2: build backend TypeScript packages + playground Vite SPA via lerna
RUN yarn lerna run build \
    --ignore @cubejs-backend/testing \
    --ignore @cubejs-client/ngx \
    --ignore @cubejs-client/dx

# ── Stage 2: production runtime ───────────────────────────────────────────────
FROM node:22.22.0-bookworm-slim

ARG IMAGE_VERSION=heartcube

ENV CUBEJS_DOCKER_IMAGE_VERSION=$IMAGE_VERSION
ENV CUBEJS_DOCKER_IMAGE_TAG=heartcube
ENV NODE_ENV=production
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    libssl3 python3.11 libpython3.11-dev ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /cubejs

RUN yarn policies set-version v1.22.22 && \
    yarn config set network-timeout 120000 -g

# Copy workspace manifests + built packages (dist/ included, no node_modules)
COPY --from=builder /cubejs/package.json  ./
COPY --from=builder /cubejs/lerna.json    ./
COPY --from=builder /cubejs/yarn.lock     ./
COPY --from=builder /cubejs/packages      ./packages
COPY --from=builder /cubejs/rust          ./rust

# DevServer serves this directory as the Playground static root.
RUN cp -R packages/cubejs-server-core/playground/build/. packages/cubejs-server-core/playground/

# Install production deps only (workspace symlinks use our built dist/ files)
RUN yarn install --prod \
    && rm -rf /cubejs/node_modules/duckdb/src \
    && yarn cache clean

ENV NODE_PATH=/cubejs/conf/node_modules:/cubejs/node_modules

RUN ln -sf /cubejs/node_modules/.bin/cubejs /usr/local/bin/cubejs || true
RUN ln -sf /cubejs/node_modules/.bin/cubestore-dev /usr/local/bin/cubestore-dev || true

WORKDIR /cubejs/conf

EXPOSE 4000

CMD ["cubejs", "server"]

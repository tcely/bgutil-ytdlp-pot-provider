FROM node:25-slim AS install
RUN apt-get update && apt-get install -y bash-static
#USER node
WORKDIR /app

COPY package.json package-lock.json ./
RUN chown -v -R node:node /app 
USER node

##RUN --mount=type=cache,target=/home/node/.npm,uid=1000,gid=1000 \
RUN \
    npm ci --omit=dev --no-audit --no-fund && \
    npm audit fix && npm audit signatures

RUN cp -v -p /lib/*/libuuid.so.1.* \
    node_modules/canvas/build/Release/libuuid.so.1 && \
    chmod -c 00755 node_modules/canvas/build/Release/* && \
    ldd node_modules/canvas/build/Release/canvas.node

##FROM install AS build_node

##RUN --mount=type=cache,target=/home/node/.npm,uid=1000,gid=1000 \
##    npm ci --no-audit --no-fund && \
##    npm audit fix && npm audit signatures

##COPY tsconfig.json ./
##COPY src/ src/
##COPY types/ types/
##RUN npx tsc

##FROM install AS server_node

##COPY --from=build_node /app/build /app/build

##EXPOSE 4416
##ENTRYPOINT ["/usr/local/bin/node", "build/main.js"]

FROM denoland/deno:alpine-2.6.8 AS build_deno
#USER deno
WORKDIR /app
ENV DENO_DIR=/home/deno/.cache/deno

#COPY types/ types/
#COPY tsconfig.json ./
COPY package.json deno.lock ./
COPY src/ src/
##COPY --from=install /app/node_modules node_modules/

RUN chown -R deno:deno /app
USER deno

##RUN --mount=type=cache,target=/home/deno/.cache/deno,uid=1000,gid=1000 \
RUN \
    printf > deno.json \
        '{"compilerOptions":{"useUnknownInCatchVariables": false}}\n' && \
    rm -f node_modules/canvas/build/Release/lib* && \
    : deno compile --frozen --output server \
    --allow-env --allow-net \
    --allow-ffi=/tmp/deno-compile-server/node_modules \
    --allow-read=/tmp/deno-compile-server/node_modules \
    src/main.ts

FROM debian:12-slim AS deno-install

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        ca-certificates curl unzip

ARG GIT_BLOB_DENO_INSTALL='25c0b6035a1bfc7a72db2fb43d453c30ccfab522'
ARG SHA256_DENO_INSTALL='0b66d046246a3079dea67bb41916a5a5fa55a41a286645bcdf2244cb598104d0'

WORKDIR /usr/src/deno_install

ADD "https://github.com/denoland/deno_install/raw/${GIT_BLOB_DENO_INSTALL}/install.sh" ./install.sh
RUN printf > install.sh.sha256 -- \
    '%s *install.sh\n' "${SHA256_DENO_INSTALL}" && \
    sha256sum --strict -cw install.sh.sha256 && \
    chmod -c 00755 install.sh

ENV DENO_INSTALL='/usr'
RUN CI=true sh /usr/src/deno_install/install.sh && \
    chown -c root:root /usr/bin/deno && \
    stat /usr/bin/deno

FROM scratch AS deno-bin
COPY --from=deno-install /usr/bin/deno /deno

FROM gcr.io/distroless/cc-debian12:debug AS server_deno
USER nonroot
WORKDIR /app

COPY --chown=nonroot:nonroot types/ types/

#COPY --from=build_deno --chown=nonroot:nonroot /app/server /app/server
#COPY --from=install --chown=nonroot:nonroot /app/node_modules/canvas/build/Release/ /app/canvas/
COPY --from=install /usr/sbin/ldconfig /usr/sbin/ldconfig
COPY --from=install /bin/bash-static /bin/bash
COPY --from=install /usr/bin/ldd /usr/bin/ldd

#ENV LD_LIBRARY_PATH='/app/canvas'

COPY --from=deno-bin /deno /usr/bin/deno
COPY --from=install --chown=nonroot:nonroot /app/node_modules /app/node_modules
COPY --chown=nonroot:nonroot package.json tsconfig.json deno.lock ./
COPY --chown=nonroot:nonroot src/ src/

EXPOSE 4416
ENTRYPOINT ["/usr/bin/deno", "run", "--allow-env", "--allow-net", "--allow-ffi=node_modules", "--allow-read=node_modules", "/app/src/main.ts"]

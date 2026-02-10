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
COPY --from=install /app/node_modules node_modules/

RUN chown -R deno:deno /app
USER deno

##RUN --mount=type=cache,target=/home/deno/.cache/deno,uid=1000,gid=1000 \
RUN \
    printf > deno.json \
        '{"compilerOptions":{"useUnknownInCatchVariables": false}}\n' && \
    rm -f node_modules/canvas/build/Release/lib* && \
    deno compile --frozen --output server \
    --allow-env --allow-net \
    --allow-ffi=/tmp/deno-compile-server/node_modules \
    --allow-read=/tmp/deno-compile-server/node_modules \
    src/main.ts

FROM gcr.io/distroless/cc-debian12:debug AS server_deno
USER nonroot
WORKDIR /app

COPY --from=build_deno --chown=nonroot:nonroot /app/server /app/server
COPY --from=install --chown=nonroot:nonroot /app/node_modules/canvas/build/Release/ /app/canvas/
COPY --from=install /bin/bash-static /bin/bash
COPY --from=install /usr/bin/ldd /usr/bin/ldd

ENV LD_LIBRARY_PATH='/app/canvas'

EXPOSE 4416
ENTRYPOINT ["/app/server"]

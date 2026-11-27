#!/bin/sh
# Generate Python and TypeScript from proto/cerm/execution/v1/element_solution.proto.
# Python: grpcio-tools (bundled protoc), output shared/python.
# TypeScript: protobufjs-cli inside a Node container, output shared/ts.
set -eu
cd "$(dirname "$0")/.."

PY="${PY:-.venv/bin/python}"
"$PY" -m grpc_tools.protoc \
  -I proto \
  --python_out=shared/python \
  proto/cerm/execution/v1/element_solution.proto

for pkg in cerm cerm/execution cerm/execution/v1; do
  touch "shared/python/$pkg/__init__.py"
done

docker run --rm -v "$PWD":/work -w /work node:22-bookworm-slim bash -lc '
  npm install --prefix /tmp/pb protobufjs-cli typescript >/dev/null
  /tmp/pb/node_modules/.bin/pbjs -t static-module -w es6 \
    -o shared/ts/element_solution.js \
    proto/cerm/execution/v1/element_solution.proto
  /tmp/pb/node_modules/.bin/pbts -o shared/ts/element_solution.d.ts \
    shared/ts/element_solution.js
  # pbts emits an unused CommonJS import that breaks ESM typechecking.
  sed -i "/import Long = require/d" shared/ts/element_solution.d.ts
'

echo "generated shared/python and shared/ts"

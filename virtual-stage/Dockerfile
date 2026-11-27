FROM node:22-bookworm-slim

WORKDIR /app
COPY virtual-stage/package.json /app/package.json
RUN npm install
COPY virtual-stage /app
# src/gen is a symlink to the repo contracts. Inside the image that link
# points outside /app, so Vite cannot resolve protobufjs. Replace it with
# the generated files.
RUN rm -rf /app/src/gen && mkdir -p /app/src/gen
COPY shared/ts/element_solution.js shared/ts/element_solution.d.ts /app/src/gen/
EXPOSE 5174
CMD ["npm", "run", "dev"]

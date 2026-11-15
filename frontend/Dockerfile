# Stage 1: build. Node turns the TypeScript and React code into plain files
# in dist/. This stage is thrown away once the build is done.
FROM node:24-alpine AS build

WORKDIR /app

# The package files alone first: Docker reuses this `npm ci` layer until one
# of them changes, so editing App.tsx does not reinstall every package.
COPY package.json package-lock.json .npmrc ./
RUN npm ci

COPY . .
RUN npm run build

# Stage 2: serve. Only nginx and the finished files go into the final image:
# no Node, no node_modules, no source code.
FROM nginx:1.30-alpine

COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

EXPOSE 80

FROM craks0d0kubesvc1.azurecr.io/americannational/ext-node:20.17-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
RUN npm run build

FROM craks0d0kubesvc1.azurecr.io/americannational/ext-nginx:1.26.1-alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80

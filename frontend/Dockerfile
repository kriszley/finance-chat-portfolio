FROM node:20-slim

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .

ENV BACKEND_URL=http://backend:8000
ENV NEXT_PUBLIC_BACKEND_URL=http://localhost:8000

EXPOSE 3000

CMD ["npm", "run", "dev"]

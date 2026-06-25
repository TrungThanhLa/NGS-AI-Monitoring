FROM node:20-slim

RUN apt-get update && apt-get install -y --no-install-recommends curl && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY frontend/package.json frontend/package.json
RUN cd frontend && npm install

COPY frontend frontend

WORKDIR /app/frontend

CMD ["npm", "run", "dev"]

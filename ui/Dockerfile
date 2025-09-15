FROM node:20-alpine

WORKDIR /app

ENV NEXT_PUBLIC_NODE_ENV=local
ENV NEXT_PUBLIC_AUTH_PROVIDER=local
ENV NEXT_PUBLIC_DEPLOYMENT_MODE=oss
ENV NEXT_PUBLIC_BACKEND_URL="http://localhost:8000"
ENV BACKEND_URL="http://api:8000"


# Copy package files and other config files needed for build
COPY package*.json ./
COPY tsconfig.json ./
COPY next.config.ts ./
COPY components.json ./
COPY sentry.edge.config.ts ./
COPY sentry.server.config.ts ./
COPY postcss.config.mjs ./

# Install dependencies (including dev deps for building)
RUN npm ci

# Copy all source file
COPY public ./public
COPY src ./src

RUN npm run build

# Expose the port Next.js runs on
EXPOSE 3000

# Start the production server
CMD ["npm", "run", "start"]
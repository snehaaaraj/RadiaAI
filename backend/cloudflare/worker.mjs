import { env } from "cloudflare:workers";
import { Container, getContainer } from "@cloudflare/containers";

const CONTAINER_ENV_KEYS = [
  "ENVIRONMENT",
  "DEBUG",
  "LOG_LEVEL",
  "APP_NAME",
  "APP_VERSION",
  "ALLOWED_ORIGINS",
  "API_PREFIX",
  "RETRIEVAL_TOP_K",
  "CHUNK_SIZE",
  "CHUNK_OVERLAP",
  "AZURE_OPENAI_ENDPOINT",
  "AZURE_OPENAI_API_KEY",
  "AZURE_OPENAI_API_VERSION",
  "AZURE_OPENAI_CHAT_DEPLOYMENT",
  "AZURE_OPENAI_EMBEDDING_DEPLOYMENT",
  "AZURE_OPENAI_EMBEDDING_DIMENSIONS",
  "AZURE_OPENAI_MAX_TOKENS",
  "AZURE_OPENAI_TEMPERATURE",
  "AZURE_SEARCH_ENDPOINT",
  "AZURE_SEARCH_API_KEY",
  "AZURE_SEARCH_INDEX_NAME",
  "AZURE_SEARCH_SEMANTIC_CONFIG_NAME",
  "AZURE_BLOB_CONNECTION_STRING",
  "AZURE_BLOB_CONTAINER_NAME",
  "ENTRA_TENANT_ID",
  "ENTRA_CLIENT_ID",
  "ENTRA_CLIENT_SECRET",
  "ENTRA_AUDIENCE",
  "SHAREPOINT_TENANT_ID",
  "SHAREPOINT_CLIENT_ID",
  "SHAREPOINT_CLIENT_SECRET",
  "SHAREPOINT_SITE_URL",
  "SHAREPOINT_DRIVE_NAME",
  "SHAREPOINT_STANDARDS_FOLDER",
  "SHAREPOINT_CACHE_TTL_SECONDS",
];

function serializeEnvValue(value) {
  if (typeof value === "string") {
    return value;
  }
  if (typeof value === "number" || typeof value === "boolean") {
    return String(value);
  }
  if (Array.isArray(value) || (value && typeof value === "object")) {
    return JSON.stringify(value);
  }
  return "";
}

function getContainerEnvVars(bindings) {
  return Object.fromEntries(
    CONTAINER_ENV_KEYS.flatMap((key) => {
      const value = serializeEnvValue(bindings[key]);
      return value.length > 0 ? [[key, value]] : [];
    }),
  );
}

export class RadiaBackendContainer extends Container {
  defaultPort = 8000;
  sleepAfter = "10m";
  pingEndpoint = "localhost/api/v1/health";
  envVars = getContainerEnvVars(env);
}

export default {
  async fetch(request, workerEnv) {
    const container = getContainer(workerEnv.RADIA_BACKEND, "radia-backend");
    return container.fetch(request);
  },
};

import fs from "node:fs";
import path from "node:path";

function stripWrappingQuotes(value) {
  if (value.length >= 2 && value.startsWith('"') && value.endsWith('"')) {
    return value.slice(1, -1);
  }
  if (value.length >= 2 && value.startsWith("'") && value.endsWith("'")) {
    return value.slice(1, -1);
  }
  return value;
}

export function parseEnvFile(content) {
  const values = {};
  for (const rawLine of content.split(/\r?\n/u)) {
    const line = rawLine.trim();
    if (!line || line.startsWith("#")) continue;
    const separatorIndex = line.indexOf("=");
    if (separatorIndex <= 0) continue;
    const key = line.slice(0, separatorIndex).trim();
    const value = line.slice(separatorIndex + 1).trim();
    values[key] = stripWrappingQuotes(value);
  }
  return values;
}

export function resolveFrontendBuildEnvironment({
  cwd = process.cwd(),
  prodEnvPath = "/home/app/config/.env",
  fileExists = fs.existsSync,
  readFile = (targetPath) => fs.readFileSync(targetPath, "utf8")
} = {}) {
  const backendEnvPath = path.resolve(cwd, "../backend/.env");
  const envFilePath = fileExists(prodEnvPath) ? prodEnvPath : backendEnvPath;
  const parsed = fileExists(envFilePath) ? parseEnvFile(readFile(envFilePath)) : {};
  return {
    appEnv: (parsed.APP_ENV || "dev").toLowerCase(),
    envFilePath
  };
}

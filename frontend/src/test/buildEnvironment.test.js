import { describe, expect, test } from "vitest";

import { resolveFrontendBuildEnvironment } from "../../build/environment.js";

describe("resolveFrontendBuildEnvironment", () => {
  test("prefers /home/app/config/.env for prod builds", () => {
    const env = resolveFrontendBuildEnvironment({
      cwd: "/workspace/frontend",
      prodEnvPath: "/home/app/config/.env",
      fileExists: (targetPath) => targetPath === "/home/app/config/.env",
      readFile: (targetPath) => {
        expect(targetPath).toBe("/home/app/config/.env");
        return "APP_ENV=prod\n";
      }
    });

    expect(env).toEqual({
      appEnv: "prod",
      envFilePath: "/home/app/config/.env"
    });
  });

  test("falls back to backend/.env when prod env file is absent", () => {
    const env = resolveFrontendBuildEnvironment({
      cwd: "/workspace/frontend",
      prodEnvPath: "/home/app/config/.env",
      fileExists: (targetPath) => targetPath === "/workspace/backend/.env",
      readFile: (targetPath) => {
        expect(targetPath).toBe("/workspace/backend/.env");
        return "APP_ENV=dev\n";
      }
    });

    expect(env).toEqual({
      appEnv: "dev",
      envFilePath: "/workspace/backend/.env"
    });
  });
});

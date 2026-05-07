import { afterEach, beforeEach, describe, expect, test } from "vitest";
import { readOAuthAuthContext } from "../authContext";

const oauthUser = {
  account: "oauth.user",
  name: "OAuth User",
  email: "oauth.user@example.com",
  department: "R&D",
  sysid: "oauth-sysid-1",
  role: "user"
};

describe("readOAuthAuthContext", () => {
  beforeEach(() => {
    delete window.__AS_AUTH_CONTEXT__;
    window.sessionStorage.clear();
  });

  afterEach(() => {
    delete window.__AS_AUTH_CONTEXT__;
    window.sessionStorage.clear();
  });

  test("returns auth context from window when valid", () => {
    window.__AS_AUTH_CONTEXT__ = { ...oauthUser };
    expect(readOAuthAuthContext()).toEqual(oauthUser);
  });

  test("falls back to sessionStorage when window context is missing", () => {
    window.sessionStorage.setItem("as-api-console-auth-context", JSON.stringify(oauthUser));
    expect(readOAuthAuthContext()).toEqual(oauthUser);
  });

  test("window context has priority over sessionStorage", () => {
    window.__AS_AUTH_CONTEXT__ = { ...oauthUser, sysid: "window-sysid" };
    window.sessionStorage.setItem(
      "as-api-console-auth-context",
      JSON.stringify({ ...oauthUser, sysid: "session-sysid" })
    );

    expect(readOAuthAuthContext()?.sysid).toBe("window-sysid");
  });

  test("returns null for invalid role or missing fields", () => {
    window.__AS_AUTH_CONTEXT__ = { ...oauthUser, role: "owner" };
    expect(readOAuthAuthContext()).toBeNull();

    window.__AS_AUTH_CONTEXT__ = undefined;
    window.sessionStorage.setItem(
      "as-api-console-auth-context",
      JSON.stringify({ ...oauthUser, sysid: "" })
    );
    expect(readOAuthAuthContext()).toBeNull();
  });
});

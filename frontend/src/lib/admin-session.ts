import "server-only";

import { createCipheriv, createDecipheriv, createHash, randomBytes } from "crypto";

import { cookies } from "next/headers";
import { redirect } from "next/navigation";

import { ADMIN_SESSION_COOKIE, ADMIN_SESSION_MAX_AGE_SECONDS } from "@/lib/admin-session-constants";

type AdminSession = {
  username: string;
  password: string;
  issuedAt: number;
};

function getBackendBaseUrl(): string | null {
  return process.env.PANEL_BACKEND_URL || process.env.NEXT_PUBLIC_PANEL_BACKEND_URL || null;
}

function getSessionSecretKey(): Buffer | null {
  const secret = process.env.ADMIN_SESSION_SECRET;
  if (!secret) {
    return null;
  }
  return createHash("sha256").update(secret).digest();
}

function buildEnvBasicAuthHeader(): string | null {
  const username = process.env.PANEL_AUTH_USERNAME;
  const password = process.env.PANEL_AUTH_PASSWORD;
  if (!username || !password) {
    return null;
  }
  return buildBasicAuthHeader(username, password);
}

export function buildBasicAuthHeader(username: string, password: string): string {
  return `Basic ${Buffer.from(`${username}:${password}`).toString("base64")}`;
}

function shouldUseSecureCookies(): boolean {
  const publicBaseUrl = process.env.ADMIN_PUBLIC_URL || process.env.NEXT_PUBLIC_ADMIN_URL || "";
  return publicBaseUrl.startsWith("https://");
}

export function sessionCookieOptions() {
  return {
    httpOnly: true,
    sameSite: "lax" as const,
    secure: shouldUseSecureCookies(),
    path: "/",
    maxAge: ADMIN_SESSION_MAX_AGE_SECONDS,
  };
}

export function getAdminSessionConfigError(): string | null {
  if (!getBackendBaseUrl()) {
    return "backend_not_configured";
  }
  if (!process.env.ADMIN_SESSION_SECRET) {
    return "session_secret_not_configured";
  }
  return null;
}

function encodeSessionToken(session: AdminSession): string | null {
  const key = getSessionSecretKey();
  if (!key) {
    return null;
  }

  const iv = randomBytes(12);
  const cipher = createCipheriv("aes-256-gcm", key, iv);
  const payload = Buffer.from(JSON.stringify(session), "utf-8");
  const encrypted = Buffer.concat([cipher.update(payload), cipher.final()]);
  const tag = cipher.getAuthTag();
  return [iv.toString("base64url"), tag.toString("base64url"), encrypted.toString("base64url")].join(".");
}

function decodeSessionToken(token: string | undefined): AdminSession | null {
  if (!token) {
    return null;
  }

  const key = getSessionSecretKey();
  if (!key) {
    return null;
  }

  const [ivPart, tagPart, dataPart] = token.split(".");
  if (!ivPart || !tagPart || !dataPart) {
    return null;
  }

  try {
    const decipher = createDecipheriv("aes-256-gcm", key, Buffer.from(ivPart, "base64url"));
    decipher.setAuthTag(Buffer.from(tagPart, "base64url"));
    const decrypted = Buffer.concat([
      decipher.update(Buffer.from(dataPart, "base64url")),
      decipher.final(),
    ]);
    const payload = JSON.parse(decrypted.toString("utf-8")) as AdminSession;
    if (!payload.username || !payload.password || !payload.issuedAt) {
      return null;
    }
    const ageSeconds = Math.floor((Date.now() - payload.issuedAt) / 1000);
    if (ageSeconds < 0 || ageSeconds > ADMIN_SESSION_MAX_AGE_SECONDS) {
      return null;
    }
    return payload;
  } catch {
    return null;
  }
}

export async function createAdminSessionCookieValue(
  username: string,
  password: string,
): Promise<string | null> {
  return encodeSessionToken({
    username,
    password,
    issuedAt: Date.now(),
  });
}

export async function getAdminSession(): Promise<AdminSession | null> {
  const cookieStore = await cookies();
  const token = cookieStore.get(ADMIN_SESSION_COOKIE)?.value;
  return decodeSessionToken(token);
}

export async function getBackendAuthorizationHeader(): Promise<string | null> {
  const session = await getAdminSession();
  if (session) {
    return buildBasicAuthHeader(session.username, session.password);
  }
  return buildEnvBasicAuthHeader();
}

export async function requireAdminPageSession(): Promise<AdminSession> {
  const session = await getAdminSession();
  if (!session) {
    redirect("/login?error=session_required");
  }
  return session;
}

export async function verifyPanelCredentials(
  username: string,
  password: string,
): Promise<{ ok: boolean; error?: string }> {
  const baseUrl = getBackendBaseUrl();
  if (!baseUrl) {
    return { ok: false, error: "backend_not_configured" };
  }

  const response = await fetch(`${baseUrl}/painel/api/snapshot`, {
    cache: "no-store",
    headers: {
      Authorization: buildBasicAuthHeader(username, password),
    },
  });

  if (response.ok) {
    return { ok: true };
  }
  if (response.status === 401) {
    return { ok: false, error: "invalid_credentials" };
  }
  return { ok: false, error: `backend_http_${response.status}` };
}

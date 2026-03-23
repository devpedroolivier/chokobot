export function resolveAdminPublicUrl(path: string, requestUrl?: string): URL {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  const publicBaseUrl = process.env.ADMIN_PUBLIC_URL || process.env.NEXT_PUBLIC_ADMIN_URL;
  if (publicBaseUrl) {
    return new URL(normalizedPath, publicBaseUrl);
  }
  return new URL(normalizedPath, requestUrl || "http://127.0.0.1:3000");
}

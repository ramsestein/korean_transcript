// Simple cookie utility for auth token storage
// Using cookies allows the browser to persist session across restarts
//
// SECURITY NOTE: HttpOnly flag can only be set by the server, not JavaScript.
// For production, the server should set the auth cookie via Set-Cookie header
// with HttpOnly; Secure; SameSite=Strict flags.
//
// Current flags set:
// - Secure: Only sent over HTTPS (set when window.location.protocol === 'https:')
// - SameSite=Strict: Prevents CSRF by not sending cookie on cross-site requests
// - Max-Age: 30 days session persistence

const COOKIE_NAME = 'auth_token';

function getCookieOptions(maxAgeSeconds: number): string {
  const isHttps = typeof window !== 'undefined' && window.location.protocol === 'https:';
  const secureFlag = isHttps ? '; Secure' : '';
  return `Path=/; SameSite=Strict${secureFlag}; Max-Age=${maxAgeSeconds}`;
}

export function setCookie(name: string, value: string, maxAgeDays = 30): void {
  const maxAge = maxAgeDays * 24 * 60 * 60;
  const options = getCookieOptions(maxAge);
  document.cookie = `${name}=${encodeURIComponent(value)}; ${options}`;
}

export function getCookie(name: string): string | null {
  const cookies = document.cookie.split(';');
  for (const cookie of cookies) {
    const [cookieName, cookieValue] = cookie.trim().split('=');
    if (cookieName === name) {
      return decodeURIComponent(cookieValue);
    }
  }
  return null;
}

export function deleteCookie(name: string): void {
  document.cookie = `${name}=; Path=/; SameSite=Strict; Max-Age=0; Expires=Thu, 01 Jan 1970 00:00:00 GMT`;
}

// Auth-specific helpers
export function setAuthToken(token: string): void {
  setCookie(COOKIE_NAME, token);
}

export function getAuthToken(): string | null {
  return getCookie(COOKIE_NAME);
}

export function clearAuthToken(): void {
  deleteCookie(COOKIE_NAME);
}

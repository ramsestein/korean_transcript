// Simple cookie utility for auth token storage
// Using cookies allows the browser to persist session across restarts

const COOKIE_NAME = 'auth_token';
const COOKIE_OPTIONS = 'Path=/; SameSite=Strict; Max-Age=2592000'; // 30 days

export function setCookie(name: string, value: string, maxAgeDays = 30): void {
  const maxAge = maxAgeDays * 24 * 60 * 60;
  document.cookie = `${name}=${encodeURIComponent(value)}; Path=/; SameSite=Strict; Max-Age=${maxAge}`;
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

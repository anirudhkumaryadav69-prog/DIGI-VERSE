/**
 * Runtime API response validation and safe state coercion helpers.
 * Prevents SPA HTML fallback responses or malformed payloads from crashing UI rendering
 * or creating false-positive authenticated sessions.
 */

export function isPlainObject(value) {
  return Boolean(value) && typeof value === 'object' && !Array.isArray(value);
}

export function asArray(value) {
  return Array.isArray(value) ? value : [];
}

export function asPlainObject(value) {
  return isPlainObject(value) ? value : {};
}

export function asPaginatedItems(value) {
  return isPlainObject(value) && Array.isArray(value.items) ? value.items : [];
}

export function isHtmlPayload(data) {
  if (typeof data !== 'string') return false;
  const trimmed = data.trimStart().toLowerCase();
  return trimmed.startsWith('<!doctype html') || trimmed.startsWith('<html');
}

export function isExplicitNonJsonRequest(config) {
  if (!config || typeof config !== 'object') return false;
  if (config.allowHtmlResponse === true) return true;
  const responseType = String(config.responseType || '').toLowerCase();
  return ['blob', 'arraybuffer', 'document', 'stream'].includes(responseType);
}

export function validateApiResponse(response) {
  if (!response || isExplicitNonJsonRequest(response.config)) {
    return response;
  }

  const rawContentType =
    response.headers?.['content-type'] ||
    (typeof response.headers?.get === 'function' ? response.headers.get('content-type') : '') ||
    '';
  const contentType = String(rawContentType).toLowerCase();

  const hasHtmlHeader =
    contentType.includes('text/html') || contentType.includes('application/xhtml+xml');
  const hasHtmlBody = isHtmlPayload(response.data);

  if (hasHtmlHeader || hasHtmlBody) {
    const message =
      'API returned an HTML document instead of JSON. Check backend availability or API routing configuration.';
    const error = new Error(message);
    error.code = 'API_HTML_RESPONSE';
    error.isApiValidationError = true;
    error.config = response.config;
    error.response = {
      status: response.status || 502,
      statusText: 'Invalid API Response',
      headers: response.headers || {},
      config: response.config,
      data: { detail: message },
    };
    throw error;
  }

  return response;
}

export function isValidCustomerProfile(profile) {
  return (
    isPlainObject(profile) &&
    Boolean(profile.id) &&
    (typeof profile.email === 'string' || typeof profile.full_name === 'string')
  );
}

export function isValidAdminProfile(profile) {
  return isPlainObject(profile) && Boolean(profile.id) && profile.role === 'ADMIN';
}

/**
 * Pure API payload and response validation helpers.
 * Ensures unexpected HTML fallback pages, malformed strings, or mismatched types
 * are rejected cleanly instead of crashing UI components or corrupting auth state.
 */

const NON_JSON_RESPONSE_TYPES = new Set(['blob', 'arraybuffer', 'document', 'text', 'stream']);

export function isPlainObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

export function isHtmlContentType(contentType) {
  if (!contentType) return false;
  const normalized = String(contentType).toLowerCase();
  return normalized.includes('text/html') || normalized.includes('application/xhtml+xml');
}

export function isHtmlStringPayload(data) {
  if (typeof data !== 'string') return false;
  const trimmed = data.trimStart().toLowerCase();
  return (
    trimmed.startsWith('<!doctype html') ||
    trimmed.startsWith('<html') ||
    trimmed.startsWith('<head') ||
    trimmed.startsWith('<body')
  );
}

export function createStructuredApiError(message, { code, status, response, config } = {}) {
  const error = new Error(message);
  error.name = 'ApiResponseError';
  error.code = code || 'INVALID_API_RESPONSE';
  error.isApiUnavailable = true;
  error.config = config || response?.config;
  error.response = {
    status: status ?? response?.status ?? 503,
    statusText: response?.statusText || 'Service Unavailable',
    headers: response?.headers || {},
    config: config || response?.config || {},
    data: {
      detail: message,
      code: error.code,
    },
  };
  return error;
}

/**
 * Validate an Axios response at the interceptor boundary before returning it to callers.
 * Skips 204 No Content and explicitly non-JSON binary/text responses (e.g. blob downloads).
 */
export function validateApiResponse(response) {
  if (!response) {
    throw createStructuredApiError('Empty response received from the API server.', {
      code: 'API_EMPTY_RESPONSE',
    });
  }

  const responseType = String(response.config?.responseType || '').toLowerCase();
  if (response.status === 204 || NON_JSON_RESPONSE_TYPES.has(responseType)) {
    return response;
  }

  const contentType = String(response.headers?.['content-type'] || '').toLowerCase();
  const data = response.data;

  if (isHtmlContentType(contentType) || isHtmlStringPayload(data)) {
    throw createStructuredApiError(
      'Backend API is unavailable or returned HTML instead of JSON.',
      {
        code: 'API_HTML_RESPONSE',
        status: response.status,
        response,
      }
    );
  }

  if (typeof data === 'string' && data.trim().length > 0) {
    if (contentType.includes('application/json')) {
      try {
        response.data = JSON.parse(data);
        return response;
      } catch {
        throw createStructuredApiError('Received malformed JSON from the API server.', {
          code: 'API_MALFORMED_JSON',
          status: response.status,
          response,
        });
      }
    }

    throw createStructuredApiError('Received unexpected non-JSON text from the API server.', {
      code: 'API_NON_JSON_RESPONSE',
      status: response.status,
      response,
    });
  }

  return response;
}

export function assertArrayResponse(data, label = 'data') {
  if (!Array.isArray(data)) {
    throw createStructuredApiError(`Expected an array response for ${label}.`, {
      code: 'API_INVALID_ARRAY',
    });
  }
  return data;
}

export function assertObjectResponse(data, label = 'data') {
  if (!isPlainObject(data)) {
    throw createStructuredApiError(`Expected a JSON object response for ${label}.`, {
      code: 'API_INVALID_OBJECT',
    });
  }
  return data;
}

export function assertPaginatedResponse(data, label = 'items') {
  if (!isPlainObject(data) || !Array.isArray(data.items)) {
    throw createStructuredApiError(`Expected a paginated response with an items array for ${label}.`, {
      code: 'API_INVALID_PAGINATED_RESPONSE',
    });
  }
  return data;
}

export function isValidCustomerProfile(profile) {
  return (
    isPlainObject(profile) &&
    typeof profile.email === 'string' &&
    profile.email.length > 0 &&
    Boolean(profile.id || profile.full_name)
  );
}

export function isValidAdminProfile(profile) {
  return (
    isPlainObject(profile) &&
    profile.role === 'ADMIN' &&
    Boolean(profile.id || profile.email || profile.username)
  );
}

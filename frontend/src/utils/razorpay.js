export const RAZORPAY_CHECKOUT_SCRIPT_URL = 'https://checkout.razorpay.com/v1/checkout.js';

let sdkLoadPromise = null;

/**
 * Lazily load Razorpay Checkout SDK only when checkout requires it.
 * Deduplicates concurrent calls and allows clean retries if a previous load failed.
 */
export function loadRazorpaySdk({ doc = typeof document !== 'undefined' ? document : null, timeoutMs = 15000 } = {}) {
  const win = doc?.defaultView || (typeof window !== 'undefined' ? window : null);

  if (win && typeof win.Razorpay === 'function') {
    return Promise.resolve(win.Razorpay);
  }

  if (!doc || !doc.head) {
    return Promise.reject(
      new Error('Browser document is unavailable to load the Razorpay Checkout SDK.')
    );
  }

  if (sdkLoadPromise) {
    return sdkLoadPromise;
  }

  sdkLoadPromise = new Promise((resolve, reject) => {
    const existingScript = doc.querySelector(
      `script[src="${RAZORPAY_CHECKOUT_SCRIPT_URL}"]`
    );

    if (existingScript && existingScript.dataset?.razorpayLoadError === 'true') {
      existingScript.remove();
    }

    const activeExisting = doc.querySelector(
      `script[src="${RAZORPAY_CHECKOUT_SCRIPT_URL}"]`
    );
    const script = activeExisting || doc.createElement('script');
    let settled = false;
    let timerId = null;

    const cleanupListeners = () => {
      if (timerId !== null) {
        clearTimeout(timerId);
        timerId = null;
      }
      script.removeEventListener('load', handleLoad);
      script.removeEventListener('error', handleError);
    };

    const fail = (message) => {
      if (settled) return;
      settled = true;
      cleanupListeners();
      if (script.dataset) {
        script.dataset.razorpayLoadError = 'true';
      }
      sdkLoadPromise = null;
      reject(new Error(message));
    };

    const handleLoad = () => {
      if (settled) return;
      if (win && typeof win.Razorpay === 'function') {
        settled = true;
        cleanupListeners();
        if (script.dataset) {
          delete script.dataset.razorpayLoadError;
        }
        resolve(win.Razorpay);
        return;
      }
      fail('Razorpay Checkout SDK loaded, but window.Razorpay is unavailable.');
    };

    const handleError = () => {
      fail(
        'Unable to load the Razorpay payment gateway. Please check your connection or disable any script blocker and try again.'
      );
    };

    script.addEventListener('load', handleLoad);
    script.addEventListener('error', handleError);

    timerId = setTimeout(() => {
      fail(
        'Timed out while loading the Razorpay payment gateway. Your order is saved; please try again.'
      );
    }, timeoutMs);

    if (!activeExisting) {
      script.src = RAZORPAY_CHECKOUT_SCRIPT_URL;
      script.async = true;
      if (script.dataset) {
        script.dataset.digiverseRazorpay = 'true';
      }
      doc.head.appendChild(script);
    } else if (win && typeof win.Razorpay === 'function') {
      handleLoad();
    }
  });

  return sdkLoadPromise;
}

export function resetRazorpayLoaderForTests() {
  sdkLoadPromise = null;
}

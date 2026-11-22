import { createContext, useCallback, useContext, useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { adminAuthApi, commerceApi, customerAuthApi } from '../services/api';
import {
  isPlainObject,
  isValidAdminProfile,
  isValidCustomerProfile,
} from '../utils/apiValidation';

const AuthContext = createContext(null);

export const AuthProvider = ({ children }) => {
  const location = useLocation();
  const isAdminPath = location.pathname.startsWith('/admin');
  const [customer, setCustomer] = useState(null);
  const [admin, setAdmin] = useState(null);
  const [customerLoading, setCustomerLoading] = useState(true);
  const [adminLoading, setAdminLoading] = useState(isAdminPath);
  const [cartCount, setCartCount] = useState(0);
  const [wishlistCount, setWishlistCount] = useState(0);
  const [otpDeliveryStatus, setOtpDeliveryStatus] = useState(null);

  const refreshCartAndWishlistCounts = useCallback(async () => {
    try {
      const [cartData, wishData] = await Promise.all([
        commerceApi.getCart(),
        commerceApi.getWishlist(),
      ]);
      setCartCount(isPlainObject(cartData) ? Number(cartData.total_quantity || 0) : 0);
      setWishlistCount(isPlainObject(wishData) ? Number(wishData.total_items || 0) : 0);
    } catch {
      setCartCount(0);
      setWishlistCount(0);
    }
  }, []);

  const refreshCustomerProfile = useCallback(async () => {
    try {
      const profile = await customerAuthApi.getProfile();
      if (!isValidCustomerProfile(profile)) {
        throw new Error('Invalid customer profile payload');
      }
      setCustomer(profile);
      await refreshCartAndWishlistCounts();
      return profile;
    } catch {
      setCustomer(null);
      setCartCount(0);
      setWishlistCount(0);
      return null;
    } finally {
      setCustomerLoading(false);
    }
  }, [refreshCartAndWishlistCounts]);

  const refreshAdminProfile = useCallback(async () => {
    try {
      const profile = await adminAuthApi.getMe();
      if (!isValidAdminProfile(profile)) {
        throw new Error('Invalid administrator profile payload');
      }
      setAdmin(profile);
      return profile;
    } catch {
      setAdmin(null);
      return null;
    } finally {
      setAdminLoading(false);
    }
  }, []);

  useEffect(() => {
    customerAuthApi.getCsrf().catch(() => {});
    refreshCustomerProfile();

    const handleSessionExpired = (event) => {
      const url = event?.detail?.url || '';
      if (url.startsWith('/admin')) {
        setAdmin(null);
      } else {
        setCustomer(null);
        setCartCount(0);
        setWishlistCount(0);
      }
    };

    window.addEventListener('digiverse:session-expired', handleSessionExpired);
    return () => window.removeEventListener('digiverse:session-expired', handleSessionExpired);
  }, [refreshCustomerProfile]);

  useEffect(() => {
    if (isAdminPath) {
      setAdminLoading(true);
      refreshAdminProfile();
    }
  }, [isAdminPath, refreshAdminProfile]);

  const registerCustomer = async (payload) => {
    const data = await customerAuthApi.register(payload);
    if (!isPlainObject(data) || !isValidCustomerProfile(data.customer)) {
      throw new Error('Unexpected registration response from API server.');
    }
    setCustomer(data.customer);
    setOtpDeliveryStatus({
      status: data.otp_delivery_status,
      detail: data.otp_delivery_detail,
    });
    await refreshCartAndWishlistCounts();
    return data;
  };

  const loginCustomer = async (payload) => {
    const data = await customerAuthApi.login(payload);
    if (!isPlainObject(data) || !isValidCustomerProfile(data.customer)) {
      throw new Error('Unexpected login response from API server.');
    }
    setCustomer(data.customer);
    await refreshCartAndWishlistCounts();
    return data;
  };

  const logoutCustomer = async () => {
    try {
      await customerAuthApi.logout();
    } finally {
      setCustomer(null);
      setCartCount(0);
      setWishlistCount(0);
    }
  };

  const logoutAllCustomerDevices = async () => {
    try {
      await customerAuthApi.logoutAll();
    } finally {
      setCustomer(null);
      setCartCount(0);
      setWishlistCount(0);
    }
  };

  const loginAdmin = async (payload) => {
    const data = await adminAuthApi.login(payload);
    if (!isPlainObject(data) || !isValidAdminProfile(data.admin)) {
      throw new Error('Unexpected administrator login response from API server.');
    }
    setAdmin(data.admin);
    return data;
  };

  const logoutAdmin = async () => {
    try {
      await adminAuthApi.logout();
    } finally {
      setAdmin(null);
    }
  };

  const value = {
    user: customer,
    customer,
    setCustomer,
    otpDeliveryStatus,
    setOtpDeliveryStatus,
    loading: customerLoading,
    customerLoading,
    isAuthenticated: Boolean(customer),
    isPhoneVerified: Boolean(customer?.is_phone_verified),
    isSeller: Boolean(customer?.is_seller),
    sellerStatus: customer?.seller_status || null,
    sellerStoreSlug: customer?.seller_store_slug || null,
    cartCount,
    setCartCount,
    wishlistCount,
    setWishlistCount,
    refreshCartAndWishlistCounts,
    registerCustomer,
    loginCustomer,
    logoutCustomer,
    logoutAllCustomerDevices,
    refreshCustomerProfile,

    admin,
    setAdmin,
    adminLoading,
    isAdminAuthenticated: Boolean(admin),
    isAdmin: Boolean(admin && admin.role === 'ADMIN'),
    adminMustChangePassword: Boolean(admin?.must_change_password),
    loginAdmin,
    logoutAdmin,
    refreshAdminProfile,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
};

export const useAuth = () => {
  const context = useContext(AuthContext);
  if (!context) {
    throw new Error('useAuth must be used within an AuthProvider');
  }
  return context;
};

export default AuthContext;

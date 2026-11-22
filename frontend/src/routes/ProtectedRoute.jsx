import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { LoadingState } from '../components/common/StorefrontDesignSystem';

const ProtectedRoute = ({ requirePhoneVerified = false }) => {
  const { isAuthenticated, isPhoneVerified, customerLoading } = useAuth();
  const location = useLocation();

  if (customerLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#EAF4FC] text-[#263445] p-6">
        <LoadingState label="Verifying session..." />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (requirePhoneVerified && !isPhoneVerified && location.pathname !== '/verify-phone') {
    return <Navigate to="/verify-phone" replace />;
  }

  return <Outlet />;
};

export default ProtectedRoute;

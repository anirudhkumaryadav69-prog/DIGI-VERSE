import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const ProtectedRoute = ({ requirePhoneVerified = false }) => {
  const { isAuthenticated, isPhoneVerified, customerLoading } = useAuth();
  const location = useLocation();

  if (customerLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#FFFAF5] text-[#243247]">
        <span className="text-xs tracking-[0.2em] uppercase text-[#64748B]">
          Verifying Session...
        </span>
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

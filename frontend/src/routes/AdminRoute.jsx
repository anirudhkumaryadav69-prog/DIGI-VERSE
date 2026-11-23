import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { LoadingState } from '../components/common/StorefrontDesignSystem';

const AdminRoute = ({ allowPasswordChangePending = false }) => {
  const { isAdminAuthenticated, isAdmin, adminMustChangePassword, adminLoading } = useAuth();
  const location = useLocation();

  if (adminLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#080D19] text-[#F1F5F9] p-6">
        <LoadingState label="Verifying administrator session..." />
      </div>
    );
  }

  if (!isAdminAuthenticated || !isAdmin) {
    return <Navigate to="/admin/login" state={{ from: location }} replace />;
  }

  if (adminMustChangePassword && !allowPasswordChangePending) {
    return <Navigate to="/admin/change-password" replace />;
  }

  return <Outlet />;
};

export default AdminRoute;

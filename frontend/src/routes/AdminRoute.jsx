import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';

const AdminRoute = ({ allowPasswordChangePending = false }) => {
  const { isAdminAuthenticated, isAdmin, adminMustChangePassword, adminLoading } = useAuth();
  const location = useLocation();

  if (adminLoading) {
    return (
      <div className="min-h-screen flex items-center justify-center bg-[#FFFAF5] text-[#243247]">
        <span className="text-xs tracking-[0.2em] uppercase text-[#64748B]">
          Verifying Administrator Session...
        </span>
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

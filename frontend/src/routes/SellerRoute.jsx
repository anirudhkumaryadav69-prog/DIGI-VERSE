import { Navigate, Outlet, useLocation } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import { LoadingState } from '../components/common/StorefrontDesignSystem';

const SellerRoute = () => {
  const { isAuthenticated, isSeller, customerLoading } = useAuth();
  const location = useLocation();

  if (customerLoading) {
    return (
      <div className="min-h-screen bg-[#080D19] text-[#F1F5F9] flex items-center justify-center p-6">
        <LoadingState label="Verifying seller permissions..." />
      </div>
    );
  }

  if (!isAuthenticated) {
    return <Navigate to="/login" state={{ from: location }} replace />;
  }

  if (!isSeller) {
    return <Navigate to="/seller/apply" state={{ from: location }} replace />;
  }

  return <Outlet />;
};

export default SellerRoute;

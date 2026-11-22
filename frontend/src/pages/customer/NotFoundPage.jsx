import { Link } from 'react-router-dom';
import { Compass, ArrowRight } from 'lucide-react';
import StorefrontLayout from '../../components/common/StorefrontLayout';
import { EmptyState, useDocumentMeta } from '../../components/common/StorefrontDesignSystem';

const NotFoundPage = () => {
  useDocumentMeta({
    title: 'Page Not Found',
    description: 'The requested page could not be found on DIGI-VERSE.',
  });

  return (
    <StorefrontLayout>
      <div className="py-12">
        <EmptyState
          icon={Compass}
          title="404 — Page Not Found"
          description="The page or digital product you are looking for may have been moved, archived, or never existed."
          action={
            <div className="flex flex-wrap items-center justify-center gap-3">
              <Link
                to="/products"
                className="dv-btn-primary px-5 py-2.5 text-[13px] font-semibold inline-flex items-center gap-2"
              >
                <span>Browse Digital Catalog</span>
                <ArrowRight className="w-3.5 h-3.5" aria-hidden="true" />
              </Link>
              <Link
                to="/"
                className="dv-btn-secondary px-5 py-2.5 text-[13px] font-semibold"
              >
                Return Home
              </Link>
            </div>
          }
        />
      </div>
    </StorefrontLayout>
  );
};

export default NotFoundPage;

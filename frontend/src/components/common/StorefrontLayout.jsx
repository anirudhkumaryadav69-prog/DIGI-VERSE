import { useEffect, useState } from 'react';
import StorefrontHeader from './StorefrontHeader';
import StorefrontFooter from './StorefrontFooter';
import { publicCatalogApi } from '../../services/api';

let cachedPublicSettings = null;

const StorefrontLayout = ({ children }) => {
  const [storeSettings, setStoreSettings] = useState(cachedPublicSettings || {});

  useEffect(() => {
    if (cachedPublicSettings) return;
    publicCatalogApi
      .getPublicSettings()
      .then((data) => {
        cachedPublicSettings = data || {};
        setStoreSettings(cachedPublicSettings);
      })
      .catch(() => {});
  }, []);

  return (
    <div className="min-h-screen bg-[#EAF4FC] text-[#263445] flex flex-col justify-between px-4 py-6 sm:px-6 md:px-10 overflow-x-hidden">
      <StorefrontHeader
        announcementText={storeSettings['store.announcement_text']}
        storeName={storeSettings['store.name'] || 'DIGI-VERSE'}
      />
      <main className="max-w-7xl w-full mx-auto py-8 md:py-10 flex-1">{children}</main>
      <StorefrontFooter storeSettings={storeSettings} />
    </div>
  );
};

export default StorefrontLayout;

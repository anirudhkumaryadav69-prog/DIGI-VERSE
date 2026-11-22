import { FolderTree } from 'lucide-react';

/**
 * Recognizable Python dual-mark emblem (24x24 grid, clean flat vector paths).
 */
export const PythonBrandIcon = ({ className = 'w-5 h-5', ...props }) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    className={className}
    aria-hidden="true"
    {...props}
  >
    <path
      d="M11.9 2.5c-4.7 0-4.4 2.05-4.4 2.05v2.12h4.48v.64H5.75S2.75 6.97 2.75 11.7c0 4.73 2.62 4.56 2.62 4.56h1.56v-2.18s-.08-2.62 2.58-2.62h4.42s2.48.04 2.48-2.4V5.02S16.78 2.5 11.9 2.5Zm-2.44 1.44a.84.84 0 1 1 0 1.68.84.84 0 0 1 0-1.68Z"
      fill="#2563EB"
    />
    <path
      d="M12.1 21.5c4.7 0 4.4-2.05 4.4-2.05v-2.12h-4.48v-.64h6.23s3 .34 3-4.39c0-4.73-2.62-4.56-2.62-4.56h-1.56v2.18s.08 2.62-2.58 2.62h-4.42s-2.48-.04-2.48 2.4v4.04S7.22 21.5 12.1 21.5Zm2.44-1.44a.84.84 0 1 1 0-1.68.84.84 0 0 1 0 1.68Z"
      fill="#D97706"
    />
  </svg>
);

/**
 * Geometric Figma-style vector nodes & design shapes mark (24x24 grid).
 */
export const DesignVectorMarkIcon = ({ className = 'w-5 h-5', ...props }) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    className={className}
    aria-hidden="true"
    {...props}
  >
    <path
      d="M8.5 3h3.5v6H8.5a3 3 0 0 1 0-6Z"
      fill="#7C3AED"
      fillOpacity="0.18"
      stroke="#6D28D9"
      strokeWidth="1.75"
    />
    <path
      d="M12 3h3.5a3 3 0 0 1 0 6H12V3Z"
      fill="#2563EB"
      fillOpacity="0.18"
      stroke="#2563EB"
      strokeWidth="1.75"
    />
    <path
      d="M8.5 9H12v6H8.5a3 3 0 0 1 0-6Z"
      fill="#7C3AED"
      fillOpacity="0.28"
      stroke="#6D28D9"
      strokeWidth="1.75"
    />
    <circle
      cx="15"
      cy="12"
      r="3"
      fill="#0EA5E9"
      fillOpacity="0.25"
      stroke="#0EA5E9"
      strokeWidth="1.75"
    />
    <path
      d="M8.5 15H12v3a3 3 0 1 1-3.5-3Z"
      fill="#16A34A"
      fillOpacity="0.22"
      stroke="#16A34A"
      strokeWidth="1.75"
    />
  </svg>
);

/**
 * Mathematics & Education emblem: clean academic mortarboard + calculator & Sigma/Pi detail.
 */
export const MathEducationMarkIcon = ({ className = 'w-5 h-5', ...props }) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    className={className}
    aria-hidden="true"
    {...props}
  >
    <rect
      x="3.5"
      y="3.5"
      width="17"
      height="17"
      rx="3.5"
      fill="#16A34A"
      fillOpacity="0.1"
      stroke="#15803D"
      strokeWidth="1.75"
    />
    <path
      d="M14.5 7.5H8.5l3.2 4-3.2 4h6"
      stroke="#15803D"
      strokeWidth="1.9"
      strokeLinecap="round"
      strokeLinejoin="round"
    />
    <path
      d="M16.2 12h2.2M17.3 10.9v2.2"
      stroke="#2563EB"
      strokeWidth="1.75"
      strokeLinecap="round"
    />
  </svg>
);

/**
 * Studio Headphones & Audio Waveform mark for Music & Audio / Audio & Video.
 */
export const AudioStudioMarkIcon = ({ className = 'w-5 h-5', ...props }) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    className={className}
    aria-hidden="true"
    {...props}
  >
    <path
      d="M4 13v-1a8 8 0 0 1 16 0v1"
      stroke="#0284C7"
      strokeWidth="1.85"
      strokeLinecap="round"
    />
    <rect
      x="3"
      y="13"
      width="3.8"
      height="6.2"
      rx="1.6"
      fill="#0EA5E9"
      fillOpacity="0.2"
      stroke="#0284C7"
      strokeWidth="1.75"
    />
    <rect
      x="17.2"
      y="13"
      width="3.8"
      height="6.2"
      rx="1.6"
      fill="#0EA5E9"
      fillOpacity="0.2"
      stroke="#0284C7"
      strokeWidth="1.75"
    />
    <path
      d="M9.5 16.5v-2.2M12 17.5v-4.2M14.5 16.5v-2.2"
      stroke="#2563EB"
      strokeWidth="1.85"
      strokeLinecap="round"
    />
  </svg>
);

/**
 * Neural workflow circuit graph (clean interconnected nodes, no glowing orbs or cartoon robots).
 */
export const AiWorkflowMarkIcon = ({ className = 'w-5 h-5', ...props }) => (
  <svg
    viewBox="0 0 24 24"
    fill="none"
    xmlns="http://www.w3.org/2000/svg"
    className={className}
    aria-hidden="true"
    {...props}
  >
    <path
      d="M6.5 7.5 12 12m0 0-5.5 4.5M12 12h5.5M12 12V6"
      stroke="#0284C7"
      strokeWidth="1.75"
      strokeLinecap="round"
    />
    <circle cx="5.5" cy="7" r="2.2" fill="#E0F2FE" stroke="#0284C7" strokeWidth="1.75" />
    <circle cx="5.5" cy="17" r="2.2" fill="#E0F2FE" stroke="#0284C7" strokeWidth="1.75" />
    <circle cx="12" cy="5.5" r="2" fill="#EAF4FC" stroke="#2563EB" strokeWidth="1.75" />
    <circle cx="12" cy="12" r="2.7" fill="#2563EB" fillOpacity="0.2" stroke="#2563EB" strokeWidth="1.85" />
    <circle cx="18.5" cy="12" r="2.3" fill="#E0F2FE" stroke="#0EA5E9" strokeWidth="1.75" />
  </svg>
);

/**
 * Renders the primary realistic icon for a category (supports custom SVGs & Lucide icons).
 */
export const CategoryVisualIcon = ({ theme, className = 'w-5 h-5' }) => {
  const IconComponent = theme?.icon || FolderTree;
  return <IconComponent className={className} strokeWidth={1.85} aria-hidden="true" />;
};

/**
 * Renders 2-3 small crisp secondary discipline glyphs that reinforce what products live in the category.
 */
export const CategoryDisciplineStrip = ({ icons = [], className = 'w-3.5 h-3.5' }) => {
  if (!icons.length) return null;
  return (
    <div className="inline-flex items-center gap-1.5 text-[#64748B]" aria-hidden="true">
      {icons.map((IconComp, idx) => (
        <IconComp key={idx} className={className} strokeWidth={1.8} />
      ))}
    </div>
  );
};

import { useEffect, useState } from 'react';
import { Store } from 'lucide-react';

/**
 * Clean, domain-specific SVG architectural illustration for storefront card banners
 * when no custom banner image is uploaded (or when a banner URL fails to load).
 */
export const StorefrontBannerIllustration = ({ themeKey = 'default' }) => {
  switch (themeKey) {
    case 'business':
      return (
        <svg
          viewBox="0 0 360 112"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="w-full h-full object-cover"
          preserveAspectRatio="xMidYMid slice"
          aria-hidden="true"
        >
          {/* Subtle architectural ledger grid */}
          <path
            d="M0 28h360M0 56h360M0 84h360M90 0v112M180 0v112M270 0v112"
            stroke="#DCE6EF"
            strokeWidth="0.75"
            strokeDasharray="2 3"
          />
          {/* Left-offset clean spreadsheet / ledger lines */}
          <rect
            x="24"
            y="18"
            width="104"
            height="54"
            rx="8"
            fill="#FFFFFF"
            fillOpacity="0.88"
            stroke="#D5DEE8"
          />
          <rect x="34" y="28" width="44" height="5" rx="2.5" fill="#0D9488" fillOpacity="0.28" />
          <rect x="34" y="39" width="78" height="4" rx="2" fill="#DCE6EF" />
          <rect x="34" y="48" width="64" height="4" rx="2" fill="#DCE6EF" />
          <rect x="34" y="57" width="48" height="4" rx="2" fill="#BAE6FD" />
          {/* Right realistic KPI & revenue bar chart widget */}
          <rect
            x="148"
            y="16"
            width="186"
            height="82"
            rx="10"
            fill="#FFFFFF"
            stroke="#CBD5E1"
          />
          <rect x="162" y="27" width="48" height="6" rx="3" fill="#263445" fillOpacity="0.18" />
          <rect x="162" y="37" width="30" height="4" rx="2" fill="#0D9488" fillOpacity="0.5" />
          {/* Vertical bars */}
          <rect x="166" y="68" width="14" height="18" rx="3" fill="#DCE6EF" />
          <rect x="186" y="58" width="14" height="28" rx="3" fill="#99F6E4" />
          <rect x="206" y="62" width="14" height="24" rx="3" fill="#BFDBFE" />
          <rect x="226" y="48" width="14" height="38" rx="3" fill="#0D9488" fillOpacity="0.78" />
          <rect x="246" y="53" width="14" height="33" rx="3" fill="#60A5FA" />
          <rect x="266" y="40" width="14" height="46" rx="3" fill="#2563EB" />
          <rect x="286" y="45" width="14" height="41" rx="3" fill="#0EA5E9" fillOpacity="0.7" />
          <path
            d="M173 62 L193 52 L213 56 L233 43 L253 47 L273 34 L293 39"
            stroke="#0F766E"
            strokeWidth="1.75"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <circle cx="273" cy="34" r="3" fill="#2563EB" stroke="#FFFFFF" strokeWidth="1.2" />
        </svg>
      );

    case 'development':
      return (
        <svg
          viewBox="0 0 360 112"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="w-full h-full object-cover"
          preserveAspectRatio="xMidYMid slice"
          aria-hidden="true"
        >
          {/* Subtle developer grid */}
          <path d="M0 32h360M0 64h360M0 96h360" stroke="#E0E7FF" strokeWidth="0.75" />
          {/* Mini terminal chip left */}
          <rect
            x="22"
            y="18"
            width="102"
            height="52"
            rx="8"
            fill="#1E293B"
            stroke="#334155"
          />
          <circle cx="33" cy="27" r="2.2" fill="#64748B" />
          <circle cx="41" cy="27" r="2.2" fill="#64748B" />
          <circle cx="49" cy="27" r="2.2" fill="#64748B" />
          <path
            d="M32 42 l6 4 -6 4"
            stroke="#38BDF8"
            strokeWidth="1.75"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <rect x="43" y="44" width="44" height="4" rx="2" fill="#94A3B8" />
          <rect x="32" y="56" width="66" height="4" rx="2" fill="#34D399" fillOpacity="0.8" />
          {/* Realistic Light-Mode Code Editor Panel */}
          <rect
            x="140"
            y="14"
            width="196"
            height="86"
            rx="10"
            fill="#FFFFFF"
            stroke="#C7D2FE"
          />
          <path d="M140 34h196" stroke="#E2E8F0" />
          <rect x="150" y="20" width="38" height="8" rx="4" fill="#EEF2FF" />
          <rect x="194" y="20" width="32" height="8" rx="4" fill="#F8FAFC" />
          {/* Syntax lines */}
          <rect x="152" y="43" width="24" height="4.5" rx="2.2" fill="#4F46E5" fillOpacity="0.78" />
          <rect x="181" y="43" width="48" height="4.5" rx="2.2" fill="#2563EB" fillOpacity="0.35" />
          <rect x="234" y="43" width="28" height="4.5" rx="2.2" fill="#0EA5E9" fillOpacity="0.5" />

          <rect x="162" y="54" width="32" height="4.5" rx="2.2" fill="#0D9488" fillOpacity="0.65" />
          <rect x="199" y="54" width="68" height="4.5" rx="2.2" fill="#CBD5E1" />

          <rect x="162" y="65" width="26" height="4.5" rx="2.2" fill="#2563EB" fillOpacity="0.7" />
          <rect x="193" y="65" width="46" height="4.5" rx="2.2" fill="#16A34A" fillOpacity="0.55" />
          <rect x="244" y="65" width="36" height="4.5" rx="2.2" fill="#CBD5E1" />

          <rect x="152" y="76" width="54" height="4.5" rx="2.2" fill="#94A3B8" fillOpacity="0.55" />
          <rect x="212" y="76" width="40" height="4.5" rx="2.2" fill="#4F46E5" fillOpacity="0.45" />

          <rect x="152" y="87" width="30" height="4.5" rx="2.2" fill="#CBD5E1" />
        </svg>
      );

    case 'design':
      return (
        <svg
          viewBox="0 0 360 112"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="w-full h-full object-cover"
          preserveAspectRatio="xMidYMid slice"
          aria-hidden="true"
        >
          {/* Dot artboard canvas */}
          <path
            d="M0 28h360M0 56h360M0 84h360M72 0v112M144 0v112M216 0v112M288 0v112"
            stroke="#EDE9FE"
            strokeWidth="0.75"
          />
          {/* Typography specimen mini-card left */}
          <rect
            x="24"
            y="18"
            width="92"
            height="54"
            rx="8"
            fill="#FFFFFF"
            stroke="#DDD6FE"
          />
          <text
            x="38"
            y="49"
            fill="#5B21B6"
            fontSize="20"
            fontWeight="700"
            fontFamily="Inter, system-ui, sans-serif"
          >
            Aa
          </text>
          <rect x="70" y="34" width="34" height="4" rx="2" fill="#C4B5FD" />
          <rect x="70" y="42" width="26" height="4" rx="2" fill="#E2E8F0" />
          <circle cx="42" cy="60" r="4" fill="#7C3AED" />
          <circle cx="54" cy="60" r="4" fill="#2563EB" />
          <circle cx="66" cy="60" r="4" fill="#0EA5E9" />
          <circle cx="78" cy="60" r="4" fill="#16A34A" />

          {/* Artboard vector frame right */}
          <rect
            x="138"
            y="16"
            width="196"
            height="82"
            rx="10"
            fill="#FFFFFF"
            stroke="#DDD6FE"
          />
          {/* Vector selection handles */}
          <rect x="156" y="28" width="102" height="58" rx="6" fill="#F5F3FF" stroke="#7C3AED" strokeDasharray="3 2" />
          <rect x="153.5" y="25.5" width="5" height="5" fill="#FFFFFF" stroke="#7C3AED" strokeWidth="1.2" />
          <rect x="255.5" y="25.5" width="5" height="5" fill="#FFFFFF" stroke="#7C3AED" strokeWidth="1.2" />
          <rect x="153.5" y="83.5" width="5" height="5" fill="#FFFFFF" stroke="#7C3AED" strokeWidth="1.2" />
          <rect x="255.5" y="83.5" width="5" height="5" fill="#FFFFFF" stroke="#7C3AED" strokeWidth="1.2" />
          {/* Bezier curve inside frame */}
          <path
            d="M168 70 C 186 38, 224 76, 246 42"
            stroke="#6D28D9"
            strokeWidth="2.2"
            strokeLinecap="round"
          />
          <circle cx="168" cy="70" r="3" fill="#2563EB" />
          <circle cx="246" cy="42" r="3" fill="#0EA5E9" />
          {/* Right UI inspector swatches */}
          <rect x="272" y="28" width="48" height="16" rx="4" fill="#F8FAFC" stroke="#E2E8F0" />
          <rect x="278" y="34" width="22" height="4" rx="2" fill="#64748B" fillOpacity="0.4" />
          <rect x="272" y="50" width="48" height="16" rx="4" fill="#EAF4FC" stroke="#BFDBFE" />
          <rect x="278" y="56" width="28" height="4" rx="2" fill="#2563EB" fillOpacity="0.5" />
          <rect x="272" y="72" width="48" height="14" rx="4" fill="#F3F0FF" stroke="#DDD6FE" />
        </svg>
      );

    case 'education':
      return (
        <svg
          viewBox="0 0 360 112"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="w-full h-full object-cover"
          preserveAspectRatio="xMidYMid slice"
          aria-hidden="true"
        >
          {/* Faint academic ruled lines */}
          <path d="M0 24h360M0 48h360M0 72h360M0 96h360" stroke="#D1FAE5" strokeWidth="0.75" />
          {/* Formula flashcard left */}
          <rect
            x="24"
            y="18"
            width="96"
            height="54"
            rx="8"
            fill="#FFFFFF"
            stroke="#A7F3D0"
          />
          <rect x="34" y="27" width="38" height="4.5" rx="2" fill="#16A34A" fillOpacity="0.32" />
          <text
            x="34"
            y="50"
            fill="#15803D"
            fontSize="14"
            fontWeight="700"
            fontFamily="Georgia, serif"
          >
            ∑ f(x) · π
          </text>
          <rect x="34" y="58" width="64" height="3.5" rx="1.75" fill="#CBD5E1" />

          {/* Open handbook spread right */}
          <rect
            x="138"
            y="15"
            width="198"
            height="84"
            rx="10"
            fill="#FFFFFF"
            stroke="#CBD5E1"
          />
          <path d="M237 15v84" stroke="#E2E8F0" strokeWidth="1.2" />
          {/* Left page */}
          <rect x="150" y="27" width="52" height="6" rx="3" fill="#15803D" fillOpacity="0.72" />
          <rect x="150" y="40" width="74" height="4" rx="2" fill="#DCE6EF" />
          <rect x="150" y="49" width="68" height="4" rx="2" fill="#DCE6EF" />
          <rect x="150" y="58" width="58" height="4" rx="2" fill="#DCE6EF" />
          <rect x="150" y="70" width="74" height="16" rx="4" fill="#ECFDF5" stroke="#A7F3D0" />
          <rect x="158" y="76" width="46" height="4" rx="2" fill="#16A34A" fillOpacity="0.55" />
          {/* Right page checklist & diagram */}
          <rect x="250" y="27" width="48" height="6" rx="3" fill="#2563EB" fillOpacity="0.65" />
          <circle cx="254" cy="43" r="3" fill="#16A34A" fillOpacity="0.25" stroke="#16A34A" strokeWidth="1.2" />
          <rect x="262" y="41" width="56" height="4" rx="2" fill="#CBD5E1" />
          <circle cx="254" cy="56" r="3" fill="#16A34A" fillOpacity="0.25" stroke="#16A34A" strokeWidth="1.2" />
          <rect x="262" y="54" width="48" height="4" rx="2" fill="#CBD5E1" />
          <circle cx="254" cy="69" r="3" fill="#EAF4FC" stroke="#2563EB" strokeWidth="1.2" />
          <rect x="262" y="67" width="52" height="4" rx="2" fill="#CBD5E1" />
          <rect x="250" y="80" width="70" height="7" rx="3.5" fill="#EAF4FC" />
        </svg>
      );

    case 'ai':
      return (
        <svg
          viewBox="0 0 360 112"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="w-full h-full object-cover"
          preserveAspectRatio="xMidYMid slice"
          aria-hidden="true"
        >
          <path
            d="M0 28h360M0 56h360M0 84h360M60 0v112M180 0v112M300 0v112"
            stroke="#E0F2FE"
            strokeWidth="0.75"
          />
          {/* Node connectors */}
          <path
            d="M112 44 C132 44, 134 54, 154 54 M228 54 C246 54, 248 40, 266 40 M228 54 C246 54, 248 74, 266 74"
            stroke="#0EA5E9"
            strokeWidth="1.75"
            strokeLinecap="round"
          />
          {/* Input Prompt Node */}
          <rect x="28" y="24" width="84" height="40" rx="8" fill="#FFFFFF" stroke="#BAE6FD" />
          <circle cx="40" cy="36" r="3.5" fill="#0EA5E9" />
          <rect x="49" y="34" width="44" height="4" rx="2" fill="#263445" fillOpacity="0.24" />
          <rect x="38" y="48" width="60" height="4" rx="2" fill="#DCE6EF" />
          {/* Agent Workflow Hub */}
          <rect x="154" y="32" width="74" height="44" rx="10" fill="#FFFFFF" stroke="#2563EB" strokeWidth="1.3" />
          <circle cx="167" cy="46" r="4" fill="#2563EB" fillOpacity="0.2" stroke="#2563EB" strokeWidth="1.4" />
          <rect x="176" y="44" width="40" height="4.5" rx="2.2" fill="#2563EB" fillOpacity="0.7" />
          <rect x="164" y="58" width="52" height="4" rx="2" fill="#CBD5E1" />
          {/* Output Nodes */}
          <rect x="266" y="22" width="68" height="32" rx="8" fill="#FFFFFF" stroke="#BAE6FD" />
          <rect x="276" y="32" width="42" height="4" rx="2" fill="#16A34A" fillOpacity="0.65" />
          <rect x="276" y="41" width="32" height="3.5" rx="1.75" fill="#DCE6EF" />

          <rect x="266" y="60" width="68" height="32" rx="8" fill="#FFFFFF" stroke="#BAE6FD" />
          <rect x="276" y="70" width="44" height="4" rx="2" fill="#0EA5E9" fillOpacity="0.7" />
          <rect x="276" y="79" width="28" height="3.5" rx="1.75" fill="#DCE6EF" />
        </svg>
      );

    case 'music':
      return (
        <svg
          viewBox="0 0 360 112"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="w-full h-full object-cover"
          preserveAspectRatio="xMidYMid slice"
          aria-hidden="true"
        >
          <rect x="26" y="18" width="308" height="76" rx="10" fill="#FFFFFF" stroke="#BAE6FD" />
          <path d="M26 36h308" stroke="#E0F2FE" />
          <rect x="40" y="25" width="38" height="5" rx="2.5" fill="#0284C7" fillOpacity="0.55" />
          <rect x="86" y="25" width="26" height="5" rx="2.5" fill="#CBD5E1" />
          {/* Waveform bars */}
          {[
            16, 26, 38, 22, 42, 34, 20, 44, 30, 18, 36, 46, 28, 22, 38, 30, 16, 40, 24, 32, 42, 20,
            28, 36, 18,
          ].map((h, i) => (
            <rect
              key={i}
              x={140 + i * 7.5}
              y={65 - h / 2}
              width="4"
              height={h}
              rx="2"
              fill={i % 3 === 0 ? '#2563EB' : '#0EA5E9'}
              fillOpacity={i % 2 === 0 ? 0.8 : 0.45}
            />
          ))}
        </svg>
      );

    case 'marketing':
      return (
        <svg
          viewBox="0 0 360 112"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="w-full h-full object-cover"
          preserveAspectRatio="xMidYMid slice"
          aria-hidden="true"
        >
          <rect x="140" y="16" width="194" height="82" rx="10" fill="#FFFFFF" stroke="#BFDBFE" />
          <rect x="156" y="28" width="60" height="5" rx="2.5" fill="#2563EB" fillOpacity="0.6" />
          <path
            d="M158 78 L190 66 L220 70 L254 48 L286 52 L316 32"
            stroke="#2563EB"
            strokeWidth="2.2"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <circle cx="316" cy="32" r="3.5" fill="#16A34A" />
          <rect x="156" y="42" width="44" height="14" rx="4" fill="#EAF4FC" />
          <rect x="208" y="42" width="44" height="14" rx="4" fill="#F8FAFC" stroke="#E2E8F0" />
        </svg>
      );

    default:
      return (
        <svg
          viewBox="0 0 360 112"
          fill="none"
          xmlns="http://www.w3.org/2000/svg"
          className="w-full h-full object-cover"
          preserveAspectRatio="xMidYMid slice"
          aria-hidden="true"
        >
          <path
            d="M0 28h360M0 56h360M0 84h360M90 0v112M180 0v112M270 0v112"
            stroke="#DCE6EF"
            strokeWidth="0.75"
          />
          <rect x="148" y="18" width="184" height="76" rx="10" fill="#FFFFFF" stroke="#D5DEE8" />
          <rect x="164" y="30" width="66" height="6" rx="3" fill="#2563EB" fillOpacity="0.45" />
          <rect x="164" y="44" width="144" height="4" rx="2" fill="#DCE6EF" />
          <rect x="164" y="54" width="120" height="4" rx="2" fill="#DCE6EF" />
          <rect x="164" y="68" width="52" height="14" rx="5" fill="#EAF4FC" stroke="#BFDBFE" />
        </svg>
      );
  }
};

/**
 * Storefront card/header banner with custom banner_url support and automatic fallback
 * to a domain-matched architectural illustration if missing or broken.
 */
export const StorefrontBannerVisual = ({
  store,
  theme,
  showDomainPill = true,
  className = '',
}) => {
  const [imgFailed, setImgFailed] = useState(false);

  useEffect(() => {
    setImgFailed(false);
  }, [store?.banner_url]);

  const hasValidBanner = Boolean(store?.banner_url && !imgFailed);
  const AccentIcon = theme?.secondaryIcon || Store;

  return (
    <div
      className={`relative w-full h-full overflow-hidden ${
        hasValidBanner ? 'bg-[#F8FAFC]' : theme?.bannerBgClass || 'bg-[#F8FAFC]'
      } ${className}`}
    >
      {/* Top 3px domain accent stripe */}
      <div
        className={`absolute inset-x-0 top-0 h-[3px] z-10 ${theme?.accentLineClass || 'bg-[#2563EB]'}`}
        aria-hidden="true"
      />

      {hasValidBanner ? (
        <img
          src={store.banner_url}
          alt={`${store.store_name || 'Creator storefront'} banner`}
          loading="lazy"
          onError={() => setImgFailed(true)}
          className="w-full h-full object-cover"
        />
      ) : (
        <StorefrontBannerIllustration themeKey={theme?.key || 'default'} />
      )}

      {showDomainPill && theme?.shortTag && (
        <span
          className={`absolute top-2.5 right-3 z-10 inline-flex items-center gap-1.5 rounded-full border px-2.5 py-0.5 text-[11px] font-semibold shadow-2xs backdrop-blur-xs ${
            theme.pillClass || 'bg-white/95 text-[#1D4ED8] border-[#BFDBFE]'
          }`}
        >
          <AccentIcon className="w-3 h-3 shrink-0" aria-hidden="true" />
          <span>{theme.shortTag}</span>
        </span>
      )}
    </div>
  );
};

/**
 * Storefront avatar square with logo_url support and domain-specific icon fallback
 * when no uploaded logo exists or an image fails to load.
 */
export const StorefrontAvatarLogo = ({
  store,
  theme,
  sizeClass = 'w-14 h-14 rounded-2xl',
  iconSizeClass = 'w-6 h-6',
}) => {
  const [imgFailed, setImgFailed] = useState(false);

  useEffect(() => {
    setImgFailed(false);
  }, [store?.logo_url]);

  const hasValidLogo = Boolean(store?.logo_url && !imgFailed);
  const IconComp = theme?.icon || Store;

  return (
    <div
      className={`${sizeClass} border-2 shadow-xs overflow-hidden flex items-center justify-center shrink-0 transition-transform duration-200 group-hover:scale-[1.03] ${
        hasValidLogo
          ? `bg-white ${theme?.avatarBorderClass || 'border-[#BFDBFE]'}`
          : theme?.iconBoxClass || 'bg-[#EAF4FC] text-[#2563EB] border-[#BFDBFE]'
      }`}
    >
      {hasValidLogo ? (
        <img
          src={store.logo_url}
          alt={store?.store_name || 'Store logo'}
          loading="lazy"
          onError={() => setImgFailed(true)}
          className="w-full h-full object-cover"
        />
      ) : (
        <IconComp className={iconSizeClass} strokeWidth={1.85} aria-hidden="true" />
      )}
    </div>
  );
};

import {
  BarChart3,
  BrainCircuit,
  Briefcase,
  Calculator,
  CheckSquare,
  Clapperboard,
  Code2,
  Cpu,
  Database,
  FileSpreadsheet,
  FileText,
  FolderTree,
  Globe,
  GraduationCap,
  Headphones,
  Landmark,
  Layers,
  Megaphone,
  Mic,
  Music,
  Palette,
  PenTool,
  Receipt,
  Server,
  Sigma,
  Store,
  Target,
  Terminal,
  TrendingUp,
  Video,
  Wallet,
  Workflow,
} from 'lucide-react';
import {
  AiWorkflowMarkIcon,
  AudioStudioMarkIcon,
  DesignVectorMarkIcon,
  MathEducationMarkIcon,
  PythonBrandIcon,
} from '../components/products/CategoryVisual';

const CATEGORY_THEMES = {
  'design-and-graphics': {
    accentName: 'violet',
    icon: DesignVectorMarkIcon,
    badgeIcon: PenTool,
    disciplineIcons: [PenTool, Layers, Palette],
    disciplineLabel: 'Vector · UI · Artboards',
    badgeClass: 'bg-[#F3F0FF] text-[#5B21B6] border-[#DDD6FE]',
    iconBoxClass: 'bg-[#F3F0FF] text-[#6D28D9] border-[#DDD6FE]',
    accentLineClass: 'bg-[#7C3AED]',
    softSurfaceClass: 'bg-[#F8FAFC]',
  },
  'documents-and-productivity': {
    accentName: 'blue',
    icon: FileSpreadsheet,
    badgeIcon: FileText,
    disciplineIcons: [FileSpreadsheet, CheckSquare, FileText],
    disciplineLabel: 'Sheets · PDFs · Planners',
    badgeClass: 'bg-[#EAF4FC] text-[#1D4ED8] border-[#BFDBFE]',
    iconBoxClass: 'bg-[#EAF4FC] text-[#2563EB] border-[#BFDBFE]',
    accentLineClass: 'bg-[#2563EB]',
    softSurfaceClass: 'bg-[#F8FAFC]',
  },
  'education-and-learning': {
    accentName: 'green',
    icon: GraduationCap,
    badgeIcon: GraduationCap,
    disciplineIcons: [Calculator, Sigma, GraduationCap],
    disciplineLabel: 'Math · Code · Notes',
    badgeClass: 'bg-emerald-50 text-[#15803D] border-emerald-200',
    iconBoxClass: 'bg-emerald-50 text-[#16A34A] border-emerald-200',
    accentLineClass: 'bg-[#16A34A]',
    softSurfaceClass: 'bg-[#F8FAFC]',
  },
  'mathematics-and-education': {
    accentName: 'green',
    icon: MathEducationMarkIcon,
    badgeIcon: Calculator,
    disciplineIcons: [Calculator, Sigma, GraduationCap],
    disciplineLabel: 'Algebra · Calculus · Formulas',
    badgeClass: 'bg-emerald-50 text-[#15803D] border-emerald-200',
    iconBoxClass: 'bg-emerald-50 text-[#15803D] border-emerald-200',
    accentLineClass: 'bg-[#16A34A]',
    softSurfaceClass: 'bg-[#F8FAFC]',
  },
  'development-and-technology': {
    accentName: 'indigo',
    icon: Terminal,
    badgeIcon: Code2,
    disciplineIcons: [Terminal, Code2, Database],
    disciplineLabel: 'Python · React · APIs',
    badgeClass: 'bg-[#EEF2FF] text-[#3730A3] border-[#C7D2FE]',
    iconBoxClass: 'bg-[#EEF2FF] text-[#1D4ED8] border-[#C7D2FE]',
    accentLineClass: 'bg-[#4F46E5]',
    softSurfaceClass: 'bg-[#F8FAFC]',
  },
  'python-and-programming': {
    accentName: 'indigo',
    icon: PythonBrandIcon,
    badgeIcon: Terminal,
    disciplineIcons: [Terminal, Code2, Cpu],
    disciplineLabel: 'Python · CLI · Automation',
    badgeClass: 'bg-[#EEF2FF] text-[#1D4ED8] border-[#C7D2FE]',
    iconBoxClass: 'bg-[#EAF4FC] text-[#2563EB] border-[#BFDBFE]',
    accentLineClass: 'bg-[#2563EB]',
    softSurfaceClass: 'bg-[#F8FAFC]',
  },
  'web-and-technology': {
    accentName: 'indigo',
    icon: Globe,
    badgeIcon: Server,
    disciplineIcons: [Globe, Code2, Database],
    disciplineLabel: 'Web · Server · Database',
    badgeClass: 'bg-[#EEF2FF] text-[#3730A3] border-[#C7D2FE]',
    iconBoxClass: 'bg-[#EEF2FF] text-[#4F46E5] border-[#C7D2FE]',
    accentLineClass: 'bg-[#4F46E5]',
    softSurfaceClass: 'bg-[#F8FAFC]',
  },
  'ai-resources-and-automation': {
    accentName: 'cyan',
    icon: AiWorkflowMarkIcon,
    badgeIcon: Workflow,
    disciplineIcons: [BrainCircuit, Workflow, Cpu],
    disciplineLabel: 'Prompts · Agents · Flows',
    badgeClass: 'bg-[#E0F2FE] text-[#0369A1] border-[#BAE6FD]',
    iconBoxClass: 'bg-[#E0F2FE] text-[#0284C7] border-[#BAE6FD]',
    accentLineClass: 'bg-[#0EA5E9]',
    softSurfaceClass: 'bg-[#F8FAFC]',
  },
  'digital-marketing': {
    accentName: 'slate-blue',
    icon: Megaphone,
    badgeIcon: Megaphone,
    disciplineIcons: [Megaphone, Target, TrendingUp],
    disciplineLabel: 'Campaigns · Analytics · ROI',
    badgeClass: 'bg-[#DCE6EF] text-[#263445] border-[#CBD5E1]',
    iconBoxClass: 'bg-[#EAF4FC] text-[#2563EB] border-[#BFDBFE]',
    accentLineClass: 'bg-[#2563EB]',
    softSurfaceClass: 'bg-[#F8FAFC]',
  },
  'audio-and-video': {
    accentName: 'slate-sky',
    icon: AudioStudioMarkIcon,
    badgeIcon: Clapperboard,
    disciplineIcons: [Headphones, Music, Clapperboard],
    disciplineLabel: 'Audio · LUTs · Motion',
    badgeClass: 'bg-[#F1F5F9] text-[#263445] border-[#D5DEE8]',
    iconBoxClass: 'bg-[#EDF5FC] text-[#0284C7] border-[#BAE6FD]',
    accentLineClass: 'bg-[#0EA5E9]',
    softSurfaceClass: 'bg-[#F8FAFC]',
  },
  'music-and-audio': {
    accentName: 'slate-sky',
    icon: AudioStudioMarkIcon,
    badgeIcon: Headphones,
    disciplineIcons: [Headphones, Music, Mic],
    disciplineLabel: 'Stems · WAV · Sound FX',
    badgeClass: 'bg-[#EDF5FC] text-[#0369A1] border-[#BAE6FD]',
    iconBoxClass: 'bg-[#EDF5FC] text-[#0284C7] border-[#BAE6FD]',
    accentLineClass: 'bg-[#0EA5E9]',
    softSurfaceClass: 'bg-[#F8FAFC]',
  },
  'video-and-animation': {
    accentName: 'slate-sky',
    icon: Clapperboard,
    badgeIcon: Video,
    disciplineIcons: [Clapperboard, Video, Layers],
    disciplineLabel: 'LUTs · Timeline · Keyframes',
    badgeClass: 'bg-[#F1F5F9] text-[#263445] border-[#D5DEE8]',
    iconBoxClass: 'bg-[#EDF5FC] text-[#0284C7] border-[#BAE6FD]',
    accentLineClass: 'bg-[#0EA5E9]',
    softSurfaceClass: 'bg-[#F8FAFC]',
  },
  'business-resources': {
    accentName: 'teal',
    icon: BarChart3,
    badgeIcon: Briefcase,
    disciplineIcons: [BarChart3, Landmark, Receipt],
    disciplineLabel: 'Finance · Decks · Invoices',
    badgeClass: 'bg-teal-50 text-[#0F766E] border-teal-200',
    iconBoxClass: 'bg-teal-50 text-[#0D9488] border-teal-200',
    accentLineClass: 'bg-[#0D9488]',
    softSurfaceClass: 'bg-[#F8FAFC]',
  },
};

const DEFAULT_THEME = {
  accentName: 'blue',
  icon: FolderTree,
  badgeIcon: FolderTree,
  disciplineIcons: [FolderTree],
  disciplineLabel: 'Digital Collection',
  badgeClass: 'bg-[#EAF4FC] text-[#1D4ED8] border-[#D5DEE8]',
  iconBoxClass: 'bg-[#EAF4FC] text-[#2563EB] border-[#D5DEE8]',
  accentLineClass: 'bg-[#2563EB]',
  softSurfaceClass: 'bg-[#F8FAFC]',
};

const KEYWORD_FALLBACKS = [
  { keywords: ['math', 'calculus', 'algebra'], target: 'mathematics-and-education' },
  { keywords: ['python'], target: 'python-and-programming' },
  { keywords: ['education', 'learn', 'ebook', 'study', 'course'], target: 'education-and-learning' },
  { keywords: ['music', 'audio', 'sound', 'guitar'], target: 'music-and-audio' },
  { keywords: ['video', 'film', 'animation', 'motion'], target: 'video-and-animation' },
  { keywords: ['design', 'graphic', 'figma', 'ui'], target: 'design-and-graphics' },
  { keywords: ['business', 'finance', 'invoice', 'startup'], target: 'business-resources' },
  { keywords: ['ai', 'automation', 'prompt', 'workflow'], target: 'ai-resources-and-automation' },
  { keywords: ['marketing', 'social', 'campaign', 'seo'], target: 'digital-marketing' },
  { keywords: ['document', 'productivity', 'pdf', 'spreadsheet', 'notion'], target: 'documents-and-productivity' },
  { keywords: ['web', 'cloud', 'database', 'server'], target: 'web-and-technology' },
  { keywords: ['dev', 'code', 'tech', 'software', 'program'], target: 'development-and-technology' },
];

export const getCategoryTheme = (slugOrName) => {
  if (!slugOrName) return DEFAULT_THEME;
  const normalized = String(slugOrName).trim().toLowerCase();
  if (CATEGORY_THEMES[normalized]) {
    return CATEGORY_THEMES[normalized];
  }
  const match = KEYWORD_FALLBACKS.find((entry) =>
    entry.keywords.some((kw) => normalized.includes(kw))
  );
  return match ? CATEGORY_THEMES[match.target] : DEFAULT_THEME;
};

const STOREFRONT_THEMES = {
  business: {
    key: 'business',
    icon: Briefcase,
    secondaryIcon: BarChart3,
    accentIcon: Wallet,
    shortTag: 'Finance & Templates',
    iconBoxClass: 'bg-teal-50 text-[#0F766E] border-teal-200',
    avatarBorderClass: 'border-[#99F6E4]',
    accentLineClass: 'bg-[#0D9488]',
    bannerBgClass: 'bg-gradient-to-br from-[#F0FDFA] via-[#F8FAFC] to-[#EAF4FC]',
    pillClass: 'bg-white/95 text-[#0F766E] border-[#CCFBF1]',
  },
  development: {
    key: 'development',
    icon: Terminal,
    secondaryIcon: Code2,
    accentIcon: PythonBrandIcon,
    shortTag: 'Code & Dev Starters',
    iconBoxClass: 'bg-[#EEF2FF] text-[#1D4ED8] border-[#C7D2FE]',
    avatarBorderClass: 'border-[#C7D2FE]',
    accentLineClass: 'bg-[#4F46E5]',
    bannerBgClass: 'bg-gradient-to-br from-[#EEF2FF] via-[#F8FAFC] to-[#EAF4FC]',
    pillClass: 'bg-white/95 text-[#3730A3] border-[#C7D2FE]',
  },
  design: {
    key: 'design',
    icon: DesignVectorMarkIcon,
    secondaryIcon: PenTool,
    accentIcon: Palette,
    shortTag: 'Design & UI Kits',
    iconBoxClass: 'bg-[#F3F0FF] text-[#6D28D9] border-[#DDD6FE]',
    avatarBorderClass: 'border-[#DDD6FE]',
    accentLineClass: 'bg-[#7C3AED]',
    bannerBgClass: 'bg-gradient-to-br from-[#F5F3FF] via-[#F8FAFC] to-[#EAF4FC]',
    pillClass: 'bg-white/95 text-[#5B21B6] border-[#DDD6FE]',
  },
  education: {
    key: 'education',
    icon: GraduationCap,
    secondaryIcon: MathEducationMarkIcon,
    accentIcon: Calculator,
    shortTag: 'Guides & Learning',
    iconBoxClass: 'bg-emerald-50 text-[#15803D] border-emerald-200',
    avatarBorderClass: 'border-[#A7F3D0]',
    accentLineClass: 'bg-[#16A34A]',
    bannerBgClass: 'bg-gradient-to-br from-[#ECFDF5] via-[#F8FAFC] to-[#EAF4FC]',
    pillClass: 'bg-white/95 text-[#15803D] border-emerald-200',
  },
  ai: {
    key: 'ai',
    icon: AiWorkflowMarkIcon,
    secondaryIcon: BrainCircuit,
    accentIcon: Workflow,
    shortTag: 'AI & Automation',
    iconBoxClass: 'bg-[#E0F2FE] text-[#0284C7] border-[#BAE6FD]',
    avatarBorderClass: 'border-[#BAE6FD]',
    accentLineClass: 'bg-[#0EA5E9]',
    bannerBgClass: 'bg-gradient-to-br from-[#E0F2FE] via-[#F8FAFC] to-[#EAF4FC]',
    pillClass: 'bg-white/95 text-[#0369A1] border-[#BAE6FD]',
  },
  music: {
    key: 'music',
    icon: AudioStudioMarkIcon,
    secondaryIcon: Headphones,
    accentIcon: Music,
    shortTag: 'Audio & Production',
    iconBoxClass: 'bg-[#EDF5FC] text-[#0284C7] border-[#BAE6FD]',
    avatarBorderClass: 'border-[#BAE6FD]',
    accentLineClass: 'bg-[#0284C7]',
    bannerBgClass: 'bg-gradient-to-br from-[#EDF5FC] via-[#F8FAFC] to-[#E0F2FE]',
    pillClass: 'bg-white/95 text-[#0369A1] border-[#BAE6FD]',
  },
  marketing: {
    key: 'marketing',
    icon: Megaphone,
    secondaryIcon: Target,
    accentIcon: TrendingUp,
    shortTag: 'Growth & Marketing',
    iconBoxClass: 'bg-[#EAF4FC] text-[#1D4ED8] border-[#BFDBFE]',
    avatarBorderClass: 'border-[#BFDBFE]',
    accentLineClass: 'bg-[#2563EB]',
    bannerBgClass: 'bg-gradient-to-br from-[#DCE6EF] via-[#F8FAFC] to-[#EAF4FC]',
    pillClass: 'bg-white/95 text-[#1D4ED8] border-[#BFDBFE]',
  },
  default: {
    key: 'default',
    icon: Store,
    secondaryIcon: Layers,
    accentIcon: FolderTree,
    shortTag: 'Verified Storefront',
    iconBoxClass: 'bg-[#EAF4FC] text-[#2563EB] border-[#BFDBFE]',
    avatarBorderClass: 'border-[#BFDBFE]',
    accentLineClass: 'bg-[#2563EB]',
    bannerBgClass: 'bg-gradient-to-br from-[#EDF5FC] via-[#F8FAFC] to-[#DCE6EF]',
    pillClass: 'bg-white/95 text-[#1D4ED8] border-[#BFDBFE]',
  },
};

const STOREFRONT_MATCHERS = [
  {
    key: 'business',
    keywords: [
      'business',
      'finance',
      'financial',
      'template',
      'invoice',
      'accounting',
      'spreadsheet',
      'notion',
      'workbook',
      'productivity',
    ],
  },
  {
    key: 'development',
    keywords: [
      'software',
      'code',
      'dev',
      'developer',
      'programming',
      'python',
      'starter',
      'react',
      'api',
      'lab',
      'tech',
    ],
  },
  {
    key: 'education',
    keywords: [
      'education',
      'educational',
      'publisher',
      'learning',
      'academy',
      'vault',
      'handbook',
      'study',
      'math',
      'course',
      'dsa',
    ],
  },
  {
    key: 'design',
    keywords: ['design', 'graphic', 'pixel', 'craft', 'ui', 'figma', 'vector', 'creative'],
  },
  {
    key: 'ai',
    keywords: ['ai', 'automation', 'prompt', 'neural', 'agent', 'workflow'],
  },
  {
    key: 'music',
    keywords: ['music', 'audio', 'sound', 'studio', 'guitar', 'podcast', 'beat'],
  },
  {
    key: 'marketing',
    keywords: ['marketing', 'growth', 'campaign', 'seo', 'social', 'ads'],
  },
];

/**
 * Determine a storefront's domain visual theme from its actual business type,
 * declared product categories, and storefront metadata.
 */
export const resolveStorefrontTheme = (store) => {
  if (!store) return STOREFRONT_THEMES.default;

  const signals = [
    store.business_type,
    ...(Array.isArray(store.product_categories) ? store.product_categories : []),
    store.store_name,
    store.store_description,
  ]
    .filter(Boolean)
    .map((val) => String(val).toLowerCase());

  // Pass 1: prioritize the store's primary declared business_type and primary category first.
  const primarySignal = [store.business_type, store.product_categories?.[0]]
    .filter(Boolean)
    .join(' ')
    .toLowerCase();

  if (primarySignal) {
    const primaryMatch = STOREFRONT_MATCHERS.find((entry) =>
      entry.keywords.some((kw) => primarySignal.includes(kw))
    );
    if (primaryMatch) {
      return STOREFRONT_THEMES[primaryMatch.key];
    }
  }

  // Pass 2: check full list of categories, store name, and description.
  const combinedSignal = signals.join(' ');
  const fallbackMatch = STOREFRONT_MATCHERS.find((entry) =>
    entry.keywords.some((kw) => combinedSignal.includes(kw))
  );

  return fallbackMatch ? STOREFRONT_THEMES[fallbackMatch.key] : STOREFRONT_THEMES.default;
};

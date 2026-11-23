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
    badgeClass: 'bg-violet-950/50 text-violet-300 border-[#DDD6FE]',
    iconBoxClass: 'bg-violet-950/50 text-violet-300 border-[#DDD6FE]',
    accentLineClass: 'bg-[#7C3AED]',
    softSurfaceClass: 'bg-[#18243A]',
  },
  'documents-and-productivity': {
    accentName: 'blue',
    icon: FileSpreadsheet,
    badgeIcon: FileText,
    disciplineIcons: [FileSpreadsheet, CheckSquare, FileText],
    disciplineLabel: 'Sheets · PDFs · Planners',
    badgeClass: 'bg-[#18243A] text-[#93C5FD] border-[#BFDBFE]',
    iconBoxClass: 'bg-[#18243A] text-[#60A5FA] border-[#BFDBFE]',
    accentLineClass: 'bg-[#2563EB]',
    softSurfaceClass: 'bg-[#18243A]',
  },
  'education-and-learning': {
    accentName: 'green',
    icon: GraduationCap,
    badgeIcon: GraduationCap,
    disciplineIcons: [Calculator, Sigma, GraduationCap],
    disciplineLabel: 'Math · Code · Notes',
    badgeClass: 'bg-emerald-950/50 text-emerald-300 border-emerald-200',
    iconBoxClass: 'bg-emerald-950/50 text-emerald-300 border-emerald-200',
    accentLineClass: 'bg-[#16A34A]',
    softSurfaceClass: 'bg-[#18243A]',
  },
  'mathematics-and-education': {
    accentName: 'green',
    icon: MathEducationMarkIcon,
    badgeIcon: Calculator,
    disciplineIcons: [Calculator, Sigma, GraduationCap],
    disciplineLabel: 'Algebra · Calculus · Formulas',
    badgeClass: 'bg-emerald-950/50 text-emerald-300 border-emerald-200',
    iconBoxClass: 'bg-emerald-950/50 text-emerald-300 border-emerald-200',
    accentLineClass: 'bg-[#16A34A]',
    softSurfaceClass: 'bg-[#18243A]',
  },
  'development-and-technology': {
    accentName: 'indigo',
    icon: Terminal,
    badgeIcon: Code2,
    disciplineIcons: [Terminal, Code2, Database],
    disciplineLabel: 'Python · React · APIs',
    badgeClass: 'bg-indigo-950/50 text-indigo-300 border-[#C7D2FE]',
    iconBoxClass: 'bg-indigo-950/50 text-[#93C5FD] border-[#C7D2FE]',
    accentLineClass: 'bg-[#4F46E5]',
    softSurfaceClass: 'bg-[#18243A]',
  },
  'python-and-programming': {
    accentName: 'indigo',
    icon: PythonBrandIcon,
    badgeIcon: Terminal,
    disciplineIcons: [Terminal, Code2, Cpu],
    disciplineLabel: 'Python · CLI · Automation',
    badgeClass: 'bg-indigo-950/50 text-[#93C5FD] border-[#C7D2FE]',
    iconBoxClass: 'bg-[#18243A] text-[#60A5FA] border-[#BFDBFE]',
    accentLineClass: 'bg-[#2563EB]',
    softSurfaceClass: 'bg-[#18243A]',
  },
  'web-and-technology': {
    accentName: 'indigo',
    icon: Globe,
    badgeIcon: Server,
    disciplineIcons: [Globe, Code2, Database],
    disciplineLabel: 'Web · Server · Database',
    badgeClass: 'bg-indigo-950/50 text-indigo-300 border-[#C7D2FE]',
    iconBoxClass: 'bg-indigo-950/50 text-indigo-300 border-[#C7D2FE]',
    accentLineClass: 'bg-[#4F46E5]',
    softSurfaceClass: 'bg-[#18243A]',
  },
  'ai-resources-and-automation': {
    accentName: 'cyan',
    icon: AiWorkflowMarkIcon,
    badgeIcon: Workflow,
    disciplineIcons: [BrainCircuit, Workflow, Cpu],
    disciplineLabel: 'Prompts · Agents · Flows',
    badgeClass: 'bg-sky-950/50 text-sky-300 border-[#BAE6FD]',
    iconBoxClass: 'bg-sky-950/50 text-sky-300 border-[#BAE6FD]',
    accentLineClass: 'bg-[#0EA5E9]',
    softSurfaceClass: 'bg-[#18243A]',
  },
  'digital-marketing': {
    accentName: 'slate-blue',
    icon: Megaphone,
    badgeIcon: Megaphone,
    disciplineIcons: [Megaphone, Target, TrendingUp],
    disciplineLabel: 'Campaigns · Analytics · ROI',
    badgeClass: 'bg-[#18243A] text-[#F1F5F9] border-[#CBD5E1]',
    iconBoxClass: 'bg-[#18243A] text-[#60A5FA] border-[#BFDBFE]',
    accentLineClass: 'bg-[#2563EB]',
    softSurfaceClass: 'bg-[#18243A]',
  },
  'audio-and-video': {
    accentName: 'slate-sky',
    icon: AudioStudioMarkIcon,
    badgeIcon: Clapperboard,
    disciplineIcons: [Headphones, Music, Clapperboard],
    disciplineLabel: 'Audio · LUTs · Motion',
    badgeClass: 'bg-[#18243A] text-[#F1F5F9] border-[#D5DEE8]',
    iconBoxClass: 'bg-[#18243A] text-sky-300 border-[#BAE6FD]',
    accentLineClass: 'bg-[#0EA5E9]',
    softSurfaceClass: 'bg-[#18243A]',
  },
  'music-and-audio': {
    accentName: 'slate-sky',
    icon: AudioStudioMarkIcon,
    badgeIcon: Headphones,
    disciplineIcons: [Headphones, Music, Mic],
    disciplineLabel: 'Stems · WAV · Sound FX',
    badgeClass: 'bg-[#18243A] text-sky-300 border-[#BAE6FD]',
    iconBoxClass: 'bg-[#18243A] text-sky-300 border-[#BAE6FD]',
    accentLineClass: 'bg-[#0EA5E9]',
    softSurfaceClass: 'bg-[#18243A]',
  },
  'video-and-animation': {
    accentName: 'slate-sky',
    icon: Clapperboard,
    badgeIcon: Video,
    disciplineIcons: [Clapperboard, Video, Layers],
    disciplineLabel: 'LUTs · Timeline · Keyframes',
    badgeClass: 'bg-[#18243A] text-[#F1F5F9] border-[#D5DEE8]',
    iconBoxClass: 'bg-[#18243A] text-sky-300 border-[#BAE6FD]',
    accentLineClass: 'bg-[#0EA5E9]',
    softSurfaceClass: 'bg-[#18243A]',
  },
  'business-resources': {
    accentName: 'teal',
    icon: BarChart3,
    badgeIcon: Briefcase,
    disciplineIcons: [BarChart3, Landmark, Receipt],
    disciplineLabel: 'Finance · Decks · Invoices',
    badgeClass: 'bg-teal-950/50 text-teal-300 border-teal-200',
    iconBoxClass: 'bg-teal-950/50 text-teal-300 border-teal-200',
    accentLineClass: 'bg-[#0D9488]',
    softSurfaceClass: 'bg-[#18243A]',
  },
};

const DEFAULT_THEME = {
  accentName: 'blue',
  icon: FolderTree,
  badgeIcon: FolderTree,
  disciplineIcons: [FolderTree],
  disciplineLabel: 'Digital Collection',
  badgeClass: 'bg-[#18243A] text-[#93C5FD] border-[#D5DEE8]',
  iconBoxClass: 'bg-[#18243A] text-[#60A5FA] border-[#D5DEE8]',
  accentLineClass: 'bg-[#2563EB]',
  softSurfaceClass: 'bg-[#18243A]',
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
    iconBoxClass: 'bg-teal-950/50 text-teal-300 border-teal-200',
    avatarBorderClass: 'border-[#99F6E4]',
    accentLineClass: 'bg-[#0D9488]',
    bannerBgClass: 'bg-gradient-to-br from-[#0D1424] via-[#111C30] to-[#18243A]',
    pillClass: 'bg-[#111C30]/95 text-teal-300 border-[#CCFBF1]',
  },
  development: {
    key: 'development',
    icon: Terminal,
    secondaryIcon: Code2,
    accentIcon: PythonBrandIcon,
    shortTag: 'Code & Dev Starters',
    iconBoxClass: 'bg-indigo-950/50 text-[#93C5FD] border-[#C7D2FE]',
    avatarBorderClass: 'border-[#C7D2FE]',
    accentLineClass: 'bg-[#4F46E5]',
    bannerBgClass: 'bg-gradient-to-br from-[#0D1424] via-[#111C30] to-[#18243A]',
    pillClass: 'bg-[#111C30]/95 text-indigo-300 border-[#C7D2FE]',
  },
  design: {
    key: 'design',
    icon: DesignVectorMarkIcon,
    secondaryIcon: PenTool,
    accentIcon: Palette,
    shortTag: 'Design & UI Kits',
    iconBoxClass: 'bg-violet-950/50 text-violet-300 border-[#DDD6FE]',
    avatarBorderClass: 'border-[#DDD6FE]',
    accentLineClass: 'bg-[#7C3AED]',
    bannerBgClass: 'bg-gradient-to-br from-[#0D1424] via-[#111C30] to-[#18243A]',
    pillClass: 'bg-[#111C30]/95 text-violet-300 border-[#DDD6FE]',
  },
  education: {
    key: 'education',
    icon: GraduationCap,
    secondaryIcon: MathEducationMarkIcon,
    accentIcon: Calculator,
    shortTag: 'Guides & Learning',
    iconBoxClass: 'bg-emerald-950/50 text-emerald-300 border-emerald-200',
    avatarBorderClass: 'border-[#A7F3D0]',
    accentLineClass: 'bg-[#16A34A]',
    bannerBgClass: 'bg-gradient-to-br from-[#0D1424] via-[#111C30] to-[#18243A]',
    pillClass: 'bg-[#111C30]/95 text-emerald-300 border-emerald-200',
  },
  ai: {
    key: 'ai',
    icon: AiWorkflowMarkIcon,
    secondaryIcon: BrainCircuit,
    accentIcon: Workflow,
    shortTag: 'AI & Automation',
    iconBoxClass: 'bg-sky-950/50 text-sky-300 border-[#BAE6FD]',
    avatarBorderClass: 'border-[#BAE6FD]',
    accentLineClass: 'bg-[#0EA5E9]',
    bannerBgClass: 'bg-gradient-to-br from-[#0D1424] via-[#111C30] to-[#18243A]',
    pillClass: 'bg-[#111C30]/95 text-sky-300 border-[#BAE6FD]',
  },
  music: {
    key: 'music',
    icon: AudioStudioMarkIcon,
    secondaryIcon: Headphones,
    accentIcon: Music,
    shortTag: 'Audio & Production',
    iconBoxClass: 'bg-[#18243A] text-sky-300 border-[#BAE6FD]',
    avatarBorderClass: 'border-[#BAE6FD]',
    accentLineClass: 'bg-[#0284C7]',
    bannerBgClass: 'bg-gradient-to-br from-[#0D1424] via-[#111C30] to-[#18243A]',
    pillClass: 'bg-[#111C30]/95 text-sky-300 border-[#BAE6FD]',
  },
  marketing: {
    key: 'marketing',
    icon: Megaphone,
    secondaryIcon: Target,
    accentIcon: TrendingUp,
    shortTag: 'Growth & Marketing',
    iconBoxClass: 'bg-[#18243A] text-[#93C5FD] border-[#BFDBFE]',
    avatarBorderClass: 'border-[#BFDBFE]',
    accentLineClass: 'bg-[#2563EB]',
    bannerBgClass: 'bg-gradient-to-br from-[#0D1424] via-[#111C30] to-[#18243A]',
    pillClass: 'bg-[#111C30]/95 text-[#93C5FD] border-[#BFDBFE]',
  },
  default: {
    key: 'default',
    icon: Store,
    secondaryIcon: Layers,
    accentIcon: FolderTree,
    shortTag: 'Verified Storefront',
    iconBoxClass: 'bg-[#18243A] text-[#60A5FA] border-[#BFDBFE]',
    avatarBorderClass: 'border-[#BFDBFE]',
    accentLineClass: 'bg-[#2563EB]',
    bannerBgClass: 'bg-gradient-to-br from-[#0D1424] via-[#111C30] to-[#18243A]',
    pillClass: 'bg-[#111C30]/95 text-[#93C5FD] border-[#BFDBFE]',
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

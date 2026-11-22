const esc = (value) =>
  String(value ?? '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
    .replace(/'/g, '&#39;');

const truncate = (value, maxLen = 36) => {
  const s = String(value ?? '').trim();
  if (s.length <= maxLen) return s;
  return `${s.slice(0, maxLen - 1)}…`;
};

const toSvgDataUri = (innerSvg, bgTop = '#EAF4FC', bgBottom = '#DCE6EF', dotColor = '#2563EB') => {
  const svg = `<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 640 400" width="640" height="400">
  <defs>
    <linearGradient id="bg" x1="0" y1="0" x2="1" y2="1">
      <stop offset="0%" stop-color="${bgTop}"/>
      <stop offset="100%" stop-color="${bgBottom}"/>
    </linearGradient>
    <pattern id="dots" width="24" height="24" patternUnits="userSpaceOnUse">
      <circle cx="12" cy="12" r="1.2" fill="${dotColor}" fill-opacity="0.12"/>
    </pattern>
  </defs>
  <rect width="640" height="400" fill="url(#bg)"/>
  <rect width="640" height="400" fill="url(#dots)"/>
  ${innerSvg}
</svg>`;
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(svg)}`;
};

const PYTHON_EMBLEM = (x, y, scale = 1) => `
  <g transform="translate(${x},${y}) scale(${scale})">
    <path d="M19.8 2c-7.8 0-7.3 3.4-7.3 3.4v3.5h7.4v1.1H9.6S4.6 9.4 4.6 17.3c0 7.9 4.3 7.6 4.3 7.6h2.6v-3.6s-.1-4.4 4.3-4.4h7.4s4.1.1 4.1-4V6.2S27.9 2 19.8 2Zm-4 2.4a1.4 1.4 0 1 1 0 2.8 1.4 1.4 0 0 1 0-2.8Z" fill="#2563EB"/>
    <path d="M20.2 33.6c7.8 0 7.3-3.4 7.3-3.4v-3.5h-7.4v-1.1h10.3s5 .6 5-7.3c0-7.9-4.3-7.6-4.3-7.6h-2.6v3.6s.1 4.4-4.3 4.4h-7.4s-4.1-.1-4.1 4v6.7s-.6 4.2 7.5 4.2Zm4-2.4a1.4 1.4 0 1 1 0-2.8 1.4 1.4 0 0 1 0 2.8Z" fill="#D97706"/>
  </g>`;

const SLUG_TO_SCENE = {
  'demo-modern-social-media-kit': 'design_social',
  'demo-minimal-portfolio-ui-kit': 'design_figma',
  'demo-creative-icon-collection': 'design_icons',
  'demo-brand-identity-starter-pack': 'design_brand',

  'demo-ultimate-notion-productivity-dashboard': 'notion',
  'demo-professional-resume-bundle': 'resume',
  'demo-personal-finance-tracker': 'spreadsheet',
  'demo-weekly-planner-collection': 'planner',

  'demo-python-programming-starter-guide': 'python_guide',
  'demo-data-structures-algorithms-notes': 'dsa',
  'demo-computer-networks-study-handbook': 'networks',
  'demo-mathematics-formula-reference': 'math',

  'demo-modern-portfolio-website-template': 'portfolio_web',
  'demo-react-component-starter-kit': 'react',
  'demo-python-automation-toolkit': 'python_cli',
  'demo-rest-api-starter-project': 'rest_api',

  'demo-ai-productivity-prompt-library': 'ai_prompts',
  'demo-ai-content-creation-toolkit': 'ai_content',
  'demo-research-assistant-prompt-pack': 'ai_research',
  'demo-automation-workflow-blueprint': 'ai_workflow',

  'demo-instagram-content-calendar': 'marketing_calendar',
  'demo-digital-marketing-strategy-workbook': 'marketing_strategy',
  'demo-social-media-analytics-dashboard': 'marketing_analytics',
  'demo-small-business-marketing-kit': 'marketing_kit',

  'demo-cinematic-video-editing-presets': 'video_lut',
  'demo-royalty-free-sound-effects-pack': 'audio_sfx',
  'demo-motion-graphics-starter-pack': 'video_motion',
  'demo-video-creator-resource-bundle': 'video_creator',

  'demo-startup-pitch-deck-template': 'biz_pitch_deck',
  'demo-business-plan-workbook': 'biz_plan',
  'demo-startup-financial-model': 'biz_financial_model',
  'demo-business-proposal-template': 'biz_proposal',
};

function detectSceneKey(product) {
  const slug = (product?.slug || product?.product_slug || '').toLowerCase();
  if (SLUG_TO_SCENE[slug]) return SLUG_TO_SCENE[slug];

  const text = `${slug} ${product?.name || product?.product_name || ''} ${product?.product_type || ''}`.toLowerCase();
  if (text.includes('python')) return text.includes('guide') || text.includes('ebook') ? 'python_guide' : 'python_cli';
  if (text.includes('math') || text.includes('calculus') || text.includes('algebra')) return 'math';
  if (text.includes('react')) return 'react';
  if (text.includes('api') || text.includes('backend')) return 'rest_api';
  if (text.includes('guitar') || text.includes('sound') || text.includes('audio') || text.includes('music')) return 'audio_sfx';
  if (text.includes('video') || text.includes('film') || text.includes('lut')) return 'video_lut';
  if (text.includes('motion') || text.includes('animation')) return 'video_motion';
  if (text.includes('invoice') || text.includes('proposal')) return 'biz_proposal';
  if (text.includes('financial') || text.includes('p&l') || text.includes('forecast')) return 'biz_financial_model';
  if (text.includes('pitch')) return 'biz_pitch_deck';
  if (text.includes('spreadsheet') || text.includes('finance') || text.includes('budget')) return 'spreadsheet';
  if (text.includes('resume')) return 'resume';
  if (text.includes('planner')) return 'planner';
  if (text.includes('figma') || text.includes('ui kit')) return 'design_figma';
  if (text.includes('icon')) return 'design_icons';
  if (text.includes('brand')) return 'design_brand';
  if (text.includes('marketing') || text.includes('campaign')) return 'marketing_analytics';
  if (text.includes('ai') || text.includes('prompt') || text.includes('workflow')) return 'ai_workflow';

  const catSlug = (product?.category?.slug || '').toLowerCase();
  if (catSlug.includes('design')) return 'design_social';
  if (catSlug.includes('document')) return 'notion';
  if (catSlug.includes('education') || catSlug.includes('math')) return 'math';
  if (catSlug.includes('development') || catSlug.includes('tech') || catSlug.includes('web')) return 'portfolio_web';
  if (catSlug.includes('ai')) return 'ai_prompts';
  if (catSlug.includes('marketing')) return 'marketing_analytics';
  if (catSlug.includes('audio') || catSlug.includes('video') || catSlug.includes('music')) return 'video_creator';
  if (catSlug.includes('business')) return 'biz_plan';
  return 'portfolio_web';
}

function renderScene(scene, product) {
  const fontSans = "system-ui, -apple-system, 'Segoe UI', sans-serif";
  const fontMono = "'Consolas', 'Courier New', monospace";
  const titleLabel = esc(truncate(product?.name || product?.product_name || 'Digital Resource', 30));

  switch (scene) {
    case 'python_guide':
    case 'python_cli': {
      const isGuide = scene === 'python_guide';
      return toSvgDataUri(`
        <rect x="44" y="34" width="552" height="332" rx="18" fill="#0F172A" stroke="#334155" stroke-width="2"/>
        <rect x="44" y="34" width="552" height="42" rx="18" fill="#1E293B"/>
        <rect x="44" y="60" width="552" height="16" fill="#1E293B"/>
        <circle cx="72" cy="55" r="5.5" fill="#EF4444"/>
        <circle cx="92" cy="55" r="5.5" fill="#F59E0B"/>
        <circle cx="112" cy="55" r="5.5" fill="#16A34A"/>
        <text x="140" y="59" font-family="${fontMono}" font-size="13" fill="#94A3B8">${isGuide ? 'starter_guide.py — Chapter 04' : 'toolkit_cli.py — Python 3.12'}</text>
        <rect x="454" y="42" width="124" height="24" rx="12" fill="#2563EB" fill-opacity="0.22" stroke="#3B82F6" stroke-width="1"/>
        <text x="516" y="58" text-anchor="middle" font-family="${fontSans}" font-size="11" font-weight="600" fill="#93C5FD">${isGuide ? 'Study PDF' : 'CLI Script'}</text>

        <text x="68" y="114" font-family="${fontMono}" font-size="13" fill="#475569">01</text>
        <text x="102" y="114" font-family="${fontMono}" font-size="14" fill="#60A5FA">def <tspan fill="#F8FAFC">${isGuide ? 'binary_search' : 'normalize_batch'}</tspan>(items):</text>
        <text x="68" y="142" font-family="${fontMono}" font-size="13" fill="#475569">02</text>
        <text x="122" y="142" font-family="${fontMono}" font-size="14" fill="#94A3B8">"""${isGuide ? 'Clean documented Python walkthrough' : 'Idempotent CSV &amp; index helper'}"""</text>
        <text x="68" y="170" font-family="${fontMono}" font-size="13" fill="#475569">03</text>
        <text x="122" y="170" font-family="${fontMono}" font-size="14" fill="#38BDF8">cleaned = [x.strip() <tspan fill="#C084FC">for</tspan> x <tspan fill="#C084FC">in</tspan> items]</text>
        <text x="68" y="198" font-family="${fontMono}" font-size="13" fill="#475569">04</text>
        <text x="122" y="198" font-family="${fontMono}" font-size="14" fill="#34D399">return <tspan fill="#FBBF24">sorted</tspan>(cleaned)</text>

        <rect x="66" y="236" width="356" height="104" rx="12" fill="#1E293B" stroke="#334155"/>
        <text x="86" y="264" font-family="${fontMono}" font-size="13" fill="#94A3B8">$ python ${isGuide ? 'examples/ch04.py' : 'csv_normalizer.py --clean'}</text>
        <text x="86" y="290" font-family="${fontMono}" font-size="13" fill="#34D399">OK  Processed 1,420 records (0 errors)</text>
        <text x="86" y="316" font-family="${fontMono}" font-size="12" fill="#60A5FA">Standard Library Only · Ready to Run</text>

        <rect x="444" y="218" width="128" height="122" rx="16" fill="#FFFFFF" stroke="#D5DEE8" stroke-width="1.5"/>
        ${PYTHON_EMBLEM(484, 240, 1.25)}
        <text x="508" y="310" text-anchor="middle" font-family="${fontSans}" font-size="13" font-weight="700" fill="#263445">Python 3</text>
        <text x="508" y="328" text-anchor="middle" font-family="${fontSans}" font-size="11" fill="#64748B">${isGuide ? 'Reference Guide' : 'Automation Kit'}</text>
      `, '#E8F2FC', '#DCE6EF', '#1D4ED8');
    }

    case 'math':
      return toSvgDataUri(`
        <rect x="52" y="34" width="536" height="332" rx="16" fill="#FFFFFF" stroke="#D5DEE8" stroke-width="2"/>
        <line x1="122" y1="34" x2="122" y2="366" stroke="#FCA5A5" stroke-width="1.5"/>
        <line x1="52" y1="92" x2="588" y2="92" stroke="#E2E8F0" stroke-width="1"/>
        <line x1="52" y1="138" x2="588" y2="138" stroke="#E2E8F0" stroke-width="1"/>
        <line x1="52" y1="184" x2="588" y2="184" stroke="#E2E8F0" stroke-width="1"/>
        <line x1="52" y1="230" x2="588" y2="230" stroke="#E2E8F0" stroke-width="1"/>
        <line x1="52" y1="276" x2="588" y2="276" stroke="#E2E8F0" stroke-width="1"/>
        <line x1="52" y1="322" x2="588" y2="322" stroke="#E2E8F0" stroke-width="1"/>

        <circle cx="86" cy="115" r="7" fill="#EAF4FC" stroke="#93C5FD"/>
        <circle cx="86" cy="207" r="7" fill="#EAF4FC" stroke="#93C5FD"/>
        <circle cx="86" cy="299" r="7" fill="#EAF4FC" stroke="#93C5FD"/>

        <rect x="142" y="50" width="166" height="26" rx="13" fill="#ECFDF5" stroke="#A7F3D0"/>
        <text x="225" y="67" text-anchor="middle" font-family="${fontSans}" font-size="12" font-weight="700" fill="#15803D">Mathematics Formula Sheet</text>

        <text x="146" y="124" font-family="Georgia, serif" font-size="22" font-weight="700" fill="#263445">&#x222B; f(x) dx = F(b) &#x2212; F(a)</text>
        <text x="146" y="170" font-family="Georgia, serif" font-size="20" fill="#2563EB">&#x2211; (x&#x1D62; &#x2212; &#x03BC;)&#x00B2; / n  =  &#x03C3;&#x00B2;</text>
        <text x="146" y="216" font-family="Georgia, serif" font-size="19" fill="#263445">a&#x00B2; + b&#x00B2; = c&#x00B2;   &#x00B7;   e^(i&#x03C0;) + 1 = 0</text>
        <text x="146" y="262" font-family="Georgia, serif" font-size="18" fill="#475569">det(A &#x2212; &#x03BB;I) = 0   &#x00B7;   P(A|B)</text>

        <rect x="404" y="114" width="162" height="162" rx="14" fill="#F8FAFC" stroke="#D5DEE8" stroke-width="1.5"/>
        <line x1="422" y1="246" x2="548" y2="246" stroke="#64748B" stroke-width="1.5"/>
        <line x1="485" y1="132" x2="485" y2="262" stroke="#64748B" stroke-width="1.5"/>
        <path d="M432 146 Q485 270 538 146" fill="none" stroke="#2563EB" stroke-width="3" stroke-linecap="round"/>
        <circle cx="485" cy="208" r="4" fill="#16A34A"/>
        <text x="485" y="266" text-anchor="middle" font-family="${fontMono}" font-size="11" fill="#2563EB">f(x) = x&#x00B2;</text>

        <rect x="142" y="294" width="424" height="44" rx="10" fill="#EAF4FC" stroke="#BFDBFE"/>
        <text x="162" y="321" font-family="${fontSans}" font-size="13" font-weight="600" fill="#1D4ED8">Algebra &#x00B7; Calculus &#x00B7; Linear Algebra &#x00B7; Probability</text>
      `, '#ECFDF5', '#EAF4FC', '#16A34A');

    case 'dsa':
      return toSvgDataUri(`
        <rect x="48" y="36" width="544" height="328" rx="18" fill="#FFFFFF" stroke="#D5DEE8" stroke-width="2"/>
        <rect x="74" y="58" width="188" height="26" rx="13" fill="#ECFDF5" stroke="#A7F3D0"/>
        <text x="168" y="75" text-anchor="middle" font-family="${fontSans}" font-size="12" font-weight="700" fill="#15803D">Binary Tree &amp; Graph Patterns</text>

        <line x1="210" y1="132" x2="140" y2="202" stroke="#93C5FD" stroke-width="3"/>
        <line x1="210" y1="132" x2="280" y2="202" stroke="#93C5FD" stroke-width="3"/>
        <line x1="140" y1="202" x2="100" y2="276" stroke="#CBD5E1" stroke-width="2.5"/>
        <line x1="140" y1="202" x2="178" y2="276" stroke="#CBD5E1" stroke-width="2.5"/>
        <line x1="280" y1="202" x2="246" y2="276" stroke="#93C5FD" stroke-width="2.5"/>
        <line x1="280" y1="202" x2="318" y2="276" stroke="#CBD5E1" stroke-width="2.5"/>

        <circle cx="210" cy="132" r="22" fill="#2563EB"/>
        <text x="210" y="138" text-anchor="middle" font-family="${fontMono}" font-size="14" font-weight="700" fill="#FFFFFF">42</text>
        <circle cx="140" cy="202" r="20" fill="#EAF4FC" stroke="#2563EB" stroke-width="2"/>
        <text x="140" y="207" text-anchor="middle" font-family="${fontMono}" font-size="13" font-weight="700" fill="#1D4ED8">18</text>
        <circle cx="280" cy="202" r="20" fill="#EAF4FC" stroke="#2563EB" stroke-width="2"/>
        <text x="280" y="207" text-anchor="middle" font-family="${fontMono}" font-size="13" font-weight="700" fill="#1D4ED8">67</text>

        <circle cx="100" cy="276" r="17" fill="#F8FAFC" stroke="#CBD5E1" stroke-width="2"/>
        <text x="100" y="281" text-anchor="middle" font-family="${fontMono}" font-size="12" fill="#263445">11</text>
        <circle cx="178" cy="276" r="17" fill="#F8FAFC" stroke="#CBD5E1" stroke-width="2"/>
        <text x="178" y="281" text-anchor="middle" font-family="${fontMono}" font-size="12" fill="#263445">29</text>
        <circle cx="246" cy="276" r="17" fill="#ECFDF5" stroke="#16A34A" stroke-width="2"/>
        <text x="246" y="281" text-anchor="middle" font-family="${fontMono}" font-size="12" font-weight="700" fill="#15803D">54</text>
        <circle cx="318" cy="276" r="17" fill="#F8FAFC" stroke="#CBD5E1" stroke-width="2"/>
        <text x="318" y="281" text-anchor="middle" font-family="${fontMono}" font-size="12" fill="#263445">83</text>

        <rect x="366" y="96" width="198" height="238" rx="14" fill="#F8FAFC" stroke="#D5DEE8" stroke-width="1.5"/>
        <text x="386" y="126" font-family="${fontSans}" font-size="13" font-weight="700" fill="#263445">Big-O Complexity</text>
        <line x1="392" y1="248" x2="540" y2="248" stroke="#94A3B8" stroke-width="1.5"/>
        <line x1="392" y1="146" x2="392" y2="248" stroke="#94A3B8" stroke-width="1.5"/>
        <path d="M394 242 Q442 224 534 152" fill="none" stroke="#DC2626" stroke-width="2.5"/>
        <path d="M394 242 Q458 232 534 214" fill="none" stroke="#16A34A" stroke-width="2.5"/>
        <text x="392" y="278" font-family="${fontMono}" font-size="12" fill="#15803D">O(log n)  Fast</text>
        <text x="392" y="302" font-family="${fontMono}" font-size="12" fill="#2563EB">O(n log n) MergeSort</text>
      `, '#EAF4FC', '#DCE6EF', '#16A34A');

    case 'networks':
      return toSvgDataUri(`
        <rect x="48" y="36" width="544" height="328" rx="18" fill="#FFFFFF" stroke="#D5DEE8" stroke-width="2"/>
        <text x="76" y="72" font-family="${fontSans}" font-size="15" font-weight="700" fill="#263445">OSI &amp; TCP/IP Protocol Architecture</text>
        <rect x="76" y="94" width="236" height="44" rx="10" fill="#EAF4FC" stroke="#BFDBFE"/>
        <text x="94" y="121" font-family="${fontMono}" font-size="13" font-weight="700" fill="#1D4ED8">L7  HTTP/2 &#x00B7; DNS &#x00B7; TLS 1.3</text>
        <rect x="76" y="150" width="236" height="44" rx="10" fill="#EDF5FC" stroke="#93C5FD"/>
        <text x="94" y="177" font-family="${fontMono}" font-size="13" font-weight="700" fill="#2563EB">L4  TCP / UDP Segments</text>
        <rect x="76" y="206" width="236" height="44" rx="10" fill="#F8FAFC" stroke="#D5DEE8"/>
        <text x="94" y="233" font-family="${fontMono}" font-size="13" font-weight="700" fill="#263445">L3  IPv4 &#x00B7; Routing &#x00B7; CIDR</text>
        <rect x="76" y="262" width="236" height="44" rx="10" fill="#ECFDF5" stroke="#A7F3D0"/>
        <text x="94" y="289" font-family="${fontMono}" font-size="13" font-weight="700" fill="#15803D">L2  Frames &#x00B7; ARP &#x00B7; MAC</text>

        <rect x="346" y="94" width="218" height="212" rx="14" fill="#0F172A"/>
        <text x="366" y="124" font-family="${fontMono}" font-size="12" fill="#94A3B8">TCP 3-Way Handshake</text>
        <line x1="376" y1="154" x2="534" y2="176" stroke="#38BDF8" stroke-width="2.5"/>
        <text x="454" y="152" text-anchor="middle" font-family="${fontMono}" font-size="11" fill="#38BDF8">SYN &#x2192;</text>
        <line x1="534" y1="198" x2="376" y2="222" stroke="#34D399" stroke-width="2.5"/>
        <text x="454" y="198" text-anchor="middle" font-family="${fontMono}" font-size="11" fill="#34D399">&#x2190; SYN-ACK</text>
        <line x1="376" y1="244" x2="534" y2="266" stroke="#60A5FA" stroke-width="2.5"/>
        <text x="454" y="246" text-anchor="middle" font-family="${fontMono}" font-size="11" fill="#93C5FD">ACK &#x2192; 200 OK</text>
      `, '#EAF4FC', '#DCE6EF', '#0284C7');

    case 'react':
      return toSvgDataUri(`
        <rect x="46" y="34" width="548" height="332" rx="18" fill="#0F172A" stroke="#334155" stroke-width="2"/>
        <g transform="translate(110,120)">
          <circle cx="0" cy="0" r="8" fill="#38BDF8"/>
          <ellipse cx="0" cy="0" rx="44" ry="17" fill="none" stroke="#38BDF8" stroke-width="2.5"/>
          <ellipse cx="0" cy="0" rx="44" ry="17" fill="none" stroke="#38BDF8" stroke-width="2.5" transform="rotate(60)"/>
          <ellipse cx="0" cy="0" rx="44" ry="17" fill="none" stroke="#38BDF8" stroke-width="2.5" transform="rotate(120)"/>
        </g>
        <text x="176" y="114" font-family="${fontSans}" font-size="20" font-weight="700" fill="#F8FAFC">React UI Kit</text>
        <text x="176" y="138" font-family="${fontMono}" font-size="13" fill="#94A3B8">Hooks &#x00B7; Accessible JSX &#x00B7; Tokens</text>
        <rect x="68" y="184" width="248" height="148" rx="12" fill="#1E293B" stroke="#334155"/>
        <text x="86" y="216" font-family="${fontMono}" font-size="13" fill="#C084FC">&lt;DataCard</text>
        <text x="102" y="242" font-family="${fontMono}" font-size="13" fill="#93C5FD">variant=<tspan fill="#34D399">"elevated"</tspan></text>
        <text x="102" y="268" font-family="${fontMono}" font-size="13" fill="#93C5FD">action=<tspan fill="#FBBF24">{onSelect}</tspan></text>
        <text x="86" y="294" font-family="${fontMono}" font-size="13" fill="#C084FC">/&gt;</text>

        <rect x="336" y="64" width="234" height="270" rx="16" fill="#FFFFFF" stroke="#D5DEE8" stroke-width="1.5"/>
        <rect x="358" y="88" width="90" height="22" rx="11" fill="#EAF4FC"/>
        <text x="403" y="103" text-anchor="middle" font-family="${fontSans}" font-size="11" font-weight="700" fill="#2563EB">Preview</text>
        <rect x="358" y="128" width="190" height="72" rx="10" fill="#F8FAFC" stroke="#D5DEE8"/>
        <circle cx="388" cy="164" r="14" fill="#2563EB"/>
        <rect x="414" y="150" width="112" height="10" rx="5" fill="#263445"/>
        <rect x="414" y="168" width="76" height="8" rx="4" fill="#94A3B8"/>
        <rect x="358" y="218" width="190" height="38" rx="10" fill="#2563EB"/>
        <text x="453" y="242" text-anchor="middle" font-family="${fontSans}" font-size="13" font-weight="600" fill="#FFFFFF">Primary Action</text>
        <rect x="358" y="270" width="190" height="38" rx="10" fill="#EDF5FC" stroke="#BFDBFE"/>
        <text x="453" y="294" text-anchor="middle" font-family="${fontSans}" font-size="13" font-weight="600" fill="#1D4ED8">Secondary Button</text>
      `, '#EEF2FF', '#DCE6EF', '#4F46E5');

    case 'portfolio_web':
      return toSvgDataUri(`
        <rect x="44" y="42" width="424" height="312" rx="16" fill="#FFFFFF" stroke="#D5DEE8" stroke-width="2"/>
        <rect x="44" y="42" width="424" height="36" rx="16" fill="#F8FAFC"/>
        <rect x="44" y="64" width="424" height="14" fill="#F8FAFC"/>
        <line x1="44" y1="78" x2="468" y2="78" stroke="#E5E7EB"/>
        <circle cx="66" cy="60" r="4.5" fill="#CBD5E1"/>
        <circle cx="82" cy="60" r="4.5" fill="#CBD5E1"/>
        <circle cx="98" cy="60" r="4.5" fill="#CBD5E1"/>
        <rect x="122" y="51" width="210" height="18" rx="9" fill="#EAF4FC"/>
        <text x="227" y="64" text-anchor="middle" font-family="${fontMono}" font-size="10" fill="#2563EB">portfolio-studio.dev</text>

        <rect x="70" y="102" width="96" height="18" rx="9" fill="#EAF4FC"/>
        <text x="118" y="114" text-anchor="middle" font-family="${fontSans}" font-size="10" font-weight="700" fill="#1D4ED8">WEB TEMPLATE</text>
        <rect x="70" y="134" width="236" height="16" rx="6" fill="#263445"/>
        <rect x="70" y="158" width="176" height="10" rx="5" fill="#94A3B8"/>
        <rect x="70" y="182" width="102" height="28" rx="8" fill="#2563EB"/>

        <rect x="70" y="232" width="112" height="96" rx="10" fill="#EAF4FC" stroke="#BFDBFE"/>
        <rect x="196" y="232" width="112" height="96" rx="10" fill="#F8FAFC" stroke="#D5DEE8"/>
        <rect x="322" y="232" width="118" height="96" rx="10" fill="#ECFDF5" stroke="#A7F3D0"/>

        <rect x="446" y="108" width="146" height="256" rx="22" fill="#263445" stroke="#475569" stroke-width="2"/>
        <rect x="456" y="126" width="126" height="220" rx="14" fill="#FFFFFF"/>
        <rect x="470" y="144" width="98" height="12" rx="6" fill="#2563EB"/>
        <rect x="470" y="166" width="84" height="8" rx="4" fill="#64748B"/>
        <rect x="470" y="190" width="98" height="60" rx="8" fill="#EAF4FC"/>
        <rect x="470" y="262" width="98" height="60" rx="8" fill="#F8FAFC" stroke="#D5DEE8"/>
      `, '#EAF4FC', '#DCE6EF', '#2563EB');

    case 'rest_api':
      return toSvgDataUri(`
        <rect x="48" y="34" width="544" height="332" rx="18" fill="#0F172A" stroke="#334155" stroke-width="2"/>
        <text x="76" y="70" font-family="${fontSans}" font-size="14" font-weight="700" fill="#F8FAFC">REST API &amp; OpenAPI Endpoints</text>
        <rect x="454" y="48" width="112" height="26" rx="13" fill="#16A34A" fill-opacity="0.2" stroke="#16A34A"/>
        <text x="510" y="65" text-anchor="middle" font-family="${fontMono}" font-size="11" font-weight="700" fill="#4ADE80">200 OK · 12ms</text>

        <rect x="74" y="96" width="492" height="46" rx="10" fill="#1E293B" stroke="#334155"/>
        <rect x="88" y="107" width="56" height="24" rx="6" fill="#2563EB"/>
        <text x="116" y="123" text-anchor="middle" font-family="${fontMono}" font-size="12" font-weight="700" fill="#FFFFFF">GET</text>
        <text x="160" y="124" font-family="${fontMono}" font-size="13" fill="#E2E8F0">/api/v1/products?category=dev</text>

        <rect x="74" y="156" width="492" height="46" rx="10" fill="#1E293B" stroke="#334155"/>
        <rect x="88" y="167" width="56" height="24" rx="6" fill="#16A34A"/>
        <text x="116" y="183" text-anchor="middle" font-family="${fontMono}" font-size="12" font-weight="700" fill="#FFFFFF">POST</text>
        <text x="160" y="184" font-family="${fontMono}" font-size="13" fill="#E2E8F0">/api/v1/orders/verify-signature</text>

        <rect x="74" y="218" width="492" height="122" rx="12" fill="#020617" stroke="#1E293B"/>
        <text x="94" y="246" font-family="${fontMono}" font-size="13" fill="#94A3B8">{</text>
        <text x="114" y="270" font-family="${fontMono}" font-size="13" fill="#60A5FA">"service": <tspan fill="#34D399">"fastapi-scaffold"</tspan>,</text>
        <text x="114" y="294" font-family="${fontMono}" font-size="13" fill="#60A5FA">"openapi": <tspan fill="#FBBF24">"3.1.0"</tspan>, "tests": <tspan fill="#34D399">"passing"</tspan></text>
        <text x="94" y="318" font-family="${fontMono}" font-size="13" fill="#94A3B8">}</text>
      `, '#EEF2FF', '#DCE6EF', '#4F46E5');

    case 'design_social':
      return toSvgDataUri(`
        <rect x="52" y="42" width="164" height="196" rx="14" fill="#FFFFFF" stroke="#D5DEE8" stroke-width="2"/>
        <rect x="66" y="56" width="136" height="104" rx="10" fill="#F3F0FF"/>
        <circle cx="134" cy="108" r="28" fill="#7C3AED"/>
        <rect x="66" y="174" width="92" height="12" rx="6" fill="#263445"/>
        <rect x="66" y="196" width="128" height="8" rx="4" fill="#94A3B8"/>

        <rect x="236" y="34" width="168" height="292" rx="16" fill="#FFFFFF" stroke="#C4B5FD" stroke-width="2"/>
        <rect x="252" y="50" width="136" height="24" rx="8" fill="#7C3AED"/>
        <text x="320" y="66" text-anchor="middle" font-family="${fontSans}" font-size="11" font-weight="700" fill="#FFFFFF">9:16 Story Frame</text>
        <rect x="252" y="88" width="136" height="148" rx="12" fill="#EAF4FC" stroke="#BFDBFE"/>
        <circle cx="320" cy="162" r="34" fill="#2563EB" fill-opacity="0.2" stroke="#2563EB" stroke-width="2"/>
        <rect x="252" y="252" width="110" height="12" rx="6" fill="#263445"/>
        <rect x="252" y="274" width="136" height="32" rx="8" fill="#7C3AED"/>

        <rect x="424" y="62" width="164" height="242" rx="14" fill="#FFFFFF" stroke="#D5DEE8" stroke-width="2"/>
        <text x="444" y="92" font-family="${fontSans}" font-size="12" font-weight="700" fill="#263445">Brand Tokens</text>
        <circle cx="460" cy="128" r="14" fill="#7C3AED"/>
        <circle cx="496" cy="128" r="14" fill="#2563EB"/>
        <circle cx="532" cy="128" r="14" fill="#0EA5E9"/>
        <circle cx="568" cy="128" r="14" fill="#263445"/>
        <rect x="444" y="164" width="124" height="118" rx="10" fill="#F8FAFC" stroke="#E5E7EB"/>
        <text x="506" y="220" text-anchor="middle" font-family="${fontSans}" font-size="22" font-weight="700" fill="#6D28D9">Aa</text>
        <text x="506" y="244" text-anchor="middle" font-family="${fontMono}" font-size="11" fill="#64748B">30 Layouts</text>
      `, '#F3F0FF', '#EAF4FC', '#7C3AED');

    case 'design_figma':
      return toSvgDataUri(`
        <rect x="44" y="34" width="552" height="332" rx="18" fill="#FFFFFF" stroke="#D5DEE8" stroke-width="2"/>
        <rect x="44" y="34" width="122" height="332" rx="18" fill="#F8FAFC"/>
        <rect x="148" y="34" width="18" height="332" fill="#F8FAFC"/>
        <line x1="166" y1="34" x2="166" y2="366" stroke="#E5E7EB"/>
        <text x="64" y="68" font-family="${fontSans}" font-size="12" font-weight="700" fill="#263445">Layers</text>
        <rect x="60" y="86" width="90" height="24" rx="6" fill="#EAF4FC"/>
        <text x="70" y="102" font-family="${fontSans}" font-size="11" font-weight="600" fill="#1D4ED8">Hero Frame</text>
        <text x="70" y="128" font-family="${fontSans}" font-size="11" fill="#64748B">Navbar Bar</text>
        <text x="70" y="150" font-family="${fontSans}" font-size="11" fill="#64748B">Bezier Icon</text>
        <text x="70" y="172" font-family="${fontSans}" font-size="11" fill="#64748B">Card Grid</text>

        <rect x="196" y="64" width="236" height="266" rx="14" fill="#F8FAFC" stroke="#7C3AED" stroke-width="1.75" stroke-dasharray="5 4"/>
        <rect x="218" y="88" width="192" height="96" rx="12" fill="#FFFFFF" stroke="#D5DEE8"/>
        <path d="M240 160 C272 104, 344 104, 384 156" fill="none" stroke="#7C3AED" stroke-width="3"/>
        <circle cx="240" cy="160" r="5" fill="#FFFFFF" stroke="#7C3AED" stroke-width="2"/>
        <circle cx="384" cy="156" r="5" fill="#FFFFFF" stroke="#7C3AED" stroke-width="2"/>
        <rect x="306" y="106" width="10" height="10" fill="#2563EB"/>

        <rect x="218" y="202" width="90" height="104" rx="10" fill="#FFFFFF" stroke="#D5DEE8"/>
        <rect x="320" y="202" width="90" height="104" rx="10" fill="#FFFFFF" stroke="#D5DEE8"/>

        <rect x="456" y="34" width="140" height="332" rx="18" fill="#F8FAFC"/>
        <rect x="456" y="34" width="18" height="332" fill="#F8FAFC"/>
        <line x1="456" y1="34" x2="456" y2="366" stroke="#E5E7EB"/>
        <text x="476" y="68" font-family="${fontSans}" font-size="12" font-weight="700" fill="#263445">Design Tool</text>
        <text x="476" y="100" font-family="${fontMono}" font-size="11" fill="#64748B">W: 1440  H: 900</text>
        <text x="476" y="124" font-family="${fontMono}" font-size="11" fill="#64748B">R: 16px  Auto</text>
        <rect x="476" y="150" width="98" height="30" rx="8" fill="#7C3AED"/>
        <text x="525" y="169" text-anchor="middle" font-family="${fontSans}" font-size="11" font-weight="700" fill="#FFFFFF">UI Kit Tokens</text>
      `, '#F3F0FF', '#EAF4FC', '#6D28D9');

    case 'design_icons': {
      const cells = [];
      for (let r = 0; r < 2; r += 1) {
        for (let c = 0; c < 4; c += 1) {
          const bx = 94 + c * 118;
          const by = 92 + r * 114;
          cells.push(`<rect x="${bx}" y="${by}" width="92" height="92" rx="16" fill="#FFFFFF" stroke="#D5DEE8" stroke-width="1.5"/>`);
        }
      }
      return toSvgDataUri(`
        <rect x="52" y="34" width="536" height="332" rx="18" fill="#F8FAFC" stroke="#D5DEE8" stroke-width="2"/>
        <text x="94" y="70" font-family="${fontSans}" font-size="14" font-weight="700" fill="#263445">24px Precision Vector Icon Set</text>
        ${cells.join('')}
        <circle cx="136" cy="134" r="14" fill="none" stroke="#2563EB" stroke-width="3"/>
        <line x1="146" y1="144" x2="156" y2="154" stroke="#2563EB" stroke-width="3" stroke-linecap="round"/>

        <path d="M242 152 L258 122 L274 152 Z" fill="none" stroke="#7C3AED" stroke-width="3" stroke-linejoin="round"/>
        <rect x="358" y="122" width="36" height="30" rx="5" fill="none" stroke="#0EA5E9" stroke-width="3"/>
        <path d="M478 138 L490 124 L502 138 L490 152 Z" fill="none" stroke="#16A34A" stroke-width="3"/>

        <path d="M126 254 L140 236 L154 254" fill="none" stroke="#263445" stroke-width="3" stroke-linecap="round"/>
        <rect x="242" y="238" width="32" height="28" rx="6" fill="none" stroke="#2563EB" stroke-width="3"/>
        <circle cx="376" cy="252" r="14" fill="none" stroke="#7C3AED" stroke-width="3"/>
        <path d="M476 252 H504 M490 238 V266" stroke="#0EA5E9" stroke-width="3" stroke-linecap="round"/>
      `, '#F3F0FF', '#EAF4FC', '#7C3AED');
    }

    case 'design_brand':
      return toSvgDataUri(`
        <rect x="48" y="38" width="544" height="324" rx="18" fill="#FFFFFF" stroke="#D5DEE8" stroke-width="2"/>
        <line x1="320" y1="38" x2="320" y2="362" stroke="#E5E7EB" stroke-width="1.5"/>
        <rect x="80" y="72" width="208" height="208" rx="16" fill="#F8FAFC" stroke="#DDD6FE" stroke-dasharray="5 4"/>
        <line x1="80" y1="176" x2="288" y2="176" stroke="#DDD6FE"/>
        <line x1="184" y1="72" x2="184" y2="280" stroke="#DDD6FE"/>
        <circle cx="184" cy="176" r="56" fill="#7C3AED" fill-opacity="0.14" stroke="#7C3AED" stroke-width="2.5"/>
        <polygon points="184,136 220,204 148,204" fill="#2563EB"/>
        <text x="184" y="318" text-anchor="middle" font-family="${fontMono}" font-size="12" fill="#64748B">Clearspace Grid 2x</text>

        <text x="352" y="88" font-family="${fontSans}" font-size="12" font-weight="700" fill="#6D28D9">BRAND SYSTEM</text>
        <text x="352" y="142" font-family="${fontSans}" font-size="32" font-weight="700" fill="#263445">Aa Bb</text>
        <text x="352" y="176" font-family="${fontSans}" font-size="13" fill="#64748B">Inter Bold · Regular Hierarchy</text>
        <rect x="352" y="210" width="46" height="46" rx="10" fill="#263445"/>
        <rect x="408" y="210" width="46" height="46" rx="10" fill="#2563EB"/>
        <rect x="464" y="210" width="46" height="46" rx="10" fill="#7C3AED"/>
        <rect x="520" y="210" width="46" height="46" rx="10" fill="#EAF4FC" stroke="#BFDBFE"/>
        <text x="352" y="316" font-family="${fontSans}" font-size="13" font-weight="600" fill="#263445">Guidelines PDF Workbook</text>
      `, '#F3F0FF', '#EAF4FC', '#7C3AED');

    case 'spreadsheet':
      return toSvgDataUri(`
        <rect x="46" y="36" width="548" height="328" rx="16" fill="#FFFFFF" stroke="#D5DEE8" stroke-width="2"/>
        <rect x="46" y="36" width="548" height="44" rx="16" fill="#EAF4FC"/>
        <rect x="46" y="64" width="548" height="16" fill="#EAF4FC"/>
        <text x="72" y="64" font-family="${fontSans}" font-size="14" font-weight="700" fill="#1D4ED8">Spreadsheet Budget &amp; Ledger</text>
        <rect x="460" y="45" width="112" height="26" rx="13" fill="#16A34A"/>
        <text x="516" y="62" text-anchor="middle" font-family="${fontMono}" font-size="11" font-weight="700" fill="#FFFFFF">+&#x20B9;18,400 Net</text>

        <rect x="68" y="98" width="504" height="34" fill="#F8FAFC" stroke="#E5E7EB"/>
        <text x="86" y="120" font-family="${fontMono}" font-size="12" font-weight="700" fill="#64748B">A  Category</text>
        <text x="274" y="120" font-family="${fontMono}" font-size="12" font-weight="700" fill="#64748B">B  Budget</text>
        <text x="386" y="120" font-family="${fontMono}" font-size="12" font-weight="700" fill="#64748B">C  Actual</text>
        <text x="494" y="120" font-family="${fontMono}" font-size="12" font-weight="700" fill="#64748B">Status</text>

        <line x1="68" y1="176" x2="572" y2="176" stroke="#E5E7EB"/>
        <text x="86" y="160" font-family="${fontSans}" font-size="13" fill="#263445">Monthly Income</text>
        <text x="274" y="160" font-family="${fontMono}" font-size="13" fill="#263445">&#x20B9;85,000</text>
        <text x="386" y="160" font-family="${fontMono}" font-size="13" fill="#16A34A">&#x20B9;92,000</text>
        <text x="494" y="160" font-family="${fontSans}" font-size="12" font-weight="700" fill="#16A34A">On Track</text>

        <line x1="68" y1="220" x2="572" y2="220" stroke="#E5E7EB"/>
        <text x="86" y="204" font-family="${fontSans}" font-size="13" fill="#263445">Cloud &amp; Tools</text>
        <text x="274" y="204" font-family="${fontMono}" font-size="13" fill="#263445">&#x20B9;12,000</text>
        <text x="386" y="204" font-family="${fontMono}" font-size="13" fill="#263445">&#x20B9;10,800</text>
        <text x="494" y="204" font-family="${fontSans}" font-size="12" font-weight="700" fill="#2563EB">Saved 10%</text>

        <line x1="68" y1="264" x2="572" y2="264" stroke="#E5E7EB"/>
        <text x="86" y="248" font-family="${fontSans}" font-size="13" fill="#263445">Reserve Fund</text>
        <text x="274" y="248" font-family="${fontMono}" font-size="13" fill="#263445">&#x20B9;25,000</text>
        <text x="386" y="248" font-family="${fontMono}" font-size="13" fill="#16A34A">&#x20B9;25,000</text>
        <text x="494" y="248" font-family="${fontSans}" font-size="12" font-weight="700" fill="#16A34A">100%</text>

        <rect x="68" y="286" width="504" height="54" rx="10" fill="#F8FAFC" stroke="#D5DEE8"/>
        <text x="90" y="318" font-family="${fontMono}" font-size="12" fill="#2563EB">RFC-4180 CSV &#x00B7; Excel &#x00B7; Google Sheets Compatible</text>
      `, '#EAF4FC', '#DCE6EF', '#2563EB');

    case 'notion':
    case 'planner': {
      const isPlanner = scene === 'planner';
      return toSvgDataUri(`
        <rect x="46" y="36" width="548" height="328" rx="18" fill="#FFFFFF" stroke="#D5DEE8" stroke-width="2"/>
        <text x="76" y="74" font-family="${fontSans}" font-size="15" font-weight="700" fill="#263445">${isPlanner ? 'Weekly Time-Block Schedule' : 'Sprint &amp; Task Dashboard'}</text>
        <rect x="438" y="52" width="128" height="28" rx="14" fill="#EAF4FC" stroke="#BFDBFE"/>
        <text x="502" y="70" text-anchor="middle" font-family="${fontSans}" font-size="12" font-weight="700" fill="#1D4ED8">${isPlanner ? 'Printable PDF' : 'CSV + Markdown'}</text>

        <rect x="74" y="98" width="152" height="236" rx="12" fill="#F8FAFC" stroke="#E5E7EB"/>
        <text x="92" y="124" font-family="${fontSans}" font-size="12" font-weight="700" fill="#64748B">${isPlanner ? 'MON — FOCUS' : 'TO DO'}</text>
        <rect x="88" y="142" width="124" height="44" rx="8" fill="#FFFFFF" stroke="#D5DEE8"/>
        <rect x="88" y="198" width="124" height="44" rx="8" fill="#FFFFFF" stroke="#D5DEE8"/>
        <rect x="88" y="254" width="124" height="44" rx="8" fill="#EAF4FC" stroke="#BFDBFE"/>

        <rect x="244" y="98" width="152" height="236" rx="12" fill="#EAF4FC" stroke="#BFDBFE"/>
        <text x="262" y="124" font-family="${fontSans}" font-size="12" font-weight="700" fill="#1D4ED8">${isPlanner ? 'WED — BUILD' : 'IN PROGRESS'}</text>
        <rect x="258" y="142" width="124" height="62" rx="8" fill="#FFFFFF" stroke="#93C5FD"/>
        <rect x="272" y="158" width="76" height="8" rx="4" fill="#2563EB"/>
        <rect x="272" y="176" width="94" height="7" rx="3.5" fill="#94A3B8"/>
        <rect x="258" y="218" width="124" height="62" rx="8" fill="#FFFFFF" stroke="#93C5FD"/>

        <rect x="414" y="98" width="152" height="236" rx="12" fill="#ECFDF5" stroke="#A7F3D0"/>
        <text x="432" y="124" font-family="${fontSans}" font-size="12" font-weight="700" fill="#15803D">${isPlanner ? 'FRI — REVIEW' : 'COMPLETED'}</text>
        <rect x="428" y="142" width="124" height="44" rx="8" fill="#FFFFFF" stroke="#A7F3D0"/>
        <circle cx="446" cy="164" r="8" fill="#16A34A"/>
        <rect x="462" y="160" width="72" height="8" rx="4" fill="#263445"/>
        <rect x="428" y="198" width="124" height="44" rx="8" fill="#FFFFFF" stroke="#A7F3D0"/>
        <circle cx="446" cy="220" r="8" fill="#16A34A"/>
        <rect x="462" y="216" width="64" height="8" rx="4" fill="#263445"/>
      `, '#EAF4FC', '#DCE6EF', '#2563EB');
    }

    case 'resume':
      return toSvgDataUri(`
        <rect x="74" y="34" width="234" height="332" rx="14" fill="#FFFFFF" stroke="#D5DEE8" stroke-width="2"/>
        <rect x="74" y="34" width="234" height="58" rx="14" fill="#263445"/>
        <rect x="74" y="76" width="234" height="16" fill="#263445"/>
        <rect x="96" y="50" width="120" height="12" rx="6" fill="#FFFFFF"/>
        <rect x="96" y="70" width="84" height="7" rx="3.5" fill="#93C5FD"/>
        <text x="96" y="120" font-family="${fontSans}" font-size="11" font-weight="700" fill="#2563EB">EXPERIENCE</text>
        <rect x="96" y="134" width="186" height="9" rx="4.5" fill="#263445"/>
        <rect x="96" y="152" width="166" height="7" rx="3.5" fill="#94A3B8"/>
        <rect x="96" y="168" width="174" height="7" rx="3.5" fill="#94A3B8"/>
        <text x="96" y="206" font-family="${fontSans}" font-size="11" font-weight="700" fill="#2563EB">SKILLS</text>
        <rect x="96" y="220" width="56" height="20" rx="10" fill="#EAF4FC"/>
        <rect x="160" y="220" width="56" height="20" rx="10" fill="#EAF4FC"/>
        <rect x="224" y="220" width="56" height="20" rx="10" fill="#EAF4FC"/>
        <rect x="96" y="264" width="186" height="74" rx="10" fill="#F8FAFC" stroke="#E5E7EB"/>

        <rect x="332" y="54" width="234" height="312" rx="14" fill="#FFFFFF" stroke="#BFDBFE" stroke-width="2"/>
        <rect x="356" y="80" width="110" height="24" rx="12" fill="#EAF4FC"/>
        <text x="411" y="96" text-anchor="middle" font-family="${fontSans}" font-size="11" font-weight="700" fill="#1D4ED8">ATS-Friendly</text>
        <text x="356" y="132" font-family="${fontSans}" font-size="16" font-weight="700" fill="#263445">Cover Letter</text>
        <rect x="356" y="150" width="182" height="8" rx="4" fill="#CBD5E1"/>
        <rect x="356" y="170" width="174" height="8" rx="4" fill="#CBD5E1"/>
        <rect x="356" y="190" width="186" height="8" rx="4" fill="#CBD5E1"/>
        <rect x="356" y="210" width="142" height="8" rx="4" fill="#CBD5E1"/>
        <rect x="356" y="254" width="116" height="36" rx="10" fill="#2563EB"/>
        <text x="414" y="277" text-anchor="middle" font-family="${fontSans}" font-size="12" font-weight="600" fill="#FFFFFF">Resume Bundle</text>
      `, '#EAF4FC', '#DCE6EF', '#2563EB');

    case 'ai_prompts':
      return toSvgDataUri(`
        <rect x="46" y="34" width="548" height="332" rx="18" fill="#0F172A" stroke="#334155" stroke-width="2"/>
        <rect x="72" y="54" width="224" height="28" rx="14" fill="#0EA5E9" fill-opacity="0.18" stroke="#38BDF8"/>
        <text x="184" y="72" text-anchor="middle" font-family="${fontSans}" font-size="12" font-weight="700" fill="#7DD3FC">JSON Prompt Architecture</text>

        <rect x="72" y="98" width="318" height="242" rx="12" fill="#1E293B" stroke="#334155"/>
        <text x="92" y="130" font-family="${fontMono}" font-size="13" fill="#94A3B8">{</text>
        <text x="110" y="156" font-family="${fontMono}" font-size="13" fill="#60A5FA">"role": <tspan fill="#34D399">"systems_architect"</tspan>,</text>
        <text x="110" y="182" font-family="${fontMono}" font-size="13" fill="#60A5FA">"task": <tspan fill="#FBBF24">"audit_spec"</tspan>,</text>
        <text x="110" y="208" font-family="${fontMono}" font-size="13" fill="#60A5FA">"vars": <tspan fill="#E2E8F0">["{{context}}", "{{goal}}"]</tspan>,</text>
        <text x="110" y="234" font-family="${fontMono}" font-size="13" fill="#60A5FA">"rubric": <tspan fill="#34D399">"strict_grounded"</tspan></text>
        <text x="92" y="260" font-family="${fontMono}" font-size="13" fill="#94A3B8">}</text>
        <rect x="92" y="284" width="118" height="30" rx="8" fill="#2563EB"/>
        <text x="151" y="304" text-anchor="middle" font-family="${fontMono}" font-size="11" font-weight="700" fill="#FFFFFF">20 Prompts JSON</text>

        <rect x="408" y="98" width="164" height="242" rx="12" fill="#FFFFFF"/>
        <text x="424" y="128" font-family="${fontSans}" font-size="12" font-weight="700" fill="#263445">Categories</text>
        <rect x="424" y="144" width="132" height="32" rx="8" fill="#EAF4FC"/>
        <text x="436" y="164" font-family="${fontSans}" font-size="11" font-weight="600" fill="#1D4ED8">Engineering</text>
        <rect x="424" y="186" width="132" height="32" rx="8" fill="#F8FAFC" stroke="#E5E7EB"/>
        <text x="436" y="206" font-family="${fontSans}" font-size="11" fill="#263445">Planning</text>
        <rect x="424" y="228" width="132" height="32" rx="8" fill="#ECFDF5"/>
        <text x="436" y="248" font-family="${fontSans}" font-size="11" font-weight="600" fill="#15803D">QA Review</text>
        <rect x="424" y="274" width="132" height="44" rx="10" fill="#E0F2FE"/>
        <text x="490" y="301" text-anchor="middle" font-family="${fontMono}" font-size="11" font-weight="700" fill="#0369A1">UTF-8 Validated</text>
      `, '#E0F2FE', '#EAF4FC', '#0284C7');

    case 'ai_content':
      return toSvgDataUri(`
        <rect x="46" y="34" width="548" height="332" rx="18" fill="#FFFFFF" stroke="#BAE6FD" stroke-width="2"/>
        <text x="74" y="70" font-family="${fontSans}" font-size="14" font-weight="700" fill="#263445">Editorial Content Pipeline</text>
        <rect x="430" y="48" width="138" height="26" rx="13" fill="#E0F2FE"/>
        <text x="499" y="65" text-anchor="middle" font-family="${fontSans}" font-size="11" font-weight="700" fill="#0369A1">Repurpose Kit</text>

        <rect x="74" y="114" width="144" height="196" rx="14" fill="#F8FAFC" stroke="#93C5FD" stroke-width="1.5"/>
        <text x="94" y="144" font-family="${fontMono}" font-size="12" font-weight="700" fill="#2563EB">01 Brief.md</text>
        <rect x="94" y="164" width="102" height="9" rx="4.5" fill="#263445"/>
        <rect x="94" y="184" width="90" height="7" rx="3.5" fill="#94A3B8"/>
        <rect x="94" y="202" width="96" height="7" rx="3.5" fill="#94A3B8"/>
        <rect x="94" y="248" width="102" height="36" rx="8" fill="#EAF4FC"/>
        <text x="145" y="271" text-anchor="middle" font-family="${fontSans}" font-size="11" font-weight="600" fill="#1D4ED8">Outline Prompt</text>

        <path d="M222 212 H270" stroke="#0EA5E9" stroke-width="3" stroke-linecap="round"/>
        <polygon points="276,212 264,205 264,219" fill="#0EA5E9"/>

        <rect x="282" y="108" width="286" height="58" rx="12" fill="#EAF4FC" stroke="#BFDBFE"/>
        <text x="304" y="142" font-family="${fontSans}" font-size="13" font-weight="700" fill="#1D4ED8">A. Long-Form Essay Draft</text>

        <rect x="282" y="184" width="286" height="58" rx="12" fill="#F8FAFC" stroke="#D5DEE8"/>
        <text x="304" y="218" font-family="${fontSans}" font-size="13" font-weight="700" fill="#263445">B. Multi-Slide Carousel Copy</text>

        <rect x="282" y="260" width="286" height="58" rx="12" fill="#ECFDF5" stroke="#A7F3D0"/>
        <text x="304" y="294" font-family="${fontSans}" font-size="13" font-weight="700" fill="#15803D">C. Weekly Newsletter Digest</text>
      `, '#E0F2FE', '#EAF4FC', '#0EA5E9');

    case 'ai_research':
      return toSvgDataUri(`
        <rect x="52" y="34" width="536" height="332" rx="16" fill="#FFFFFF" stroke="#D5DEE8" stroke-width="2"/>
        <rect x="52" y="34" width="536" height="48" rx="16" fill="#F8FAFC"/>
        <line x1="52" y1="82" x2="588" y2="82" stroke="#E5E7EB"/>
        <text x="80" y="64" font-family="${fontMono}" font-size="14" font-weight="700" fill="#263445"># Literature_Synthesis.md</text>
        <rect x="444" y="45" width="118" height="26" rx="13" fill="#E0F2FE"/>
        <text x="503" y="62" text-anchor="middle" font-family="${fontMono}" font-size="11" font-weight="700" fill="#0369A1">Markdown Pack</text>

        <rect x="78" y="102" width="484" height="36" rx="8" fill="#EAF4FC"/>
        <text x="98" y="125" font-family="${fontMono}" font-size="12" font-weight="700" fill="#1D4ED8">| Paper</text>
        <text x="234" y="125" font-family="${fontMono}" font-size="12" font-weight="700" fill="#1D4ED8">| Finding</text>
        <text x="454" y="125" font-family="${fontMono}" font-size="12" font-weight="700" fill="#1D4ED8">| Verified</text>

        <rect x="78" y="148" width="484" height="44" rx="8" fill="#F8FAFC" stroke="#E5E7EB"/>
        <text x="98" y="175" font-family="${fontSans}" font-size="12" fill="#263445">Attention Benchmarks</text>
        <text x="234" y="175" font-family="${fontSans}" font-size="12" fill="#64748B">Citation Matrix + Summary</text>
        <circle cx="484" cy="170" r="8" fill="#16A34A"/>

        <rect x="78" y="202" width="484" height="44" rx="8" fill="#F8FAFC" stroke="#E5E7EB"/>
        <text x="98" y="229" font-family="${fontSans}" font-size="12" fill="#263445">Claim Comparison</text>
        <text x="234" y="229" font-family="${fontSans}" font-size="12" fill="#64748B">Source Grounding Checklist</text>
        <circle cx="484" cy="224" r="8" fill="#16A34A"/>

        <rect x="78" y="264" width="484" height="72" rx="12" fill="#F0FDFA" stroke="#99F6E4"/>
        <text x="98" y="294" font-family="${fontMono}" font-size="12" font-weight="700" fill="#0F766E">&gt; Obsidian &amp; Notion Ready Prompts</text>
        <text x="98" y="318" font-family="${fontSans}" font-size="12" fill="#263445">Study outlines, methodology audit, and structured notes</text>
      `, '#F0F9FF', '#DCE6EF', '#0284C7');

    case 'ai_workflow':
      return toSvgDataUri(`
        <rect x="46" y="34" width="548" height="332" rx="18" fill="#FFFFFF" stroke="#BAE6FD" stroke-width="2"/>
        <rect x="74" y="56" width="248" height="28" rx="14" fill="#E0F2FE"/>
        <text x="198" y="74" text-anchor="middle" font-family="${fontSans}" font-size="12" font-weight="700" fill="#0369A1">Webhook &amp; Node Automation Graph</text>

        <path d="M188 150 C252 150, 240 202, 294 202" fill="none" stroke="#0EA5E9" stroke-width="3"/>
        <path d="M188 262 C252 262, 240 202, 294 202" fill="none" stroke="#2563EB" stroke-width="3"/>
        <path d="M394 202 C438 202, 434 150, 470 150" fill="none" stroke="#2563EB" stroke-width="3"/>
        <path d="M394 202 C438 202, 434 262, 470 262" fill="none" stroke="#16A34A" stroke-width="3"/>

        <rect x="72" y="122" width="122" height="56" rx="12" fill="#F8FAFC" stroke="#93C5FD" stroke-width="1.5"/>
        <text x="133" y="148" text-anchor="middle" font-family="${fontMono}" font-size="12" font-weight="700" fill="#263445">Webhook In</text>
        <text x="133" y="166" text-anchor="middle" font-family="${fontMono}" font-size="10" fill="#64748B">POST /events</text>

        <rect x="72" y="234" width="122" height="56" rx="12" fill="#F8FAFC" stroke="#93C5FD" stroke-width="1.5"/>
        <text x="133" y="260" text-anchor="middle" font-family="${fontMono}" font-size="12" font-weight="700" fill="#263445">Retry Guard</text>
        <text x="133" y="278" text-anchor="middle" font-family="${fontMono}" font-size="10" fill="#64748B">Exp. Backoff</text>

        <rect x="280" y="164" width="124" height="76" rx="14" fill="#2563EB"/>
        <text x="342" y="198" text-anchor="middle" font-family="${fontSans}" font-size="13" font-weight="700" fill="#FFFFFF">Event Router</text>
        <text x="342" y="220" text-anchor="middle" font-family="${fontMono}" font-size="11" fill="#BFDBFE">JSON Schema</text>

        <rect x="466" y="122" width="104" height="56" rx="12" fill="#EAF4FC" stroke="#BFDBFE" stroke-width="1.5"/>
        <text x="518" y="155" text-anchor="middle" font-family="${fontMono}" font-size="12" font-weight="700" fill="#1D4ED8">Digest Queue</text>

        <rect x="466" y="234" width="104" height="56" rx="12" fill="#ECFDF5" stroke="#A7F3D0" stroke-width="1.5"/>
        <text x="518" y="267" text-anchor="middle" font-family="${fontMono}" font-size="12" font-weight="700" fill="#15803D">DB Escalation</text>
      `, '#E0F2FE', '#EAF4FC', '#0284C7');

    case 'marketing_calendar': {
      const days = [];
      const colors = ['#EAF4FC', '#F3F0FF', '#ECFDF5', '#F8FAFC', '#E0F2FE'];
      const tags = ['Reel', 'Carousel', 'Story', 'Tip', 'Launch'];
      for (let r = 0; r < 3; r += 1) {
        for (let c = 0; c < 5; c += 1) {
          const idx = r * 5 + c;
          const bx = 74 + c * 100;
          const by = 112 + r * 78;
          days.push(`
            <rect x="${bx}" y="${by}" width="88" height="66" rx="10" fill="#FFFFFF" stroke="#D5DEE8"/>
            <text x="${bx + 10}" y="${by + 20}" font-family="${fontMono}" font-size="11" font-weight="700" fill="#64748B">Day ${idx + 1}</text>
            <rect x="${bx + 10}" y="${by + 34}" width="68" height="20" rx="6" fill="${colors[idx % colors.length]}"/>
            <text x="${bx + 44}" y="${by + 48}" text-anchor="middle" font-family="${fontSans}" font-size="10" font-weight="600" fill="#263445">${tags[idx % tags.length]}</text>
          `);
        }
      }
      return toSvgDataUri(`
        <rect x="46" y="34" width="548" height="332" rx="18" fill="#F8FAFC" stroke="#D5DEE8" stroke-width="2"/>
        <text x="74" y="72" font-family="${fontSans}" font-size="15" font-weight="700" fill="#263445">30-Day Instagram Content Calendar</text>
        <rect x="444" y="48" width="118" height="28" rx="14" fill="#EAF4FC" stroke="#BFDBFE"/>
        <text x="503" y="66" text-anchor="middle" font-family="${fontMono}" font-size="11" font-weight="700" fill="#1D4ED8">CSV Schedule</text>
        ${days.join('')}
      `, '#EAF4FC', '#DCE6EF', '#2563EB');
    }

    case 'marketing_strategy':
      return toSvgDataUri(`
        <rect x="46" y="34" width="548" height="332" rx="18" fill="#FFFFFF" stroke="#D5DEE8" stroke-width="2"/>
        <text x="74" y="72" font-family="${fontSans}" font-size="15" font-weight="700" fill="#263445">Campaign Funnel &amp; Positioning</text>
        <rect x="430" y="48" width="136" height="28" rx="14" fill="#DCE6EF"/>
        <text x="498" y="66" text-anchor="middle" font-family="${fontSans}" font-size="11" font-weight="700" fill="#263445">Strategy PDF</text>

        <polygon points="82,116 362,116 334,174 110,174" fill="#EAF4FC" stroke="#93C5FD" stroke-width="1.5"/>
        <text x="222" y="150" text-anchor="middle" font-family="${fontSans}" font-size="13" font-weight="700" fill="#1D4ED8">100% Awareness &amp; Reach</text>

        <polygon points="116,186 328,186 300,244 144,244" fill="#DCE6EF" stroke="#93C5FD" stroke-width="1.5"/>
        <text x="222" y="220" text-anchor="middle" font-family="${fontSans}" font-size="13" font-weight="700" fill="#263445">54% Engaged Consideration</text>

        <polygon points="150,256 294,256 270,314 174,314" fill="#2563EB"/>
        <text x="222" y="290" text-anchor="middle" font-family="${fontSans}" font-size="13" font-weight="700" fill="#FFFFFF">18% Conversion</text>

        <rect x="394" y="114" width="174" height="202" rx="14" fill="#F8FAFC" stroke="#D5DEE8"/>
        <circle cx="481" cy="176" r="36" fill="#EAF4FC" stroke="#2563EB" stroke-width="2.5"/>
        <circle cx="481" cy="176" r="21" fill="none" stroke="#0EA5E9" stroke-width="2.5"/>
        <circle cx="481" cy="176" r="7" fill="#2563EB"/>
        <text x="481" y="242" text-anchor="middle" font-family="${fontSans}" font-size="13" font-weight="700" fill="#263445">ICP Targeting</text>
        <text x="481" y="266" text-anchor="middle" font-family="${fontMono}" font-size="11" fill="#64748B">Budget &amp; Brief</text>
        <text x="481" y="286" text-anchor="middle" font-family="${fontMono}" font-size="11" fill="#16A34A">Launch Playbook</text>
      `, '#EAF4FC', '#DCE6EF', '#2563EB');

    case 'marketing_analytics':
      return toSvgDataUri(`
        <rect x="46" y="34" width="340" height="332" rx="16" fill="#FFFFFF" stroke="#D5DEE8" stroke-width="2"/>
        <rect x="70" y="56" width="166" height="24" rx="12" fill="#EAF4FC"/>
        <text x="153" y="72" text-anchor="middle" font-family="${fontSans}" font-size="11" font-weight="700" fill="#1D4ED8">Social KPI Analytics</text>
        <rect x="76" y="220" width="32" height="96" rx="6" fill="#DCE6EF"/>
        <rect x="124" y="190" width="32" height="126" rx="6" fill="#93C5FD"/>
        <rect x="172" y="162" width="32" height="154" rx="6" fill="#0EA5E9"/>
        <rect x="220" y="138" width="32" height="178" rx="6" fill="#2563EB"/>
        <rect x="268" y="112" width="32" height="204" rx="6" fill="#1D4ED8"/>
        <rect x="316" y="96" width="32" height="220" rx="6" fill="#16A34A"/>
        <polyline points="92,202 140,174 188,146 236,124 284,98 332,82" fill="none" stroke="#263445" stroke-width="3" stroke-linecap="round"/>

        <rect x="406" y="34" width="188" height="332" rx="16" fill="#FFFFFF" stroke="#D5DEE8" stroke-width="2"/>
        <text x="430" y="76" font-family="${fontSans}" font-size="12" font-weight="700" fill="#64748B">ENGAGEMENT</text>
        <text x="430" y="110" font-family="${fontSans}" font-size="28" font-weight="700" fill="#263445">4.8%</text>
        <text x="430" y="132" font-family="${fontMono}" font-size="12" font-weight="700" fill="#16A34A">+18.4% MoM</text>
        <line x1="430" y1="154" x2="570" y2="154" stroke="#E5E7EB"/>
        <text x="430" y="186" font-family="${fontSans}" font-size="12" font-weight="700" fill="#64748B">CLICK RATE</text>
        <text x="430" y="218" font-family="${fontSans}" font-size="24" font-weight="700" fill="#2563EB">3.6x ROAS</text>
        <rect x="428" y="256" width="144" height="38" rx="10" fill="#EAF4FC" stroke="#BFDBFE"/>
        <text x="500" y="280" text-anchor="middle" font-family="${fontSans}" font-size="12" font-weight="600" fill="#1D4ED8">CSV + KPI Specs</text>
      `, '#EAF4FC', '#DCE6EF', '#2563EB');

    case 'marketing_kit':
      return toSvgDataUri(`
        <rect x="48" y="36" width="296" height="328" rx="16" fill="#FFFFFF" stroke="#D5DEE8" stroke-width="2"/>
        <rect x="48" y="36" width="296" height="54" rx="16" fill="#2563EB"/>
        <rect x="48" y="74" width="296" height="16" fill="#2563EB"/>
        <text x="72" y="69" font-family="${fontSans}" font-size="14" font-weight="700" fill="#FFFFFF">Email Launch Newsletter</text>
        <rect x="72" y="114" width="248" height="86" rx="12" fill="#EAF4FC" stroke="#BFDBFE"/>
        <text x="196" y="154" text-anchor="middle" font-family="${fontSans}" font-size="14" font-weight="700" fill="#1D4ED8">Seasonal Promo Hero</text>
        <text x="196" y="176" text-anchor="middle" font-family="${fontMono}" font-size="11" fill="#2563EB">UTM Tracking Ready</text>
        <rect x="72" y="220" width="248" height="12" rx="6" fill="#CBD5E1"/>
        <rect x="72" y="246" width="210" height="12" rx="6" fill="#CBD5E1"/>
        <rect x="72" y="286" width="144" height="38" rx="10" fill="#2563EB"/>
        <text x="144" y="310" text-anchor="middle" font-family="${fontSans}" font-size="12" font-weight="700" fill="#FFFFFF">Campaign CTA</text>

        <rect x="364" y="54" width="228" height="292" rx="16" fill="#FFFFFF" stroke="#D5DEE8" stroke-width="2"/>
        <text x="386" y="88" font-family="${fontSans}" font-size="13" font-weight="700" fill="#263445">Launch Checklist</text>
        <rect x="386" y="108" width="184" height="44" rx="10" fill="#ECFDF5" stroke="#A7F3D0"/>
        <circle cx="408" cy="130" r="8" fill="#16A34A"/>
        <text x="426" y="135" font-family="${fontSans}" font-size="12" font-weight="600" fill="#15803D">Announcement Copy</text>
        <rect x="386" y="166" width="184" height="44" rx="10" fill="#ECFDF5" stroke="#A7F3D0"/>
        <circle cx="408" cy="188" r="8" fill="#16A34A"/>
        <text x="426" y="193" font-family="${fontSans}" font-size="12" font-weight="600" fill="#15803D">Promo Calendar CSV</text>
        <rect x="386" y="224" width="184" height="44" rx="10" fill="#EAF4FC" stroke="#BFDBFE"/>
        <circle cx="408" cy="246" r="8" fill="#2563EB"/>
        <text x="426" y="251" font-family="${fontSans}" font-size="12" font-weight="600" fill="#1D4ED8">Small Business Kit</text>
      `, '#EAF4FC', '#DCE6EF', '#2563EB');

    case 'audio_sfx': {
      const bars = [];
      for (let i = 0; i < 16; i += 1) {
        const h = 26 + Math.round(62 * Math.abs(Math.sin((i + 1) * 0.55)));
        bars.push(
          `<rect x="${268 + i * 17}" y="${148 - Math.round(h / 2)}" width="9" height="${h}" rx="4.5" fill="${i % 4 === 0 ? '#0EA5E9' : '#2563EB'}"/>`
        );
      }
      return toSvgDataUri(`
        <rect x="46" y="36" width="548" height="328" rx="18" fill="#0F172A" stroke="#334155" stroke-width="2"/>
        <rect x="74" y="64" width="154" height="170" rx="16" fill="#1E293B" stroke="#334155"/>
        <circle cx="151" cy="166" r="34" fill="#D97706" fill-opacity="0.22" stroke="#F59E0B" stroke-width="2.5"/>
        <circle cx="151" cy="148" r="14" fill="#0F172A" stroke="#F59E0B" stroke-width="2"/>
        <rect x="145" y="84" width="12" height="58" rx="4" fill="#94A3B8"/>
        <rect x="139" y="76" width="24" height="16" rx="4" fill="#38BDF8"/>
        <text x="151" y="220" text-anchor="middle" font-family="${fontMono}" font-size="11" fill="#7DD3FC">Studio Audio WAV</text>

        <text x="268" y="78" font-family="${fontSans}" font-size="14" font-weight="700" fill="#F8FAFC">44.1 kHz &#x00B7; 16-bit PCM Sound Pack</text>
        ${bars.join('')}
        <rect x="74" y="256" width="488" height="10" rx="5" fill="#1E293B"/>
        <rect x="74" y="256" width="296" height="10" rx="5" fill="#0EA5E9"/>
        <circle cx="370" cy="261" r="9" fill="#FFFFFF" stroke="#0EA5E9" stroke-width="3"/>
        <text x="74" y="302" font-family="${fontMono}" font-size="13" fill="#94A3B8">00:00  &#x25B6;  Acoustic &amp; Synth Chimes  &#x00B7;  Royalty-Free</text>
      `, '#EDF5FC', '#DCE6EF', '#0EA5E9');
    }

    case 'video_lut':
      return toSvgDataUri(`
        <rect x="46" y="36" width="548" height="328" rx="18" fill="#0F172A" stroke="#334155" stroke-width="2"/>
        <text x="76" y="72" font-family="${fontSans}" font-size="14" font-weight="700" fill="#F8FAFC">3D LUT Color Grading &amp; Timeline</text>
        <rect x="444" y="48" width="122" height="26" rx="13" fill="#0EA5E9" fill-opacity="0.2" stroke="#38BDF8"/>
        <text x="505" y="65" text-anchor="middle" font-family="${fontMono}" font-size="11" fill="#7DD3FC">.CUBE LUTs</text>

        <circle cx="132" cy="154" r="40" fill="#1E293B" stroke="#38BDF8" stroke-width="3"/>
        <circle cx="132" cy="154" r="14" fill="#38BDF8" fill-opacity="0.35"/>
        <text x="132" y="212" text-anchor="middle" font-family="${fontMono}" font-size="10" fill="#94A3B8">LIFT</text>

        <circle cx="242" cy="154" r="40" fill="#1E293B" stroke="#F59E0B" stroke-width="3"/>
        <circle cx="242" cy="154" r="14" fill="#F59E0B" fill-opacity="0.35"/>
        <text x="242" y="212" text-anchor="middle" font-family="${fontMono}" font-size="10" fill="#94A3B8">GAMMA</text>

        <circle cx="352" cy="154" r="40" fill="#1E293B" stroke="#34D399" stroke-width="3"/>
        <circle cx="352" cy="154" r="14" fill="#34D399" fill-opacity="0.35"/>
        <text x="352" y="212" text-anchor="middle" font-family="${fontMono}" font-size="10" fill="#94A3B8">GAIN</text>

        <rect x="418" y="106" width="144" height="96" rx="12" fill="#1E293B" stroke="#334155"/>
        <path d="M434 186 C468 186, 488 122, 546 122" fill="none" stroke="#34D399" stroke-width="3"/>

        <rect x="74" y="242" width="490" height="30" rx="8" fill="#1E293B"/>
        <rect x="78" y="246" width="180" height="22" rx="6" fill="#2563EB"/>
        <rect x="266" y="246" width="146" height="22" rx="6" fill="#0EA5E9"/>
        <rect x="74" y="284" width="490" height="30" rx="8" fill="#1E293B"/>
        <rect x="78" y="288" width="248" height="22" rx="6" fill="#0D9488"/>
      `, '#EDF5FC', '#DCE6EF', '#0EA5E9');

    case 'video_motion':
      return toSvgDataUri(`
        <rect x="46" y="36" width="548" height="328" rx="18" fill="#0F172A" stroke="#334155" stroke-width="2"/>
        <text x="76" y="72" font-family="${fontSans}" font-size="14" font-weight="700" fill="#F8FAFC">Keyframe Animation &amp; Easing Curves</text>
        <rect x="434" y="48" width="132" height="26" rx="13" fill="#2563EB" fill-opacity="0.25" stroke="#60A5FA"/>
        <text x="500" y="65" text-anchor="middle" font-family="${fontMono}" font-size="11" fill="#93C5FD">60fps Motion</text>

        <rect x="74" y="98" width="248" height="148" rx="14" fill="#1E293B" stroke="#334155"/>
        <line x1="98" y1="220" x2="296" y2="220" stroke="#475569"/>
        <line x1="98" y1="120" x2="98" y2="220" stroke="#475569"/>
        <path d="M104 214 C166 214, 210 128, 290 128" fill="none" stroke="#38BDF8" stroke-width="3.5"/>
        <circle cx="166" cy="214" r="5" fill="#FBBF24"/>
        <circle cx="210" cy="128" r="5" fill="#FBBF24"/>

        <rect x="344" y="98" width="220" height="148" rx="14" fill="#1E293B" stroke="#38BDF8" stroke-width="1.5"/>
        <rect x="372" y="138" width="164" height="44" rx="10" fill="#2563EB"/>
        <text x="454" y="165" text-anchor="middle" font-family="${fontSans}" font-size="14" font-weight="700" fill="#FFFFFF">Lower-Third UI</text>
        <text x="454" y="210" text-anchor="middle" font-family="${fontMono}" font-size="11" fill="#94A3B8">cubic-bezier JSON</text>

        <rect x="74" y="268" width="490" height="58" rx="12" fill="#1E293B" stroke="#334155"/>
        <line x1="100" y1="297" x2="538" y2="297" stroke="#475569" stroke-width="2"/>
        <polygon points="150,287 160,297 150,307 140,297" fill="#38BDF8"/>
        <polygon points="318,287 328,297 318,307 308,297" fill="#FBBF24"/>
        <polygon points="486,287 496,297 486,307 476,297" fill="#34D399"/>
      `, '#EDF5FC', '#DCE6EF', '#2563EB');

    case 'video_creator':
      return toSvgDataUri(`
        <rect x="46" y="36" width="548" height="328" rx="18" fill="#0F172A" stroke="#334155" stroke-width="2"/>
        <text x="76" y="72" font-family="${fontSans}" font-size="14" font-weight="700" fill="#F8FAFC">Clapperboard &amp; Creator Production Pack</text>

        <rect x="76" y="98" width="204" height="148" rx="14" fill="#1E293B" stroke="#475569" stroke-width="2"/>
        <rect x="76" y="98" width="204" height="34" rx="8" fill="#F8FAFC"/>
        <polygon points="96,98 118,98 104,132 82,132" fill="#0F172A"/>
        <polygon points="142,98 164,98 150,132 128,132" fill="#0F172A"/>
        <polygon points="188,98 210,98 196,132 174,132" fill="#0F172A"/>
        <polygon points="234,98 256,98 242,132 220,132" fill="#0F172A"/>
        <text x="98" y="164" font-family="${fontMono}" font-size="12" fill="#94A3B8">PROD: CREATOR KIT</text>
        <text x="98" y="192" font-family="${fontMono}" font-size="15" font-weight="700" fill="#38BDF8">SCENE 04 · TAKE 02</text>
        <text x="98" y="220" font-family="${fontMono}" font-size="11" fill="#34D399">A/V Stinger Ready</text>

        <rect x="304" y="98" width="260" height="148" rx="14" fill="#1E293B" stroke="#334155"/>
        <text x="326" y="130" font-family="${fontSans}" font-size="13" font-weight="700" fill="#F8FAFC">Production Tracks</text>
        <rect x="326" y="148" width="216" height="24" rx="6" fill="#2563EB"/>
        <text x="338" y="164" font-family="${fontMono}" font-size="11" fill="#FFFFFF">V1  B-Roll &amp; Cutaways</text>
        <rect x="326" y="182" width="184" height="24" rx="6" fill="#0EA5E9"/>
        <text x="338" y="198" font-family="${fontMono}" font-size="11" fill="#FFFFFF">A1  intro-stinger.wav</text>

        <rect x="76" y="268" width="488" height="62" rx="12" fill="#1E293B" stroke="#334155"/>
        <text x="98" y="304" font-family="${fontMono}" font-size="13" fill="#E2E8F0">Pre-Shoot Script Checklist  &#x00B7;  WAV Audio Cue  &#x00B7;  Pacing Guide</text>
      `, '#EDF5FC', '#DCE6EF', '#0EA5E9');

    case 'biz_financial_model':
      return toSvgDataUri(`
        <rect x="46" y="36" width="548" height="328" rx="18" fill="#FFFFFF" stroke="#D5DEE8" stroke-width="2"/>
        <text x="74" y="72" font-family="${fontSans}" font-size="15" font-weight="700" fill="#263445">SaaS P&amp;L Financial Projection</text>
        <rect x="418" y="48" width="148" height="28" rx="14" fill="#F0FDFA" stroke="#99F6E4"/>
        <text x="492" y="66" text-anchor="middle" font-family="${fontMono}" font-size="12" font-weight="700" fill="#0F766E">Gross Margin 84%</text>

        <rect x="74" y="100" width="244" height="226" rx="12" fill="#F8FAFC" stroke="#E5E7EB"/>
        <rect x="98" y="244" width="28" height="58" rx="6" fill="#CCFBF1"/>
        <rect x="138" y="216" width="28" height="86" rx="6" fill="#5EEAD4"/>
        <rect x="178" y="182" width="28" height="120" rx="6" fill="#14B8A6"/>
        <rect x="218" y="152" width="28" height="150" rx="6" fill="#0D9488"/>
        <rect x="258" y="124" width="28" height="178" rx="6" fill="#0F766E"/>
        <text x="98" y="136" font-family="${fontMono}" font-size="12" font-weight="700" fill="#0F766E">+28% QoQ</text>

        <rect x="336" y="100" width="230" height="226" rx="12" fill="#FFFFFF" stroke="#D5DEE8"/>
        <rect x="336" y="100" width="230" height="36" rx="12" fill="#F0FDFA"/>
        <text x="356" y="123" font-family="${fontSans}" font-size="12" font-weight="700" fill="#0F766E">12-Month Summary (INR)</text>
        <text x="356" y="164" font-family="${fontMono}" font-size="12" fill="#263445">Q1 Revenue    &#x20B9;4,20,000</text>
        <text x="356" y="196" font-family="${fontMono}" font-size="12" fill="#263445">Q2 Revenue    &#x20B9;6,15,000</text>
        <text x="356" y="228" font-family="${fontMono}" font-size="12" fill="#263445">Q3 Revenue    &#x20B9;8,90,000</text>
        <line x1="356" y1="248" x2="546" y2="248" stroke="#E5E7EB"/>
        <text x="356" y="276" font-family="${fontMono}" font-size="13" font-weight="700" fill="#16A34A">Net Profit    +&#x20B9;11.4L</text>
      `, '#F0FDFA', '#EAF4FC', '#0D9488');

    case 'biz_proposal':
      return toSvgDataUri(`
        <rect x="74" y="34" width="492" height="332" rx="16" fill="#FFFFFF" stroke="#D5DEE8" stroke-width="2"/>
        <rect x="74" y="34" width="492" height="58" rx="16" fill="#F8FAFC"/>
        <line x1="74" y1="92" x2="566" y2="92" stroke="#E5E7EB"/>
        <text x="104" y="68" font-family="${fontSans}" font-size="16" font-weight="700" fill="#263445">Client Proposal &amp; Invoice Spec</text>
        <rect x="436" y="48" width="102" height="26" rx="13" fill="#F0FDFA" stroke="#99F6E4"/>
        <text x="487" y="65" text-anchor="middle" font-family="${fontMono}" font-size="11" font-weight="700" fill="#0F766E">INV-2026</text>

        <text x="104" y="128" font-family="${fontSans}" font-size="12" font-weight="700" fill="#64748B">DELIVERABLE</text>
        <text x="480" y="128" text-anchor="end" font-family="${fontSans}" font-size="12" font-weight="700" fill="#64748B">MILESTONE FEE</text>
        <line x1="104" y1="140" x2="536" y2="140" stroke="#E5E7EB"/>

        <text x="104" y="172" font-family="${fontSans}" font-size="13" fill="#263445">01. Discovery &amp; Scope Blueprint</text>
        <text x="536" y="172" text-anchor="end" font-family="${fontMono}" font-size="13" fill="#263445">&#x20B9;45,000</text>
        <line x1="104" y1="188" x2="536" y2="188" stroke="#F1F5F9"/>

        <text x="104" y="218" font-family="${fontSans}" font-size="13" fill="#263445">02. Architecture &amp; Asset Delivery</text>
        <text x="536" y="218" text-anchor="end" font-family="${fontMono}" font-size="13" fill="#263445">&#x20B9;75,000</text>
        <line x1="104" y1="238" x2="536" y2="238" stroke="#E5E7EB"/>

        <rect x="330" y="256" width="206" height="44" rx="10" fill="#EAF4FC" stroke="#BFDBFE"/>
        <text x="348" y="283" font-family="${fontSans}" font-size="13" font-weight="700" fill="#1D4ED8">Total</text>
        <text x="520" y="283" text-anchor="end" font-family="${fontMono}" font-size="14" font-weight="700" fill="#1D4ED8">&#x20B9;1,20,000</text>
        <text x="104" y="324" font-family="${fontSans}" font-size="12" fill="#64748B">Signed Statement of Work &#x00B7; PDF Template</text>
      `, '#F0FDFA', '#EAF4FC', '#0D9488');

    case 'biz_plan':
      return toSvgDataUri(`
        <rect x="46" y="34" width="548" height="332" rx="18" fill="#FFFFFF" stroke="#D5DEE8" stroke-width="2"/>
        <text x="74" y="72" font-family="${fontSans}" font-size="15" font-weight="700" fill="#263445">Lean Business Plan &amp; 90-Day Roadmap</text>
        <rect x="436" y="48" width="128" height="28" rx="14" fill="#F0FDFA" stroke="#99F6E4"/>
        <text x="500" y="66" text-anchor="middle" font-family="${fontSans}" font-size="11" font-weight="700" fill="#0F766E">Workbook PDF</text>

        <rect x="74" y="100" width="154" height="128" rx="12" fill="#F8FAFC" stroke="#D5DEE8"/>
        <text x="90" y="126" font-family="${fontSans}" font-size="12" font-weight="700" fill="#0F766E">Value Canvas</text>
        <rect x="90" y="142" width="114" height="10" rx="5" fill="#263445"/>
        <rect x="90" y="164" width="96" height="8" rx="4" fill="#94A3B8"/>
        <rect x="90" y="184" width="108" height="8" rx="4" fill="#94A3B8"/>

        <rect x="242" y="100" width="154" height="128" rx="12" fill="#EAF4FC" stroke="#BFDBFE"/>
        <text x="258" y="126" font-family="${fontSans}" font-size="12" font-weight="700" fill="#1D4ED8">Pricing Tiers</text>
        <rect x="258" y="142" width="114" height="10" rx="5" fill="#2563EB"/>
        <rect x="258" y="164" width="96" height="8" rx="4" fill="#64748B"/>
        <rect x="258" y="184" width="108" height="8" rx="4" fill="#64748B"/>

        <rect x="410" y="100" width="154" height="128" rx="12" fill="#F0FDFA" stroke="#99F6E4"/>
        <text x="426" y="126" font-family="${fontSans}" font-size="12" font-weight="700" fill="#0F766E">Risk Matrix</text>
        <rect x="426" y="142" width="114" height="10" rx="5" fill="#0D9488"/>
        <rect x="426" y="164" width="96" height="8" rx="4" fill="#64748B"/>
        <rect x="426" y="184" width="108" height="8" rx="4" fill="#64748B"/>

        <rect x="74" y="246" width="490" height="92" rx="12" fill="#F8FAFC" stroke="#E5E7EB"/>
        <text x="94" y="274" font-family="${fontSans}" font-size="12" font-weight="700" fill="#263445">Quarterly Milestones</text>
        <rect x="94" y="294" width="144" height="24" rx="12" fill="#2563EB"/>
        <text x="166" y="310" text-anchor="middle" font-family="${fontMono}" font-size="11" font-weight="700" fill="#FFFFFF">Day 30: Validate</text>
        <rect x="248" y="294" width="144" height="24" rx="12" fill="#0D9488"/>
        <text x="320" y="310" text-anchor="middle" font-family="${fontMono}" font-size="11" font-weight="700" fill="#FFFFFF">Day 60: Launch</text>
        <rect x="402" y="294" width="144" height="24" rx="12" fill="#16A34A"/>
        <text x="474" y="310" text-anchor="middle" font-family="${fontMono}" font-size="11" font-weight="700" fill="#FFFFFF">Day 90: Scale</text>
      `, '#F0FDFA', '#EAF4FC', '#0D9488');

    case 'biz_pitch_deck':
    default:
      return toSvgDataUri(`
        <rect x="64" y="42" width="324" height="236" rx="16" fill="#FFFFFF" stroke="#D5DEE8" stroke-width="2"/>
        <rect x="86" y="64" width="128" height="24" rx="12" fill="#F0FDFA" stroke="#99F6E4"/>
        <text x="150" y="80" text-anchor="middle" font-family="${fontSans}" font-size="11" font-weight="700" fill="#0F766E">SLIDE 01 · THESIS</text>
        <rect x="86" y="106" width="236" height="14" rx="6" fill="#263445"/>
        <rect x="86" y="130" width="188" height="9" rx="4.5" fill="#94A3B8"/>
        <rect x="86" y="162" width="84" height="84" rx="12" fill="#EAF4FC"/>
        <rect x="182" y="162" width="84" height="84" rx="12" fill="#F0FDFA"/>
        <rect x="278" y="162" width="84" height="84" rx="12" fill="#F8FAFC" stroke="#E5E7EB"/>

        <rect x="264" y="128" width="318" height="226" rx="16" fill="#FFFFFF" stroke="#0D9488" stroke-width="2"/>
        <text x="290" y="162" font-family="${fontSans}" font-size="13" font-weight="700" fill="#0F766E">${titleLabel}</text>
        <rect x="290" y="240" width="34" height="72" rx="6" fill="#DCE6EF"/>
        <rect x="336" y="216" width="34" height="96" rx="6" fill="#5EEAD4"/>
        <rect x="382" y="190" width="34" height="122" rx="6" fill="#0D9488"/>
        <rect x="428" y="166" width="34" height="146" rx="6" fill="#2563EB"/>
        <circle cx="520" cy="240" r="38" fill="none" stroke="#E5E7EB" stroke-width="12"/>
        <circle cx="520" cy="240" r="38" fill="none" stroke="#0D9488" stroke-width="12" stroke-dasharray="178 240"/>
      `, '#F0FDFA', '#EAF4FC', '#0D9488');
  }
}

function renderDetailSpecSlide(product, slideIndex) {
  const fontSans = "system-ui, -apple-system, 'Segoe UI', sans-serif";
  const fontMono = "'Consolas', 'Courier New', monospace";
  const name = esc(truncate(product?.name || product?.product_name || 'Digital Product', 38));
  const typeLabel = esc(product?.product_type || 'Digital Asset');
  const meta = product?.product_metadata || {};
  const format = esc(meta.format || 'VERIFIED');
  const fileSize = esc(meta.file_size || 'Instant Download');

  if (slideIndex === 1) {
    const includes = Array.isArray(meta.includes) && meta.includes.length > 0
      ? meta.includes.slice(0, 4)
      : [typeLabel, 'Clean Documentation', 'Verified Package Archive'];
    const rows = includes
      .map(
        (item, idx) => `
      <rect x="76" y="${142 + idx * 46}" width="488" height="36" rx="10" fill="#F8FAFC" stroke="#E5E7EB"/>
      <circle cx="98" cy="${160 + idx * 46}" r="8" fill="#16A34A"/>
      <text x="118" y="${165 + idx * 46}" font-family="${fontSans}" font-size="13" font-weight="600" fill="#263445">${esc(truncate(item, 48))}</text>
    `
      )
      .join('');
    return toSvgDataUri(`
      <rect x="44" y="34" width="552" height="332" rx="18" fill="#FFFFFF" stroke="#D5DEE8" stroke-width="2"/>
      <text x="76" y="72" font-family="${fontSans}" font-size="12" font-weight="700" fill="#2563EB">PACKAGE CONTENTS PREVIEW</text>
      <text x="76" y="102" font-family="${fontSans}" font-size="19" font-weight="700" fill="#263445">${name}</text>
      <rect x="454" y="54" width="112" height="28" rx="14" fill="#EAF4FC" stroke="#BFDBFE"/>
      <text x="510" y="72" text-anchor="middle" font-family="${fontMono}" font-size="11" font-weight="700" fill="#1D4ED8">${format} · ${fileSize}</text>
      ${rows}
    `, '#EAF4FC', '#DCE6EF', '#2563EB');
  }

  const tags = Array.isArray(meta.tags) && meta.tags.length > 0
    ? meta.tags.slice(0, 4)
    : ['digital', 'verified', 'instant-access'];
  const pills = tags
    .map(
      (tag, idx) => `
    <rect x="${76 + idx * 120}" y="256" width="110" height="30" rx="15" fill="#EAF4FC" stroke="#BFDBFE"/>
    <text x="${131 + idx * 120}" y="275" text-anchor="middle" font-family="${fontMono}" font-size="11" font-weight="600" fill="#1D4ED8">#${esc(truncate(tag, 12))}</text>
  `
    )
    .join('');

  return toSvgDataUri(`
    <rect x="44" y="34" width="552" height="332" rx="18" fill="#FFFFFF" stroke="#D5DEE8" stroke-width="2"/>
    <text x="76" y="74" font-family="${fontSans}" font-size="12" font-weight="700" fill="#0EA5E9">VERIFIED DIGITAL DELIVERY</text>
    <text x="76" y="104" font-family="${fontSans}" font-size="18" font-weight="700" fill="#263445">${name}</text>
    <rect x="76" y="128" width="234" height="104" rx="14" fill="#F8FAFC" stroke="#E5E7EB"/>
    <text x="96" y="160" font-family="${fontSans}" font-size="13" font-weight="700" fill="#263445">Asset Format</text>
    <text x="96" y="186" font-family="${fontMono}" font-size="14" fill="#2563EB">${typeLabel}</text>
    <text x="96" y="210" font-family="${fontMono}" font-size="12" fill="#64748B">${format} · ${fileSize}</text>

    <rect x="330" y="128" width="234" height="104" rx="14" fill="#ECFDF5" stroke="#A7F3D0"/>
    <text x="350" y="160" font-family="${fontSans}" font-size="13" font-weight="700" fill="#15803D">Signed Access</text>
    <text x="350" y="186" font-family="${fontSans}" font-size="13" fill="#263445">Unlocked after checkout</text>
    <text x="350" y="210" font-family="${fontMono}" font-size="12" fill="#16A34A">Printable Invoice Ready</text>

    <text x="76" y="324" font-family="${fontSans}" font-size="12" fill="#64748B">Included in your permanent DIGI-VERSE Downloads Library</text>
    ${pills}
  `, '#F8FAFC', '#EAF4FC', '#0EA5E9');
}

export const isDemoCatalogProduct = (product) => {
  if (!product) return false;
  const slug = String(product.slug || product.product_slug || '').toLowerCase();
  return Boolean(product.product_metadata?.demo_seed) || slug.startsWith('demo-');
};

export const buildProductThumbnailDataUri = (product, slideIndex = 0) => {
  if (slideIndex > 0) {
    return renderDetailSpecSlide(product, slideIndex);
  }
  const sceneKey = detectSceneKey(product);
  return renderScene(sceneKey, product);
};

export const resolveProductThumbnailUrl = (product, rawImageUrl, slideIndex = 0) => {
  if (isDemoCatalogProduct(product) || !rawImageUrl) {
    return buildProductThumbnailDataUri(product, slideIndex);
  }
  return rawImageUrl;
};

export const resolveProductGalleryImages = (product) => {
  if (!product) return [];
  const rawImages = Array.isArray(product.images) ? product.images : [];
  if (isDemoCatalogProduct(product) || rawImages.length === 0) {
    const count = Math.max(3, rawImages.length);
    return Array.from({ length: count }, (_, idx) => ({
      id: rawImages[idx]?.id ?? `visual-slide-${idx}`,
      image_url: buildProductThumbnailDataUri(product, idx),
    }));
  }
  return rawImages;
};

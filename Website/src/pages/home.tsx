// src/pages/home.tsx
import { useEffect, useState, useMemo, useCallback, memo, useRef } from 'react';
import { 
  Monitor, 
  Network, 
  Shield, 
  Code, 
  Wrench, 
  ShoppingCart,
  Laptop,
  Server,
  Monitor as MonitorIcon,
  Dock,
  Mouse,
  ArrowRight,
  CheckCircle2,
  ChevronRight,
  KeyRound,
  LifeBuoy,
  Headset,
  ShieldCheck,
  Users,
  Cloud,
  Phone,
  Mail,
  MessageCircle,
  ChevronLeft,
  ChevronRight as ChevronRightIcon,
  Check,
} from 'lucide-react';
import { useTheme } from '../context/ThemeContext';
import { useStore } from '../lib/store-context';
import LoadingAnimation from '../components/LoadingAnimation';

// Import BOTH light and dark background images from your assets folder
import showcaseBgLight from '../assets/background.png';
import showcaseBgDark from '../assets/dark-background.png';

// Import product images
import laptop1 from '../assets/laptop-1.png';
import laptop2 from '../assets/laptop-2.png';
import laptop3 from '../assets/laptop-3.png';
import monitor1 from '../assets/monitor-1.png';

// ============================================
// YOUR ORIGINAL DATA FROM HOME.TSX
// ============================================
const SERVICES = [
  { icon: Monitor, label: "End User Computing", blurb: "Laptop & desktop deployment, imaging and onboarding." },
  { icon: Network, label: "ICT Infrastructure", blurb: "Network design, cabling, servers and data centre." },
  { icon: Shield, label: "Security & Surveillance", blurb: "CCTV, access control and integrated monitoring." },
  { icon: Code, label: "Software Solutions", blurb: "Business apps, BI and digital transformation." },
  { icon: Wrench, label: "Technical Support", blurb: "Maintenance, troubleshooting and managed services." },
  { icon: ShoppingCart, label: "Technology Procurement", blurb: "OEM-backed sourcing and equipment supply." }
];

const PARTNERS = [
  "DELL", "HP", "LENOVO", "ASUS", "HUAWEI", 
  "HIKVISION", "EATON", "BROTHER", "BIXOLON", 
  "DATALOGIC", "ATEN", "G&G"
];

// ============================================
// PRODUCT DATA WITH UNIQUE IDs
// ============================================
interface Product {
  id: string;
  badge?: string;
  badgeTone?: 'lime' | 'deal';
  name: string;
  image: string;
  specs: string[];
  price: string;
  wasPrice?: string;
}

const products: Product[] = [
  {
    id: 'dell-latitude-5410',
    badge: "Ready now!",
    badgeTone: "lime",
    name: "Dell Latitude 5410",
    image: laptop1,
    specs: [
      "Intel Core i5 10th Gen",
      "8GB RAM",
      "256GB NVMe SSD",
      '14" FHD Display',
      "Windows 11 Pro",
      "3 Month Back-to-base Warranty",
    ],
    price: "R15 950.00",
    wasPrice: "R18 500.00",
  },
  {
    id: 'dell-latitude-5420',
    badge: "Ready now!",
    badgeTone: "lime",
    name: "Dell Latitude 5420",
    image: laptop2,
    specs: [
      "Intel Core i5 11th Gen",
      "16GB RAM",
      "512GB NVMe SSD",
      '14" FHD Display',
      "Backlit Keyboard",
      "3 Month Back-to-base Warranty",
    ],
    price: "R15 950.00",
  },
  {
    id: 'dell-latitude-5440',
    badge: "Ready now!",
    badgeTone: "lime",
    name: "Dell Latitude 5440",
    image: laptop3,
    specs: [
      "Intel Core i7 12th Gen",
      "16GB RAM",
      "512GB NVMe SSD",
      '14" FHD Display',
      "Thunderbolt 4",
      "3 Month Back-to-base Warranty",
    ],
    price: "R18 950.00",
  },
  {
    id: 'dell-monitor-p2422h',
    badge: "Special price!",
    badgeTone: "deal",
    name: 'Dell 24" Monitor - P2422H',
    image: monitor1,
    specs: [
      '24" IPS FHD Panel',
      "1920 x 1080 @ 60Hz",
      "HDMI, DisplayPort, VGA",
      "Height adjustable stand",
      "Ultrathin bezels",
    ],
    price: "R2 950.00",
    wasPrice: "R3 600.00",
  },
];

// ============================================
// OPTIMIZED ServiceOrbit COMPONENT
// ============================================
const ServiceOrbit = memo(({ theme }: { theme: "light" | "dark" }) => {
  const getRadius = useCallback(() => {
    if (typeof window === 'undefined') return 155;
    
    const width = window.innerWidth;
    if (width < 400) return 80;
    if (width < 480) return 95;
    if (width < 640) return 110;
    if (width < 768) return 125;
    if (width < 1024) return 140;
    return 155;
  }, []);

  const [radius, setRadius] = useState(() => getRadius());
  const [isMounted, setIsMounted] = useState(false);

  useEffect(() => {
    setIsMounted(true);
    
    let timeoutId: NodeJS.Timeout;
    let rafId: number;
    
    const handleResize = () => {
      cancelAnimationFrame(rafId);
      clearTimeout(timeoutId);
      
      rafId = requestAnimationFrame(() => {
        timeoutId = setTimeout(() => {
          setRadius(getRadius());
        }, 100);
      });
    };

    handleResize();
    window.addEventListener('resize', handleResize, { passive: true });
    
    return () => {
      cancelAnimationFrame(rafId);
      clearTimeout(timeoutId);
      window.removeEventListener('resize', handleResize);
    };
  }, [getRadius]);

  const svgContent = useMemo(() => {
    const containerSize = radius * 2 + 60;
    const maxContainer = Math.min(containerSize, 480);
    const isSmall = radius < 110;

    const serviceAngles = SERVICES.map((_, i) => 
      (i / SERVICES.length) * Math.PI * 2 - Math.PI / 2
    );

    return (
      <div 
        className="relative mx-auto w-full aspect-square orbit-container"
        style={{ 
          maxWidth: maxContainer,
          maxHeight: maxContainer
        }}
      >
        <svg
          viewBox={`0 0 ${containerSize} ${containerSize}`}
          className="absolute inset-0 h-full w-full"
          style={{ color: "#839705" }}
          aria-hidden="true"
        >
          <circle
            cx={containerSize / 2}
            cy={containerSize / 2}
            r={radius}
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeDasharray="6 10"
            className="animate-dash-flow"
          />
          
          <circle
            cx={containerSize / 2}
            cy={containerSize / 2}
            r={radius * 0.68}
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeDasharray="3 12"
            className="animate-dash-flow"
            style={{ animationDirection: "reverse", animationDuration: "9s" }}
          />
          
          {serviceAngles.map((angle, i) => (
            <line
              key={i}
              x1={containerSize / 2}
              y1={containerSize / 2}
              x2={containerSize / 2 + Math.cos(angle) * radius}
              y2={containerSize / 2 + Math.sin(angle) * radius}
              stroke="currentColor"
              strokeWidth="1.5"
              strokeDasharray="4 8"
              className="animate-dash-flow"
              style={{ animationDelay: `${i * 0.4}s` }}
            />
          ))}
        </svg>

        <div className="absolute inset-0 animate-orbit">
          {SERVICES.map((service, i) => {
            const angle = serviceAngles[i];
            const Icon = service.icon;
            const iconSize = isSmall ? 'size-10' : radius < 130 ? 'size-12' : 'size-13';
            const iconInnerSize = isSmall ? 'size-4.5' : radius < 130 ? 'size-5' : 'size-5.5';
            
            return (
              <div
                key={service.label}
                className="absolute left-1/2 top-1/2"
                style={{
                  transform: `translate(-50%, -50%) translate(${Math.cos(angle) * radius}px, ${
                    Math.sin(angle) * radius
                  }px)`,
                }}
              >
                <div className="animate-orbit-counter">
                  <div
                    className={`group flex ${iconSize} items-center justify-center rounded-2xl border transition-transform duration-300 hover:scale-110 ${
                      theme === "light"
                        ? "border-[#D7E2C8] bg-white shadow-[0_8px_30px_rgb(0,0,0,0.06)]"
                        : "border-[#3A4331] bg-[#111111] shadow-[0_8px_30px_rgb(0,0,0,0.3)]"
                    }`}
                    title={service.label}
                  >
                    <Icon className={`${iconInnerSize} text-[#839705]`} aria-hidden="true" />
                    <span className="sr-only">{service.label}</span>
                  </div>
                </div>
              </div>
            );
          })}
        </div>

        <div className="absolute left-1/2 top-1/2 -translate-x-1/2 -translate-y-1/2">
          <span className={`absolute inset-0 rounded-full ${
            theme === "light" ? "bg-[#839705]/30" : "bg-[#839705]/20"
          } animate-pulse-ring`} />
          <span
            className={`absolute inset-0 rounded-full ${
              theme === "light" ? "bg-[#839705]/20" : "bg-[#839705]/10"
            } animate-pulse-ring`}
            style={{ animationDelay: "1.4s" }}
          />
          <div className={`relative flex items-center justify-center overflow-hidden rounded-full border transition-all duration-300 ${
            theme === "light"
              ? "border-[#D7E2C8] bg-white shadow-[0_0_40px_rgba(131,151,5,0.15)]"
              : "border-[#3A4331] bg-[#000000] shadow-[0_0_40px_rgba(131,151,5,0.08)]"
          } animate-float-soft ${
            isSmall ? 'size-16' : radius < 130 ? 'size-20' : 'size-26'
          }`}>
            <img
              src={theme === "dark" ? "/dark-logo.svg" : "/light-logo.svg"}
              alt="Untangled IT Solutions"
              className={`object-contain ${
                isSmall ? 'size-10' : radius < 130 ? 'size-14' : 'size-20'
              }`}
              loading="lazy"
              decoding="async"
            />
          </div>
        </div>
      </div>
    );
  }, [radius, theme]);

  if (!isMounted) {
    return (
      <div className="relative mx-auto w-full max-w-[340px] aspect-square">
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="size-20 rounded-full border-2 border-[#839705]/30 animate-pulse" />
        </div>
      </div>
    );
  }

  return svgContent;
});

ServiceOrbit.displayName = 'ServiceOrbit';

// ============================================
// UPDATED PRODUCT CARD COMPONENT - Matching your design
// ============================================
const ProductCard = memo(({ product, theme }: { product: Product; theme: "light" | "dark" }) => {
  const { cart, addToCart, setCartQty, removeFromCart } = useStore();
  
  const badgeColor = product.badgeTone === 'lime' 
    ? 'bg-[#839705] text-white' 
    : 'bg-[#D97706] text-white';

  // Check if product is in cart
  const isInCart = cart && cart[product.id] !== undefined;
  const cartQuantity = isInCart ? cart[product.id].quantity : 0;

  const handleAddToCart = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    
    console.log('🛒 Adding to cart:', product.name);
    
    // Parse price
    const priceValue = parseFloat(product.price.replace(/[^0-9.]/g, ''));
    console.log('💰 Price:', priceValue);
    
    // Create product data object (matches what store expects)
    const productData = {
      id: product.id,
      name: product.name,
      brand: product.name.split(' ')[0] || 'Dell',
      category: product.name.includes('Monitor') ? 'Monitors' : 'Laptops',
      segment: 'products' as const,
      shortDescription: product.specs.slice(0, 2).join(', '),
      specs: product.specs,
      price: priceValue,
      availability: 'in-stock' as const,
      quoteOnly: false,
      image: product.image,
    };
    
    console.log('📦 Product data:', productData);
    
    // Add to cart with product data
    addToCart(product.id, 1, productData);
  }, [product, addToCart]);

  const handleRemoveFromCart = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    console.log('🗑️ Removing from cart:', product.name);
    removeFromCart(product.id);
  }, [product.id, removeFromCart]);

  const handleIncrement = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    console.log('⬆️ Increasing quantity:', product.name);
    setCartQty(product.id, cartQuantity + 1);
  }, [product.id, cartQuantity, setCartQty]);

  const handleDecrement = useCallback((e: React.MouseEvent) => {
    e.stopPropagation();
    if (cartQuantity > 1) {
      console.log('⬇️ Decreasing quantity:', product.name);
      setCartQty(product.id, cartQuantity - 1);
    } else {
      console.log('🗑️ Removing from cart (quantity 0):', product.name);
      removeFromCart(product.id);
    }
  }, [product.id, cartQuantity, setCartQty, removeFromCart]);

  return (
    <div className={`group relative flex flex-col rounded-xl border p-4 sm:p-5 pt-6 sm:pt-7 transition-all duration-300 hover:-translate-y-1 hover:shadow-lg ${
      theme === "light"
        ? "border-[#D7E2C8] bg-white hover:shadow-[0_8px_30px_rgb(0,0,0,0.08)]"
        : "border-[#3A4331] bg-[#1A1A1A] hover:shadow-[0_8px_30px_rgb(0,0,0,0.3)]"
    }`}>
      {/* Badge */}
      {product.badge && (
        <span className={`absolute -top-2 left-3 z-10 rounded-full px-3 py-0.5 text-[10px] font-bold uppercase tracking-wide shadow-md ${badgeColor}`}>
          {product.badge}
        </span>
      )}
      
      {/* Product Image */}
      <div className="flex items-center justify-center py-3 sm:py-4">
        <img
          src={product.image}
          alt={product.name}
          className="h-24 w-auto object-contain sm:h-28 md:h-32"
          loading="lazy"
        />
      </div>
      
      {/* Product Name */}
      <h3 className={`text-sm font-bold leading-tight ${theme === "light" ? "text-[#111111]" : "text-[#F9FAFB]"}`}>
        {product.name}
      </h3>
      
      {/* Specs List - Using Check icon like your design */}
      <ul className="mt-2 space-y-1 flex-1">
        {product.specs.slice(0, 3).map((spec, i) => (
          <li key={i} className="flex items-start gap-1.5 text-[10px] sm:text-xs text-[#6B7280] dark:text-[#9CA3AF]">
            <Check className="mt-0.5 h-3 w-3 shrink-0 text-[#839705]" />
            <span>{spec}</span>
          </li>
        ))}
        {product.specs.length > 3 && (
          <li className="text-[10px] sm:text-xs text-[#839705] font-semibold mt-0.5">
            +{product.specs.length - 3} more specs ▼
          </li>
        )}
      </ul>
      
      {/* Price Section */}
      <div className="mt-3 border-t border-border pt-3">
        {product.wasPrice && (
          <p className="text-xs text-muted-foreground line-through">
            {product.wasPrice}
          </p>
        )}
        <div className="flex items-baseline gap-2">
          <span className="text-xl font-bold text-[#839705]">{product.price}</span>
          <span className="text-[10px] text-green-600 dark:text-green-400 font-medium">
            In stock
          </span>
        </div>
      </div>
      
      {/* Cart Controls */}
      {isInCart ? (
        <div className="mt-3 flex items-center gap-2">
          <button
            onClick={handleDecrement}
            className="flex h-8 w-8 items-center justify-center rounded-lg border border-[#D7E2C8] text-sm font-semibold hover:bg-gray-50 dark:border-[#3A4331] dark:hover:bg-gray-800"
          >
            -
          </button>
          <span className="w-8 text-center text-sm font-semibold">{cartQuantity}</span>
          <button
            onClick={handleIncrement}
            className="flex h-8 w-8 items-center justify-center rounded-lg bg-[#839705] text-sm font-semibold text-white hover:bg-[#98ab06]"
          >
            +
          </button>
          <button
            onClick={handleRemoveFromCart}
            className="ml-1 text-xs text-red-500 hover:text-red-700 font-medium"
          >
            Remove
          </button>
        </div>
      ) : (
        <button
          onClick={handleAddToCart}
          className={`mt-3 w-full rounded-lg px-4 py-2 text-xs font-semibold transition-all ${
            theme === "light"
              ? "bg-[#839705] text-white hover:bg-[#98ab06] hover:scale-[1.02] active:scale-[0.98]"
              : "bg-[#839705] text-white hover:bg-[#98ab06] hover:scale-[1.02] active:scale-[0.98]"
          }`}
        >
          Add to cart
        </button>
      )}
    </div>
  );
});

ProductCard.displayName = 'ProductCard';

// ============================================
// MEMOIZED SUB-COMPONENTS
// ============================================

// Service Card Component
const ServiceCard = memo(({ 
  icon: Icon, 
  title, 
  body, 
  theme 
}: { 
  icon: any; 
  title: string; 
  body: string; 
  theme: "light" | "dark" 
}) => (
  <article
    className={`group flex flex-col p-4 sm:p-5 md:p-7 transition-colors ${
      theme === "light"
        ? "bg-white hover:bg-[#F7F9F4]"
        : "bg-[#1A1A1A] hover:bg-[#0F0F0F]"
    }`}
  >
    <Icon className={`size-7 sm:size-9 stroke-[1.25] text-[#839705]`} aria-hidden />
    <h3 className={`mt-4 sm:mt-6 md:mt-8 whitespace-pre-line font-bold uppercase leading-snug tracking-wide text-sm sm:text-base ${
      theme === "light" ? "text-[#111111]" : "text-[#F9FAFB]"
    }`}>
      {title}
    </h3>
    <p className={`mt-2 sm:mt-3 text-xs sm:text-sm leading-relaxed ${
      theme === "light" ? "text-[#6B7280]" : "text-[#9CA3AF]"
    }`}>
      {body}
    </p>
    <a
      href="#solutions"
      className={`mt-4 sm:mt-6 md:mt-8 inline-flex items-center gap-2 text-[10px] sm:text-[11px] font-semibold uppercase tracking-[0.18em] text-[#839705]`}
    >
      Learn more
      <ArrowRight className="size-3 sm:size-3.5 transition-transform group-hover:translate-x-1" />
    </a>
  </article>
));

ServiceCard.displayName = 'ServiceCard';

// Stat Item Component
const StatItem = memo(({ stat }: { stat: { value: string; label: string } }) => (
  <div>
    <p className="text-lg sm:text-2xl md:text-3xl font-extrabold">{stat.value}</p>
    <p className="text-[10px] sm:text-sm font-medium opacity-80">{stat.label}</p>
  </div>
));

StatItem.displayName = 'StatItem';

// Contact Item Component
const ContactItem = memo(({ 
  icon: Icon, 
  title, 
  subtitle, 
  href,
  colSpan = false
}: { 
  icon: any; 
  title: string; 
  subtitle: string; 
  href: string;
  colSpan?: boolean;
}) => (
  <a
    href={href}
    className={`flex items-center gap-2 sm:gap-3 rounded-xl bg-white/5 p-2.5 sm:p-4 transition-colors hover:bg-white/10 ${colSpan ? 'sm:col-span-2' : ''}`}
  >
    <span className="grid h-7 w-7 sm:h-10 sm:w-10 shrink-0 place-items-center rounded-full bg-[#839705] text-white">
      <Icon className="h-3.5 w-3.5 sm:h-5 sm:w-5" />
    </span>
    <span className="min-w-0">
      <span className="block text-xs sm:text-sm font-bold">{title}</span>
      <span className="block truncate text-xs sm:text-sm text-white/70">{subtitle}</span>
    </span>
  </a>
));

ContactItem.displayName = 'ContactItem';

// ============================================
// DATA
// ============================================
const offers = [
  {
    icon: Headset,
    title: "IT Support &\nManaged Services",
    body: "Proactive monitoring and a round-the-clock helpdesk that keeps your people working, whatever the day throws at them."
  },
  {
    icon: Cloud,
    title: "Microsoft 365\nSolutions",
    body: "Licensing, migration and day-to-day administration of the productivity suite your team already lives in."
  },
  {
    icon: Laptop,
    title: "Hardware &\nDevices",
    body: "Specified, procured, imaged and delivered — laptops, desktops and peripherals ready on day one."
  },
  {
    icon: Network,
    title: "Network &\nInfrastructure",
    body: "Structured cabling, firewalls, Wi-Fi and cloud infrastructure built to scale without the rebuild."
  },
  {
    icon: ShieldCheck,
    title: "Backup &\nCyber Security",
    body: "Layered protection, tested restores and awareness training so an incident stays an inconvenience."
  },
];

const pillars = [
  { icon: Headset, title: "Fast", sub: "response" },
  { icon: ShieldCheck, title: "Reliable", sub: "& secure" },
  { icon: Users, title: "Expert", sub: "team" },
];

const stats = [
  { value: "150+", label: "Happy clients" },
  { value: "1000+", label: "Devices deployed" },
  { value: "99.9%", label: "Uptime support" },
  { value: "2hr", label: "Average response" },
  { value: "10+", label: "Years experience" },
];

// ============================================
// MAIN COMPONENT
// ============================================
interface HomeProps {
  onNavigate?: (page: string) => void;
}

export default function Home({ onNavigate }: HomeProps) {
  const { theme } = useTheme();
  const { cart, getCartCount } = useStore();
  const [isInView, setIsInView] = useState(false);
  const [isLoading, setIsLoading] = useState(true);
  const trackRef = useRef<HTMLDivElement>(null);

  // Handle loading completion
  const handleLoadingComplete = useCallback(() => {
    setIsLoading(false);
    // Trigger entrance animation
    requestAnimationFrame(() => {
      setIsInView(true);
    });
  }, []);

  // Check if this is a first visit or refresh
  useEffect(() => {
    // Check if we've already shown the loading animation in this session
    const hasLoaded = sessionStorage.getItem('homeLoaded');
    
    if (hasLoaded) {
      // Already loaded this session, skip animation
      setIsLoading(false);
      setIsInView(true);
    } else {
      // First visit or refresh - show animation
      setIsLoading(true);
      // Store in session to skip on next navigation
      sessionStorage.setItem('homeLoaded', 'true');
    }

    // Cleanup on unmount
    return () => {
      // Don't clear sessionStorage on unmount
    };
  }, []);

  const handleNavigation = useCallback((page: string) => {
    if (onNavigate) {
      onNavigate(page);
    }
  }, [onNavigate]);

  const scrollBy = useCallback((dir: 1 | -1) => {
    const track = trackRef.current;
    if (!track) return;
    track.scrollBy({ left: dir * track.clientWidth * 0.8, behavior: "smooth" });
  }, []);

  const heroCheckItems = useMemo(() => 
    ["IT Support", "Hardware", "Microsoft 365", "Network Solutions"].map((item) => (
      <li key={item} className="flex items-center gap-1 sm:gap-2">
        <CheckCircle2 className="h-2.5 w-2.5 sm:h-4 sm:w-4" /> {item}
      </li>
    )),
  []);

  const serviceCards = useMemo(() => 
    offers.map(({ icon, title, body }) => (
      <ServiceCard key={title} icon={icon} title={title} body={body} theme={theme} />
    )),
    [theme]
  );

  const productCards = useMemo(() => 
    products.map((product) => (
      <div
        key={product.id}
        className="w-[85%] shrink-0 snap-start sm:w-[46%] lg:w-[calc(25%-0.94rem)]"
      >
        <ProductCard product={product} theme={theme} />
      </div>
    )),
    [theme]
  );

  const statsElements = useMemo(() => 
    stats.map((stat) => <StatItem key={stat.label} stat={stat} />),
    []
  );

  const partnersList = useMemo(() => 
    [...PARTNERS, ...PARTNERS].map((partner, i) => (
      <span
        key={`${partner}-${i}`}
        className={`text-xs sm:text-base md:text-lg font-bold tracking-wide whitespace-nowrap ${
          theme === "light" ? "text-[#111111]/60" : "text-[#F9FAFB]/60"
        }`}
      >
        {partner}
      </span>
    )),
    [theme]
  );

  const pillarItems = useMemo(() => 
    pillars.map(({ icon: Icon, title, sub }) => (
      <div key={title} className="flex items-center justify-center gap-2 sm:gap-3 px-3 sm:px-6 py-3 sm:py-5">
        <Icon className="h-4 w-4 sm:h-6 sm:w-6 shrink-0 text-[#839705]" />
        <p className={`text-[10px] sm:text-sm font-bold uppercase leading-tight text-center ${
          theme === "light" ? "text-[#111111]" : "text-[#F9FAFB]"
        }`}>
          {title}
          <span className={`block font-medium opacity-70 ${
            theme === "light" ? "text-[#6B7280]" : "text-[#9CA3AF]"
          }`}>{sub}</span>
        </p>
      </div>
    )),
    [theme]
  );

  const cartCount = getCartCount ? getCartCount() : 0;

  // Show loading animation
  if (isLoading) {
    return <LoadingAnimation onComplete={handleLoadingComplete} />;
  }

  return (
    <div className={`flex min-h-screen flex-col ${theme === "light" ? "bg-white" : "bg-black"}`}>
      <main className="min-h-screen">
        
        {/* ============================================================
            HERO SECTION
            ============================================================ */}
        <section className="relative isolate flex min-h-[550px] sm:min-h-[650px] items-start sm:items-center pt-20 sm:pt-0 pb-10 sm:pb-0 overflow-hidden">
          <div className="absolute inset-0 -z-10" aria-hidden="true">
            <img
              src={theme === "dark" ? showcaseBgDark : showcaseBgLight}
              alt="ICT Showcase"
              className="h-full w-full object-cover object-center animate-slow-pan"
              loading="lazy"
              decoding="async"
              fetchPriority="high"
            />
            <div className="absolute inset-0 bg-gradient-to-r from-[#0B0F04]/90 via-[#0B0F04]/55 to-[#839705]/10" />
            <div className="absolute inset-x-0 bottom-0 h-40 bg-gradient-to-t from-black/80 to-transparent" />
            <span className="pointer-events-none absolute inset-y-0 -left-1/3 w-1/3 skew-x-12 bg-white/15 blur-3xl animate-sheen" />
          </div>

          <div className="relative w-full py-0 sm:py-12 lg:py-20">
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-0 sm:gap-6 lg:gap-10 items-start lg:items-center max-w-6xl mx-auto px-3 sm:px-6 lg:px-8">
              
              {/* Left Content */}
              <div className={`pt-0 sm:pt-0 text-left transition-all duration-1000 ${
                isInView ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'
              }`}>
                
                <h1 className={`text-xl xs:text-2xl sm:text-4xl md:text-5xl lg:text-6xl font-extrabold uppercase leading-[1.05] sm:leading-[1.02] text-left drop-shadow-[0_2px_20px_rgba(0,0,0,0.35)] ${
                  theme === "light" ? "text-white" : "text-[#F9FAFB]"
                }`}>
                  Smart IT solutions
                  <br />
                  for a <span className="text-[#C9E265]">smarter future</span>
                </h1>
                
                <p className={`mt-1 sm:mt-5 max-w-lg text-[10px] xs:text-xs sm:text-sm md:text-base font-medium text-left opacity-80 ${
                  theme === "light" ? "text-white/80" : "text-[#9CA3AF]"
                }`}>
                  We help businesses stay connected, secure and productive with reliable IT support,
                  hardware, licensing and cloud solutions.
                </p>
                
                <ul className="mt-1.5 sm:mt-6 flex flex-wrap gap-x-2 sm:gap-x-6 gap-y-0.5 sm:gap-y-2 text-[10px] xs:text-xs sm:text-sm font-semibold text-white">
                  {heroCheckItems}
                </ul>
                
                <div className="mt-2 sm:mt-8 flex flex-wrap gap-2 sm:gap-3 justify-start">
                  <a
                    href="#services"
                    className="rounded-xl bg-[#839705] px-3 sm:px-6 py-1.5 sm:py-3 text-[10px] xs:text-xs sm:text-sm font-semibold text-white shadow-[0_10px_40px_rgba(131,151,5,0.45)] transition-transform hover:-translate-y-0.5 hover:bg-[#98ab06]"
                  >
                    Our services <ArrowRight className="ml-1 h-3 w-3 sm:h-4 sm:w-4 inline" />
                  </a>
                  
                  <button
                    onClick={() => handleNavigation('products')}
                    className="inline-flex items-center gap-1.5 sm:gap-2 rounded-xl border border-white/30 bg-white/10 px-3 sm:px-6 py-1.5 sm:py-3 text-[10px] xs:text-xs sm:text-sm font-semibold text-white backdrop-blur-sm transition-colors hover:bg-white/20"
                  >
                    <ShoppingCart className="h-3 w-3 sm:h-4 sm:w-4" /> View products
                  </button>
                </div>
              </div>

              {/* Right Column - Orbit with badge */}
              <div className={`flex flex-col items-center justify-center w-full transition-all duration-1000 delay-150 mt-0 sm:mt-0 ${
                isInView ? 'opacity-100 translate-y-0' : 'opacity-0 translate-y-8'
              }`}>
                <div className="relative w-full flex flex-col lg:block items-center">
                  <div className="w-full max-w-[190px] xs:max-w-[230px] sm:max-w-[340px] md:max-w-[400px] lg:max-w-[440px] mx-auto">
                    <ServiceOrbit theme={theme} />
                  </div>
                  
                  <div className="mt-6 sm:mt-8 lg:mt-0 lg:absolute lg:top-[95%] lg:-translate-y-1/2 lg:right-[-100px] w-full lg:w-auto flex justify-center">
                    <div className={`rounded-xl p-2 xs:p-2.5 sm:p-3.5 text-center min-w-[110px] xs:min-w-[140px] sm:min-w-[180px] shadow-lg ${
                      theme === "light"
                        ? "bg-white/95 backdrop-blur-sm shadow-[0_8px_30px_rgba(0,0,0,0.15)] border-2 border-[#839705]/30"
                        : "bg-black/90 backdrop-blur-sm shadow-[0_8px_30px_rgba(0,0,0,0.5)] border-2 border-[#3A4331]"
                    }`}>
                      <ShieldCheck className={`mx-auto h-3.5 w-3.5 xs:h-4 xs:w-4 sm:h-6 sm:w-6 text-[#839705]`} />
                      <p className={`mt-0.5 text-[8px] xs:text-[9px] sm:text-xs font-bold uppercase tracking-wide leading-tight ${
                        theme === "light" ? "text-[#111111]" : "text-[#F9FAFB]"
                      }`}>
                        Trusted IT partner
                      </p>
                      <p className={`text-[6px] xs:text-[7px] sm:text-[9px] leading-tight mt-0.5 ${
                        theme === "light" ? "text-[#6B7280]" : "text-[#9CA3AF]"
                      }`}>
                        For businesses across South Africa.
                      </p>
                    </div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        </section>

        {/* ============================================================
            PILLARS SECTION
            ============================================================ */}
        <div className="max-w-6xl mx-auto px-3 sm:px-6 lg:px-8 -mt-8 sm:-mt-16 md:-mt-20 relative z-10">
          <div className={`grid divide-y rounded-xl shadow-[0_8px_30px_rgb(0,0,0,0.08)] sm:grid-cols-3 sm:divide-x sm:divide-y-0 border max-w-2xl mx-auto ${
            theme === "light"
              ? "divide-[#D7E2C8] bg-white border-[#D7E2C8]"
              : "divide-[#3A4331] bg-[#1A1A1A] border-[#3A4331]"
          }`}>
            {pillarItems}
          </div>
        </div>

        <div className="h-0 sm:h-3 md:h-4" aria-hidden="true" />

        {/* ============================================================
            WHAT WE DO
            ============================================================ */}
        <section className={`w-full border-b-8 border-[#839705] -mt-2 sm:-mt-4 ${
          theme === "light" ? "bg-[#F7F9F4]" : "bg-[#0F0F0F]"
        }`}>
          <div className="max-w-6xl mx-auto px-3 sm:px-6 lg:px-8">
            <div className="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-3 sm:gap-6 py-3 sm:py-6 md:py-8">
              <div>
                <span className="text-[10px] sm:text-xs font-semibold uppercase tracking-[0.28em] text-[#839705]">
                  What we do
                </span>
                <h2 className={`mt-2 sm:mt-3 font-extrabold uppercase leading-[1.1] tracking-tight text-lg sm:text-2xl md:text-3xl lg:text-4xl ${
                  theme === "light" ? "text-[#111111]" : "text-[#F9FAFB]"
                }`}>
                  Complete IT solutions
                  <br />
                  for <span className="text-[#839705]">your business</span>
                </h2>
              </div>
              <a
                href="#solutions"
                className={`inline-flex w-fit items-center gap-2 border ${
                  theme === "light" 
                    ? "border-[#111111]/40 text-[#111111] hover:border-[#839705] hover:text-[#839705]" 
                    : "border-[#F9FAFB]/40 text-[#F9FAFB] hover:border-[#839705] hover:text-[#839705]"
                } px-4 sm:px-6 py-2 sm:py-3 text-[10px] sm:text-xs font-semibold uppercase tracking-[0.18em] transition-colors`}
              >
                View all services
                <ArrowRight className="size-3 sm:size-4" />
              </a>
            </div>

            <div className="grid gap-px bg-[#D7E2C8] dark:bg-[#3A4331] grid-cols-1 sm:grid-cols-2 lg:grid-cols-5">
              {serviceCards}
            </div>
          </div>
        </section>

        <div className="h-0 sm:h-3 md:h-4" aria-hidden="true" />

        {/* ============================================================
            FEATURED PRODUCTS
            ============================================================ */}
        <section className={`w-full ${theme === "light" ? "bg-white" : "bg-black"}`}>
          <div className="max-w-7xl mx-auto px-3 sm:px-6 lg:px-8 py-2 sm:py-4">
            <div className="flex flex-wrap items-end justify-between gap-4 sm:gap-6">
              <div>
                <span className={`text-[10px] sm:text-xs font-bold uppercase tracking-[0.35em] text-[#839705]`}>
                  Featured products
                </span>
                <h2 className={`mt-2 sm:mt-3 font-extrabold uppercase leading-[0.95] tracking-tight text-xl sm:text-3xl md:text-4xl ${
                  theme === "light" ? "text-[#111111]" : "text-[#F9FAFB]"
                }`}>
                  Quality devices.
                  <br />
                  <span className="text-[#839705]">Great prices.</span>
                </h2>
              </div>

              <div className="flex items-center gap-4">
                {/* Cart count indicator */}
                {cartCount > 0 && (
                  <button
                    onClick={() => handleNavigation('cart')}
                    className={`flex items-center gap-2 rounded-full px-3 py-1.5 text-sm font-semibold transition-all hover:scale-105 ${
                      theme === "light"
                        ? "bg-[#839705]/10 text-[#839705] hover:bg-[#839705]/20"
                        : "bg-[#839705]/20 text-[#839705] hover:bg-[#839705]/30"
                    }`}
                  >
                    <ShoppingCart className="h-4 w-4" />
                    <span>{cartCount} items</span>
                  </button>
                )}
                
                <div className="flex gap-2">
                  <button
                    onClick={() => scrollBy(-1)}
                    aria-label="Previous products"
                    className={`flex size-8 sm:size-10 items-center justify-center border transition-colors ${
                      theme === "light"
                        ? "border-[#D7E2C8] bg-white hover:border-[#839705] hover:text-[#839705]"
                        : "border-[#3A4331] bg-[#1A1A1A] hover:border-[#839705] hover:text-[#839705]"
                    }`}
                  >
                    <ChevronLeft className="size-4 sm:size-5" />
                  </button>
                  <button
                    onClick={() => scrollBy(1)}
                    aria-label="Next products"
                    className={`flex size-8 sm:size-10 items-center justify-center border transition-colors ${
                      theme === "light"
                        ? "border-[#D7E2C8] bg-white hover:border-[#839705] hover:text-[#839705]"
                        : "border-[#3A4331] bg-[#1A1A1A] hover:border-[#839705] hover:text-[#839705]"
                    }`}
                  >
                    <ChevronRightIcon className="size-4 sm:size-5" />
                  </button>
                </div>
              </div>
            </div>

            <div
              ref={trackRef}
              className="mt-6 sm:mt-10 flex snap-x snap-mandatory gap-3 sm:gap-5 overflow-x-auto pb-4 [scrollbar-width:none] [&::-webkit-scrollbar]:hidden"
            >
              {productCards}
            </div>
          </div>
        </section>

        <div className="h-6 sm:h-12 md:h-16" aria-hidden="true" />

        {/* ============================================================
            STATS SECTION
            ============================================================ */}
        <section className="bg-[#839705] px-3 sm:px-6 py-6 sm:py-10 text-white">
          <div className="mx-auto grid max-w-6xl gap-3 sm:gap-6 text-center grid-cols-2 sm:grid-cols-3 lg:grid-cols-5">
            {statsElements}
          </div>
        </section>

        {/* ============================================================
            CONTACT / CTA SECTION
            ============================================================ */}
        <section className="w-full bg-black text-white py-10 sm:py-16">
          <div className="max-w-6xl mx-auto px-3 sm:px-6 lg:px-8">
            <div className="grid gap-5 sm:gap-8 lg:grid-cols-[1fr_1.2fr] lg:items-center">
              <div>
                <h2 className="text-xl sm:text-3xl font-extrabold">
                  Let&rsquo;s <span className="text-[#839705]">Untangle</span> Your IT.
                </h2>
                <p className="mt-2 sm:mt-4 max-w-xl text-white/70 text-sm sm:text-base">
                  Get in touch today for a free consultation and see how we can help your business grow.
                </p>
                <div className="mt-3 sm:mt-6 flex flex-wrap gap-2 sm:gap-3">
                  <a href="#contact" className="rounded-xl bg-[#839705] px-3.5 sm:px-6 py-2 sm:py-3 text-xs sm:text-sm font-semibold text-white hover:bg-[#98ab06] transition-colors">
                    Book a consultation
                  </a>
                  <a href="#about" className="rounded-xl border border-white/30 bg-white/10 px-3.5 sm:px-6 py-2 sm:py-3 text-xs sm:text-sm font-semibold text-white backdrop-blur-sm hover:bg-white/20 transition-colors">
                    About us
                  </a>
                </div>
              </div>
              <div className="grid gap-2.5 sm:gap-4 grid-cols-1 sm:grid-cols-2">
                <ContactItem
                  icon={Phone}
                  title="Call us"
                  subtitle="+27 12 345 6789"
                  href="tel:+27123456789"
                />
                <ContactItem
                  icon={Mail}
                  title="Email us"
                  subtitle="siyanda.nkosi.developer@gmail.com"
                  href="mailto:siyanda.nkosi.developer@gmail.com"
                />
                <ContactItem
                  icon={MessageCircle}
                  title="Send an enquiry"
                  subtitle="We reply within one business day"
                  href="#contact"
                  colSpan={true}
                />
              </div>
            </div>
          </div>
        </section>

        {/* ============================================================
            OEM PARTNERS SECTION
            ============================================================ */}
        <section className={`w-full border-y ${
          theme === "light"
            ? "border-[#D7E2C8] bg-white"
            : "border-[#3A4331] bg-black"
        }`}>
          <div className="max-w-6xl mx-auto px-3 sm:px-6 lg:px-8 py-5 sm:py-10">
            <p className={`text-center text-[8px] sm:text-xs font-semibold uppercase tracking-[0.15em] sm:tracking-[0.3em] ${
              theme === "light" ? "text-[#6B7280]" : "text-[#9CA3AF]"
            }`}>
              Our OEM partners
            </p>
            <div className="mt-3 sm:mt-6 overflow-hidden">
              <div className="flex w-max animate-marquee gap-4 sm:gap-8 md:gap-12 pr-4 sm:pr-8 md:pr-12">
                {partnersList}
              </div>
            </div>
          </div>
        </section>
      </main>
    </div>
  );
}
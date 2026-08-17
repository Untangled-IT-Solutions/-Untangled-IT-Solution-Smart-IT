// src/components/header.tsx
import { useState } from "react";
import { Menu, Moon, Sun, X, ShoppingCart, FileText, PackageSearch } from "lucide-react";
import { useTheme } from "../context/ThemeContext";
import { useStore } from "../lib/store-context";

interface HeaderProps {
  onNavigate: (page: 'home' | 'products' | 'refurbished' | 'software' | 'support' | 'solutions' | 'help-me-choose' | 'cart' | 'checkout' | 'quote' | 'track-quote') => void;
  onRequestQuote: () => void;
  currentPage: 'home' | 'products' | 'refurbished' | 'software' | 'support' | 'solutions' | 'help-me-choose' | 'cart' | 'checkout' | 'quote' | 'track-quote';
}

const NAV_ITEMS = [
  { label: "Home", page: "home" },
  { label: "Products", page: "products" },
  { label: "Refurbished", page: "refurbished" },
  { label: "Software", page: "software" },
  { label: "Support", page: "support" },
  { label: "Solutions", page: "solutions" },
  { label: "Help", page: "help-me-choose" },
];

export default function Header({ onNavigate, onRequestQuote, currentPage }: HeaderProps) {
  const { theme, toggle } = useTheme();
  const [open, setOpen] = useState(false);
  const store = useStore();

  const handleNavigation = (page: any) => {
    onNavigate(page);
    setOpen(false);
  };

  // Determine if we're on the home page to apply transparent styling
  const isHome = currentPage === 'home';

  return (
    <header 
      className={`w-full transition-all duration-300 ${
        isHome 
          ? 'absolute top-0 left-0 right-0 z-50 bg-transparent' 
          : theme === "light" 
            ? 'bg-white border-b border-[#D7E2C8]' 
            : 'bg-black border-b border-[#3A4331]'
      }`}
    >
      <div className="px-2 sm:px-4">
        <div className="flex items-center justify-between h-24">
          
          {/* Brand - Updated Logo Logic */}
          <button 
            onClick={() => handleNavigation('home')}
            className="flex items-center shrink-0 cursor-pointer"
          >
            {/* 
              Rule:
              1. Home Page (Any Theme): Use transparent icon (logos-trans.svg or logo-white.svg on dark)
              2. Internal Pages (Dark Mode): Use white icon (logo-white.svg)
              3. Internal Pages (Light Mode): Use full logo with text (logo-full.png)
            */}
            <img
              src={
                isHome 
                  ? (theme === "dark" ? "/logo-white.svg" : "/logos-trans.svg")
                  : (theme === "dark" ? "/logo-white.svg" : "/logo-transparent.svg")
              }
              alt="Untangled IT Solutions"
              className="h-20 w-auto sm:h-24 md:h-28 object-contain"
            />
          </button>

          {/* Desktop Navigation */}
          <nav className="hidden md:flex items-center gap-1">
            {NAV_ITEMS.map((item) => {
              if (currentPage === item.page) return null;
              
              return (
                <button
                  key={item.label}
                  onClick={() => handleNavigation(item.page)}
                  className={`rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                    currentPage === item.page
                      ? "text-[#839705]"
                      : isHome
                        ? "text-white hover:bg-white/10 hover:text-white"
                        : theme === "light" 
                          ? "text-gray-700 hover:bg-[#839705]/10 hover:text-[#839705]" 
                          : "text-white hover:bg-white/10 hover:text-white"
                  }`}
                >
                  {item.label}
                </button>
              );
            })}
          </nav>

          {/* Actions */}
          <div className="flex items-center gap-2">
            <button
              onClick={toggle}
              aria-label="Toggle theme"
              className={`rounded-lg p-2 transition-colors ${
                isHome
                  ? "text-white hover:bg-white/10 hover:text-white"
                  : theme === "light" 
                    ? "text-gray-700 hover:bg-[#839705]/10 hover:text-[#839705]" 
                    : "text-white hover:bg-white/10 hover:text-white"
              }`}
            >
              {theme === "light" ? <Moon className="h-5 w-5" /> : <Sun className="h-5 w-5" />}
            </button>

            {/* Shopping Cart Button with count */}
            <button
              onClick={() => handleNavigation('cart')}
              className={`relative rounded-lg p-2 transition-colors ${
                isHome
                  ? "text-white hover:bg-white/10 hover:text-white"
                  : theme === "light" 
                    ? "text-gray-700 hover:bg-[#839705]/10 hover:text-[#839705]" 
                    : "text-white hover:bg-white/10 hover:text-white"
              }`}
            >
              <ShoppingCart className="h-5 w-5" />
              {store.cartCount > 0 && (
                <span className={`absolute -right-1 -top-1 grid h-5 min-w-5 place-items-center rounded-full px-1 text-xs font-bold ${
                  isHome
                    ? "bg-[#839705] text-white"
                    : theme === "light"
                      ? "bg-[#839705] text-white"
                      : "bg-white text-black"
                }`}>
                  {store.cartCount}
                </span>
              )}
            </button>

            {/* Track Quote Button - ALWAYS VISIBLE */}
            <button
              onClick={() => handleNavigation('track-quote')}
              className={`relative inline-flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                isHome
                  ? "text-white hover:bg-white/10 hover:text-white"
                  : theme === "light" 
                    ? "text-gray-700 hover:bg-[#839705]/10 hover:text-[#839705]" 
                    : "text-white hover:bg-white/10 hover:text-white"
              }`}
            >
              <PackageSearch className="h-5 w-5" />
              <span>Quote track</span>
              {store.quoteCount > 0 && (
                <span className={`absolute -right-1 -top-1 grid h-5 min-w-5 place-items-center rounded-full px-1 text-xs font-bold ${
                  isHome
                    ? "bg-[#839705] text-white"
                    : theme === "light"
                      ? "bg-[#839705] text-white"
                      : "bg-white text-black"
                }`}>
                  {store.quoteCount}
                </span>
              )}
            </button>

            {/* Request a Quote button */}
            <button
              onClick={onRequestQuote}
              className={`relative hidden xl:inline-flex rounded-lg px-4 py-2 text-sm font-semibold transition-colors items-center gap-2 ${
                isHome
                  ? "bg-[#839705] text-white hover:bg-[#98ab06]"
                  : theme === "light" 
                    ? "bg-[#839705] text-white hover:bg-[#98ab06]" 
                    : "bg-white text-black hover:bg-gray-200"
              }`}
            >
              <FileText className="h-4 w-4" />
              Request a Quote
              {store.quoteCount > 0 && (
                <span className={`absolute -top-2 -right-2 grid h-5 min-w-5 place-items-center rounded-full px-1 text-xs font-bold ${
                  isHome
                    ? "bg-red-500 text-white"
                    : theme === "light"
                      ? "bg-red-500 text-white"
                      : "bg-red-400 text-black"
                }`}>
                  {store.quoteCount}
                </span>
              )}
            </button>

            <button
              onClick={() => setOpen((o) => !o)}
              aria-label="Toggle menu"
              aria-expanded={open}
              className={`rounded-lg p-2 transition-colors md:hidden ${
                isHome
                  ? "text-white hover:bg-white/10 hover:text-white"
                  : theme === "light" 
                    ? "text-gray-700 hover:bg-[#839705]/10 hover:text-[#839705]" 
                    : "text-white hover:bg-white/10 hover:text-white"
              }`}
            >
              {open ? <X className="h-5 w-5" /> : <Menu className="h-5 w-5" />}
            </button>
          </div>
        </div>

        {/* Mobile menu */}
        {open && (
          <div className={`border-t pt-4 pb-6 md:hidden ${
            isHome
              ? "border-white/20 bg-black/80 backdrop-blur-md"
              : theme === "light" 
                ? "border-gray-200 bg-white"
                : "border-white/20 bg-black"
          }`}>
            <nav className="flex flex-col gap-1">
              {NAV_ITEMS.map((item) => (
                <button
                  key={item.label}
                  onClick={() => {
                    handleNavigation(item.page);
                    setOpen(false);
                  }}
                  className={`rounded-lg px-4 py-3 text-base font-medium transition-colors text-left ${
                    currentPage === item.page
                      ? "text-[#839705]"
                      : isHome
                        ? "text-white hover:bg-white/10 hover:text-white"
                        : theme === "light" 
                          ? "text-gray-700 hover:bg-[#839705]/10 hover:text-[#839705]" 
                          : "text-white hover:bg-white/10 hover:text-white"
                  }`}
                >
                  {item.label}
                </button>
              ))}
            </nav>
            
            <div className="mt-4 flex flex-col gap-3">
              <button
                onClick={() => {
                  handleNavigation('cart');
                  setOpen(false);
                }}
                className={`rounded-lg px-4 py-3 text-center text-base font-semibold transition-colors inline-flex items-center justify-center gap-2 ${
                  isHome
                    ? "border border-white/30 bg-white/10 text-white backdrop-blur-sm hover:bg-white/20"
                    : theme === "light" 
                      ? "border border-[#D7E2C8] bg-white text-[#111111] hover:bg-[#EEF3E7]" 
                      : "border border-[#3A4331] bg-[#111111] text-[#F9FAFB] hover:bg-[#2A2E24]"
                }`}
              >
                <ShoppingCart className="h-4 w-4" />
                Cart ({store.cartCount} items)
              </button>
              
              <button
                onClick={() => {
                  handleNavigation('track-quote');
                  setOpen(false);
                }}
                className={`rounded-lg px-4 py-3 text-center text-base font-semibold transition-colors inline-flex items-center justify-center gap-2 ${
                  isHome
                    ? "border border-white/30 bg-white/10 text-white backdrop-blur-sm hover:bg-white/20"
                    : theme === "light" 
                      ? "border border-[#D7E2C8] bg-white text-[#111111] hover:bg-[#EEF3E7]" 
                      : "border border-[#3A4331] bg-[#111111] text-[#F9FAFB] hover:bg-[#2A2E24]"
                }`}
              >
                <PackageSearch className="h-4 w-4" />
                Quote track
                {store.quoteCount > 0 && (
                  <span className="ml-1 text-xs font-bold text-[#839705]">
                    ({store.quoteCount})
                  </span>
                )}
              </button>
              
              <button
                onClick={() => {
                  onRequestQuote();
                  setOpen(false);
                }}
                className={`relative rounded-lg px-4 py-3 text-center text-base font-semibold transition-colors inline-flex items-center justify-center gap-2 ${
                  isHome
                    ? "bg-[#839705] text-white hover:bg-[#98ab06]"
                    : theme === "light" 
                      ? "bg-[#839705] text-white hover:bg-[#98ab06]" 
                      : "bg-white text-black hover:bg-gray-200"
                }`}
              >
                <FileText className="h-4 w-4" />
                Request a Quote
                {store.quoteCount > 0 && (
                  <span className={`absolute -top-2 -right-2 grid h-5 min-w-5 place-items-center rounded-full px-1 text-xs font-bold ${
                    isHome
                      ? "bg-red-500 text-white"
                      : theme === "light"
                        ? "bg-red-500 text-white"
                        : "bg-red-400 text-black"
                  }`}>
                    {store.quoteCount}
                  </span>
                )}
              </button>
            </div>
          </div>
        )}
      </div>
    </header>
  );
}
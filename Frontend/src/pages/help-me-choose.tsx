// src/pages/help-me-choose.tsx
import { ArrowRight } from "lucide-react";
import { useTheme } from "../context/ThemeContext";
import type { Page } from "../lib/navigation";

interface HelpOption {
  label: string;
  page: Page;
  description: string;
}

const HELP_OPTIONS: HelpOption[] = [
  { label: "I want to buy a product", page: "products", description: "Browse our IT products store" },
  { label: "I need computers for my business", page: "refurbished", description: "View refurbished devices" },
  { label: "I need something developed", page: "software", description: "Software & web development" },
  { label: "I have a computer or IT problem", page: "support", description: "Technical support" },
  { label: "I need a complete IT solution", page: "solutions", description: "IT infrastructure & business solutions" },
  { label: "I want to request a quote", page: "quote", description: "Get a quote for multiple items" },
];

interface HelpMeChoosePageProps {
  onNavigate?: (page: Page) => void;
  onRequestQuote?: () => void;
}

export default function HelpMeChoosePage({ onNavigate, onRequestQuote }: HelpMeChoosePageProps) {
  const { theme } = useTheme();

  const handleClick = (option: HelpOption) => {
    if (option.page === 'quote' && onRequestQuote) {
      onRequestQuote();
    } else if (onNavigate) {
      onNavigate(option.page);
    }
  };

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <header className="space-y-1.5">
        <p className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Not sure what you need?
        </p>
        <h1 className="text-3xl font-black tracking-tight sm:text-4xl text-foreground">
          Help Me Choose
        </h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          Tell us what you're trying to achieve and we'll help you find the right solution.
        </p>
      </header>

      <h2 className="mt-8 text-xl font-extrabold text-foreground">What are you looking for?</h2>
      <div className="mt-4 grid gap-3">
        {HELP_OPTIONS.map((option) => (
          <button
            key={option.label}
            onClick={() => handleClick(option)}
            className={`grid grid-cols-[minmax(0,1fr)_auto] items-center gap-4 rounded-2xl border p-5 transition-colors ${
              theme === "light"
                ? "border-[#D7E2C8] bg-white hover:bg-[#EEF3E7]"
                : "border-[#3A4331] bg-[#1A1A1A] hover:bg-[#2A2E24]"
            }`}
          >
            <span className="min-w-0">
              <span className="block text-base font-bold text-foreground">{option.label}</span>
              <span className="mt-0.5 block text-sm text-muted-foreground">{option.description}</span>
            </span>
            <ArrowRight className="h-5 w-5 shrink-0 text-[#839705]" />
          </button>
        ))}
      </div>

      <div className={`mt-6 rounded-2xl p-4 text-sm ${
        theme === "light" ? "bg-[#F7F9F4]" : "bg-[#1A1A1A]"
      }`}>
        <p className="text-muted-foreground">
          Still stuck? Send a quote request describing what you're trying to achieve — quotes are free and we respond within 24 hours.{" "}
          <button onClick={() => onRequestQuote?.()} className="font-semibold text-[#839705] hover:underline">
            Open a quote request
          </button>
          .
        </p>
      </div>
    </div>
  );
}

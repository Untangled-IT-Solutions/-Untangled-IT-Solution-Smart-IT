// src/lib/catalog.ts
export type Category = "refurbished" | "accessories" | "software" | "services";

export interface CatalogItem {
  id: string;
  name: string;
  category: Category;
  blurb: string;
  from: number | null;
  unit?: string;
  tags: string[];
}

export const CATEGORY_LABELS: Record<Category, string> = {
  refurbished: "Refurbished Devices",
  accessories: "Accessories & Repairs",
  software: "Software Development",
  services: "Technical Services",
};

export const CATALOG: CatalogItem[] = [
  {
    id: "rf-lat-5400",
    name: 'Dell Latitude 5400 · i5 · 8GB · 256GB SSD · 14"',
    category: "refurbished",
    blurb: "Grade A business laptop, 6-month warranty, Windows 11 Pro installed.",
    from: 5499,
    unit: "per unit",
    tags: ["Grade A", "6mo warranty"],
  },
  {
    id: "rf-hp-elitebook",
    name: 'HP EliteBook 840 G6 · i7 · 16GB · 512GB SSD · 14"',
    category: "refurbished",
    blurb: "Power user spec, tested battery above 80% health.",
    from: 8299,
    unit: "per unit",
    tags: ["Grade A", "i7"],
  },
  {
    id: "rf-lenovo-tiny",
    name: "Lenovo ThinkCentre M720 Tiny Desktop · i5 · 8GB · 256GB",
    category: "refurbished",
    blurb: "Compact office desktop, ideal for reception and call-centre rollouts.",
    from: 3999,
    unit: "per unit",
    tags: ["Bulk friendly"],
  },
  {
    id: "rf-monitor-24",
    name: '24" Refurbished LED Monitor (Dell / HP)',
    category: "refurbished",
    blurb: "Full HD, tested panels, stand and power cable included.",
    from: 1099,
    unit: "per unit",
    tags: ["Bulk friendly"],
  },
  {
    id: "rf-server-node",
    name: "Refurbished Rack Server · Dell PowerEdge R640",
    category: "refurbished",
    blurb: "Dual Xeon configurations, built to your RAM and storage spec.",
    from: 24999,
    unit: "per unit",
    tags: ["Made to spec"],
  },
  {
    id: "ac-dock",
    name: "USB-C Docking Station · Dual Display",
    category: "accessories",
    blurb: "100W power delivery, HDMI + DisplayPort, gigabit ethernet.",
    from: 1499,
    unit: "per unit",
    tags: ["New stock"],
  },
  {
    id: "ac-kbm",
    name: "Wireless Keyboard & Mouse Combo",
    category: "accessories",
    blurb: "Quiet keys, 2.4GHz receiver, ideal for office rollouts.",
    from: 349,
    unit: "per unit",
    tags: ["New stock"],
  },
  {
    id: "ac-ups",
    name: "Eaton 850VA Line-Interactive UPS",
    category: "accessories",
    blurb: "Keeps routers and workstations alive through load-shedding dips.",
    from: 1899,
    unit: "per unit",
    tags: ["Load-shedding"],
  },
  {
    id: "ac-screen-repair",
    name: "Laptop Screen Replacement",
    category: "accessories",
    blurb: 'Most 13"-15.6" panels in stock, same-day turnaround where possible.',
    from: 1250,
    unit: "per repair",
    tags: ["Repair"],
  },
  {
    id: "ac-battery",
    name: "Battery Replacement & Health Check",
    category: "accessories",
    blurb: "OEM-equivalent batteries with a 6-month warranty.",
    from: 890,
    unit: "per repair",
    tags: ["Repair"],
  },
  {
    id: "sw-website",
    name: "Business Website / Landing Site",
    category: "software",
    blurb: "Responsive marketing site, CMS, SEO setup and hosting handover.",
    from: 12000,
    unit: "from",
    tags: ["2-4 weeks"],
  },
  {
    id: "sw-webapp",
    name: "Custom Web Application",
    category: "software",
    blurb: "Dashboards, portals and internal tools with user accounts and roles.",
    from: null,
    tags: ["Scoped per project"],
  },
  {
    id: "sw-mobile",
    name: "Mobile App (Android / iOS)",
    category: "software",
    blurb: "Cross-platform build, store submission and post-launch support.",
    from: null,
    tags: ["Scoped per project"],
  },
  {
    id: "sw-integration",
    name: "System Integration & Automation",
    category: "software",
    blurb: "Connect accounting, CRM, stock and reporting systems into one flow.",
    from: null,
    tags: ["Scoped per project"],
  },
  {
    id: "sv-network",
    name: "Network Design, Cabling & Wi-Fi",
    category: "services",
    blurb: "Site survey, structured cabling, switching and access point rollout.",
    from: null,
    tags: ["Site survey"],
  },
  {
    id: "sv-cctv",
    name: "CCTV & Access Control Installation",
    category: "services",
    blurb: "Hikvision-backed surveillance, remote viewing and access control.",
    from: null,
    tags: ["On-site"],
  },
  {
    id: "sv-support",
    name: "Managed IT Support (Monthly Retainer)",
    category: "services",
    blurb: "Helpdesk, patching, backups and monitoring for your team.",
    from: 3500,
    unit: "per month",
    tags: ["Retainer"],
  },
  {
    id: "sv-euc",
    name: "End User Computing Rollout & Imaging",
    category: "services",
    blurb: "Imaging, asset tagging, onboarding and delivery to your sites.",
    from: null,
    tags: ["Per device"],
  },
];

export const WHATSAPP_NUMBER = "27116646500";
export const PHONE_DISPLAY = "011 664 6500";
export const SALES_EMAIL = "sales@untangledits.co.za";

export function formatZar(value: number) {
  return `R${value.toLocaleString("en-ZA")}`;
}
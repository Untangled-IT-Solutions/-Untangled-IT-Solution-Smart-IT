// src/pages/support.tsx
import { useState } from "react";
import { CheckCircle2, Mail, ArrowLeft, Laptop, MapPin, Info } from "lucide-react";
import { useTheme } from "../context/ThemeContext";
import { SALES_EMAIL } from "../lib/catalog";

const SUPPORT_SERVICES = [
  { id: "hardware-troubleshooting", name: "Hardware Troubleshooting", description: "Something not working? We diagnose the hardware." },
  { id: "software-troubleshooting", name: "Software Troubleshooting", description: "Errors, crashes, updates and application problems." },
  { id: "laptop-repair", name: "Laptop Repair", description: "Screens, keyboards, batteries, hinges and ports." },
  { id: "hardware-replacement", name: "Hardware Replacement", description: "Replace failed parts or whole devices quickly." },
  { id: "device-diagnostics", name: "Device Diagnostics", description: "Full health check before you spend on repairs." },
  { id: "endpoint-support", name: "Endpoint Support", description: "Ongoing support for staff laptops and desktops." },
  { id: "it-consulting-support", name: "IT Consulting", description: "Advice on what to buy, replace or change." },
  { id: "technical-support", name: "Technical Support", description: "General technical help for your team." },
  { id: "device-deployment-support", name: "Device Deployment", description: "Setup, imaging and handover of new devices." },
  { id: "lifecycle-support", name: "Lifecycle Support", description: "Manage devices from purchase to retirement." },
];

export default function SupportPage() {
  const { theme } = useTheme();
  const [selected, setSelected] = useState<string | null>(null);
  const [done, setDone] = useState(false);
  const [formData, setFormData] = useState({
    name: "",
    company: "",
    email: "",
    phone: "",
    address: "",
    city: "",
    postalCode: "",
    deviceMake: "",
    deviceModel: "",
    serialNumber: "",
    biosVersion: "",
    osVersion: "",
    problem: "",
  });

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (!selected) {
      alert("Please select what you need help with.");
      return;
    }
    
    const selectedService = SUPPORT_SERVICES.find(s => s.id === selected);
    const subject = `Support Request - ${formData.name}`;
    const body = [
      "New support request:",
      "",
      `Service: ${selectedService?.name || selected}`,
      "",
      "--- CONTACT DETAILS ---",
      `Name: ${formData.name}`,
      `Company: ${formData.company || "N/A"}`,
      `Email: ${formData.email}`,
      `Phone: ${formData.phone || "N/A"}`,
      "",
      "--- ADDRESS DETAILS ---",
      `Address: ${formData.address || "N/A"}`,
      `City: ${formData.city || "N/A"}`,
      `Postal Code: ${formData.postalCode || "N/A"}`,
      "",
      "--- DEVICE DETAILS ---",
      `Make: ${formData.deviceMake || "N/A"}`,
      `Model: ${formData.deviceModel || "N/A"}`,
      `Serial Number: ${formData.serialNumber || "N/A"}`,
      `BIOS Version: ${formData.biosVersion || "N/A"}`,
      `OS Version: ${formData.osVersion || "N/A"}`,
      "",
      "--- PROBLEM DESCRIPTION ---",
      formData.problem || "N/A",
    ].join("\n");

    window.location.href = `mailto:${SALES_EMAIL}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
    setDone(true);
  };

  const handleBackToSelection = () => {
    setSelected(null);
  };

  if (done) {
    return (
      <div className="mx-auto max-w-xl px-4 py-20 text-center">
        <CheckCircle2 className="mx-auto h-14 w-14 text-green-500" />
        <h1 className="mt-4 text-3xl font-extrabold text-foreground">Support request sent</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          We've received your request and will respond within 24 hours.
        </p>
        <button
          className="mt-6 rounded-xl bg-[#839705] px-6 py-2.5 text-sm font-semibold text-white hover:bg-[#98ab06] transition-colors"
          onClick={() => { setDone(false); setSelected(null); setFormData({ 
            name: "", company: "", email: "", phone: "", address: "", city: "", postalCode: "",
            deviceMake: "", deviceModel: "", serialNumber: "", biosVersion: "", osVersion: "", problem: "" 
          }); }}
        >
          Log another request
        </button>
      </div>
    );
  }

  const selectedService = selected ? SUPPORT_SERVICES.find(s => s.id === selected) : null;

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <header className="space-y-1.5">
        <p className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Technical support for your business
        </p>
        <h1 className="text-3xl font-black tracking-tight sm:text-4xl text-foreground">
          IT Services & Support
        </h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          For customers who need assistance with their existing technology. Three quick steps — no technical jargon needed.
        </p>
      </header>

      {/* Show selection grid only when no option is selected */}
      {!selected && (
        <>
          <h2 className="mt-8 text-lg font-extrabold text-foreground">What do you need help with?</h2>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {SUPPORT_SERVICES.map((s) => {
              const active = selected === s.id;
              return (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => setSelected(s.id)}
                  className={`rounded-2xl border p-4 text-left transition-colors ${
                    active 
                      ? "border-[#839705] bg-[#839705]/10" 
                      : theme === "light"
                        ? "border-[#D7E2C8] bg-white hover:bg-[#EEF3E7]"
                        : "border-[#3A4331] bg-[#1A1A1A] hover:bg-[#2A2E24]"
                  }`}
                >
                  <span className={`block text-sm font-bold ${active ? "text-[#839705]" : "text-foreground"}`}>
                    {s.name}
                  </span>
                  <span className="mt-1 block text-xs text-muted-foreground">{s.description}</span>
                </button>
              );
            })}
          </div>
        </>
      )}

      {/* Show form when an option is selected */}
      {selected && (
        <>
          <div className="mt-6 flex items-center gap-3">
            <button
              onClick={handleBackToSelection}
              className="rounded-lg p-2 text-muted-foreground hover:bg-muted transition-colors inline-flex items-center gap-1"
            >
              <ArrowLeft className="h-4 w-4" />
              <span className="text-sm">Back to options</span>
            </button>
          </div>

          <div className="mt-4 rounded-2xl border border-[#839705] bg-[#839705]/5 p-4">
            <div className="flex items-center gap-2">
              <span className="text-sm text-muted-foreground">You selected:</span>
              <span className="rounded-full bg-[#839705]/20 px-3 py-1 text-sm font-semibold text-[#839705]">
                {selectedService?.name || selected}
              </span>
              <button 
                type="button" 
                className="text-xs underline text-muted-foreground hover:text-foreground transition-colors" 
                onClick={handleBackToSelection}
              >
                change
              </button>
            </div>
          </div>

          <form
            className={`mt-4 rounded-2xl border p-5 ${
              theme === "light"
                ? "border-[#D7E2C8] bg-white"
                : "border-[#3A4331] bg-[#1A1A1A]"
            }`}
            onSubmit={handleSubmit}
          >
            {/* Contact Details Section */}
            <div className="mb-6">
              <h3 className="text-base font-bold text-foreground flex items-center gap-2">
                <span className="w-1 h-6 bg-[#839705] rounded-full"></span>
                Contact Details
              </h3>
              <div className="mt-3 grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="text-sm font-medium text-foreground">Full name *</label>
                  <input
                    required
                    value={formData.name}
                    onChange={(e) => setFormData({ ...formData, name: e.target.value })}
                    className="mt-1.5 h-11 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                    placeholder="John Doe"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-foreground">Company (optional)</label>
                  <input
                    value={formData.company}
                    onChange={(e) => setFormData({ ...formData, company: e.target.value })}
                    className="mt-1.5 h-11 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                    placeholder="Your company name"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-foreground">Email *</label>
                  <input
                    type="email"
                    required
                    value={formData.email}
                    onChange={(e) => setFormData({ ...formData, email: e.target.value })}
                    className="mt-1.5 h-11 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                    placeholder="you@company.co.za"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-foreground">Phone *</label>
                  <input
                    required
                    value={formData.phone}
                    onChange={(e) => setFormData({ ...formData, phone: e.target.value })}
                    className="mt-1.5 h-11 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                    placeholder="082 123 4567"
                  />
                </div>
              </div>
            </div>

            {/* Address Section */}
            <div className="mb-6">
              <h3 className="text-base font-bold text-foreground flex items-center gap-2">
                <MapPin className="h-4 w-4 text-[#839705]" />
                Address Details
              </h3>
              <div className="mt-3 grid gap-4 sm:grid-cols-2">
                <div className="sm:col-span-2">
                  <label className="text-sm font-medium text-foreground">Street Address *</label>
                  <input
                    required
                    value={formData.address}
                    onChange={(e) => setFormData({ ...formData, address: e.target.value })}
                    className="mt-1.5 h-11 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                    placeholder="123 Main Street"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-foreground">City *</label>
                  <input
                    required
                    value={formData.city}
                    onChange={(e) => setFormData({ ...formData, city: e.target.value })}
                    className="mt-1.5 h-11 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                    placeholder="Johannesburg"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-foreground">Postal Code</label>
                  <input
                    value={formData.postalCode}
                    onChange={(e) => setFormData({ ...formData, postalCode: e.target.value })}
                    className="mt-1.5 h-11 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                    placeholder="2000"
                  />
                </div>
              </div>
            </div>

            {/* Device Details Section */}
            <div className="mb-6">
              <h3 className="text-base font-bold text-foreground flex items-center gap-2">
                <Laptop className="h-4 w-4 text-[#839705]" />
                Device Details
              </h3>
              <p className="text-xs text-muted-foreground mt-1">Please provide as much detail as possible about the device.</p>
              <div className="mt-3 grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="text-sm font-medium text-foreground">Device Make *</label>
                  <input
                    required
                    value={formData.deviceMake}
                    onChange={(e) => setFormData({ ...formData, deviceMake: e.target.value })}
                    className="mt-1.5 h-11 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                    placeholder="Dell, HP, Lenovo, etc."
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-foreground">Device Model *</label>
                  <input
                    required
                    value={formData.deviceModel}
                    onChange={(e) => setFormData({ ...formData, deviceModel: e.target.value })}
                    className="mt-1.5 h-11 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                    placeholder="Latitude 5420, ThinkPad T14, etc."
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-foreground">Serial Number</label>
                  <input
                    value={formData.serialNumber}
                    onChange={(e) => setFormData({ ...formData, serialNumber: e.target.value })}
                    className="mt-1.5 h-11 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                    placeholder="e.g., 1A2B3C4D5E6F"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-foreground">BIOS Version</label>
                  <input
                    value={formData.biosVersion}
                    onChange={(e) => setFormData({ ...formData, biosVersion: e.target.value })}
                    className="mt-1.5 h-11 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                    placeholder="e.g., 1.2.3"
                  />
                </div>
                <div className="sm:col-span-2">
                  <label className="text-sm font-medium text-foreground">Operating System Version</label>
                  <input
                    value={formData.osVersion}
                    onChange={(e) => setFormData({ ...formData, osVersion: e.target.value })}
                    className="mt-1.5 h-11 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                    placeholder="Windows 11 Pro 22H2, macOS Ventura 13.2, etc."
                  />
                </div>
              </div>
            </div>

            {/* Problem Description */}
            <div className="mb-4">
              <h3 className="text-base font-bold text-foreground flex items-center gap-2">
                <Info className="h-4 w-4 text-[#839705]" />
                Problem Description
              </h3>
              <div className="mt-3">
                <label className="text-sm font-medium text-foreground">Describe the problem in detail *</label>
                <textarea
                  required
                  rows={5}
                  value={formData.problem}
                  onChange={(e) => setFormData({ ...formData, problem: e.target.value })}
                  placeholder="For example: my laptop won't switch on since yesterday. I've tried charging it but the battery light doesn't come on. The laptop is about 2 years old."
                  className="mt-1.5 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                />
              </div>
            </div>

            <button
              type="submit"
              className="mt-5 w-full rounded-xl bg-[#839705] px-6 py-3 text-sm font-semibold text-white hover:bg-[#98ab06] transition-colors inline-flex items-center justify-center gap-2"
            >
              <Mail className="h-4 w-4" />
              Request Technical Support
            </button>
          </form>
        </>
      )}
    </div>
  );
}
// src/pages/solutions.tsx
import { useState } from "react";
import { CheckCircle2, Mail, ArrowLeft, Server, Shield, Users, Building, Network, FileText, ShoppingCart } from "lucide-react";
import { useTheme } from "../context/ThemeContext";
import { SALES_EMAIL } from "../lib/catalog";

const SOLUTIONS_SERVICES = [
  { id: "it-infrastructure", name: "IT Infrastructure", description: "Servers, storage, connectivity and the racks between." },
  { id: "hardware-procurement", name: "Hardware Procurement", description: "Sourcing and supplying hardware at scale." },
  { id: "device-deployment", name: "Device Deployment", description: "Roll out devices across sites and teams." },
  { id: "networking", name: "Networking", description: "Switching, Wi-Fi, firewalls and cabling." },
  { id: "enterprise-hardware", name: "Enterprise Hardware", description: "Servers, workstations and enterprise-grade equipment." },
  { id: "licensing", name: "Licensing", description: "Microsoft and vendor licensing, correctly sized." },
  { id: "system-integration-solutions", name: "System Integration", description: "Make separate business systems work as one." },
  { id: "it-consulting", name: "IT Consulting", description: "Strategy, budgets and roadmaps for your IT." },
  { id: "cybersecurity", name: "Cybersecurity", description: "Protect endpoints, email, data and access." },
  { id: "business-technology", name: "Business Technology Solutions", description: "End-to-end solutions built around business outcomes." },
];

export default function SolutionsPage() {
  const { theme } = useTheme();
  const [selected, setSelected] = useState<string[]>([]);
  const [done, setDone] = useState(false);
  const [formData, setFormData] = useState({
    name: "",
    company: "",
    email: "",
    phone: "",
    address: "",
    city: "",
    postalCode: "",
    projectName: "",
    timeline: "",
    budget: "",
    userCount: "",
    existingInfrastructure: "",
    currentSystems: "",
    complianceRequirements: "",
    // Licensing specific fields
    softwareRequirements: "",
    osVersions: "",
    licenseType: "",
    licenseQuantity: "",
    currentLicenseStatus: "",
    windowsUpdateNeeds: "",
    microsoftProducts: "",
    thirdPartySoftware: "",
    // General
    businessGoals: "",
    message: "",
  });

  const toggle = (id: string) =>
    setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (selected.length === 0) {
      alert("Please select at least one solution.");
      return;
    }
    
    const selectedServices = selected.map(id => SOLUTIONS_SERVICES.find(s => s.id === id)).filter(Boolean);
    const isLicensingSelected = selected.includes("licensing");
    
    const subject = `Business Solutions Enquiry - ${formData.name}`;
    const body = [
      "New business solutions enquiry:",
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
      "--- PROJECT DETAILS ---",
      `Project Name: ${formData.projectName || "N/A"}`,
      `Timeline: ${formData.timeline || "N/A"}`,
      `Budget: ${formData.budget || "N/A"}`,
      `Number of Users/Employees: ${formData.userCount || "N/A"}`,
      "",
      "--- CURRENT INFRASTRUCTURE ---",
      `Existing Infrastructure: ${formData.existingInfrastructure || "N/A"}`,
      `Current Systems: ${formData.currentSystems || "N/A"}`,
      "",
      "--- COMPLIANCE & REQUIREMENTS ---",
      `Compliance Requirements: ${formData.complianceRequirements || "N/A"}`,
      "",
      ...(isLicensingSelected ? [
        "",
        "--- LICENSING & SOFTWARE REQUIREMENTS ---",
        `Software Requirements: ${formData.softwareRequirements || "N/A"}`,
        `Current OS Versions: ${formData.osVersions || "N/A"}`,
        `License Type Needed: ${formData.licenseType || "N/A"}`,
        `Number of Licenses: ${formData.licenseQuantity || "N/A"}`,
        `Current License Status: ${formData.currentLicenseStatus || "N/A"}`,
        `Windows Update Needs: ${formData.windowsUpdateNeeds || "N/A"}`,
        `Microsoft Products Needed: ${formData.microsoftProducts || "N/A"}`,
        `Third-Party Software: ${formData.thirdPartySoftware || "N/A"}`,
      ] : []),
      "",
      "--- SOLUTIONS REQUESTED ---",
      ...selectedServices.map(s => `• ${s?.name}: ${s?.description}`),
      "",
      "--- BUSINESS GOALS ---",
      formData.businessGoals || "N/A",
      "",
      "--- ADDITIONAL INFORMATION ---",
      formData.message || "N/A",
    ].join("\n");

    window.location.href = `mailto:${SALES_EMAIL}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
    setDone(true);
  };

  if (done) {
    return (
      <div className="mx-auto max-w-xl px-4 py-20 text-center">
        <CheckCircle2 className="mx-auto h-14 w-14 text-green-500" />
        <h1 className="mt-4 text-3xl font-extrabold text-foreground">Enquiry sent</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Thank you. One of our consultants will be in touch within 24 hours to discuss your requirements.
        </p>
        <button
          className="mt-6 rounded-xl bg-[#839705] px-6 py-2.5 text-sm font-semibold text-white hover:bg-[#98ab06] transition-colors"
          onClick={() => { 
            setDone(false); 
            setSelected([]); 
            setFormData({ 
              name: "", company: "", email: "", phone: "", address: "", city: "", postalCode: "",
              projectName: "", timeline: "", budget: "", userCount: "", existingInfrastructure: "",
              currentSystems: "", complianceRequirements: "", softwareRequirements: "", osVersions: "",
              licenseType: "", licenseQuantity: "", currentLicenseStatus: "", windowsUpdateNeeds: "",
              microsoftProducts: "", thirdPartySoftware: "", businessGoals: "", message: ""
            }); 
          }}
        >
          Start another enquiry
        </button>
      </div>
    );
  }

  const selectedServices = selected.map(id => SOLUTIONS_SERVICES.find(s => s.id === id)).filter(Boolean);
  const isLicensingSelected = selected.includes("licensing");

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <header className="space-y-1.5">
        <p className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Complete IT solutions for organisations
        </p>
        <h1 className="text-3xl font-black tracking-tight sm:text-4xl text-foreground">
          IT Infrastructure & Business Solutions
        </h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          For customers with larger or more complex IT requirements. Select everything you're interested in and send it through as one enquiry.
        </p>
      </header>

      {/* Show selection grid only when no services are selected */}
      {selected.length === 0 && (
        <>
          <h2 className="mt-8 text-lg font-extrabold text-foreground">What solutions are you interested in?</h2>
          <p className="mt-1 text-sm text-muted-foreground">Select all that apply to your project.</p>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {SOLUTIONS_SERVICES.map((s) => {
              const active = selected.includes(s.id);
              return (
                <button
                  key={s.id}
                  type="button"
                  onClick={() => toggle(s.id)}
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

      {/* Show form when services are selected */}
      {selected.length > 0 && (
        <>
          <div className="mt-6 flex items-center gap-3">
            <button
              onClick={() => setSelected([])}
              className="rounded-lg p-2 text-muted-foreground hover:bg-muted transition-colors inline-flex items-center gap-1"
            >
              <ArrowLeft className="h-4 w-4" />
              <span className="text-sm">Back to options</span>
            </button>
          </div>

          <div className="mt-4 rounded-2xl border border-[#839705] bg-[#839705]/5 p-4">
            <div className="flex flex-wrap items-center gap-2">
              <span className="text-sm text-muted-foreground">Selected solutions:</span>
              {selectedServices.map((s) => (
                <span key={s?.id} className="rounded-full bg-[#839705]/20 px-3 py-1 text-sm font-semibold text-[#839705]">
                  {s?.name}
                </span>
              ))}
              <button 
                type="button" 
                className="text-xs underline text-muted-foreground hover:text-foreground transition-colors ml-2" 
                onClick={() => setSelected([])}
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
                  <label className="text-sm font-medium text-foreground">Company *</label>
                  <input
                    required
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
                <Building className="h-4 w-4 text-[#839705]" />
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

            {/* Project Details Section */}
            <div className="mb-6">
              <h3 className="text-base font-bold text-foreground flex items-center gap-2">
                <Network className="h-4 w-4 text-[#839705]" />
                Project Details
              </h3>
              <div className="mt-3 grid gap-4 sm:grid-cols-2">
                <div>
                  <label className="text-sm font-medium text-foreground">Project Name *</label>
                  <input
                    required
                    value={formData.projectName}
                    onChange={(e) => setFormData({ ...formData, projectName: e.target.value })}
                    className="mt-1.5 h-11 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                    placeholder="e.g., Office Infrastructure Upgrade"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-foreground">Number of Employees/Users *</label>
                  <input
                    required
                    value={formData.userCount}
                    onChange={(e) => setFormData({ ...formData, userCount: e.target.value })}
                    className="mt-1.5 h-11 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                    placeholder="e.g., 50-100 employees"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-foreground">Timeline</label>
                  <select
                    value={formData.timeline}
                    onChange={(e) => setFormData({ ...formData, timeline: e.target.value })}
                    className="mt-1.5 h-11 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                  >
                    <option value="">Select timeline</option>
                    <option value="immediate">Immediate (ASAP)</option>
                    <option value="1-3-months">1-3 months</option>
                    <option value="3-6-months">3-6 months</option>
                    <option value="6-12-months">6-12 months</option>
                    <option value="flexible">Flexible</option>
                  </select>
                </div>
                <div>
                  <label className="text-sm font-medium text-foreground">Estimated Budget</label>
                  <select
                    value={formData.budget}
                    onChange={(e) => setFormData({ ...formData, budget: e.target.value })}
                    className="mt-1.5 h-11 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                  >
                    <option value="">Select budget range</option>
                    <option value="under-100k">Under R100,000</option>
                    <option value="100k-500k">R100,000 - R500,000</option>
                    <option value="500k-1m">R500,000 - R1,000,000</option>
                    <option value="1m-5m">R1,000,000 - R5,000,000</option>
                    <option value="over-5m">Over R5,000,000</option>
                    <option value="unsure">Unsure - Need guidance</option>
                  </select>
                </div>
              </div>
            </div>

            {/* Current Infrastructure Section */}
            <div className="mb-6">
              <h3 className="text-base font-bold text-foreground flex items-center gap-2">
                <Server className="h-4 w-4 text-[#839705]" />
                Current Infrastructure
              </h3>
              <div className="mt-3 grid gap-4">
                <div>
                  <label className="text-sm font-medium text-foreground">Existing Infrastructure</label>
                  <textarea
                    rows={3}
                    value={formData.existingInfrastructure}
                    onChange={(e) => setFormData({ ...formData, existingInfrastructure: e.target.value })}
                    className="mt-1.5 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                    placeholder="Describe your current IT infrastructure setup (servers, networking, hardware, etc.)..."
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-foreground">Current Systems & Software</label>
                  <textarea
                    rows={2}
                    value={formData.currentSystems}
                    onChange={(e) => setFormData({ ...formData, currentSystems: e.target.value })}
                    className="mt-1.5 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                    placeholder="List the key systems and software you currently use..."
                  />
                </div>
              </div>
            </div>

            {/* Licensing & Software Requirements - Only shown when Licensing is selected */}
            {isLicensingSelected && (
              <div className="mb-6">
                <h3 className="text-base font-bold text-foreground flex items-center gap-2">
                  <ShoppingCart className="h-4 w-4 text-[#839705]" />
                  Licensing & Software Requirements
                </h3>
                <p className="text-xs text-muted-foreground mt-1">Please provide details about your software licensing needs.</p>
                <div className="mt-3 grid gap-4 sm:grid-cols-2">
                  <div className="sm:col-span-2">
                    <label className="text-sm font-medium text-foreground">Software Requirements</label>
                    <textarea
                      rows={2}
                      value={formData.softwareRequirements}
                      onChange={(e) => setFormData({ ...formData, softwareRequirements: e.target.value })}
                      className="mt-1.5 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                      placeholder="What software do you need? (e.g., Windows 11 Pro, Microsoft Office, SQL Server, Adobe Creative Cloud, etc.)"
                    />
                  </div>
                  <div className="sm:col-span-2">
                    <label className="text-sm font-medium text-foreground">Current OS Versions</label>
                    <input
                      value={formData.osVersions}
                      onChange={(e) => setFormData({ ...formData, osVersions: e.target.value })}
                      className="mt-1.5 h-11 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                      placeholder="e.g., Windows 10 Pro, Windows 11 Home, macOS Ventura"
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium text-foreground">License Type Needed</label>
                    <select
                      value={formData.licenseType}
                      onChange={(e) => setFormData({ ...formData, licenseType: e.target.value })}
                      className="mt-1.5 h-11 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                    >
                      <option value="">Select license type</option>
                      <option value="volume-licensing">Volume Licensing</option>
                      <option value="oem">OEM Licenses</option>
                      <option value="retail">Retail Licenses</option>
                      <option value="subscription">Subscription (Monthly/Annual)</option>
                      <option value="per-device">Per Device</option>
                      <option value="per-user">Per User</option>
                      <option value="enterprise-agreement">Enterprise Agreement</option>
                      <option value="unsure">Unsure - Need guidance</option>
                    </select>
                  </div>
                  <div>
                    <label className="text-sm font-medium text-foreground">Number of Licenses Needed</label>
                    <input
                      value={formData.licenseQuantity}
                      onChange={(e) => setFormData({ ...formData, licenseQuantity: e.target.value })}
                      className="mt-1.5 h-11 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                      placeholder="e.g., 50, 100, 500"
                    />
                  </div>
                  <div>
                    <label className="text-sm font-medium text-foreground">Current License Status</label>
                    <select
                      value={formData.currentLicenseStatus}
                      onChange={(e) => setFormData({ ...formData, currentLicenseStatus: e.target.value })}
                      className="mt-1.5 h-11 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                    >
                      <option value="">Select status</option>
                      <option value="no-licenses">No existing licenses - Need new</option>
                      <option value="expiring-soon">Expiring soon - Need renewal</option>
                      <option value="upgrade-needed">Need upgrade to newer version</option>
                      <option value="additional-needed">Need additional licenses</option>
                      <option value="unsure">Unsure - Need audit</option>
                    </select>
                  </div>
                  <div className="sm:col-span-2">
                    <label className="text-sm font-medium text-foreground">Windows Update Needs</label>
                    <textarea
                      rows={2}
                      value={formData.windowsUpdateNeeds}
                      onChange={(e) => setFormData({ ...formData, windowsUpdateNeeds: e.target.value })}
                      className="mt-1.5 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                      placeholder="Do you need Windows Update management? Feature updates? Security patches? WSUS setup? (e.g., Need automated updates for 100+ machines)"
                    />
                  </div>
                  <div className="sm:col-span-2">
                    <label className="text-sm font-medium text-foreground">Microsoft Products Needed</label>
                    <input
                      value={formData.microsoftProducts}
                      onChange={(e) => setFormData({ ...formData, microsoftProducts: e.target.value })}
                      className="mt-1.5 h-11 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                      placeholder="e.g., Windows 11 Pro, Microsoft 365, Office, Exchange, SharePoint, SQL Server"
                    />
                  </div>
                  <div className="sm:col-span-2">
                    <label className="text-sm font-medium text-foreground">Third-Party Software</label>
                    <input
                      value={formData.thirdPartySoftware}
                      onChange={(e) => setFormData({ ...formData, thirdPartySoftware: e.target.value })}
                      className="mt-1.5 h-11 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                      placeholder="List any non-Microsoft software licensing needs (e.g., Adobe, Autodesk, VMware, etc.)"
                    />
                  </div>
                </div>
              </div>
            )}

            {/* Compliance & Requirements Section */}
            <div className="mb-6">
              <h3 className="text-base font-bold text-foreground flex items-center gap-2">
                <Shield className="h-4 w-4 text-[#839705]" />
                Compliance & Requirements
              </h3>
              <div className="mt-3">
                <label className="text-sm font-medium text-foreground">Compliance Requirements</label>
                <textarea
                  rows={2}
                  value={formData.complianceRequirements}
                  onChange={(e) => setFormData({ ...formData, complianceRequirements: e.target.value })}
                  className="mt-1.5 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                  placeholder="Any regulatory, security or compliance requirements (POPIA, GDPR, ISO, etc.)..."
                />
              </div>
            </div>

            {/* Business Goals Section */}
            <div className="mb-6">
              <h3 className="text-base font-bold text-foreground flex items-center gap-2">
                <Users className="h-4 w-4 text-[#839705]" />
                Business Goals
              </h3>
              <div className="mt-3">
                <label className="text-sm font-medium text-foreground">What are your business goals? *</label>
                <textarea
                  required
                  rows={4}
                  value={formData.businessGoals}
                  onChange={(e) => setFormData({ ...formData, businessGoals: e.target.value })}
                  className="mt-1.5 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                  placeholder="What are you trying to achieve with this IT solution? What business problems are you solving? What are your key objectives?"
                />
              </div>
            </div>

            {/* Additional Information */}
            <div className="mb-4">
              <h3 className="text-base font-bold text-foreground flex items-center gap-2">
                <FileText className="h-4 w-4 text-[#839705]" />
                Additional Information
              </h3>
              <div className="mt-3">
                <label className="text-sm font-medium text-foreground">Anything else we should know?</label>
                <textarea
                  rows={3}
                  value={formData.message}
                  onChange={(e) => setFormData({ ...formData, message: e.target.value })}
                  className="mt-1.5 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                  placeholder="Any specific requirements, constraints, or additional context..."
                />
              </div>
            </div>

            <button
              type="submit"
              disabled={selected.length === 0}
              className={`mt-5 w-full rounded-xl px-6 py-3 text-sm font-semibold text-white transition-colors inline-flex items-center justify-center gap-2 ${
                selected.length > 0 
                  ? "bg-[#839705] hover:bg-[#98ab06]" 
                  : "bg-muted text-muted-foreground cursor-not-allowed"
              }`}
            >
              <Mail className="h-4 w-4" />
              Send Enquiry ({selected.length} solution{selected.length > 1 ? 's' : ''} selected)
            </button>
          </form>
        </>
      )}
    </div>
  );
}

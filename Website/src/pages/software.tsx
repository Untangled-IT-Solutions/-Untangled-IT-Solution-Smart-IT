// src/pages/software.tsx
import { useState } from "react";
import { CheckCircle2, Mail, ArrowLeft, Code, Users, Settings } from "lucide-react";
import { useTheme } from "../context/ThemeContext";
import { SALES_EMAIL } from "../lib/catalog";

// Software services data
const SOFTWARE_SERVICES = [
  { id: "website-development", name: "Website Development", description: "Business websites built to convert and easy to maintain." },
  { id: "web-applications", name: "Web Applications", description: "Browser-based tools tailored to how your business works." },
  { id: "mobile-applications", name: "Mobile Applications", description: "iOS and Android apps for staff or customers." },
  { id: "custom-software", name: "Custom Software", description: "Software built specifically around your processes." },
  { id: "system-integration", name: "System Integration", description: "Connect the systems you already run so data flows." },
  { id: "api-integrations", name: "API Integrations", description: "Link third-party services and internal platforms." },
  { id: "business-automation", name: "Business Automation", description: "Remove repetitive manual admin with automation." },
  { id: "crm-solutions", name: "CRM Solutions", description: "Track customers, deals and follow-ups in one place." },
  { id: "sharepoint", name: "SharePoint / Document Management", description: "Structured document storage, sharing and approval." },
  { id: "workflow-solutions", name: "Workflow Solutions", description: "Digitise approvals, forms and internal workflows." },
];

export default function SoftwarePage() {
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
    projectType: "",
    timeline: "",
    budget: "",
    existingSystems: "",
    integrations: "",
    userCount: "",
    technicalRequirements: "",
    brief: "",
  });

  const toggle = (id: string) =>
    setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    if (selected.length === 0) {
      alert("Please choose at least one service above.");
      return;
    }

    const subject = `Software Project Enquiry - ${formData.name}`;
    const body = [
      "New software project enquiry:",
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
      `Project Type: ${formData.projectType || "N/A"}`,
      `Timeline: ${formData.timeline || "N/A"}`,
      `Budget: ${formData.budget || "N/A"}`,
      `Number of Users: ${formData.userCount || "N/A"}`,
      "",
      "--- TECHNICAL DETAILS ---",
      `Existing Systems: ${formData.existingSystems || "N/A"}`,
      `Integrations Needed: ${formData.integrations || "N/A"}`,
      `Technical Requirements: ${formData.technicalRequirements || "N/A"}`,
      "",
      "--- SERVICES REQUESTED ---",
      ...selected.map(id => {
        const s = SOFTWARE_SERVICES.find(item => item.id === id);
        return `• ${s?.name}: ${s?.description}`;
      }),
      "",
      "--- PROJECT BRIEF ---",
      formData.brief || "N/A",
    ].join("\n");

    window.location.href = `mailto:${SALES_EMAIL}?subject=${encodeURIComponent(subject)}&body=${encodeURIComponent(body)}`;
    setDone(true);
  };

  if (done) {
    return (
      <div className="mx-auto max-w-xl px-4 py-20 text-center">
        <CheckCircle2 className="mx-auto h-14 w-14 text-green-500" />
        <h1 className="mt-4 text-3xl font-extrabold text-foreground">Project enquiry sent</h1>
        <p className="mt-2 text-sm text-muted-foreground">
          Thank you. One of our developers will be in touch within 24 hours to discuss your project.
        </p>
        <button
          className="mt-6 rounded-xl bg-[#839705] px-6 py-2.5 text-sm font-semibold text-white hover:bg-[#98ab06] transition-colors"
          onClick={() => {
            setDone(false);
            setSelected([]);
            setFormData({
              name: "", company: "", email: "", phone: "", address: "", city: "", postalCode: "",
              projectName: "", projectType: "", timeline: "", budget: "", existingSystems: "",
              integrations: "", userCount: "", technicalRequirements: "", brief: ""
            });
          }}
        >
          Start another project
        </button>
      </div>
    );
  }

  const selectedServices = selected.map(id => SOFTWARE_SERVICES.find(s => s.id === id)).filter(Boolean);

  return (
    <div className="mx-auto max-w-5xl px-4 py-8">
      <header className="space-y-1.5">
        <p className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          Custom software and digital solutions
        </p>
        <h1 className="text-3xl font-black tracking-tight sm:text-4xl text-foreground">
          Software & Web Development
        </h1>
        <p className="max-w-2xl text-sm text-muted-foreground">
          For customers who need something built specifically for their business. Tell us what you need — no shopping cart required.
        </p>
      </header>

      {/* Show selection grid only when no services are selected */}
      {selected.length === 0 && (
        <>
          <h2 className="mt-8 text-lg font-extrabold text-foreground">What would you like built?</h2>
          <p className="mt-1 text-sm text-muted-foreground">Select all that apply to your project.</p>
          <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
            {SOFTWARE_SERVICES.map((s) => {
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
              <span className="text-sm text-muted-foreground">Selected services:</span>
              {selectedServices.map((s, index) => (
                <span key={s?.id} className="rounded-full bg-[#839705]/20 px-3 py-1 text-sm font-semibold text-[#839705]">
                  {s?.name}
                  {index < selected.length - 1 && ""}
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
                <span className="w-1 h-6 bg-[#839705] rounded-full"></span>
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
                <Code className="h-4 w-4 text-[#839705]" />
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
                    placeholder="e.g., Customer Portal"
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-foreground">Project Type</label>
                  <select
                    value={formData.projectType}
                    onChange={(e) => setFormData({ ...formData, projectType: e.target.value })}
                    className="mt-1.5 h-11 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                  >
                    <option value="">Select project type</option>
                    <option value="new-development">New Development</option>
                    <option value="redesign">Redesign / Rebuild</option>
                    <option value="integration">Integration</option>
                    <option value="upgrade">Upgrade / Migration</option>
                    <option value="maintenance">Maintenance & Support</option>
                    <option value="other">Other</option>
                  </select>
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
                    <option value="under-50k">Under R50,000</option>
                    <option value="50k-150k">R50,000 - R150,000</option>
                    <option value="150k-500k">R150,000 - R500,000</option>
                    <option value="500k-1m">R500,000 - R1,000,000</option>
                    <option value="over-1m">Over R1,000,000</option>
                    <option value="unsure">Unsure - Need guidance</option>
                  </select>
                </div>
                <div>
                  <label className="text-sm font-medium text-foreground">Number of Users</label>
                  <input
                    value={formData.userCount}
                    onChange={(e) => setFormData({ ...formData, userCount: e.target.value })}
                    className="mt-1.5 h-11 w-full rounded-lg border border-border bg-background px-3 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                    placeholder="e.g., 50-100 users"
                  />
                </div>
              </div>
            </div>

            {/* Technical Details Section */}
            <div className="mb-6">
              <h3 className="text-base font-bold text-foreground flex items-center gap-2">
                <Settings className="h-4 w-4 text-[#839705]" />
                Technical Details
              </h3>
              <div className="mt-3 grid gap-4">
                <div>
                  <label className="text-sm font-medium text-foreground">Existing Systems</label>
                  <textarea
                    rows={2}
                    value={formData.existingSystems}
                    onChange={(e) => setFormData({ ...formData, existingSystems: e.target.value })}
                    className="mt-1.5 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                    placeholder="List any existing systems that need to be integrated or replaced..."
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-foreground">Integrations Needed</label>
                  <textarea
                    rows={2}
                    value={formData.integrations}
                    onChange={(e) => setFormData({ ...formData, integrations: e.target.value })}
                    className="mt-1.5 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                    placeholder="List any third-party services or APIs that need to be integrated..."
                  />
                </div>
                <div>
                  <label className="text-sm font-medium text-foreground">Technical Requirements</label>
                  <textarea
                    rows={2}
                    value={formData.technicalRequirements}
                    onChange={(e) => setFormData({ ...formData, technicalRequirements: e.target.value })}
                    className="mt-1.5 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                    placeholder="Any specific technology stack, hosting requirements, security needs, etc."
                  />
                </div>
              </div>
            </div>

            {/* Project Brief */}
            <div className="mb-4">
              <h3 className="text-base font-bold text-foreground flex items-center gap-2">
                <Users className="h-4 w-4 text-[#839705]" />
                Project Brief
              </h3>
              <div className="mt-3">
                <label className="text-sm font-medium text-foreground">What are you trying to achieve? *</label>
                <textarea
                  required
                  rows={5}
                  value={formData.brief}
                  onChange={(e) => setFormData({ ...formData, brief: e.target.value })}
                  placeholder="Describe the problem you want solved, in plain language. What are your goals? Who will use it? What are the most important features?"
                  className="mt-1.5 w-full rounded-lg border border-border bg-background px-3 py-2 text-sm text-foreground placeholder:text-muted-foreground focus:border-primary focus:outline-none focus:ring-2 focus:ring-primary/20"
                />
              </div>
            </div>

            <button
              type="submit"
              className="mt-5 w-full rounded-xl bg-[#839705] px-6 py-3 text-sm font-semibold text-white hover:bg-[#98ab06] transition-colors inline-flex items-center justify-center gap-2"
            >
              <Mail className="h-4 w-4" />
              Start a Project ({selected.length} service{selected.length > 1 ? 's' : ''} selected)
            </button>
          </form>
        </>
      )}
    </div>
  );
}

const yearEl = document.getElementById("year");
if (yearEl) {
  yearEl.textContent = String(new Date().getFullYear());
}

const menuToggle = document.getElementById("menuToggle");
const siteNav = document.getElementById("siteNav");

if (menuToggle && siteNav) {
  menuToggle.addEventListener("click", () => {
    const expanded = menuToggle.getAttribute("aria-expanded") === "true";
    menuToggle.setAttribute("aria-expanded", String(!expanded));
    siteNav.classList.toggle("open", !expanded);
  });

  siteNav.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", () => {
      siteNav.classList.remove("open");
      menuToggle.setAttribute("aria-expanded", "false");
    });
  });
}

const revealItems = document.querySelectorAll(".reveal-up");
if ("IntersectionObserver" in window && revealItems.length > 0) {
  const revealObserver = new IntersectionObserver(
    (entries, observer) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add("is-visible");
          observer.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.15 }
  );

  revealItems.forEach((item) => revealObserver.observe(item));
} else {
  revealItems.forEach((item) => item.classList.add("is-visible"));
}

const sectionAnchors = Array.from(document.querySelectorAll("section[id], header[id]"));
const navAnchors = Array.from(document.querySelectorAll(".site-nav a"));

function setActiveSection() {
  if (!sectionAnchors.length || !navAnchors.length) {
    return;
  }

  let currentId = "home";
  const scrollY = window.scrollY + 130;

  sectionAnchors.forEach((section) => {
    if (section.offsetTop <= scrollY) {
      currentId = section.id;
    }
  });

  navAnchors.forEach((anchor) => {
    const target = anchor.getAttribute("href");
    anchor.classList.toggle("active", target === `#${currentId}`);
  });
}

window.addEventListener("scroll", setActiveSection, { passive: true });
setActiveSection();

const chatWidget = document.getElementById("chatWidget");
const chatMessages = document.getElementById("chatMessages");
const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const chatTyping = document.getElementById("chatTyping");
const chatSuggestions = document.getElementById("chatSuggestions");

const CHAT_STORAGE_KEY = "prateek-portfolio-chat-history";
let portfolioKnowledge = null;

const EMBEDDED_PORTFOLIO_KNOWLEDGE = {
  profile: {
    name: "Prateek Parihar",
    title: "Data Analyst | AI Automation | Business Intelligence",
    location: "Auckland, New Zealand",
    summary:
      "Commercially minded Business and Insights Analyst focused on converting operational and customer data into practical business decisions.",
  },
  skills: {
    business_intelligence: ["Power BI", "Tableau", "Advanced Excel", "Power Query", "DAX"],
    data_and_analytics: ["SQL", "Python", "Root Cause Analysis", "Customer Journey Analytics", "Trend Analysis"],
    business_partnering: ["Stakeholder Management", "Influencing Leaders", "KPI Reporting", "Cross-functional Collaboration"],
    operations_and_ai: ["Process Improvement", "UAT", "Data Quality Checks", "API Integration", "GitHub Copilot", "Claude"],
  },
  projects: [
    { name: "AI CV Assistant", status: "Live Prototype", description: "AI-powered resume optimization assistant for ATS compatibility, rewrite guidance, and cover letter generation." },
    { name: "AI Business Intelligence Copilot", status: "Beta Build", description: "Analytics platform that turns uploaded datasets into business insights, dashboard recommendations, and report guidance." },
    { name: "Fuel Prices and EV Demand in New Zealand", status: "Published", description: "Master's thesis applying panel analysis, survey data, and real-world testing to evaluate EV adoption drivers." },
    { name: "AI-Powered Retail Demand Forecasting System", status: "Case Study", description: "Forecast-led planning workflow designed to reduce inventory waste and improve replenishment decisions." },
    { name: "Gilmours Workflow Analysis and Process Redesign", status: "Operational", description: "Workflow mapping and delay diagnosis project with improvement recommendations for delivery performance." },
    { name: "Synlait Milk Supply Chain Optimisation", status: "Strategy", description: "Supply chain optimization strategy using design-thinking diagnostics and KPI recommendations." },
    { name: "Generative AI Business Process Automation", status: "Automation", description: "Multi-step AI workflow automation that reduced repetitive reporting and drafting effort." },
    { name: "Genesis Energy Supply Chain Analysis", status: "Industry Case", description: "Industry case analyzing energy supply chain resilience, risks, and strategy options." },
  ],
  professional_experience: [
    { role: "Data Logician and Field Services Specialist", company: "AA New Zealand", period: "Apr 2026 - Present" },
    { role: "Customer Insights Specialist (Uber Eats Process)", company: "Teleperformance", period: "Jul 2022 - Dec 2023" },
    { role: "Customer Experience and Operations Specialist", company: "Upstox", period: "Apr 2021 - Apr 2022" },
    { role: "Data Associate", company: "Wipro Limited", period: "Oct 2019 - Mar 2021" },
  ],
  certifications: [
    "Microsoft Certified: Azure AI Fundamentals (AI-900)",
    "SQL (Simplilearn)",
    "Google Analytics Certification (Coursera)",
  ],
  education: [
    "Master of Applied Business (Business Analytics) - Unitec Institute of Technology (2024-2025)",
    "Bachelor of Technology (Automobile Engineering) - Rajasthan Technical University (2015-2019)",
  ],
  contact: {
    email: "pprateek26@gmail.com",
    linkedin: "https://linkedin.com/in/pprateek26",
    github: "https://github.com/prateek02061997",
    resume_pdf: "projects/Prateek_Parihar_CV_Generic.pdf",
  },
};

async function loadPortfolioKnowledge() {
  if (portfolioKnowledge) {
    return portfolioKnowledge;
  }

  try {
    const response = await fetch("./portfolio_data.json");
    if (!response.ok) {
      throw new Error("Failed to load local portfolio data");
    }
    portfolioKnowledge = await response.json();
  } catch {
    portfolioKnowledge = EMBEDDED_PORTFOLIO_KNOWLEDGE;
  }

  return portfolioKnowledge;
}

function appendMessage(role, text) {
  if (!chatMessages) {
    return;
  }

  const bubble = document.createElement("div");
  bubble.className = `chat-bubble ${role}`;
  bubble.textContent = text;
  chatMessages.appendChild(bubble);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function saveHistory(history) {
  sessionStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(history));
}

function loadHistory() {
  const raw = sessionStorage.getItem(CHAT_STORAGE_KEY);
  if (!raw) {
    return [];
  }

  try {
    const parsed = JSON.parse(raw);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

let chatHistory = loadHistory();

if (chatWidget && chatMessages) {
  if (chatHistory.length === 0) {
    appendMessage(
      "ai",
      "Hi, I am Prateek AI Assistant. I am powered by Gemini when the backend is available and I always stay grounded in Prateek's portfolio context. Ask me about projects, skills, certifications, resume, or contact details."
    );
  } else {
    chatHistory.forEach((item) => appendMessage(item.role, item.text));
  }
}

function setTyping(isTyping) {
  if (!chatTyping) {
    return;
  }
  chatTyping.hidden = !isTyping;
}

function toBulletList(items) {
  return items.map((item) => `- ${item}`).join("\n");
}

function buildLocalReply(message, data) {
  if (!data) {
    return "I can help with Prateek's profile summary, project highlights, skills, certifications, resume, and contact details. Ask me a specific question and I will summarize it clearly.";
  }

  const text = message.toLowerCase();
  const profile = data.profile || {};
  const contact = data.contact || {};
  const projects = data.projects || [];
  const certifications = data.certifications || [];
  const education = data.education || [];
  const experience = data.professional_experience || [];

  const topProjects = projects.slice(0, 3).map((item) => item.name);

  if (text.includes("about") || text.includes("summary") || text.includes("who is") || text.includes("profile")) {
    return [
      `${profile.name || "Prateek Parihar"} is a ${profile.title || "Data Analyst"} based in ${profile.location || "Auckland"}.`,
      profile.summary || "He focuses on analytics, business intelligence, and AI automation.",
      topProjects.length
        ? `Recent focus areas include ${topProjects.join(", ")}.
`
        : "He is currently focused on AI-enabled analytics and business impact delivery.",
    ].join(" ");
  }

  if (text.includes("contact") || text.includes("email") || text.includes("linkedin") || text.includes("github")) {
    const resumePdf = contact.resume_pdf || contact.generic_cv_pdf || "N/A";
    return [
      "Here is the best way to reach Prateek:",
      `Email: ${contact.email || "N/A"}`,
      `LinkedIn: ${contact.linkedin || "N/A"}`,
      `GitHub: ${contact.github || "N/A"}`,
      `CV PDF: ${resumePdf}`,
    ].join("\n");
  }

  if (text.includes("certification") || text.includes("certificate")) {
    return [`Prateek currently lists these certifications:`, toBulletList(certifications), "If you want, I can also suggest which ones are most relevant for a specific role."].join("\n");
  }

  if (text.includes("education")) {
    return [`Prateek's education background:`, toBulletList(education), "I can also connect this academic work to his project portfolio if helpful."].join("\n");
  }

  if (text.includes("experience") || text.includes("work")) {
    const lines = experience.map((item) => `${item.role} at ${item.company} (${item.period})`);
    return [`Here is a concise summary of Prateek's professional experience:`, toBulletList(lines), "I can break this down into data, BI, and operations impact if you want a role-focused version."].join("\n");
  }

  if (text.includes("skill") || text.includes("technology") || text.includes("tools")) {
    const groups = data.skills || {};
    const lines = Object.keys(groups).map((key) => `${key.replaceAll("_", " ")}: ${groups[key].join(", ")}`);
    return [`Prateek's skills are grouped into practical capability areas:`, toBulletList(lines), "Tell me your target role and I can map these skills to that role."].join("\n");
  }

  if (text.includes("project") || text.includes("ai") || text.includes("showcase") || text.includes("portfolio")) {
    const lines = projects.map((item) => `${item.name} (${item.status}) - ${item.description}`);
    return [`Here are Prateek's featured projects and why they matter:`, toBulletList(lines), "If you share your interest area, I can recommend the top 2 projects to review first."].join("\n");
  }

  return "I can help with Prateek's profile, projects, skills, certifications, education, experience, and contact details. Ask a specific question and I will give a concise, recruiter-friendly answer.";
}

async function askAssistant(message) {
  const payloadHistory = chatHistory.slice(-12);

  try {
    const response = await fetch("/api/chat", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message,
        history: payloadHistory,
      }),
    });

    if (!response.ok) {
      throw new Error("API request failed");
    }

    const data = await response.json();
    if (!data.reply) {
      throw new Error("Invalid assistant response");
    }

    return data.reply;
  } catch {
    const localData = await loadPortfolioKnowledge();
    return buildLocalReply(message, localData);
  }
}

async function processUserMessage(message) {
  appendMessage("user", message);
  chatHistory.push({ role: "user", text: message });
  saveHistory(chatHistory);
  setTyping(true);

  try {
    const assistantReply = await askAssistant(message);
    appendMessage("ai", assistantReply);
    chatHistory.push({ role: "ai", text: assistantReply });
    saveHistory(chatHistory);
  } catch {
    const fallback = "I am having trouble connecting right now. Please try again in a moment.";
    appendMessage("ai", fallback);
    chatHistory.push({ role: "ai", text: fallback });
    saveHistory(chatHistory);
  } finally {
    setTyping(false);
  }
}

if (chatForm && chatInput) {
  chatForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    const message = chatInput.value.trim();
    if (!message) {
      return;
    }

    chatInput.value = "";
    await processUserMessage(message);
  });
}

if (chatSuggestions && chatInput) {
  chatSuggestions.querySelectorAll("button").forEach((button) => {
    button.addEventListener("click", async () => {
      const text = button.textContent ? button.textContent.trim() : "";
      if (!text) {
        return;
      }

      await processUserMessage(text);
    });
  });
}

// Preload local knowledge so chat works even without backend runtime.
loadPortfolioKnowledge();

document.querySelectorAll("[data-placeholder]").forEach((anchor) => {
  anchor.addEventListener("click", (event) => {
    event.preventDefault();
  });
});

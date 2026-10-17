// Set current year
const yearEl = document.getElementById("currentYear");
if (yearEl) {
  yearEl.textContent = String(new Date().getFullYear());
}

// Mobile Navigation Toggle
const menuToggle = document.getElementById("menuToggle");
const siteNav = document.getElementById("siteNav");

if (menuToggle && siteNav) {
  menuToggle.addEventListener("click", () => {
    const isOpen = siteNav.classList.toggle("open");
    menuToggle.setAttribute("aria-expanded", String(isOpen));
  });

  siteNav.querySelectorAll("a").forEach((link) => {
    link.addEventListener("click", () => {
      siteNav.classList.remove("open");
      menuToggle.setAttribute("aria-expanded", "false");
    });
  });
}

// ==========================================================================
// ANIMATED METRIC COUNTERS ON SCROLL
// ==========================================================================
function animateCounters() {
  const metricValues = document.querySelectorAll(".metric-val[data-target]");
  if (!metricValues.length) return;

  const observer = new IntersectionObserver((entries, obs) => {
    entries.forEach((entry) => {
      if (entry.isIntersecting) {
        const el = entry.target;
        const target = parseInt(el.getAttribute("data-target"), 10);
        const suffix = el.getAttribute("data-suffix") || "";
        let current = 0;
        const duration = 1200;
        const stepTime = 25;
        const totalSteps = duration / stepTime;
        const increment = target / totalSteps;

        const timer = setInterval(() => {
          current += increment;
          if (current >= target) {
            el.textContent = target + suffix;
            clearInterval(timer);
          } else {
            el.textContent = Math.floor(current) + suffix;
          }
        }, stepTime);

        obs.unobserve(el);
      }
    });
  }, { threshold: 0.2 });

  metricValues.forEach((el) => observer.observe(el));
}

animateCounters();

// ==========================================================================
// INTERACTIVE PROJECT FILTER TABS
// ==========================================================================
const filterTabs = document.querySelectorAll(".filter-tab");
const projectCards = document.querySelectorAll(".project-showcase-card");

if (filterTabs.length && projectCards.length) {
  filterTabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      filterTabs.forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");

      const filter = tab.getAttribute("data-filter");

      projectCards.forEach((card) => {
        if (filter === "all") {
          card.classList.remove("is-hidden");
        } else {
          const categories = card.getAttribute("data-category") || "";
          if (categories.includes(filter)) {
            card.classList.remove("is-hidden");
          } else {
            card.classList.add("is-hidden");
          }
        }
      });
    });
  });
}

// ==========================================================================
// FLOATING AI COPILOT DRAWER LOGIC
// ==========================================================================
const floatingCopilotBtn = document.getElementById("floatingCopilotBtn");
const openChatBtn = document.getElementById("openChatBtn");
const closeChatBtn = document.getElementById("closeChatBtn");
const chatDrawer = document.getElementById("chatDrawer");

const chatMessages = document.getElementById("chatMessages");
const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const chatTyping = document.getElementById("chatTyping");
const chatSuggestions = document.getElementById("chatSuggestions");

const CHAT_STORAGE_KEY = "prateek-portfolio-chat-v4";
let chatHistory = [];

try {
  const saved = localStorage.getItem(CHAT_STORAGE_KEY);
  if (saved) {
    chatHistory = JSON.parse(saved);
  }
} catch {
  chatHistory = [];
}

function openDrawer() {
  if (chatDrawer) {
    chatDrawer.classList.add("open");
    chatDrawer.setAttribute("aria-hidden", "false");
    if (chatInput) chatInput.focus();
  }
}

function closeDrawer() {
  if (chatDrawer) {
    chatDrawer.classList.remove("open");
    chatDrawer.setAttribute("aria-hidden", "true");
  }
}

if (floatingCopilotBtn) floatingCopilotBtn.addEventListener("click", openDrawer);
if (openChatBtn) openChatBtn.addEventListener("click", openDrawer);
if (closeChatBtn) closeChatBtn.addEventListener("click", closeDrawer);

// Close on Escape key
window.addEventListener("keydown", (e) => {
  if (e.key === "Escape" && chatDrawer && chatDrawer.classList.contains("open")) {
    closeDrawer();
  }
});

// Generate dynamic follow-up prompt chips based on topic
function generateFollowUpPrompts(query, reply) {
  const q = (query + " " + reply).toLowerCase();
  const suggestions = [];

  if (q.includes("datacom") || q.includes("service desk") || q.includes("incident") || q.includes("itil")) {
    suggestions.push({ label: "Ask about AA Motoring Role", prompt: "What did Prateek do at AA Motoring with roadside telemetry?" });
    suggestions.push({ label: "Ask about AI Partnering Simulation", prompt: "Explain the Datacom Partnering with AI job simulation" });
    suggestions.push({ label: "Download CV PDF", prompt: "How do I download his Datacom CV?" });
  } else if (q.includes("thesis") || q.includes("ev") || q.includes("fuel")) {
    suggestions.push({ label: "Explore Kiwi Budget Tours Platform", prompt: "Tell me about his Kiwi Budget Tours platform build" });
    suggestions.push({ label: "Auckland Workshops", prompt: "What AI and tech workshops did he attend in Auckland?" });
    suggestions.push({ label: "Contact Details", prompt: "How can I contact Prateek?" });
  } else if (q.includes("kiwi budget") || q.includes("booking") || q.includes("platform")) {
    suggestions.push({ label: "View Creative Nails Platform", prompt: "Tell me about his Creative Nails by Nidhi build" });
    suggestions.push({ label: "Datacom ITIL Simulation", prompt: "Tell me about his Datacom Service Desk simulation" });
    suggestions.push({ label: "Contact Prateek", prompt: "What is his phone number and email?" });
  } else {
    suggestions.push({ label: "Datacom Simulations", prompt: "Tell me about his Datacom job simulations" });
    suggestions.push({ label: "AA Motoring Experience", prompt: "What did he do at AA New Zealand?" });
    suggestions.push({ label: "All Technical Builds", prompt: "Show me his 7 featured technical projects" });
  }

  return suggestions;
}

function appendMessage(role, text, originalQuery = "") {
  if (!chatMessages) return;

  const msgDiv = document.createElement("div");
  msgDiv.className = `chat-message ${role === "user" ? "user" : "assistant"}`;

  const bubbleDiv = document.createElement("div");
  bubbleDiv.className = "message-bubble";

  if (role === "assistant" && typeof window.marked !== "undefined" && typeof window.DOMPurify !== "undefined") {
    try {
      bubbleDiv.innerHTML = window.DOMPurify.sanitize(window.marked.parse(text));
    } catch {
      bubbleDiv.textContent = text;
    }
  } else {
    bubbleDiv.textContent = text;
  }

  msgDiv.appendChild(bubbleDiv);

  // If assistant reply, add dynamic follow-up chips
  if (role === "assistant") {
    const chips = generateFollowUpPrompts(originalQuery, text);
    if (chips.length) {
      const chipsRow = document.createElement("div");
      chipsRow.className = "dynamic-chips-row";
      chips.forEach((c) => {
        const btn = document.createElement("button");
        btn.type = "button";
        btn.className = "chip-suggestion";
        btn.textContent = c.label;
        btn.addEventListener("click", async () => {
          await processUserMessage(c.prompt);
        });
        chipsRow.appendChild(btn);
      });
      msgDiv.appendChild(chipsRow);
    }
  }

  chatMessages.appendChild(msgDiv);
  chatMessages.scrollTop = chatMessages.scrollHeight;
}

function setTyping(isTyping) {
  if (chatTyping) {
    chatTyping.hidden = !isTyping;
    if (isTyping && chatMessages) {
      chatMessages.scrollTop = chatMessages.scrollHeight;
    }
  }
}

async function askAssistant(message) {
  const payloadHistory = chatHistory.slice(-8);

  const primaryEndpoint = "/api/chat";
  const renderEndpoint = "https://portfolio2-lthl.onrender.com/api/chat";

  let response = null;

  try {
    response = await fetch(primaryEndpoint, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ message, history: payloadHistory }),
    });

    if (!response.ok) {
      throw new Error("Primary API endpoint failed");
    }
  } catch {
    try {
      response = await fetch(renderEndpoint, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, history: payloadHistory }),
      });
    } catch {}
  }

  if (response && response.ok) {
    const data = await response.json();
    if (data.reply) {
      return data.reply;
    }
  }

  // Graceful client fallback using static JSON if completely offline
  try {
    const res = await fetch("./portfolio_data.json");
    const json = await res.json();
    const profile = json.profile || {};
    return `### ${profile.name} — ${profile.headline}\n${profile.summary}\n\n**Email:** ${profile.email} | **LinkedIn:** ${profile.linkedin}`;
  } catch {
    return "I am having trouble reaching the AI core right now. Please try again shortly or contact Prateek directly at pprateek26@gmail.com.";
  }
}

async function processUserMessage(message) {
  appendMessage("user", message);
  chatHistory.push({ role: "user", text: message });
  try {
    localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(chatHistory.slice(-12)));
  } catch {}

  setTyping(true);

  try {
    const reply = await askAssistant(message);
    appendMessage("assistant", reply, message);
    chatHistory.push({ role: "model", text: reply });
    try {
      localStorage.setItem(CHAT_STORAGE_KEY, JSON.stringify(chatHistory.slice(-12)));
    } catch {}
  } catch {
    appendMessage("assistant", "I am currently unable to complete your request. Please try again.");
  } finally {
    setTyping(false);
  }
}

if (chatForm && chatInput) {
  chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const text = chatInput.value.trim();
    if (!text) return;
    chatInput.value = "";
    await processUserMessage(text);
  });
}

// Initial chip buttons in the header
if (chatSuggestions) {
  chatSuggestions.querySelectorAll("button").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const q = btn.textContent.trim();
      if (!q) return;
      openDrawer();
      await processUserMessage(q);
    });
  });
}

// Global listener for chip suggestion clicks
document.addEventListener("click", (e) => {
  const target = e.target.closest(".chip-suggestion[data-prompt]");
  if (target) {
    const prompt = target.getAttribute("data-prompt");
    if (prompt) {
      openDrawer();
      processUserMessage(prompt);
    }
  }
});

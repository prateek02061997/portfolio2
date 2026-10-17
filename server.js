const path = require("path");
const fs = require("fs");
const http = require("http");

// Load .env
const envPath = path.join(__dirname, ".env");
if (fs.existsSync(envPath)) {
  const lines = fs.readFileSync(envPath, "utf-8").split("\n");
  for (const line of lines) {
    const match = line.match(/^\s*([\w.-]+)\s*=\s*(.*)?\s*$/);
    if (match && !process.env[match[1]]) {
      process.env[match[1]] = (match[2] || "").trim().replace(/^['"]|['"]$/g, "");
    }
  }
}

const port = Number(process.env.PORT || 3000);
const apiKey = process.env.GEMINI_API_KEY || "";
const modelName = process.env.GEMINI_MODEL || "gemini-3.8-flash";

const portfolioDataPath = path.join(__dirname, "portfolio_data.json");
let portfolioData = {};
try {
  portfolioData = JSON.parse(fs.readFileSync(portfolioDataPath, "utf-8"));
} catch (e) {
  console.error("Failed to read portfolio_data.json:", e);
}

function buildSystemInstruction() {
  const profile = portfolioData.profile || {};
  return [
    `You are Prateek AI Assistant — an executive, highly articulate portfolio representative for Prateek Parihar (AI & Data Operations Analyst in Auckland, New Zealand).`,
    "",
    "### CORE PERSONA & BEHAVIOR:",
    "1. NATURAL CONVERSATIONAL INTELLIGENCE: Be warm, professional, concise, and executive-ready. Synthesize answers directly and naturally. Never sound like a rigid script.",
    "2. MULTI-INTENT ANSWERING: When asked multiple things (e.g., experience AND contact info), address BOTH with crisp, structured precision.",
    "3. GROUNDED IN PRATEEK'S VERIFIED PORTFOLIO: Ground answers strictly in the verified knowledge base below. Highlight his real-world impact across AA Motoring telemetry, iTech24 digital transformation, Kiwi Budget Tours AI travel booking platform, and his Master's econometrics thesis.",
    "4. CLEAN MARKDOWN: Use clear bullet points, bold key terms, and markdown links (e.g., [Kiwi Budget Tours](https://kiwibudgettours.com), [Thesis Case Study](projects/ev-fuel-price-thesis/index.html), or [Download CV](projects/Prateek_Parihar_CV_Generic.pdf)).",
    "5. DIRECT EXECUTIVE DELIVERY: Avoid robotic preambles like 'Based on my data' or 'As an AI'. Answer with natural authority and clarity.",
    "",
    `### CONTACT DETAILS:`,
    `Email: ${profile.email || "pprateek26@gmail.com"} | Phone: ${profile.phone || "+64 022 562 0449"} | LinkedIn: ${profile.linkedin || "https://linkedin.com/in/pprateek26"} | GitHub: ${profile.github || "https://github.com/prateek02061997"} | CV: ${profile.resume_pdf || "projects/Prateek_Parihar_CV_Generic.pdf"}`,
    "",
    "### VERIFIED PORTFOLIO KNOWLEDGE BASE (JSON):",
    JSON.stringify(portfolioData, null, 2),
  ].join("\n");
}

function formatHistoryForGemini(history) {
  if (!Array.isArray(history)) return [];
  return history
    .filter((item) => item && typeof item.text === "string" && (item.role === "user" || item.role === "ai" || item.role === "model"))
    .map((item) => ({
      role: item.role === "user" ? "user" : "model",
      parts: [{ text: item.text }],
    }));
}

function buildLocalFallbackReply(message) {
  const query = (message || "").toLowerCase();
  const profile = portfolioData.profile || {};
  const skills = portfolioData.skills || {};
  const projects = portfolioData.projects || [];
  const exp = portfolioData.professional_experience || [];
  const workshops = portfolioData.workshops || [];
  const contact = profile;

  if (query.includes("thesis") || query.includes("ev") || query.includes("fuel")) {
    const thesis = projects.find((p) => p.id === "ev-fuel-price-thesis") || {};
    return [
      `### [${thesis.name || "NZ EV Demand & Econometric Fuel Elasticity Thesis"}](${thesis.link || "projects/ev-fuel-price-thesis/index.html"})`,
      `${thesis.tagline || ""}`,
      "",
      "**Key Highlights:**",
      "- **15-Year International Panel Data (2010–2024)** across NZ, Norway, China, and US.",
      "- **Primary Consumer Survey (103 NZ respondents)** & 3,512 km Nissan Leaf field trial.",
      "- **Econometric Modeling**: ARIMA forecasting, Granger causality, and elasticity analysis.",
      "- **7-Step Revenue-Neutral Policy Roadmap** targeting 700k EVs and 48% transport CO2 reduction by 2030.",
      `\n-> [Read Full Thesis Case Study](${thesis.link || "projects/ev-fuel-price-thesis/index.html"})`,
    ].join("\n");
  }

  if (query.includes("workshop") || query.includes("meetup") || query.includes("event")) {
    const list = workshops.map((w) => `- **${w.title}** (${w.host})\n  *Focus: ${w.focus}*`).join("\n");
    return `### AI & Technical Workshops Attended (Auckland & Virtual):\n${list}`;
  }

  if (query.includes("experience") || query.includes("job") || query.includes("aa") || query.includes("itech24") || query.includes("kiwi budget") || query.includes("uber")) {
    const list = exp.map((e) => `- **${e.role}** at **${e.company}** (${e.period}, ${e.location})\n${e.bullets.map((b) => `  * ${b}`).join("\n")}`).join("\n");
    return `### Professional Experience:\n${list}`;
  }

  if (query.includes("project") || query.includes("build") || query.includes("portfolio")) {
    const list = projects.map((p) => `- **[${p.name}](${p.link})** (${p.status}) - *${p.category}*: ${p.tagline}`).join("\n");
    return `### Featured Projects:\n${list}`;
  }

  if (query.includes("skill") || query.includes("tool") || query.includes("tech")) {
    return [
      "### Technical Skills & Competencies:",
      `- **AI & Automation**: ${(skills.ai_automation || []).join(", ")}`,
      `- **Data & Analytics**: ${(skills.data_analytics || []).join(", ")}`,
      `- **Business Delivery**: ${(skills.business_delivery || []).join(", ")}`,
      `- **Systems & Cloud**: ${(skills.systems_cloud || []).join(", ")}`,
    ].join("\n");
  }

  return [
    `### About ${profile.name || "Prateek Parihar"}`,
    `**${profile.headline || "AI & Data Operations Analyst"}** | ${profile.location || "Auckland, NZ"}`,
    "",
    `${profile.summary || ""}`,
    "",
    `**Contact:** [${profile.email}](mailto:${profile.email}) | Phone: ${profile.phone} | [LinkedIn](${profile.linkedin}) | [CV PDF](${profile.resume_pdf})`,
  ].join("\n");
}

async function callGemini(message, history) {
  if (!apiKey) {
    console.log("[Info] No GEMINI_API_KEY. Using grounded fallback.");
    return buildLocalFallbackReply(message);
  }

  const endpoint = `https://generativelanguage.googleapis.com/v1beta/models/${modelName}:generateContent?key=${encodeURIComponent(apiKey)}`;
  const formattedHistory = formatHistoryForGemini(history);
  const contents = [
    ...formattedHistory,
    {
      role: "user",
      parts: [{ text: message }],
    },
  ];

  const payload = {
    system_instruction: {
      parts: [{ text: buildSystemInstruction() }],
    },
    contents: contents,
    generationConfig: {
      temperature: 0.3,
      topK: 20,
      topP: 0.85,
      maxOutputTokens: 1800,
    },
  };

  const response = await fetch(endpoint, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errText = await response.text();
    console.error("Gemini API error status:", response.status, errText);
    return buildLocalFallbackReply(message);
  }

  const data = await response.json();
  const parts = data?.candidates?.[0]?.content?.parts || [];
  const text = parts.map((p) => p.text).join("\n").trim();

  return text || buildLocalFallbackReply(message);
}

async function handleChatRequest(body) {
  const { message, history } = body || {};
  if (typeof message !== "string" || message.trim().length === 0) {
    throw new Error("A valid message is required.");
  }
  const safeHistory = Array.isArray(history) ? history.slice(-10) : [];
  return await callGemini(message.trim(), safeHistory);
}

// Zero-dependency HTTP static + API server
const MIME_TYPES = {
  ".html": "text/html; charset=utf-8",
  ".css": "text/css; charset=utf-8",
  ".js": "application/javascript; charset=utf-8",
  ".json": "application/json; charset=utf-8",
  ".png": "image/png",
  ".jpg": "image/jpeg",
  ".jpeg": "image/jpeg",
  ".svg": "image/svg+xml",
  ".pdf": "application/pdf",
  ".ico": "image/x-icon",
  ".txt": "text/plain; charset=utf-8",
};

const server = http.createServer(async (req, res) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  if (req.method === "OPTIONS") {
    res.writeHead(200);
    res.end();
    return;
  }

  const parsedUrl = new URL(req.url, `http://localhost:${port}`);
  const pathname = decodeURIComponent(parsedUrl.pathname);

  if (pathname === "/health" && req.method === "GET") {
    res.writeHead(200, { "Content-Type": "application/json" });
    res.end(JSON.stringify({ status: "ok", model: modelName, hasApiKey: Boolean(apiKey) }));
    return;
  }

  if (pathname === "/api/chat" && req.method === "POST") {
    let bodyStr = "";
    req.on("data", (chunk) => {
      bodyStr += chunk;
    });
    req.on("end", async () => {
      try {
        const body = JSON.parse(bodyStr || "{}");
        const reply = await handleChatRequest(body);
        res.writeHead(200, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ reply, model: modelName }));
      } catch (err) {
        console.error("Chat error:", err.message);
        res.writeHead(err.message.includes("valid message") ? 400 : 500, { "Content-Type": "application/json" });
        res.end(JSON.stringify({ error: "Unable to process request", details: err.message }));
      }
    });
    return;
  }

  // Static file serving
  let filePath = path.join(__dirname, pathname === "/" ? "index.html" : pathname);
  if (!filePath.startsWith(__dirname)) {
    res.writeHead(403);
    res.end("Forbidden");
    return;
  }

  fs.stat(filePath, (err, stats) => {
    if (err || !stats.isFile()) {
      if (stats && stats.isDirectory()) {
        filePath = path.join(filePath, "index.html");
      } else {
        res.writeHead(404, { "Content-Type": "text/plain" });
        res.end("404 Not Found");
        return;
      }
    }

    const ext = path.extname(filePath).toLowerCase();
    const contentType = MIME_TYPES[ext] || "application/octet-stream";
    res.writeHead(200, { "Content-Type": contentType });
    fs.createReadStream(filePath).pipe(res);
  });
});

server.listen(port, () => {
  console.log(`[Vengeance UI Portfolio Server] Live on http://localhost:${port}`);
  console.log(`[AI Core] Model: ${modelName} | API Key Active: ${Boolean(apiKey)}`);
});

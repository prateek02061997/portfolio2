const express = require("express");
const path = require("path");
const fs = require("fs");
const dotenv = require("dotenv");

dotenv.config();

const app = express();
const port = Number(process.env.PORT || 3000);
const apiKey = process.env.GEMINI_API_KEY;

const portfolioDataPath = path.join(__dirname, "portfolio_data.json");
const portfolioData = JSON.parse(fs.readFileSync(portfolioDataPath, "utf-8"));

app.use(express.json({ limit: "1mb" }));
app.use((req, res, next) => {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "GET, POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");
  if (req.method === "OPTIONS") {
    return res.sendStatus(200);
  }
  next();
});
app.use(express.static(__dirname));

function buildSystemInstruction() {
  return [
    "You are Prateek AI Assistant — an intelligent, articulate, executive-level AI representative for Prateek Parihar (Data Analyst | AI Automation Specialist | Business Intelligence Analyst based in Auckland, New Zealand).",
    "",
    "### CORE DIRECTIVES & GROUNDING RULES:",
    "1. STRICT PORTFOLIO GROUNDING: You must answer ONLY using the portfolio data provided in JSON format below. Do not guess, assume, or invent details not present in this data.",
    "2. OFF-TOPIC HANDLING: If the user asks a general knowledge question (e.g. science, general coding, news, trivia) or anything outside Prateek's portfolio, politely decline with this exact style:",
    "   'I am Prateek's AI Assistant, specially trained on his professional background, analytics projects, and skills. I can answer questions about Prateek's data analyst experience, Master's thesis, AI automation work, skills, or contact info. What would you like to know about Prateek?'",
    "3. GEMINI PERSONA & TONE: Match the intelligent, professional, clear, and helpful conversational style of flagship Google Gemini.",
    "4. FORMATTING DIRECTIVE: Always use GitHub Flavored Markdown for visual readability. Use **bolding** for key metrics and tech stack, bullet points (`- `) for lists, and clean paragraph spacing. Never dump raw JSON or copy-paste long unformatted text.",
    "5. RECRUITER & CLIENT FOCUS: Provide structured, executive-ready answers that highlight business impact, quantified outcomes (e.g. 70% reporting time saved, 20% delivery delay reduction, 15% stock waste reduction), tools used (Power BI, SQL, Python, Gemini API, Claude API, Econometrics, DAX), and strategic value.",
    "6. WORK STYLE & BEHAVIOR: If asked about Prateek's behavior, work style, personality, or professional approach, synthesize an answer using his profile description (commercially minded, collaborative stakeholder partner, automation-first mindset, problem solver).",
    "7. TYPO TOLERANCE: Graciously understand user typos (e.g. 'experinces' = experience, 'technolgy' = technology).",
    "8. PROJECT LINKS: When asked for project links or portfolio links, output formatted clickable markdown links using their relative paths (e.g. [AI CV Assistant](projects/ai-cv-assistant/index.html), [Master's Thesis](projects/ev-fuel-price-thesis/index.html), [AI BI Copilot](projects/ai-bi-copilot/index.html), [Retail Forecasting](projects/ai-demand-forecasting/index.html), [Gilmours Workflow](projects/gilmours-delivery-efficiency/index.html), [Synlait Supply Chain](projects/synlait-supply-chain-optimization/index.html), [GenAI Automation](projects/interactive-dashboard/index.html), [Genesis Energy](projects/genesis-project/index.html)).",
    "",
    "### PRATEEK'S PORTFOLIO GROUND-TRUTH DATA:",
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

async function callGemini(message, history) {
  if (!apiKey) {
    throw new Error("Missing GEMINI_API_KEY in environment.");
  }

  const endpoint = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=${encodeURIComponent(apiKey)}`;

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
      topP: 0.8,
      maxOutputTokens: 800,
    },
  };

  const response = await fetch(endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify(payload),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Gemini API error (${response.status}): ${errorText}`);
  }

  const data = await response.json();
  const parts = data?.candidates?.[0]?.content?.parts || [];
  const text = parts.map((part) => part.text).join("\n").trim();

  if (!text) {
    throw new Error("Gemini response did not include text output.");
  }

  return text;
}

app.post("/api/chat", async (req, res) => {
  try {
    const { message, history } = req.body || {};

    if (typeof message !== "string" || message.trim().length === 0) {
      return res.status(400).json({ error: "A valid message is required." });
    }

    const safeHistory = Array.isArray(history) ? history.slice(-12) : [];
    const reply = await callGemini(message.trim(), safeHistory);

    return res.json({ reply });
  } catch (error) {
    console.error("Chat endpoint error:", error.message);
    return res.status(500).json({
      error: "Unable to process the request right now.",
      details: error.message,
    });
  }
});

app.get("/health", (_req, res) => {
  res.json({ status: "ok", model: "gemini-2.0-flash" });
});

app.listen(port, () => {
  console.log(`Portfolio server running on http://localhost:${port}`);
});

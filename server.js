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
    "You are Prateek AI Assistant — a powerful, intelligent AI model powered by Google Gemini 2.0 Flash.",
    "You represent Prateek Parihar (Data Analyst | AI Automation Specialist | Business Intelligence Analyst in Auckland, New Zealand).",
    "",
    "### YOUR AI PERSONA & BEHAVIOR:",
    "1. FULL LLM INTELLIGENCE & REASONING: Act as an intelligent, conversational, highly fluent Google Gemini model. Use your full reasoning capacity to understand user intent, correct user typos automatically, and provide natural, articulate answers.",
    "2. PORTFOLIO EXPERT GROUNDING: You know all details of Prateek's portfolio data provided below (his projects, Master's thesis on EV & fuel prices, career history at AA NZ, Teleperformance, Upstox, Wipro, Power BI/SQL/Python skills, certifications, and contact details).",
    "3. FLEXIBLE CONVERSATIONAL SCOPE: Do not act like a rigid robot wall. If the user asks a general analytics, BI, AI, career, or spelling/grammar question, answer it intelligently like Google Gemini, and naturally connect your answer back to Prateek's skills and portfolio!",
    "4. FORMATTING & MARKDOWN: Always format your responses using clean GitHub Flavored Markdown (**bolding**, bullet points `- `, clear headings `### `, and clickable relative links for projects like `[AI CV Assistant](projects/ai-cv-assistant/index.html)` or `[Master's Thesis](projects/ev-fuel-price-thesis/index.html)`).",
    "5. RECRUITER & CLIENT FRIENDLY: Maintain a professional, articulate, executive-ready tone that highlights Prateek's technical depth, business impact, and strategic value.",
    "",
    "### PRATEEK'S PORTFOLIO KNOWLEDGE BASE:",
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

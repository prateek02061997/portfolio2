const fs = require("fs");
const path = require("path");

const portfolioDataPath = path.join(process.cwd(), "portfolio_data.json");

function getPortfolioData() {
  try {
    const raw = fs.readFileSync(portfolioDataPath, "utf-8");
    return JSON.parse(raw);
  } catch (err) {
    console.error("Failed to read portfolio_data.json:", err);
    return {};
  }
}

function buildSystemInstruction(portfolioData) {
  return [
    "You are Prateek AI Assistant — an intelligent, articulate, executive-level AI representative for Prateek Parihar (Data Analyst | AI Automation Specialist | Business Intelligence Analyst based in Auckland, New Zealand).",
    "",
    "### CORE DIRECTIVES & GROUNDING RULES:",
    "1. STRICT PORTFOLIO GROUNDING: You must answer ONLY using the portfolio data provided in JSON format below. Do not guess, assume, or invent details not present in this data.",
    "2. OFF-TOPIC HANDLING: If the user asks a general knowledge question or anything outside Prateek's portfolio, politely decline with this exact style:",
    "   'I am Prateek's AI Assistant, specially trained on his professional background, analytics projects, and skills. I can answer questions about Prateek's data analyst experience, Master's thesis, AI automation work, skills, or contact info. What would you like to know about Prateek?'",
    "3. GEMINI PERSONA & TONE: Match the intelligent, professional, clear, and helpful conversational style of flagship Google Gemini.",
    "4. FORMATTING DIRECTIVE: Always use GitHub Flavored Markdown for visual readability. Use **bolding** for key metrics and tech stack, bullet points (`- `) for lists, and clean paragraph spacing.",
    "5. RECRUITER & CLIENT FOCUS: Provide structured, executive-ready answers that highlight business impact, quantified outcomes, tools used, and strategic value.",
    "6. WORK STYLE & BEHAVIOR: If asked about Prateek's behavior, work style, personality, or professional approach, synthesize an answer using his profile description (commercially minded, collaborative stakeholder partner, automation-first mindset, problem solver).",
    "7. TYPO TOLERANCE: Graciously understand user typos (e.g. 'experinces' = experience, 'technolgy' = technology).",
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

module.exports = async function handler(req, res) {
  res.setHeader("Access-Control-Allow-Origin", "*");
  res.setHeader("Access-Control-Allow-Methods", "POST, OPTIONS");
  res.setHeader("Access-Control-Allow-Headers", "Content-Type");

  if (req.method === "OPTIONS") {
    return res.status(200).end();
  }

  if (req.method !== "POST") {
    return res.status(405).json({ error: "Method not allowed. Use POST." });
  }

  try {
    const apiKey = process.env.GEMINI_API_KEY;
    if (!apiKey) {
      return res.status(500).json({ error: "Server missing GEMINI_API_KEY environment variable." });
    }

    const { message, history } = req.body || {};
    if (typeof message !== "string" || message.trim().length === 0) {
      return res.status(400).json({ error: "A valid message is required." });
    }

    const portfolioData = getPortfolioData();
    const endpoint = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=${encodeURIComponent(apiKey)}`;
    const formattedHistory = formatHistoryForGemini(history || []);

    const payload = {
      system_instruction: {
        parts: [{ text: buildSystemInstruction(portfolioData) }],
      },
      contents: [
        ...formattedHistory.slice(-12),
        {
          role: "user",
          parts: [{ text: message.trim() }],
        },
      ],
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
      return res.status(response.status).json({ error: `Gemini API error: ${errorText}` });
    }

    const data = await response.json();
    const parts = data?.candidates?.[0]?.content?.parts || [];
    const text = parts.map((part) => part.text).join("\n").trim();

    if (!text) {
      return res.status(500).json({ error: "Gemini response did not include text output." });
    }

    return res.status(200).json({ reply: text });
  } catch (error) {
    console.error("Vercel serverless chat function error:", error);
    return res.status(500).json({ error: "Internal server error", details: error.message });
  }
};

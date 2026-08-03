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
app.use(express.static(__dirname));

function toGeminiPrompt(message, history) {
  const conversation = history
    .map((item) => `${item.role === "user" ? "User" : "Assistant"}: ${item.text}`)
    .join("\n");

  return [
    "You are Prateek AI Assistant powered by Google Gemini.",
    "You must answer only using the portfolio data provided below.",
    "Do not copy-paste long raw text or JSON fields. Synthesize clear, natural answers in your own words.",
    "Use a concise AI assistant tone: professional, human, and practical.",
    "When useful, summarize first and then add 2-4 key bullets.",
    "If the question is outside the portfolio data, reply: 'I can only answer based on Prateek's portfolio information.'",
    "Be concise, professional, and specific for recruiters, hiring managers, and clients.",
    "",
    "Portfolio Data:",
    JSON.stringify(portfolioData, null, 2),
    "",
    "Conversation History:",
    conversation || "No previous conversation.",
    "",
    `User Question: ${message}`,
  ].join("\n");
}

async function callGemini(promptText) {
  if (!apiKey) {
    throw new Error("Missing GEMINI_API_KEY in environment.");
  }

  const endpoint = `https://generativelanguage.googleapis.com/v1beta/models/gemini-2.0-flash:generateContent?key=${encodeURIComponent(apiKey)}`;

  const response = await fetch(endpoint, {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({
      contents: [
        {
          role: "user",
          parts: [{ text: promptText }],
        },
      ],
      generationConfig: {
        temperature: 0.3,
        topK: 20,
        topP: 0.8,
        maxOutputTokens: 500,
      },
    }),
  });

  if (!response.ok) {
    const errorText = await response.text();
    throw new Error(`Gemini API error: ${response.status} ${errorText}`);
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

    const safeHistory = Array.isArray(history)
      ? history
          .filter((item) => item && typeof item.text === "string" && (item.role === "user" || item.role === "ai"))
          .slice(-12)
      : [];

    const promptText = toGeminiPrompt(message.trim(), safeHistory);
    const reply = await callGemini(promptText);

    return res.json({ reply });
  } catch (error) {
    console.error("Chat endpoint error:", error.message);
    return res.status(500).json({
      error: "Unable to process the request right now.",
    });
  }
});

app.get("/health", (_req, res) => {
  res.json({ status: "ok" });
});

app.listen(port, () => {
  console.log(`Portfolio server running on http://localhost:${port}`);
});

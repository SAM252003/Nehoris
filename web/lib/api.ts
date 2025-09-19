export const API_BASE = process.env.NEXT_PUBLIC_API_BASE || "http://localhost:8001";

export async function askDetect(payload: any) {
  const res = await fetch(`${API_BASE}/geo/ask-detect`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(`API ${res.status} – ${txt}`);
  }
  return res.json();
}

export async function askDetectBatch(payload: any) {
  console.log("🚀 Envoi requête askDetectBatch:", payload);

  const controller = new AbortController();
  const timeoutId = setTimeout(() => controller.abort(), 5 * 60 * 1000); // 5 minutes

  try {
    const res = await fetch(`${API_BASE}/geo/ask-detect-batch`, {
      method: "POST",
      headers: { "content-type": "application/json" },
      body: JSON.stringify(payload),
      signal: controller.signal,
    });

    clearTimeout(timeoutId);

    console.log("📡 Réponse reçue, status:", res.status);

    if (!res.ok) {
      const txt = await res.text();
      console.error("❌ Erreur API:", res.status, txt);
      throw new Error(`API ${res.status} – ${txt}`);
    }

    const data = await res.json();
    console.log("✅ Données reçues:", data);
    return data;
  } catch (error) {
    clearTimeout(timeoutId);
    console.error("💥 Erreur fetch:", error);
    throw error;
  }
}

export async function testGpt5Web(prompt: string) {
  const res = await fetch(`${API_BASE}/llm/test-gpt5-web`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify(prompt),
  });
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(`API ${res.status} – ${txt}`);
  }
  return res.json();
}

export async function getLlmStatus() {
  const res = await fetch(`${API_BASE}/llm/status`);
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(`API ${res.status} – ${txt}`);
  }
  return res.json();
}

export async function generatePrompts(business_type: string, location: string, count: number = 20, keywords: string = "") {
  const res = await fetch(`${API_BASE}/geo/generate-prompts`, {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ business_type, location, count, keywords }),
  });
  if (!res.ok) {
    const txt = await res.text();
    throw new Error(`API ${res.status} – ${txt}`);
  }
  return res.json();
}

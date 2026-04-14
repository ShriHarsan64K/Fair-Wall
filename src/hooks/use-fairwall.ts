import { useState, useEffect, useCallback, useRef } from "react";

export type Domain = "hiring" | "lending" | "admissions" | "healthcare";

export interface TrustScoreData {
  trust_score: number;
  status: "HEALTHY" | "WARNING" | "CRITICAL";
  window_size: number;
  min_for_scoring: number;
  is_warming_up: boolean;
}

export interface MetricData {
  name: string;
  value: number;
  threshold: number;
  status: "PASS" | "WARN" | "FAIL";
  affected_attribute: string;
  affected_group: string;
}

export interface InterventionEvent {
  id: string;
  action: "FLAG" | "ADJUST" | "BLOCK";
  prediction_id: string;
  attribute: string;
  explanation: string;
  trust_score: number;
  timestamp: string;
}

export interface ReviewItem {
  doc_id: string;
  decision: "REJECTED" | "RESOLVED";
  attribute: string;
  group: string;
  score: number;
  prediction_id: string;
  features?: Record<string, unknown>;
  sensitive_attrs?: Record<string, string>;
}

export interface TrustScoreHistory {
  prediction: number;
  score: number;
}

function getBaseUrl() {
  if (typeof window === "undefined") return "http://localhost:8000";
  return localStorage.getItem("fw_api_url") || "http://localhost:8000";
}

function getHeaders(): Record<string, string> {
  const apiKey = typeof window !== "undefined"
    ? localStorage.getItem("fw_api_key") || "fw-demo-key-2026"
    : "fw-demo-key-2026";
  return { "X-API-Key": apiKey, "Content-Type": "application/json" };
}

export function useFairwall() {
  const [domain, setDomain] = useState<Domain>("hiring");
  const [trustScore, setTrustScore] = useState<TrustScoreData | null>(null);
  const [metrics, setMetrics] = useState<MetricData[]>([]);
  const [interventions, setInterventions] = useState<InterventionEvent[]>([]);
  const [reviewQueue, setReviewQueue] = useState<ReviewItem[]>([]);
  const [trustHistory, setTrustHistory] = useState<TrustScoreHistory[]>([]);
  const [isSimulating, setIsSimulating] = useState(false);
  const [simulationProgress, setSimulationProgress] = useState(0);
  const [simulationTotal] = useState(60);
  const [tenantName, setTenantName] = useState("FairWall Demo");
  const abortRef = useRef<AbortController | null>(null);

  const clearState = useCallback(() => {
    setTrustScore(null);
    setMetrics([]);
    setInterventions([]);
    setReviewQueue([]);
    setTrustHistory([]);
  }, []);

  const switchDomain = useCallback((d: Domain) => {
    clearState();
    setDomain(d);
  }, [clearState]);

  // Polling
  useEffect(() => {
    const baseUrl = getBaseUrl();
    const headers = getHeaders();
    let predictionCount = 0;

    const poll3s = setInterval(async () => {
      try {
        const [tsRes, intRes, metRes] = await Promise.all([
          fetch(`${baseUrl}/trust-score?domain=${domain}`, { headers }),
          fetch(`${baseUrl}/interventions?domain=${domain}&limit=20`, { headers }),
          fetch(`${baseUrl}/metrics?domain=${domain}`, { headers }),
        ]);
        if (tsRes.ok) {
          const data = await tsRes.json();
          setTrustScore(data);
          if (!data.is_warming_up) {
            predictionCount++;
            setTrustHistory(prev => [...prev, { prediction: prev.length + 1, score: data.trust_score }]);
          }
        }
        if (intRes.ok) {
          const data = await intRes.json();
          setInterventions(data.events || []);
        }
        if (metRes.ok) {
          const data = await metRes.json();
          setMetrics(data.metrics || []);
        }
      } catch { /* API not available */ }
    }, 3000);

    const poll5s = setInterval(async () => {
      try {
        const res = await fetch(`${baseUrl}/review-queue?domain=${domain}`, { headers });
        if (res.ok) {
          const data = await res.json();
          setReviewQueue(data.items || []);
        }
      } catch { /* */ }
    }, 5000);

    // Tenant info on mount
    fetch(`${baseUrl}/tenant-info`, { headers })
      .then(r => r.ok ? r.json() : null)
      .then(d => { if (d?.name) setTenantName(d.name); })
      .catch(() => {});

    return () => {
      clearInterval(poll3s);
      clearInterval(poll5s);
    };
  }, [domain]);

  // Load tenant name from localStorage
  useEffect(() => {
    if (typeof window !== "undefined") {
      const stored = localStorage.getItem("fw_tenant_name");
      if (stored) setTenantName(stored);
    }
  }, []);

  const runSimulation = useCallback(async () => {
    if (isSimulating) return;
    setIsSimulating(true);
    setSimulationProgress(0);
    clearState();

    const baseUrl = getBaseUrl();
    const headers = getHeaders();

    const buildPrediction = (gender: string, prediction: number, confidence: number) => ({
      domain,
      features: { age: 28, skills_score: 0.85, experience: 5, education: "bachelor" },
      sensitive_attrs: { gender },
      prediction,
      confidence,
    });

    const sequence = [
      ...Array.from({ length: 15 }, (_, i) => buildPrediction(i % 2 === 0 ? "female" : "male", 1, 0.9)),
      ...Array.from({ length: 12 }, () => buildPrediction("female", 0, 0.72)),
      ...Array.from({ length: 8 }, () => buildPrediction("male", 1, 0.85)),
      ...Array.from({ length: 25 }, () => buildPrediction("female", 0, 0.42)),
    ];

    abortRef.current = new AbortController();

    for (let i = 0; i < sequence.length; i++) {
      if (abortRef.current?.signal.aborted) break;
      try {
        await fetch(`${baseUrl}/predict`, {
          method: "POST",
          headers,
          body: JSON.stringify(sequence[i]),
          signal: abortRef.current.signal,
        });
      } catch { /* */ }
      setSimulationProgress(i + 1);
      await new Promise(r => setTimeout(r, 180));
    }

    setIsSimulating(false);
    setSimulationProgress(0);
  }, [domain, isSimulating, clearState]);

  const resolveCase = useCallback(async (docId: string) => {
    const baseUrl = getBaseUrl();
    const headers = getHeaders();
    try {
      await fetch(`${baseUrl}/resolve`, {
        method: "POST",
        headers,
        body: JSON.stringify({ doc_id: docId, resolved_by: "hr_reviewer", resolution_note: "Manually reviewed" }),
      });
    } catch { /* */ }
  }, []);

  const runCounterfactual = useCallback(async (
    selectedAttribute: string,
    originalValue: string,
    newValue: string,
  ) => {
    const baseUrl = getBaseUrl();
    const headers = getHeaders();
    const res = await fetch(`${baseUrl}/replay/demo`, {
      method: "POST",
      headers,
      body: JSON.stringify({
        domain,
        features: { age: 28, skills_score: 0.85, experience: 5 },
        sensitive_attrs: { [selectedAttribute]: originalValue },
        attribute_overrides: { [selectedAttribute]: newValue },
      }),
    });
    return res.json();
  }, [domain]);

  return {
    domain, switchDomain, trustScore, metrics, interventions,
    reviewQueue, trustHistory, isSimulating, simulationProgress,
    simulationTotal, tenantName, setTenantName, runSimulation,
    resolveCase, runCounterfactual,
  };
}

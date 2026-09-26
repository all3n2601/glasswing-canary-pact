"use client";

import type { ScenarioResult } from "@canary-pact/contracts";
import { useState } from "react";

import { simulateScenario } from "@/lib/api";
import { CompanyGraph } from "./company-graph";

const money = new Intl.NumberFormat("en-US", {
  style: "currency",
  currency: "USD",
  notation: "compact",
  maximumFractionDigits: 1,
});

export function DecisionDashboard() {
  const [result, setResult] = useState<ScenarioResult | null>(null);
  const [state, setState] = useState<"idle" | "loading" | "error">("idle");

  async function runDemo() {
    setState("loading");
    try {
      const nextResult = await simulateScenario({
        title: "Consolidate redundant data providers",
        objective: "Save at least $2B without losing critical coverage",
        removeEntityIds: ["vendor_beacon", "vendor_echo"],
        savingsTarget: 2_000_000_000,
        constraints: { complianceCoverage: 1, maximumRevenueImpact: 0.03 },
      });
      setResult(nextResult);
      setState("idle");
    } catch {
      setState("error");
    }
  }

  return (
    <main>
      <header className="topbar">
        <div className="brand"><span className="mark">C</span> Canary Pact</div>
        <div className="status"><span /> Company twin synchronized</div>
      </header>

      <section className="hero">
        <div>
          <p className="eyebrow">Decision intelligence · Northstar Technologies</p>
          <h1>See the blast radius<br />before you commit.</h1>
          <p className="lede">Model the company as one connected system. Compare possible futures, expose hidden dependencies, and find a safer plan.</p>
        </div>
        <div className="scenario-card">
          <span className="label">Leadership objective</span>
          <p>Reduce annual data-provider costs by at least $2B while preserving compliance and limiting revenue impact.</p>
          <div className="constraint-row"><span>Selected action</span><strong>Remove Beacon + Echo</strong></div>
          <button onClick={runDemo} disabled={state === "loading"}>
            {state === "loading" ? "Simulating futures…" : "Run organizational simulation"}
          </button>
          {state === "error" && <p className="error">Start the API on port 8000, then try again.</p>}
        </div>
      </section>

      <section className="metric-grid">
        <article><span>Current vendor spend</span><strong>$8.0B</strong><small>Across 7 providers</small></article>
        <article><span>Target reduction</span><strong>$2.0B</strong><small>Hard constraint</small></article>
        <article><span>Dependencies mapped</span><strong>10</strong><small>Evidence-backed edges</small></article>
        <article><span>Futures evaluated</span><strong>128</strong><small>All vendor portfolios</small></article>
      </section>

      <section className="workspace">
        <div className="panel graph-panel">
          <div className="panel-heading"><div><span className="label">Organizational twin</span><h2>Blast-radius preview</h2></div><span className="pill">Live graph</span></div>
          <CompanyGraph />
        </div>

        <aside className="panel result-panel">
          <span className="label">Decision package</span>
          {!result ? (
            <div className="empty"><div className="radar" /><h2>No simulation yet</h2><p>Run the prepared scenario to reveal savings, affected departments, and constraint violations.</p></div>
          ) : (
            <div className="results">
              <div className={`verdict ${result.status}`}><span>{result.status}</span><strong>{money.format(result.netSavings)} net savings</strong></div>
              <div className="result-numbers"><div><span>Gross</span><strong>{money.format(result.grossSavings)}</strong></div><div><span>Transition</span><strong>{money.format(result.transitionCost)}</strong></div></div>
              <h3>Affected areas</h3>
              <ul>{result.impacts.slice(0, 4).map((impact) => <li key={`${impact.entityId}-${impact.level}`}><span className={`severity ${impact.severity}`} /> <div><strong>{impact.description}</strong><small>{impact.level.replace("_", " ")} · {Math.round(impact.confidence * 100)}% confidence</small></div></li>)}</ul>
              <p className="recommendation">{result.recommendation}</p>
            </div>
          )}
        </aside>
      </section>
    </main>
  );
}


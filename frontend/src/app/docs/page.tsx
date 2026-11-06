"use client";

import { useEffect, useRef, useState } from "react";
import Link from "next/link";

const resources = [
  { title: "Getting started", category: "Guides", description: "Requirements, environment configuration, Docker Compose, and local development.", url: "https://github.com/krishujeniya/Hadron#Getting-started", keywords: "install docker node python setup local development" },
  { title: "System architecture", category: "Architecture", description: "Webhook ingress, context retrieval, LangGraph orchestration, and review dispatch.", url: "https://github.com/krishujeniya/Hadron#system-architecture", keywords: "webhooks langgraph agents overview pipeline" },
  { title: "Review specialists", category: "Architecture", description: "Security, quality, testing and documentation agents and their responsibilities.", url: "https://github.com/krishujeniya/Hadron#specialist-agents", keywords: "security quality tests docs agents" },
  { title: "Model routing", category: "Reference", description: "Review the source-controlled model-routing document.", url: "https://github.com/krishujeniya/Hadron/blob/main/docs/architecture/model-routing.md", keywords: "llm cost models routing" },
  { title: "API and integration", category: "Reference", description: "The FastAPI surface, webhooks and health endpoints in the repository.", url: "https://github.com/krishujeniya/Hadron/tree/main/backend/api", keywords: "api endpoints webhooks auth token" },
  { title: "Self-hosting and recovery", category: "Operations", description: "Operational runbooks, rollout plans and incident handling.", url: "https://github.com/krishujeniya/Hadron/tree/main/docs/operations", keywords: "deploy production rollback disaster recovery" },
  { title: "Security model", category: "Security", description: "Threat modeling, repository permissions and operational boundaries.", url: "https://github.com/krishujeniya/Hadron/blob/main/docs/security/threat-model.md", keywords: "hmac secrets permissions privacy" },
  { title: "Contributing and verification", category: "Guides", description: "Run frontend checks and the backend test suite before opening a PR.", url: "https://github.com/krishujeniya/Hadron#running-tests-and-verification", keywords: "pytest tsc lint tests ci" },
];

const commands = [
  "git clone https://github.com/krishujeniya/Hadron.git",
  "cd Hadron",
  "cp .env.example .env",
  "docker compose -f docker-compose.dev.yml up -d --build",
];

export default function DocsPage() {
  const [query, setQuery] = useState("");
  const [copied, setCopied] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);
  const results = resources.filter((item) =>
    [item.title, item.description, item.category, item.keywords].join(" ").toLowerCase().includes(query.trim().toLowerCase())
  );

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        const dialog = document.querySelector('[role="dialog"]');
        if (dialog) return;
        event.preventDefault();
        inputRef.current?.focus();
      }
    }
    document.addEventListener("keydown", onKeyDown);
    return () => document.removeEventListener("keydown", onKeyDown);
  }, []);

  async function copyCommands() {
    try {
      await navigator.clipboard.writeText(commands.join("\n"));
      setCopied(true);
    } catch {
      setCopied(false);
    }
  }

  return (
    <div className="hm-docs">
      <aside className="hm-docs-aside" aria-label="Documentation sections">
        <h2>Documentation</h2>
        <a href="#overview">Overview</a>
        <a href="#quickstart">Quickstart</a>
        <a href="#resources">Explore resources</a>
        <a href="#integration">Integration</a>
        <Link href="/">Back to Hadron ↗</Link>
      </aside>
      <article className="hm-docs-article">
        <div id="overview">
          
          <h1>Hadron documentation</h1>
          <p style={{ marginTop: 23 }}>Hadron orchestrates four specialist review agents that analyze pull-request changes, retrieve related repository context, and aggregate findings for GitHub review or human triage.</p>
          <p style={{ marginTop: 14 }}>This index links directly to the source-controlled documentation. It deliberately does not publish operational state, private configuration, or internal tracker data.</p>
        </div>
        <section id="quickstart">
          <h2>Set up locally</h2>
          <p>Copy the commands below to run the development Compose topology. Configure the example environment file before launching containers. You will need Docker, Compose, and provider credentials for the applicable integrations.</p>
          <div style={{ position: "relative" }}>
            <pre><code>{commands.join("\n")}</code></pre>
            <button type="button" onClick={copyCommands} aria-live="polite" style={{ position: "absolute", right: 13, top: 12, borderRadius: 10, padding: "8px 13px", background: "#30333c", color: "white", fontSize: 12 }}>{copied ? "Copied" : "Copy commands"}</button>
          </div>
          <p>Frontend: <code>http://localhost:3000</code> · API: <code>http://localhost:8000</code> · OpenAPI: <code>http://localhost:8000/docs</code>.</p>
        </section>
        <section id="resources">
          <h2>Explore the architecture</h2>
          <p>Search approved documentation topics and open the canonical Markdown sources on GitHub.</p>
          <label htmlFor="hm-docs-search" style={{ display: "block", fontSize: 13, marginTop: 23 }}>Search documentation</label>
          <input id="hm-docs-search" ref={inputRef} value={query} onChange={(event) => setQuery(event.target.value)} className="hm-docs-search" type="search" placeholder="Search architecture, setup, security… (⌘K)" aria-controls="hm-docs-results" />
          <div id="hm-docs-results" className="hm-docs-cards" aria-live="polite">
            {results.length ? results.map((item) => (
              <a key={item.title} className="hm-docs-card" href={item.url} target="_blank" rel="noopener noreferrer">
                <span className="hm-capability-kicker" style={{ color: "var(--hm-muted)" }}>{item.category}</span>
                <h3 style={{ marginTop: 12 }}>{item.title} ↗</h3>
                <p>{item.description}</p>
              </a>
            )) : <p role="status">No matching public documentation. Try another keyword.</p>}
          </div>
        </section>
        <section id="integration">
          <h2>Integrate with GitHub</h2>
          <p>Hadron consumes GitHub pull-request events via the backend webhook, coordinates specialized analysis, and publishes findings through its GitHub integration. Production deployments require configured credentials and infrastructure; the visual sample on the marketing page is illustrative and does not execute a remote review.</p>
          <p style={{ marginTop: 16 }}><a href="https://github.com/krishujeniya/Hadron/blob/main/.env.example" target="_blank" rel="noopener noreferrer" style={{ textDecoration: "underline" }}>Explore configuration ↗</a></p>
        </section>
      </article>
    </div>
  );
}

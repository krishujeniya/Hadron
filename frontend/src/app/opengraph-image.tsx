import { ImageResponse } from "next/og";

export const runtime = "edge";

export const alt = "Hadron — Autonomous AI PR Review Agent";
export const size = {
  width: 1200,
  height: 630,
};
export const contentType = "image/png";

export default async function Image() {
  return new ImageResponse(
    (
      <div
        style={{
          height: "100%",
          width: "100%",
          display: "flex",
          flexDirection: "column",
          justifyContent: "space-between",
          backgroundColor: "#0B0D12",
          color: "#E5E7EB",
          padding: "56px 64px",
          fontFamily: "ui-sans-serif, system-ui, sans-serif",
          position: "relative",
        }}
      >
        {/* Glow backdrop */}
        <div
          style={{
            position: "absolute",
            top: "-150px",
            right: "-150px",
            width: "600px",
            height: "600px",
            borderRadius: "50%",
            background: "radial-gradient(circle, rgba(99, 102, 241, 0.25) 0%, rgba(56, 189, 248, 0.05) 50%, transparent 70%)",
          }}
        />

        {/* Header / Brand */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            width: "100%",
            zIndex: 10,
          }}
        >
          <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
            <svg
              width="52"
              height="52"
              viewBox="0 0 100 100"
              fill="none"
              xmlns="http://www.w3.org/2000/svg"
            >
              <defs>
                <linearGradient id="hadronOgGrad" x1="0%" y1="0%" x2="100%" y2="100%">
                  <stop offset="0%" stopColor="#38BDF8" />
                  <stop offset="50%" stopColor="#6366F1" />
                  <stop offset="100%" stopColor="#A855F7" />
                </linearGradient>
              </defs>
              <circle cx="50" cy="50" r="42" stroke="url(#hadronOgGrad)" strokeWidth="4" strokeDasharray="8 6" opacity="0.6" />
              <ellipse cx="50" cy="50" rx="34" ry="14" stroke="url(#hadronOgGrad)" strokeWidth="3" transform="rotate(-30 50 50)" opacity="0.9" />
              <ellipse cx="50" cy="50" rx="34" ry="14" stroke="url(#hadronOgGrad)" strokeWidth="3" transform="rotate(30 50 50)" opacity="0.9" />
              <circle cx="50" cy="50" r="9" fill="url(#hadronOgGrad)" />
              <circle cx="50" cy="50" r="4" fill="#FFFFFF" />
            </svg>
            <div style={{ display: "flex", flexDirection: "column" }}>
              <span
                style={{
                  fontSize: "32px",
                  fontWeight: 900,
                  letterSpacing: "4px",
                  color: "#FFFFFF",
                }}
              >
                HADRON
              </span>
              <span
                style={{
                  fontSize: "12px",
                  fontWeight: 600,
                  letterSpacing: "2px",
                  color: "#38BDF8",
                }}
              >
                AUTONOMOUS PR ACCELERATOR
              </span>
            </div>
          </div>

          <div
            style={{
              display: "flex",
              alignItems: "center",
              gap: "8px",
              padding: "8px 18px",
              borderRadius: "9999px",
              backgroundColor: "rgba(99, 102, 241, 0.15)",
              border: "1px solid rgba(99, 102, 241, 0.35)",
              fontSize: "13px",
              fontWeight: 700,
              color: "#A5B4FC",
              letterSpacing: "1px",
            }}
          >
            <span>v0.1.0 PRODUCTION</span>
          </div>
        </div>

        {/* Center Hero */}
        <div style={{ display: "flex", flexDirection: "column", gap: "16px", zIndex: 10 }}>
          <div
            style={{
              fontSize: "58px",
              fontWeight: 800,
              lineHeight: 1.12,
              color: "#FFFFFF",
              maxWidth: "960px",
              letterSpacing: "-1px",
            }}
          >
            Multi-Agent PR Reviews With PhD-Level Precision.
          </div>
          <div
            style={{
              fontSize: "22px",
              color: "#8A93A6",
              maxWidth: "840px",
              lineHeight: 1.4,
            }}
          >
            Four parallel specialist agents detect security vulnerabilities, logic smells, test gaps, and documentation drift before merge.
          </div>
        </div>

        {/* Bottom Feature Pill Grid */}
        <div
          style={{
            display: "flex",
            alignItems: "center",
            justifyContent: "space-between",
            width: "100%",
            paddingTop: "24px",
            borderTop: "1px solid rgba(31, 36, 48, 0.8)",
            zIndex: 10,
          }}
        >
          <div style={{ display: "flex", gap: "14px" }}>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                padding: "8px 14px",
                borderRadius: "8px",
                backgroundColor: "rgba(17, 20, 27, 0.85)",
                border: "1px solid rgba(56, 189, 248, 0.3)",
                fontSize: "13px",
                fontWeight: 600,
                color: "#38BDF8",
              }}
            >
              <span>🛡️ Security Sub-Agent</span>
            </div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                padding: "8px 14px",
                borderRadius: "8px",
                backgroundColor: "rgba(17, 20, 27, 0.85)",
                border: "1px solid rgba(99, 102, 241, 0.3)",
                fontSize: "13px",
                fontWeight: 600,
                color: "#818CF8",
              }}
            >
              <span>⚡ Quality Sub-Agent</span>
            </div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                padding: "8px 14px",
                borderRadius: "8px",
                backgroundColor: "rgba(17, 20, 27, 0.85)",
                border: "1px solid rgba(16, 185, 129, 0.3)",
                fontSize: "13px",
                fontWeight: 600,
                color: "#34D399",
              }}
            >
              <span>🧪 Coverage Sub-Agent</span>
            </div>
            <div
              style={{
                display: "flex",
                alignItems: "center",
                gap: "8px",
                padding: "8px 14px",
                borderRadius: "8px",
                backgroundColor: "rgba(17, 20, 27, 0.85)",
                border: "1px solid rgba(168, 85, 247, 0.3)",
                fontSize: "13px",
                fontWeight: 600,
                color: "#C084FC",
              }}
            >
              <span>📚 Docs Sub-Agent</span>
            </div>
          </div>

          <div
            style={{
              fontSize: "13px",
              fontFamily: "monospace",
              color: "#8A93A6",
            }}
          >
            Tiger Cloud • DiskANN • LangGraph
          </div>
        </div>
      </div>
    ),
    {
      ...size,
    }
  );
}

"use client";

import React, { useState, useMemo } from "react";
import type { Finding } from "@/lib/types";

interface DiffViewerProps {
  diff?: string;
  findings?: Finding[];
}

interface ParsedHunkLine {
  type: "context" | "addition" | "deletion" | "header";
  text: string;
  oldLine?: number;
  newLine?: number;
}

interface ParsedFileDiff {
  oldPath: string;
  newPath: string;
  lines: ParsedHunkLine[];
}

export function parseUnifiedDiff(rawDiff: string): ParsedFileDiff[] {
  if (!rawDiff || !rawDiff.trim()) return [];

  const files: ParsedFileDiff[] = [];
  let currentFile: ParsedFileDiff | null = null;
  let oldLineNum = 0;
  let newLineNum = 0;

  for (const line of rawDiff.split("\n")) {
    if (line.startsWith("diff --git ")) {
      const parts = line.split(" ");
      const oldPath = parts[2]?.replace(/^a\//, "") || "unknown";
      const newPath = parts[3]?.replace(/^b\//, "") || "unknown";
      currentFile = { oldPath, newPath, lines: [] };
      files.push(currentFile);
      continue;
    }

    if (!currentFile) {
      if (line.startsWith("+++ b/")) {
        currentFile = { oldPath: line.slice(6), newPath: line.slice(6), lines: [] };
        files.push(currentFile);
      }
      continue;
    }

    if (line.startsWith("@@")) {
      const match = line.match(/@@ -(\d+)(?:,\d+)? \+(\d+)(?:,\d+)? @@/);
      if (match) {
        oldLineNum = parseInt(match[1], 10);
        newLineNum = parseInt(match[2], 10);
      }
      currentFile.lines.push({
        type: "header",
        text: line,
      });
      continue;
    }

    if (line.startsWith("+") && !line.startsWith("+++")) {
      currentFile.lines.push({
        type: "addition",
        text: line.slice(1),
        newLine: newLineNum++,
      });
    } else if (line.startsWith("-") && !line.startsWith("---")) {
      currentFile.lines.push({
        type: "deletion",
        text: line.slice(1),
        oldLine: oldLineNum++,
      });
    } else if (line.startsWith(" ") || line === "") {
      currentFile.lines.push({
        type: "context",
        text: line.startsWith(" ") ? line.slice(1) : line,
        oldLine: oldLineNum++,
        newLine: newLineNum++,
      });
    }
  }

  return files;
}

export function DiffViewer({ diff, findings = [] }: DiffViewerProps) {
  const files = useMemo(() => (diff ? parseUnifiedDiff(diff) : []), [diff]);
  const [selectedFileIdx, setSelectedFileIdx] = useState(0);

  // Map findings by file path and line number
  const findingsMap = useMemo(() => {
    const map = new Map<string, Finding[]>();
    for (const f of findings) {
      if (!f.file_path) continue;
      const line = f.line_start ?? 0;
      const key = `${f.file_path}:${line}`;
      const existing = map.get(key) || [];
      existing.push(f);
      map.set(key, existing);
    }
    return map;
  }, [findings]);

  if (!diff || files.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-panel/60 p-8 text-center">
        <div className="text-3xl mb-2">📄</div>
        <h3 className="text-sm font-semibold text-foreground/90">No Raw Diff Attached</h3>
        <p className="text-xs text-muted mt-1 max-w-md mx-auto">
          The unified diff for this review was streamed directly to specialist agents. You can inspect all findings in the structured breakdown tab.
        </p>
      </div>
    );
  }

  const currentFile = files[selectedFileIdx] || files[0];

  return (
    <div className="rounded-xl border border-border bg-panel overflow-hidden shadow-sm">
      {/* File Navigation Bar */}
      <div className="flex items-center gap-1.5 px-4 py-2.5 bg-surface/50 border-b border-border overflow-x-auto text-xs">
        <span className="text-muted font-medium mr-2 shrink-0">Files Changed:</span>
        {files.map((file, idx) => {
          const fileFindings = findings.filter(f => f.file_path === file.newPath);
          return (
            <button
              key={idx}
              onClick={() => setSelectedFileIdx(idx)}
              className={`px-3 py-1.5 rounded-lg font-mono text-xs transition-colors shrink-0 flex items-center gap-2 ${
                selectedFileIdx === idx
                  ? "bg-accent/15 text-accent border border-accent/30 font-semibold"
                  : "bg-panel text-muted hover:text-foreground border border-border"
              }`}
            >
              <span>{file.newPath}</span>
              {fileFindings.length > 0 && (
                <span className="px-1.5 py-0.2 rounded-full text-[10px] bg-err/20 text-err font-bold">
                  {fileFindings.length}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Code Table */}
      <div className="overflow-x-auto font-mono text-xs">
        <table className="w-full border-collapse">
          <tbody>
            {currentFile.lines.map((line, lineIdx) => {
              const fileKey = `${currentFile.newPath}:${line.newLine ?? 0}`;
              const matchingFindings = line.newLine ? findingsMap.get(fileKey) : undefined;

              return (
                <React.Fragment key={lineIdx}>
                  {line.type === "header" ? (
                    <tr className="bg-surface/30 text-muted/70">
                      <td colSpan={3} className="py-1 px-4 text-[11px] select-none italic border-y border-border/50">
                        {line.text}
                      </td>
                    </tr>
                  ) : (
                    <tr
                      className={`hover:bg-surface/40 transition-colors ${
                        line.type === "addition"
                          ? "bg-ok/10 text-ok"
                          : line.type === "deletion"
                          ? "bg-err/10 text-err"
                          : "text-foreground/80"
                      }`}
                    >
                      {/* Old Line # */}
                      <td className="w-12 py-0.5 px-2 text-right select-none text-muted/50 border-r border-border/40 text-[11px]">
                        {line.oldLine ?? ""}
                      </td>
                      {/* New Line # */}
                      <td className="w-12 py-0.5 px-2 text-right select-none text-muted/50 border-r border-border/40 text-[11px]">
                        {line.newLine ?? ""}
                      </td>
                      {/* Line Prefix & Content */}
                      <td className="py-0.5 px-3 whitespace-pre">
                        <span className="select-none font-bold mr-2 text-muted/40">
                          {line.type === "addition" ? "+" : line.type === "deletion" ? "-" : " "}
                        </span>
                        {line.text}
                      </td>
                    </tr>
                  )}

                  {/* Inline Finding Callout Badge */}
                  {matchingFindings && matchingFindings.map((finding, fIdx) => (
                    <tr key={`f-${fIdx}`} className="bg-err/10 border-y-2 border-err/40">
                      <td colSpan={2} className="bg-err/20 text-center py-2 text-err font-bold select-none text-xs">
                        ⚠️
                      </td>
                      <td className="p-3 text-foreground">
                        <div className="flex items-center gap-2 mb-1">
                          <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-err/20 text-err border border-err/30">
                            {finding.severity || "CRITICAL"}
                          </span>
                          <span className="text-xs font-semibold text-accent">
                            {finding.agent_type}
                          </span>
                          <span className="text-[10px] text-muted font-mono">
                            Confidence: {((finding.confidence ?? 0.8) * 100).toFixed(0)}%
                          </span>
                        </div>
                        <div className="text-xs font-medium text-foreground/90">
                          {finding.summary}
                        </div>
                        {finding.suggestion && (
                          <div className="mt-2 text-xs bg-panel/90 border border-border/80 rounded p-2 text-ok/90 font-mono whitespace-pre-wrap">
                            💡 {finding.suggestion}
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </React.Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </div>
  );
}

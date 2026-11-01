"use client";

import React, { useState, useMemo } from "react";
import type { Finding } from "@/lib/types";

interface DiffViewerProps {
  diff?: string;
  findings?: Finding[];
}

export interface ParsedHunkLine {
  type: "context" | "addition" | "deletion" | "header";
  text: string;
  oldLine?: number;
  newLine?: number;
}

export interface ParsedFileDiff {
  oldPath: string;
  newPath: string;
  isDeleted?: boolean;
  isNew?: boolean;
  isBinary?: boolean;
  lines: ParsedHunkLine[];
}

/**
 * Robust unified diff parser.
 * Handles:
 *  - Filenames containing spaces
 *  - Deleted files (+++ /dev/null)
 *  - Newly created files (--- /dev/null)
 *  - Binary diff markers
 *  - Old and new line coordinate tracking
 */
export function parseUnifiedDiff(rawDiff: string): ParsedFileDiff[] {
  if (!rawDiff || !rawDiff.trim()) return [];

  const files: ParsedFileDiff[] = [];
  let currentFile: ParsedFileDiff | null = null;
  let oldLineNum = 0;
  let newLineNum = 0;

  const lines = rawDiff.split("\n");

  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];

    // Standard git diff header: diff --git a/path b/path
    // Note: filenames may contain spaces, so we parse with care.
    if (line.startsWith("diff --git ")) {
      // Find paths. Standard format: "diff --git a/<old> b/<new>"
      const headerBody = line.slice(11).trim();
      let oldPath = "unknown";
      let newPath = "unknown";

      const gitMatch = headerBody.match(/^a\/(.+?)\s+b\/(.+)$/);
      if (gitMatch) {
        oldPath = gitMatch[1];
        newPath = gitMatch[2];
      } else {
        // Fallback: split on spaces
        const parts = headerBody.split(" ");
        oldPath = parts[0]?.replace(/^a\//, "") || "unknown";
        newPath = parts[parts.length - 1]?.replace(/^b\//, "") || "unknown";
      }

      currentFile = { oldPath, newPath, lines: [] };
      files.push(currentFile);
      continue;
    }

    if (!currentFile) {
      if (line.startsWith("+++ b/")) {
        const path = line.slice(6).trim();
        currentFile = { oldPath: path, newPath: path, lines: [] };
        files.push(currentFile);
      }
      continue;
    }

    // Binary file indicator
    if (line.startsWith("Binary files ") || line.includes("GIT binary patch")) {
      currentFile.isBinary = true;
      continue;
    }

    // Deleted file indicator
    if (line.startsWith("deleted file mode ") || line.startsWith("+++ /dev/null")) {
      currentFile.isDeleted = true;
      continue;
    }

    // New file indicator
    if (line.startsWith("new file mode ") || line.startsWith("--- /dev/null")) {
      currentFile.isNew = true;
      continue;
    }

    // Secondary path refinement from --- a/ and +++ b/
    if (line.startsWith("--- a/")) {
      currentFile.oldPath = line.slice(6).trim();
      continue;
    }
    if (line.startsWith("+++ b/")) {
      currentFile.newPath = line.slice(6).trim();
      continue;
    }

    // Hunk header: @@ -oldStart,oldLen +newStart,newLen @@
    if (line.startsWith("@@")) {
      const match = line.match(/@@\s+-(\d+)(?:,\d+)?\s+\+(\d+)(?:,\d+)?\s+@@/);
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

    // Addition line
    if (line.startsWith("+") && !line.startsWith("+++")) {
      currentFile.lines.push({
        type: "addition",
        text: line.slice(1),
        newLine: newLineNum++,
      });
    }
    // Deletion line
    else if (line.startsWith("-") && !line.startsWith("---")) {
      currentFile.lines.push({
        type: "deletion",
        text: line.slice(1),
        oldLine: oldLineNum++,
      });
    }
    // Context line
    else if (line.startsWith(" ") || line === "") {
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

  // Map findings by file path and coordinate (both new and old coordinates supported)
  const { lineFindingsMap, fileLevelFindingsMap } = useMemo(() => {
    const lineMap = new Map<string, Finding[]>();
    const fileMap = new Map<string, Finding[]>();

    for (const f of findings) {
      if (!f.file_path) continue;
      const cleanPath = f.file_path.replace(/^(?:a\/|b\/)/, "");

      // If line_start is missing or 0, categorize as file-level finding
      if (!f.line_start || f.line_start <= 0) {
        const existing = fileMap.get(cleanPath) || [];
        existing.push(f);
        fileMap.set(cleanPath, existing);
        continue;
      }

      // Range coordinates or single line coordinate
      const lineStart = f.line_start;
      const lineEnd = f.line_end || lineStart;

      for (let l = lineStart; l <= lineEnd; l++) {
        const key = `${cleanPath}:${l}`;
        const existing = lineMap.get(key) || [];
        if (!existing.some((item) => item.id === f.id)) {
          existing.push(f);
        }
        lineMap.set(key, existing);
      }
    }

    return { lineFindingsMap: lineMap, fileLevelFindingsMap: fileMap };
  }, [findings]);

  if (!diff || files.length === 0) {
    return (
      <div className="rounded-xl border border-border bg-panel p-8 text-center">
        <div className="text-3xl mb-2" aria-hidden="true">📄</div>
        <h3 className="text-sm font-semibold text-foreground">No Unified Diff Available</h3>
        <p className="text-xs text-muted mt-1 max-w-md mx-auto">
          Diff data was not attached or is unavailable for this pull request commit. All findings detected by specialist agents are listed in the findings breakdown.
        </p>
      </div>
    );
  }

  const currentFile = files[selectedFileIdx] || files[0];
  const activeFilePath = currentFile.newPath !== "unknown" ? currentFile.newPath : currentFile.oldPath;
  const currentFileLevelFindings = fileLevelFindingsMap.get(activeFilePath) || [];

  return (
    <div className="rounded-xl border border-border bg-panel overflow-hidden">
      {/* File Navigation Bar */}
      <div
        role="tablist"
        aria-label="Diff file selector"
        className="flex items-center gap-2 px-4 py-3 bg-surface/60 border-b border-border overflow-x-auto text-xs"
      >
        <span className="text-muted font-medium mr-1 shrink-0">Changed files:</span>
        {files.map((file, idx) => {
          const filePath = file.newPath !== "unknown" ? file.newPath : file.oldPath;
          const fileFindings = findings.filter(
            (f) => f.file_path && f.file_path.replace(/^(?:a\/|b\/)/, "") === filePath
          );
          const isSelected = selectedFileIdx === idx;

          return (
            <button
              key={idx}
              role="tab"
              aria-selected={isSelected}
              onClick={() => setSelectedFileIdx(idx)}
              className={`px-3 py-1.5 rounded-lg font-mono text-xs transition-colors shrink-0 flex items-center gap-2 ${
                isSelected
                  ? "bg-primary-action text-foreground font-semibold shadow-sm"
                  : "bg-surface text-muted hover:text-foreground border border-border hover:bg-raised"
              }`}
            >
              <span>{filePath}</span>
              {file.isDeleted && (
                <span className="px-1.5 py-0.5 rounded text-[10px] bg-err/20 text-err font-medium">
                  deleted
                </span>
              )}
              {file.isNew && (
                <span className="px-1.5 py-0.5 rounded text-[10px] bg-ok/20 text-ok font-medium">
                  new
                </span>
              )}
              {file.isBinary && (
                <span className="px-1.5 py-0.5 rounded text-[10px] bg-warn/20 text-warn font-medium">
                  binary
                </span>
              )}
              {fileFindings.length > 0 && (
                <span className="px-1.5 py-0.5 rounded-full text-[10px] bg-err/20 text-err font-bold">
                  {fileFindings.length}
                </span>
              )}
            </button>
          );
        })}
      </div>

      {/* Binary file notification */}
      {currentFile.isBinary ? (
        <div className="p-8 text-center text-sm text-muted">
          <p className="font-medium text-foreground">Binary file diff</p>
          <p className="text-xs mt-1">Binary changes cannot be displayed as inline unified text.</p>
        </div>
      ) : (
        <>
          {/* File-level findings callout */}
          {currentFileLevelFindings.length > 0 && (
            <div className="bg-warn/10 border-b border-warn/30 p-4 space-y-2">
              <p className="text-xs font-semibold text-warn uppercase tracking-wider">
                File-level findings for {activeFilePath}
              </p>
              {currentFileLevelFindings.map((f, idx) => (
                <div key={idx} className="rounded-lg border border-warn/30 bg-surface/80 p-3 text-xs">
                  <div className="flex items-center gap-2 mb-1">
                    <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-warn/20 text-warn">
                      {f.severity || "UNKNOWN"}
                    </span>
                    <span className="font-semibold text-accent">{f.agent_type || "agent"}</span>
                    <span className="text-muted font-mono">
                      {f.confidence != null
                        ? `Confidence: ${Math.round(f.confidence * 100)}%`
                        : "Confidence: Unknown"}
                    </span>
                  </div>
                  <p className="font-medium text-foreground">{f.summary}</p>
                  {f.suggestion && (
                    <pre className="mt-2 text-xs bg-bg border border-border rounded p-2 text-muted font-mono whitespace-pre-wrap">
                      {f.suggestion}
                    </pre>
                  )}
                </div>
              ))}
            </div>
          )}

          {/* Code Diff Table */}
          <div
            role="region"
            aria-label={`Diff for ${activeFilePath}`}
            tabIndex={0}
            className="overflow-x-auto font-mono text-xs focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-accent"
          >
            <table className="w-full border-collapse">
              <tbody>
                {currentFile.lines.map((line, lineIdx) => {
                  // Check matching findings on either new line or old line coordinates
                  const matchingFindings: Finding[] = [];
                  if (line.newLine) {
                    const newKey = `${activeFilePath}:${line.newLine}`;
                    const matches = lineFindingsMap.get(newKey);
                    if (matches) matchingFindings.push(...matches);
                  }
                  if (line.oldLine) {
                    const oldKey = `${activeFilePath}:${line.oldLine}`;
                    const matches = lineFindingsMap.get(oldKey);
                    if (matches) {
                      for (const m of matches) {
                        if (!matchingFindings.some((existing) => existing.id === m.id)) {
                          matchingFindings.push(m);
                        }
                      }
                    }
                  }

                  return (
                    <React.Fragment key={lineIdx}>
                      {line.type === "header" ? (
                        <tr className="bg-surface/50 text-muted/80">
                          <td
                            colSpan={3}
                            className="py-1 px-4 text-[11px] select-none italic border-y border-border"
                          >
                            {line.text}
                          </td>
                        </tr>
                      ) : (
                        <tr
                          className={`hover:bg-surface/60 transition-colors ${
                            line.type === "addition"
                              ? "bg-ok/10 text-ok"
                              : line.type === "deletion"
                              ? "bg-err/10 text-err"
                              : "text-foreground/90"
                          }`}
                        >
                          {/* Old Line # */}
                          <td className="w-12 py-0.5 px-2 text-right select-none text-muted/60 border-r border-border text-[11px]">
                            {line.oldLine ?? ""}
                          </td>
                          {/* New Line # */}
                          <td className="w-12 py-0.5 px-2 text-right select-none text-muted/60 border-r border-border text-[11px]">
                            {line.newLine ?? ""}
                          </td>
                          {/* Prefix & Line Content */}
                          <td className="py-0.5 px-3 whitespace-pre">
                            <span className="select-none font-bold mr-2 text-muted/60">
                              {line.type === "addition" ? "+" : line.type === "deletion" ? "-" : " "}
                            </span>
                            {line.text}
                          </td>
                        </tr>
                      )}

                      {/* Inline Findings Display */}
                      {matchingFindings.length > 0 &&
                        matchingFindings.map((finding, fIdx) => (
                          <tr
                            key={`finding-${fIdx}`}
                            className="bg-err/10 border-y-2 border-err/50"
                          >
                            <td
                              colSpan={2}
                              className="bg-err/20 text-center py-2 text-err font-bold select-none text-xs"
                            >
                              ⚠️
                            </td>
                            <td className="p-3 text-foreground">
                              <div className="flex flex-wrap items-center gap-2 mb-1.5">
                                <span className="px-2 py-0.5 rounded text-[10px] font-bold uppercase tracking-wider bg-err/20 text-err border border-err/30">
                                  {finding.severity || "UNKNOWN"}
                                </span>
                                <span className="text-xs font-semibold text-accent">
                                  {finding.agent_type || "agent"}
                                </span>
                                <span className="text-[10px] text-muted font-mono">
                                  {finding.confidence != null
                                    ? `Confidence: ${Math.round(finding.confidence * 100)}%`
                                    : "Confidence: Unknown"}
                                </span>
                                {finding.file_path && (
                                  <span className="text-[10px] text-muted font-mono">
                                    {finding.file_path}
                                    {finding.line_start ? `:${finding.line_start}` : ""}
                                  </span>
                                )}
                              </div>
                              <div className="text-xs font-medium text-foreground">
                                {finding.summary}
                              </div>
                              {finding.suggestion && (
                                <div className="mt-2 text-xs bg-panel border border-border rounded p-2.5 text-foreground font-mono whitespace-pre-wrap">
                                  <div className="text-muted text-[10px] uppercase tracking-wider mb-1">
                                    Suggested change:
                                  </div>
                                  {finding.suggestion}
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
        </>
      )}
    </div>
  );
}

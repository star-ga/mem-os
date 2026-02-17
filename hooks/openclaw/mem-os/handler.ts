/**
 * Mem OS hook handler for OpenClaw
 *
 * - agent:bootstrap  → injects health summary into bootstrap context
 * - command:new      → runs capture.py to extract session signals
 */

import { execSync } from "node:child_process";
import fs from "node:fs";
import path from "node:path";

// Resolve MEM_OS_WORKSPACE from hook config env, process env, or default
function resolveWorkspace(event: any): string {
  const hookEnv = event.context?.cfg?.hooks?.internal?.entries?.["mem-os"]?.env;
  return (
    hookEnv?.MEM_OS_WORKSPACE ||
    process.env.MEM_OS_WORKSPACE ||
    "."
  );
}

// Find mem-os scripts directory (relative to workspace or standard locations)
function resolveScriptsDir(workspace: string): string | null {
  // Check .mem-os/scripts/ (cloned into project)
  const dotMemOs = path.join(workspace, ".mem-os", "scripts");
  if (fs.existsSync(dotMemOs)) return dotMemOs;

  // Check mem-os/scripts/ in workspace parent
  const parentMemOs = path.join(path.dirname(workspace), "mem-os", "scripts");
  if (fs.existsSync(parentMemOs)) return parentMemOs;

  // Check MEM_OS_HOME env var
  const memOsHome = process.env.MEM_OS_HOME;
  if (memOsHome) {
    const homeScripts = path.join(memOsHome, "scripts");
    if (fs.existsSync(homeScripts)) return homeScripts;
  }

  return null;
}

const handler = async (event: any): Promise<void> => {
  const workspace = resolveWorkspace(event);

  if (event.type === "agent" && event.action === "bootstrap") {
    // Inject health summary into bootstrap context
    const statePath = path.join(workspace, "memory", "intel-state.json");
    try {
      if (!fs.existsSync(statePath)) return;

      const raw = fs.readFileSync(statePath, "utf-8");
      const state = JSON.parse(raw);
      const mode = state.governance_mode || "unknown";
      const lastScan = state.last_scan || "never";
      const contradictions = state.counters?.contradictions_open || 0;

      const summary = `mem-os health: mode=${mode} last_scan=${lastScan} contradictions=${contradictions}`;

      // Push into bootstrap files if context supports it
      if (event.context?.bootstrapFiles && Array.isArray(event.context.bootstrapFiles)) {
        event.context.bootstrapFiles.push({
          path: "mem-os-health",
          content: summary,
          type: "system",
        });
      } else {
        event.messages.push(summary);
      }
    } catch {
      // Non-fatal — workspace may not be initialized
    }
    return;
  }

  if (event.type === "command" && event.action === "new") {
    // Run capture.py on session end (/new)
    const scriptsDir = resolveScriptsDir(workspace);
    if (!scriptsDir) return;

    const capturePy = path.join(scriptsDir, "capture.py");
    if (!fs.existsSync(capturePy)) return;

    try {
      execSync(`python3 "${capturePy}" "${workspace}"`, {
        timeout: 10_000,
        stdio: "pipe",
        env: { ...process.env, MEM_OS_WORKSPACE: workspace },
      });
    } catch {
      // Non-fatal — capture failures shouldn't block /new
    }
    return;
  }
};

export default handler;

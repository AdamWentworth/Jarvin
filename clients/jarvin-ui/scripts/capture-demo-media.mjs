#!/usr/bin/env node

import { chromium } from "@playwright/test";
import { spawn } from "node:child_process";
import { promises as fs } from "node:fs";
import http from "node:http";
import net from "node:net";
import path from "node:path";
import { fileURLToPath } from "node:url";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const appRoot = path.resolve(__dirname, "..");
const outputRoot = path.join(appRoot, "artifacts", "demo-media", "jarvin");
const screenshotsDir = path.join(outputRoot, "screenshots");
const videosDir = path.join(outputRoot, "videos");
const tempVideoDir = path.join(outputRoot, ".video-temp");

const viewport = {
  width: Number(process.env.JARVIN_DEMO_WIDTH ?? 1760),
  height: Number(process.env.JARVIN_DEMO_HEIGHT ?? 1100),
};

const clickDelay = Number(process.env.JARVIN_DEMO_CLICK_DELAY_MS ?? 220);
const stepDelay = Number(process.env.JARVIN_DEMO_STEP_DELAY_MS ?? 520);

const liveSnapshot = {
  seq: 100,
  rev: 100,
  transcript: "Show me the Jarvin workspace status.",
  reply: "Workspace is ready. Host tools are available behind approval.",
  recording: false,
  processing: false,
  utter_ms: 2120,
  cycle_ms: 4380,
  event_kind: null,
  event_conversation_id: null,
  utter_ts: "2026-07-07T08:30:00.000Z",
  reply_ts: "2026-07-07T08:30:04.000Z",
  tts_url: null,
};

function nowIso() {
  return "2026-07-07T08:30:00.000Z";
}

function weatherPayload() {
  return {
    location_query: "Vancouver",
    location_label: "Vancouver, BC",
    target_label: "Today",
    date_label: "Tuesday, July 7",
    summary: "Comfortable morning, light cloud, and a dry afternoon window for errands.",
    icon_name: "partly-cloudy-day",
    temperature: "19 C",
    feels_like: "20 C",
    temperature_value: 19,
    feels_like_value: 20,
    high_value: 24,
    low_value: 15,
    precipitation_probability: 14,
    wind: "NW 10 km/h",
    daily_outlook: "Good focus block weather: bright but not too hot. Evening cools off quickly.",
    is_current_day: true,
    source: "Demo weather fixture",
  };
}

function taskPayload(status = "pending") {
  const completed = status === "completed";

  return {
    status,
    title: completed ? "Jarvin API route review complete" : "Review Jarvin API route surface",
    summary: completed
      ? "Jarvin inspected the API entry points and summarized the host-facing routes without changing files."
      : "Jarvin will inspect backend API route files and produce a short implementation map.",
    risk_level: "medium",
    access_mode: "approve_risky",
    can_approve: !completed,
    completed_steps: completed ? 3 : 0,
    total_steps: 3,
    details: [
      "Read-only workspace inspection.",
      "No commands that mutate files or services.",
      "Results will stay in the active conversation.",
    ],
    steps: [
      {
        step_id: "routes",
        title: "Locate FastAPI routers",
        action_kind: "workspace_read",
        risk_level: "low",
        status: completed ? "completed" : "pending",
        path: "backend/api/routes",
        detail: completed ? "Found health, chat, live, audio, LLM, reminders, workspace, and agent routes." : null,
      },
      {
        step_id: "app",
        title: "Inspect app wiring",
        action_kind: "workspace_read",
        risk_level: "low",
        status: completed ? "completed" : "pending",
        path: "backend/api/app.py",
        detail: completed ? "Confirmed the host serves the client shell and mounts API routers cleanly." : null,
      },
      {
        step_id: "summary",
        title: "Summarize host task boundary",
        action_kind: "assistant_reply",
        risk_level: "medium",
        status: completed ? "completed" : "pending",
        preview_block: completed
          ? "Host tools stay approval-gated by default. Reads are safe for demos; writes and commands should remain explicit."
          : "Awaiting approval before Jarvin performs the inspection.",
      },
    ],
  };
}

function approvalPayload(status = "pending") {
  return {
    status,
    action_kind: "workspace_write",
    title: "Draft README note",
    summary: "Jarvin prepared a short README note and is waiting for approval before writing it.",
    risk_level: "medium",
    details: [
      "Target path: README.md",
      "The proposed edit is documentation-only.",
      "Approve once or trust this chat for similar actions.",
    ],
    access_mode: "approve_risky",
    can_approve: status === "pending",
    can_trust_conversation: status === "pending",
    can_trust_session: status === "pending",
    trust_active: status === "trusted",
    trust_scope: status === "trusted" ? "conversation" : null,
    preview_block:
      "## Jarvin host tasks\n\nJarvin can inspect local project files, propose edits, and wait for approval before touching the workspace.",
  };
}

function createDemoState(activeConversationId = 1) {
  const profile = {
    name: "Adam",
    goal: "Ship polished project demos into Phlosion without manual filming.",
    mood: "Focused",
    communication_style: "Direct",
    response_length: "Balanced",
  };

  const histories = {
    1: [
      {
        role: "user",
        message: "Give me my morning brief for today.",
      },
      {
        role: "assistant",
        message:
          "Here is the compact version: weather is mild, the calendar is open enough for a focused block, and the highest leverage work is finishing demo media for Phlosion.",
        tool_kind: "weather",
        tool_payload: weatherPayload(),
      },
    ],
    2: [
      {
        role: "user",
        message: "Inspect the Jarvin API routes and summarize the host-task surface.",
      },
      {
        role: "assistant",
        message:
          "I can do that as a read-only host task. I will inspect the route files and report back before any risky action.",
        tool_kind: "task_request",
        tool_payload: taskPayload("pending"),
      },
    ],
    3: [
      {
        role: "user",
        message: "Can I use my phone as the microphone for Jarvin?",
      },
      {
        role: "assistant",
        message:
          "Yes. The client can capture phone audio, send it to the host for transcription, and keep uncertain transcripts in review before sending them to chat.",
      },
    ],
    4: [
      {
        role: "user",
        message: "Prepare a README note about host tasks.",
      },
      {
        role: "assistant",
        message: "I drafted the note below and need approval before writing to the workspace.",
        tool_kind: "approval_request",
        tool_payload: approvalPayload("pending"),
      },
    ],
  };

  return {
    nextConversationId: 5,
    activeConversationId,
    profile,
    histories,
    llm: {
      backend_choices: [
        { label: "llama.cpp", value: "llama_cpp" },
        { label: "Ollama", value: "ollama_http" },
      ],
      current_backend: "llama_cpp",
      current_model: "Qwen2.5 Coder 14B Instruct",
      local_model_choices: [
        { label: "Qwen2.5 Coder 14B Instruct", value: "qwen2.5-coder-14b-instruct" },
        { label: "Llama 3.1 8B Instruct", value: "llama-3.1-8b-instruct" },
      ],
      ollama_model_choices: [
        { label: "llama3.1:8b", value: "llama3.1:8b" },
        { label: "qwen2.5-coder:14b", value: "qwen2.5-coder:14b" },
      ],
      ollama_available: true,
      ollama_error: null,
      message: "Demo runtime selected. No model process is started during capture.",
    },
    audioDevices: {
      devices: [
        { index: 0, name: "ThinkPad Array Microphone" },
        { index: 1, name: "Phone remote input" },
        { index: 2, name: "USB headset microphone" },
      ],
      selected_index: 0,
      selected_name: "ThinkPad Array Microphone",
    },
    actions: [
      {
        id: 502,
        created_at: "2026-07-07T08:22:00.000Z",
        conversation_id: 2,
        event_kind: "approval_requested",
        action_kind: "workspace_read",
        risk_level: "medium",
        access_mode: "approve_risky",
        title: "Review Jarvin API route surface",
        summary: "Read-only inspection queued for backend API route files.",
        path: "backend/api/routes",
        working_directory: "/home/adam/Projects/Jarvin",
        detail: "Awaiting approval in the active conversation.",
      },
      {
        id: 501,
        created_at: "2026-07-07T08:11:00.000Z",
        conversation_id: 4,
        event_kind: "approval_requested",
        action_kind: "workspace_write",
        risk_level: "medium",
        access_mode: "approve_risky",
        title: "Draft README note",
        summary: "Prepared a documentation-only patch.",
        path: "README.md",
        diff_preview: "+ Jarvin can inspect local project files and wait for approval before risky host actions.",
      },
    ],
  };
}

function conversationTitle(id) {
  return (
    {
      1: "Morning brief",
      2: "Workspace tasks",
      3: "Voice review",
      4: "Approval guardrails",
    }[id] ?? `Conversation ${id}`
  );
}

function workspacePayload(state) {
  const ids = Object.keys(state.histories)
    .map(Number)
    .sort((a, b) => a - b);
  return {
    profile: state.profile,
    conversations: ids.map((id) => ({
      id,
      title: conversationTitle(id),
      created_at: nowIso(),
      messages: state.histories[id].length,
      is_active: id === state.activeConversationId,
    })),
    active_conversation_id: state.activeConversationId,
    history: state.histories[state.activeConversationId] ?? [],
  };
}

async function fulfillJson(route, body, status = 200) {
  await route.fulfill({
    status,
    headers: {
      "access-control-allow-origin": "*",
      "access-control-allow-headers": "*",
      "access-control-allow-methods": "GET,POST,PUT,PATCH,DELETE,OPTIONS",
    },
    contentType: "application/json",
    body: JSON.stringify(body),
  });
}

async function mockJarvinApi(page, state) {
  await page.route(/http:\/\/(127\.0\.0\.1|localhost):8000\/.*/, async (route) => {
    const request = route.request();
    const url = new URL(request.url());
    const method = request.method().toUpperCase();
    const pathname = url.pathname;

    if (method === "OPTIONS") {
      await fulfillJson(route, {});
      return;
    }

    if (pathname === "/live/stream") {
      await route.fulfill({
        status: 200,
        headers: {
          "access-control-allow-origin": "*",
          "cache-control": "no-cache",
        },
        contentType: "text/event-stream",
        body: `event: live\ndata: ${JSON.stringify(liveSnapshot)}\n\n`,
      });
      return;
    }

    if (pathname === "/workspace/bootstrap") {
      await fulfillJson(route, workspacePayload(state));
      return;
    }

    if (pathname === "/llm/options") {
      await fulfillJson(route, state.llm);
      return;
    }

    if (pathname === "/llm/select" && method === "POST") {
      const body = request.postDataJSON();
      state.llm.current_backend = body.backend;
      state.llm.current_model = body.model;
      state.llm.message = "Demo runtime selected.";
      await fulfillJson(route, state.llm);
      return;
    }

    if (pathname === "/audio/devices") {
      await fulfillJson(route, state.audioDevices);
      return;
    }

    if (pathname === "/audio/select" && method === "POST") {
      const body = request.postDataJSON();
      const selected = state.audioDevices.devices.find((device) => device.index === body.index);
      state.audioDevices.selected_index = selected?.index ?? null;
      state.audioDevices.selected_name = selected?.name ?? null;
      await fulfillJson(route, {
        ok: true,
        selected_index: state.audioDevices.selected_index,
        selected_name: state.audioDevices.selected_name,
        message: "Demo host input selected.",
      });
      return;
    }

    if (pathname === "/healthz") {
      await fulfillJson(route, { status: "ok", listening: false });
      return;
    }

    if (pathname === "/status") {
      await fulfillJson(route, { listening: false });
      return;
    }

    if (pathname === "/live") {
      await fulfillJson(route, liveSnapshot);
      return;
    }

    if (pathname === "/reminders" || pathname === "/reminders/due") {
      await fulfillJson(route, {
        reminders: [
          {
            id: 12,
            title: "Review Phlosion demo media",
            notes: "Make sure project cards stay uniform.",
            due_at: "2026-07-07T16:00:00.000Z",
            recurrence: "",
            status: "pending",
            created_at: nowIso(),
            updated_at: nowIso(),
            completed_at: null,
            is_routine: false,
            is_overdue: false,
          },
        ],
      });
      return;
    }

    if (pathname === "/agent/actions") {
      await fulfillJson(route, { actions: state.actions });
      return;
    }

    if (pathname === "/profile" && method === "PUT") {
      state.profile = request.postDataJSON();
      await fulfillJson(route, state.profile);
      return;
    }

    if (pathname === "/start" && method === "POST") {
      await fulfillJson(route, { ok: true, message: "Demo listener started." });
      return;
    }

    if (pathname === "/stop" && method === "POST") {
      await fulfillJson(route, { ok: true, message: "Demo listener paused." });
      return;
    }

    if (pathname === "/shutdown" && method === "POST") {
      await fulfillJson(route, { ok: true, message: "Demo host shutdown skipped." });
      return;
    }

    if (pathname === "/chat" && method === "POST") {
      const body = request.postDataJSON();
      const conversationId = Number(body.conversation_id ?? state.activeConversationId ?? 1);
      state.activeConversationId = conversationId;
      state.histories[conversationId] ??= [];
      const userText = String(body.user_text ?? "");
      state.histories[conversationId].push({ role: "user", message: userText });

      const lower = userText.toLowerCase();
      let reply;
      if (lower.includes("brief") || lower.includes("weather")) {
        reply = {
          role: "assistant",
          message:
            "Here is the morning pass: weather is mild, there are no urgent reminders due, and the best next move is a focused Phlosion media review.",
          tool_kind: "weather",
          tool_payload: weatherPayload(),
        };
      } else if (lower.includes("route") || lower.includes("repo") || lower.includes("host") || lower.includes("task")) {
        reply = {
          role: "assistant",
          message:
            "I can inspect that safely as a host task. This is read-only, but I will still show the action before running it.",
          tool_kind: "task_request",
          tool_payload: taskPayload("pending"),
        };
      } else {
        reply = {
          role: "assistant",
          message:
            "Done. I would keep the answer short, preserve local privacy, and only ask for host access when the task needs it.",
          tool_kind: null,
          tool_payload: null,
        };
      }

      state.histories[conversationId].push(reply);
      await fulfillJson(route, {
        reply: reply.message,
        mode_used: body.mode ?? "chat_balanced",
        conversation_id: conversationId,
        tts_url: null,
        tool_kind: reply.tool_kind,
        tool_payload: reply.tool_payload,
      });
      return;
    }

    if (pathname === "/agent/approvals/respond" && method === "POST") {
      const body = request.postDataJSON();
      const conversationId = Number(body.conversation_id ?? state.activeConversationId ?? 2);
      const decision = String(body.decision ?? "approve");
      const history = state.histories[conversationId] ?? [];
      const lastToolTurn = [...history].reverse().find((turn) => turn.role === "assistant" && turn.tool_kind);

      if (lastToolTurn?.tool_kind === "task_request") {
        lastToolTurn.message =
          decision === "deny"
            ? "No problem. I left the workspace untouched."
            : "Approved. I inspected the route files and summarized the host-task boundary below.";
        lastToolTurn.tool_payload = taskPayload(decision === "deny" ? "denied" : "completed");
      } else if (lastToolTurn?.tool_kind === "approval_request") {
        lastToolTurn.tool_payload = approvalPayload(decision.includes("trust") ? "trusted" : decision === "deny" ? "denied" : "approved");
      }

      state.actions.unshift({
        id: 503,
        created_at: nowIso(),
        conversation_id: conversationId,
        event_kind: decision === "deny" ? "approval_denied" : "approval_approved",
        action_kind: "workspace_read",
        risk_level: "medium",
        access_mode: "approve_risky",
        title: "Review Jarvin API route surface",
        summary: decision === "deny" ? "Host task was denied." : "Host task completed in read-only mode.",
        path: "backend/api/routes",
        working_directory: "/home/adam/Projects/Jarvin",
      });

      await fulfillJson(route, {
        reply: lastToolTurn?.message ?? "Approval handled.",
        mode_used: "agent_strong",
        conversation_id: conversationId,
        tts_url: null,
        tool_kind: lastToolTurn?.tool_kind ?? null,
        tool_payload: lastToolTurn?.tool_payload ?? null,
      });
      return;
    }

    const activateMatch = pathname.match(/^\/conversations\/(\d+)\/activate$/);
    if (activateMatch && method === "POST") {
      state.activeConversationId = Number(activateMatch[1]);
      await fulfillJson(route, workspacePayload(state));
      return;
    }

    const clearMatch = pathname.match(/^\/conversations\/(\d+)\/clear$/);
    if (clearMatch && method === "POST") {
      const conversationId = Number(clearMatch[1]);
      state.histories[conversationId] = [];
      await fulfillJson(route, workspacePayload(state));
      return;
    }

    const conversationMatch = pathname.match(/^\/conversations(?:\/(\d+))?$/);
    if (conversationMatch && method === "POST") {
      const body = request.postDataJSON();
      const id = state.nextConversationId++;
      state.activeConversationId = id;
      state.histories[id] = [];
      if (body?.title) {
        state.customTitles ??= {};
        state.customTitles[id] = body.title;
      }
      await fulfillJson(route, workspacePayload(state));
      return;
    }

    if (conversationMatch && method === "PATCH") {
      await fulfillJson(route, workspacePayload(state));
      return;
    }

    if (conversationMatch && method === "DELETE") {
      const id = Number(conversationMatch[1]);
      delete state.histories[id];
      state.activeConversationId = Number(Object.keys(state.histories)[0] ?? 1);
      await fulfillJson(route, workspacePayload(state));
      return;
    }

    await fulfillJson(route, { detail: `Unhandled demo route: ${method} ${pathname}` }, 404);
  });
}

async function findOpenPort(startPort) {
  for (let port = startPort; port < startPort + 50; port += 1) {
    const available = await new Promise((resolve) => {
      const server = net.createServer();
      server.once("error", () => resolve(false));
      server.once("listening", () => {
        server.close(() => resolve(true));
      });
      server.listen(port, "127.0.0.1");
    });
    if (available) {
      return port;
    }
  }
  throw new Error(`Could not find an open Vite port starting at ${startPort}.`);
}

async function waitForHttp(url, timeoutMs = 30_000) {
  const started = Date.now();
  while (Date.now() - started < timeoutMs) {
    try {
      await new Promise((resolve, reject) => {
        const request = http.get(url, (response) => {
          response.resume();
          if ((response.statusCode ?? 500) < 500) {
            resolve();
          } else {
            reject(new Error(`HTTP ${response.statusCode}`));
          }
        });
        request.on("error", reject);
        request.setTimeout(1000, () => {
          request.destroy(new Error("Timed out waiting for Vite."));
        });
      });
      return;
    } catch {
      await delay(250);
    }
  }
  throw new Error(`Timed out waiting for ${url}`);
}

async function startViteServer() {
  const port = await findOpenPort(Number(process.env.JARVIN_DEMO_PORT ?? 5178));
  const url = `http://127.0.0.1:${port}`;
  const child = spawn(
    "npm",
    ["run", "dev", "--", "--host", "127.0.0.1", "--port", String(port), "--strictPort"],
    {
      cwd: appRoot,
      env: { ...process.env, BROWSER: "none" },
      stdio: ["ignore", "pipe", "pipe"],
      detached: process.platform !== "win32",
    },
  );

  let buffered = "";
  child.stdout.on("data", (chunk) => {
    buffered += chunk.toString();
  });
  child.stderr.on("data", (chunk) => {
    buffered += chunk.toString();
  });

  child.on("exit", (code) => {
    if (code && code !== 0) {
      console.error(buffered.trim());
    }
  });

  await waitForHttp(url);
  return {
    url,
    stop: async () => {
      if (child.exitCode !== null) {
        return;
      }
      if (process.platform === "win32") {
        child.kill("SIGTERM");
      } else {
        process.kill(-child.pid, "SIGTERM");
      }
      await new Promise((resolve) => {
        child.once("exit", resolve);
        setTimeout(() => {
          if (child.exitCode === null) {
            if (process.platform === "win32") {
              child.kill("SIGKILL");
            } else {
              process.kill(-child.pid, "SIGKILL");
            }
          }
          resolve();
        }, 2500).unref();
      });
    },
  };
}

async function openDemoPage(browser, appUrl, options = {}) {
  const context = await browser.newContext({
    viewport,
    locale: "en-US",
    timezoneId: "America/Vancouver",
    recordVideo: options.videoName
      ? {
          dir: tempVideoDir,
          size: viewport,
        }
      : undefined,
  });

  await context.addInitScript((snapshot) => {
    window.localStorage.clear();
    window.localStorage.setItem("jarvin.agentAccessMode", "approve_risky");

    class JarvinDemoEventSource extends EventTarget {
      static CONNECTING = 0;
      static OPEN = 1;
      static CLOSED = 2;

      constructor(url) {
        super();
        this.url = String(url);
        this.withCredentials = false;
        this.readyState = JarvinDemoEventSource.OPEN;
        window.setTimeout(() => {
          if (this.readyState === JarvinDemoEventSource.CLOSED) {
            return;
          }
          const openEvent = new Event("open");
          this.onopen?.(openEvent);
          this.dispatchEvent(openEvent);

          const messageEvent = new MessageEvent("message", { data: JSON.stringify(snapshot) });
          this.onmessage?.(messageEvent);
          this.dispatchEvent(messageEvent);

          const liveEvent = new MessageEvent("live", { data: JSON.stringify(snapshot) });
          this.dispatchEvent(liveEvent);
        }, 80);
      }

      close() {
        this.readyState = JarvinDemoEventSource.CLOSED;
      }
    }

    window.EventSource = JarvinDemoEventSource;
  }, liveSnapshot);

  const page = await context.newPage();
  page.setDefaultTimeout(18_000);
  const state = createDemoState(options.activeConversationId ?? 1);
  await mockJarvinApi(page, state);
  await page.goto(appUrl, { waitUntil: "domcontentloaded" });
  await waitForJarvinReady(page);
  if (options.cursor !== false) {
    await installDemoCursor(page);
  }
  return { context, page, state };
}

async function waitForJarvinReady(page) {
  await page.locator(".workspace-grid").waitFor({ state: "visible", timeout: 30_000 });
  await page.locator(".loading-shell").waitFor({ state: "detached", timeout: 10_000 }).catch(() => {});
  await page.waitForLoadState("networkidle", { timeout: 6000 }).catch(() => {});
  await delay(300);
}

async function installDemoCursor(page) {
  await page.addStyleTag({
    content: `
      .jarvin-demo-cursor {
        position: fixed;
        left: 0;
        top: 0;
        width: 28px;
        height: 36px;
        z-index: 2147483647;
        pointer-events: none;
        transform: translate(36px, 36px);
        filter: drop-shadow(0 2px 4px rgba(0, 0, 0, 0.55));
      }

      .jarvin-demo-cursor svg {
        display: block;
        width: 100%;
        height: 100%;
      }

      .jarvin-demo-click-ring {
        position: fixed;
        width: 34px;
        height: 34px;
        margin: -17px 0 0 -17px;
        border: 2px solid rgba(244, 234, 209, 0.82);
        border-radius: 999px;
        z-index: 2147483646;
        pointer-events: none;
        animation: jarvinDemoClickRing 0.48s ease-out forwards;
      }

      @keyframes jarvinDemoClickRing {
        from {
          transform: scale(0.55);
          opacity: 0.9;
        }
        to {
          transform: scale(1.9);
          opacity: 0;
        }
      }
    `,
  });

  await page.evaluate(() => {
    const existing = document.querySelector(".jarvin-demo-cursor");
    if (existing) {
      existing.remove();
    }
    const cursor = document.createElement("div");
    cursor.className = "jarvin-demo-cursor";
    cursor.innerHTML = `
      <svg viewBox="0 0 28 36" aria-hidden="true">
        <path d="M3 2.5L23.8 22.9L13.7 23.5L18.9 34.1L13.5 36L8.5 25.4L1.8 32.3L3 2.5Z" fill="#f8f4ea" stroke="#111318" stroke-width="2" stroke-linejoin="round"/>
      </svg>
    `;
    document.body.append(cursor);

    window.__jarvinDemoCursorMove = (x, y) => {
      cursor.style.transform = `translate(${x}px, ${y}px)`;
    };
    window.__jarvinDemoCursorClick = (x, y) => {
      const ring = document.createElement("div");
      ring.className = "jarvin-demo-click-ring";
      ring.style.left = `${x}px`;
      ring.style.top = `${y}px`;
      document.body.append(ring);
      window.setTimeout(() => ring.remove(), 560);
    };
  });
}

async function moveMouse(page, x, y, steps = 18) {
  await page.mouse.move(x, y, { steps });
  await page.evaluate(
    ({ nextX, nextY }) => {
      window.__jarvinDemoCursorMove?.(nextX, nextY);
    },
    { nextX: x, nextY: y },
  );
}

async function clickLocator(page, locator, options = {}) {
  await locator.scrollIntoViewIfNeeded();
  const box = await locator.boundingBox();
  if (!box) {
    throw new Error(`Could not locate target for click: ${options.label ?? "unknown"}`);
  }
  const x = box.x + box.width / 2;
  const y = box.y + box.height / 2;
  await moveMouse(page, x, y, options.steps ?? 20);
  await delay(options.beforeClick ?? clickDelay);
  await page.evaluate(
    ({ nextX, nextY }) => {
      window.__jarvinDemoCursorClick?.(nextX, nextY);
    },
    { nextX: x, nextY: y },
  );
  await locator.click({ timeout: 10_000 });
  await delay(options.afterClick ?? stepDelay);
}

async function typeInto(page, locator, value) {
  await locator.scrollIntoViewIfNeeded();
  const box = await locator.boundingBox();
  if (box) {
    await moveMouse(page, box.x + Math.min(48, box.width / 2), box.y + Math.min(28, box.height / 2), 16);
  }
  await locator.click();
  await locator.fill("");
  await locator.pressSequentially(value, { delay: 18 });
  await delay(260);
}

async function selectConversation(page, title) {
  await clickLocator(page, page.locator(".conversation-main").filter({ hasText: title }).first(), {
    label: `conversation ${title}`,
  });
  await page.getByRole("heading", { name: title }).waitFor({ state: "visible" });
}

async function captureScreenshot(page, name) {
  const target = path.join(screenshotsDir, `${name}.png`);
  await page.screenshot({ path: target, fullPage: false });
  console.log(`captured ${path.relative(appRoot, target)}`);
}

async function finishVideo(context, page, videoName) {
  const video = page.video();
  await context.close();
  if (!video) {
    return;
  }
  const source = await video.path();
  const target = path.join(videosDir, `${videoName}.webm`);
  await fs.copyFile(source, target);
  await fs.rm(source, { force: true });
  console.log(`captured ${path.relative(appRoot, target)}`);
}

async function captureScreenshots(browser, appUrl) {
  const { context, page } = await openDemoPage(browser, appUrl, { cursor: false });
  await captureScreenshot(page, "jarvin-chat-workspace-desktop");

  await selectConversation(page, "Morning brief");
  await captureScreenshot(page, "jarvin-morning-brief-desktop");

  await selectConversation(page, "Workspace tasks");
  await captureScreenshot(page, "jarvin-host-task-approval-desktop");

  await clickLocator(page, page.getByLabel("Open settings"), { label: "settings" });
  await captureScreenshot(page, "jarvin-settings-general-desktop");

  await clickLocator(page, page.getByRole("tab", { name: "Voice" }), { label: "voice settings tab" });
  await captureScreenshot(page, "jarvin-settings-voice-desktop");

  await clickLocator(page, page.getByRole("tab", { name: "Profile" }), { label: "profile settings tab" });
  await captureScreenshot(page, "jarvin-settings-profile-desktop");

  await clickLocator(page, page.getByRole("tab", { name: "Diagnostics" }), { label: "diagnostics settings tab" });
  await captureScreenshot(page, "jarvin-settings-diagnostics-desktop");

  await context.close();
}

async function recordMorningBrief(browser, appUrl) {
  const videoName = "jarvin-morning-brief-desktop";
  const { context, page } = await openDemoPage(browser, appUrl, { videoName, activeConversationId: 3 });
  await selectConversation(page, "Morning brief");
  await typeInto(page, page.locator("textarea").first(), "Give me a focused morning brief with weather.");
  await clickLocator(page, page.getByLabel("Send message"), { label: "send morning brief" });
  await page.getByText("Here is the morning pass").waitFor({ state: "visible" });
  await delay(1800);
  await finishVideo(context, page, videoName);
}

async function recordHostTask(browser, appUrl) {
  const videoName = "jarvin-host-task-approval-desktop";
  const { context, page } = await openDemoPage(browser, appUrl, { videoName, activeConversationId: 1 });
  await selectConversation(page, "Workspace tasks");
  await typeInto(page, page.locator("textarea").first(), "Inspect the Jarvin API routes and summarize the host task surface.");
  await clickLocator(page, page.getByLabel("Send message"), { label: "send task request" });
  await page.getByText("Review Jarvin API route surface").last().waitFor({ state: "visible" });
  await delay(750);
  await clickLocator(page, page.getByRole("button", { name: "Approve task" }).last(), {
    label: "approve task",
    afterClick: 700,
  });
  await page.getByText("Progress: 3 / 3 steps complete.").waitFor({ state: "visible" });
  await delay(1400);
  await finishVideo(context, page, videoName);
}

async function recordSettingsTour(browser, appUrl) {
  const videoName = "jarvin-settings-tour-desktop";
  const { context, page } = await openDemoPage(browser, appUrl, { videoName, activeConversationId: 1 });
  await clickLocator(page, page.getByLabel("Open settings"), { label: "settings", afterClick: 900 });
  await clickLocator(page, page.getByRole("tab", { name: "Voice" }), { label: "voice tab", afterClick: 900 });
  await clickLocator(page, page.getByRole("tab", { name: "Profile" }), { label: "profile tab", afterClick: 900 });
  await clickLocator(page, page.getByRole("tab", { name: "Diagnostics" }), { label: "diagnostics tab", afterClick: 900 });
  await page.locator(".settings-dialog-body").evaluate((node) => node.scrollTo({ top: node.scrollHeight, behavior: "smooth" }));
  await delay(1600);
  await finishVideo(context, page, videoName);
}

async function recordApprovalGuardrails(browser, appUrl) {
  const videoName = "jarvin-approval-guardrails-desktop";
  const { context, page } = await openDemoPage(browser, appUrl, { videoName, activeConversationId: 4 });
  await selectConversation(page, "Approval guardrails");
  await delay(700);
  await clickLocator(page, page.getByRole("button", { name: "Trust this chat" }), {
    label: "trust this chat",
    afterClick: 900,
  });
  await page.getByText("Trusted").waitFor({ state: "visible" });
  await delay(1300);
  await finishVideo(context, page, videoName);
}

async function prepareOutput() {
  await fs.rm(outputRoot, { recursive: true, force: true });
  await fs.mkdir(screenshotsDir, { recursive: true });
  await fs.mkdir(videosDir, { recursive: true });
  await fs.mkdir(tempVideoDir, { recursive: true });
}

async function delay(ms) {
  await new Promise((resolve) => setTimeout(resolve, ms));
}

async function main() {
  await prepareOutput();
  const server = await startViteServer();
  const browser = await chromium.launch({ chromiumSandbox: false });
  try {
    console.log(`Jarvin demo capture running at ${server.url}`);
    console.log(`Viewport: ${viewport.width}x${viewport.height}`);
    await captureScreenshots(browser, server.url);
    await recordMorningBrief(browser, server.url);
    await recordHostTask(browser, server.url);
    await recordSettingsTour(browser, server.url);
    await recordApprovalGuardrails(browser, server.url);
    await fs.rm(tempVideoDir, { recursive: true, force: true });
    console.log(`Jarvin demo media saved under ${path.relative(process.cwd(), outputRoot)}`);
  } finally {
    await browser.close().catch(() => {});
    await server.stop();
  }
}

main().catch((error) => {
  console.error(error);
  process.exitCode = 1;
});

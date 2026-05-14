import React from "react";
import ReactDOM from "react-dom/client";
import {
  Activity,
  Bot,
  Check,
  Circle,
  FolderPlus,
  Image as ImageIcon,
  KeyRound,
  Loader2,
  Play,
  RefreshCcw,
  Send,
  Settings,
  Square,
  Terminal,
  Trash2,
  User,
  X,
} from "lucide-react";
import "./styles.css";
import { Badge } from "./components/ui/badge";
import { Button } from "./components/ui/button";
import { Dialog } from "./components/ui/dialog";
import { Input } from "./components/ui/input";
import { Textarea } from "./components/ui/textarea";
import { cn } from "./lib/utils";

type IconComponent = React.ComponentType<{ className?: string; size?: number }>;

type SessionSummary = {
  id: string;
  name: string;
  project_dir: string;
  created_at: string;
  updated_at: string;
  status: string;
  message_count: number;
};

type SessionRecord = SessionSummary & {
  messages: MessageRecord[];
};

type MessageRecord = {
  id?: string;
  type: string;
  created_at?: string;
  content?: string;
  step?: number;
  tool_call_id?: string;
  confirmation_id?: string;
  name?: string;
  arguments?: unknown;
  result?: string;
  success?: boolean;
  project_dir?: string;
  reasoning_content?: string;
  prompt?: string;
  urls?: string[];
  error?: string;
};

type SettingsRecord = {
  api_key_masked: string;
  base_url: string;
  model: string;
  thinking_enabled: boolean;
  ark_image_api_key_masked: string;
  ark_image_base_url: string;
  ark_image_model: string;
  ark_image_size: string;
  ark_image_watermark: boolean;
};

type PendingConfirmation = {
  confirmation_id: string;
  name: string;
  arguments: unknown;
  project_dir: string;
};

type StreamItem = {
  id: string;
  type: "assistant_stream" | "reasoning_stream";
  content: string;
  step?: number;
  created_at: string;
};

function App() {
  const [sessions, setSessions] = React.useState<SessionSummary[]>([]);
  const [activeId, setActiveId] = React.useState<string | null>(null);
  const [activeSession, setActiveSession] = React.useState<SessionRecord | null>(null);
  const [settings, setSettings] = React.useState<SettingsRecord | null>(null);
  const [settingsOpen, setSettingsOpen] = React.useState(false);
  const [newSessionOpen, setNewSessionOpen] = React.useState(false);
  const [pendingConfirmation, setPendingConfirmation] = React.useState<PendingConfirmation | null>(null);
  const [running, setRunning] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);
  const [draft, setDraft] = React.useState("");
  const [newName, setNewName] = React.useState("");
  const [newProject, setNewProject] = React.useState("");
  const [settingsForm, setSettingsForm] = React.useState({
    api_key: "",
    base_url: "",
    model: "",
    ark_image_api_key: "",
    ark_image_base_url: "",
    ark_image_model: "",
    ark_image_size: "",
  });
  const [thinkingEnabled, setThinkingEnabled] = React.useState(true);
  const [arkImageWatermark, setArkImageWatermark] = React.useState(true);
  const [imageFeedbackEnabled, setImageFeedbackEnabled] = React.useState(false);
  const [streamItems, setStreamItems] = React.useState<StreamItem[]>([]);
  const reasoningRef = React.useRef("");
  const currentStepRef = React.useRef<number | undefined>(undefined);
  const viewportRef = React.useRef<HTMLDivElement | null>(null);

  React.useEffect(() => {
    void Promise.all([loadSettings(), loadSessions()]);
  }, []);

  React.useEffect(() => {
    viewportRef.current?.scrollTo({ top: viewportRef.current.scrollHeight, behavior: "smooth" });
  }, [activeSession?.messages, streamItems]);

  async function loadSessions(selectId?: string) {
    const data = await api<{ sessions: SessionSummary[] }>("/api/sessions");
    setSessions(data.sessions);
    const requestedId = selectId ?? activeId;
    const nextId = requestedId && data.sessions.some((session) => session.id === requestedId)
      ? requestedId
      : data.sessions[0]?.id ?? null;
    if (nextId) {
      await openSession(nextId);
    } else {
      setActiveId(null);
      setActiveSession(null);
    }
  }

  async function loadSettings() {
    const data = await api<{ settings: SettingsRecord }>("/api/settings");
    setSettings(data.settings);
    setSettingsForm({
      api_key: "",
      base_url: data.settings.base_url,
      model: data.settings.model,
      ark_image_api_key: "",
      ark_image_base_url: data.settings.ark_image_base_url,
      ark_image_model: data.settings.ark_image_model,
      ark_image_size: data.settings.ark_image_size,
    });
    setThinkingEnabled(data.settings.thinking_enabled);
    setArkImageWatermark(data.settings.ark_image_watermark);
  }

  async function openSession(id: string) {
    const data = await api<{ session: SessionRecord }>(`/api/sessions/${id}`);
    setActiveId(id);
    setActiveSession(data.session);
  }

  async function createSession(event: React.FormEvent) {
    event.preventDefault();
    setError(null);
    const data = await api<{ session: SessionRecord }>("/api/sessions", {
      method: "POST",
      body: JSON.stringify({ name: newName, project_dir: newProject }),
    });
    setNewName("");
    setNewProject("");
    setNewSessionOpen(false);
    await loadSessions(data.session.id);
  }

  async function deleteActiveSession() {
    if (!activeId) return;
    await api(`/api/sessions/${activeId}`, { method: "DELETE" });
    setActiveId(null);
    setActiveSession(null);
    await loadSessions();
  }

  async function saveSettings(event: React.FormEvent) {
    event.preventDefault();
    await api("/api/settings", {
      method: "POST",
      body: JSON.stringify({
        ...settingsForm,
        thinking_enabled: thinkingEnabled,
        ark_image_watermark: arkImageWatermark,
      }),
    });
    await loadSettings();
    setSettingsOpen(false);
  }

  async function sendMessage(event: React.FormEvent) {
    event.preventDefault();
    if (!activeId || running || !draft.trim()) return;
    const content = draft.trim();
    setDraft("");
    setRunning(true);
    setError(null);
    setStreamItems([]);
    reasoningRef.current = "";
    currentStepRef.current = undefined;
    appendLocal({ type: "user", content, created_at: new Date().toISOString() });

    try {
      const response = await fetch(`/api/sessions/${activeId}/messages/stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ content, image_feedback: imageFeedbackEnabled }),
      });
      if (!response.ok || !response.body) throw new Error(await readError(response));

      const reader = response.body.getReader();
      const decoder = new TextDecoder();
      let buffer = "";
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buffer += decoder.decode(value, { stream: true });
        const parts = buffer.split("\n\n");
        buffer = parts.pop() ?? "";
        for (const part of parts) {
          const line = part.split("\n").find((item) => item.startsWith("data: "));
          if (!line) continue;
          handleStreamEvent(JSON.parse(line.slice(6)));
        }
      }
    } catch (err) {
      setError(err instanceof Error ? err.message : String(err));
    } finally {
      setRunning(false);
      setStreamItems([]);
      reasoningRef.current = "";
      currentStepRef.current = undefined;
      await loadSessions(activeId);
    }
  }

  function handleStreamEvent(event: MessageRecord & { message?: MessageRecord }) {
    if (event.type === "user_message") return;
    if (event.type === "step") {
      currentStepRef.current = event.step;
      return;
    }
    if (event.type === "assistant_delta") {
      appendStreamItem("assistant_stream", event.content ?? "");
      return;
    }
    if (event.type === "reasoning_delta") {
      const text = event.content ?? "";
      reasoningRef.current += text;
      appendStreamItem("reasoning_stream", text);
      return;
    }
    if (event.type === "tool_batch") return;
    if (event.type === "assistant_message_complete") {
      return;
    }
    if (event.type === "confirmation_required" && event.confirmation_id) {
      setPendingConfirmation({
        confirmation_id: event.confirmation_id,
        name: event.name ?? "run_command",
        arguments: event.arguments,
        project_dir: event.project_dir ?? "",
      });
    }
    if (event.type === "final") {
      setStreamItems([]);
      reasoningRef.current = "";
      currentStepRef.current = undefined;
      return;
    }
    if (event.type === "tool_call" || event.type === "tool_result") return;
    appendLocal({ ...event, created_at: new Date().toISOString() });
  }

  function appendStreamItem(type: StreamItem["type"], chunk: string) {
    if (!chunk) return;
    const step = currentStepRef.current;
    setStreamItems((items) => {
      const last = items[items.length - 1];
      if (last && last.type === type && last.step === step) {
        return [
          ...items.slice(0, -1),
          { ...last, content: last.content + chunk },
        ];
      }
      return [
        ...items,
        {
          id: crypto.randomUUID(),
          type,
          content: chunk,
          step,
          created_at: new Date().toISOString(),
        },
      ];
    });
  }

  function appendLocal(message: MessageRecord) {
    setActiveSession((session) => {
      if (!session) return session;
      return { ...session, messages: [...session.messages, { ...message, id: crypto.randomUUID() }] };
    });
  }

  async function stopSession() {
    if (!activeId) return;
    await api(`/api/sessions/${activeId}/stop`, { method: "POST" });
    setRunning(false);
  }

  async function resolveConfirmation(approved: boolean) {
    if (!pendingConfirmation) return;
    await api(`/api/tool-confirmations/${pendingConfirmation.confirmation_id}`, {
      method: "POST",
      body: JSON.stringify({ approved }),
    });
    setPendingConfirmation(null);
  }

  const activeSummary = sessions.find((session) => session.id === activeId);
  const messages = activeSession?.messages ?? [];

  return (
    <main className="flex h-screen overflow-hidden bg-[#f7f7f4] text-zinc-950">
      <aside className="flex w-[316px] shrink-0 flex-col border-r border-zinc-900 bg-[#151719] text-zinc-100">
        <div className="flex h-14 items-center justify-between border-b border-zinc-800 px-4">
          <div>
            <div className="text-sm font-semibold">AgentV2</div>
            <div className="text-xs text-zinc-500">local coding workspace</div>
          </div>
          <div className="flex gap-1">
            <Button size="icon" variant="ghost" className="text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100" onClick={() => void loadSessions()}>
              <RefreshCcw size={15} />
            </Button>
            <Button size="icon" variant="ghost" className="text-zinc-400 hover:bg-zinc-800 hover:text-zinc-100" onClick={() => setSettingsOpen(true)}>
              <Settings size={15} />
            </Button>
          </div>
        </div>

        <div className="border-b border-zinc-800 p-3">
            <Button
              className="w-full bg-zinc-100 text-zinc-950 hover:bg-white"
              onClick={() => {
                setNewName("");
                setNewProject("");
                setNewSessionOpen(true);
              }}
            >
            <FolderPlus size={15} />
            New session
          </Button>
        </div>

        <div className="flex items-center gap-2 border-b border-zinc-800 px-4 py-3 text-xs text-zinc-400">
          <KeyRound size={14} />
          <span className="truncate">{settings?.model || "No model"}</span>
          <Badge className="ml-auto border-zinc-700 bg-zinc-800 text-zinc-300">{settings?.api_key_masked ? "key set" : "no key"}</Badge>
        </div>

        <div className="border-b border-zinc-800 p-3">
          <Button
            variant="outline"
            className="w-full border-zinc-700 bg-zinc-900 text-zinc-100 hover:bg-zinc-800"
            onClick={() => setSettingsOpen(true)}
          >
            <Settings size={15} />
            Model config
          </Button>
        </div>

        <div className="flex-1 overflow-y-auto p-2">
          {sessions.length === 0 ? (
            <div className="px-3 py-8 text-center text-sm text-zinc-500">No sessions yet.</div>
          ) : (
            sessions.map((session) => (
              <button
                key={session.id}
                className={cn(
                  "group mb-1 w-full rounded-lg px-3 py-2.5 text-left transition",
                  session.id === activeId ? "bg-zinc-800 text-white" : "text-zinc-300 hover:bg-zinc-800/70",
                )}
                onClick={() => void openSession(session.id)}
              >
                <div className="flex items-center gap-2">
                  <Circle className={cn("h-2.5 w-2.5 fill-current", statusColor(session.status))} />
                  <span className="min-w-0 flex-1 truncate text-sm font-medium">{session.name}</span>
                  <span className="text-[11px] text-zinc-500">{session.message_count}</span>
                </div>
                <div className="mt-1 truncate pl-4 text-xs text-zinc-500">{session.project_dir}</div>
              </button>
            ))
          )}
        </div>
      </aside>

      <section className="flex min-w-0 flex-1 flex-col">
        <header className="flex h-14 items-center justify-between border-b border-zinc-200 bg-[#fbfbf8]/90 px-5 backdrop-blur">
          <div className="min-w-0">
            <div className="flex items-center gap-2">
              <h1 className="truncate text-sm font-semibold">{activeSession?.name ?? "Select a session"}</h1>
              {activeSummary ? <Badge>{activeSummary.status}</Badge> : null}
            </div>
            <p className="mt-0.5 truncate text-xs text-zinc-500">{activeSession?.project_dir ?? "Create a session from the sidebar."}</p>
          </div>
          <div className="flex items-center gap-2">
            <div className="hidden items-center gap-2 rounded-md border border-zinc-200 bg-white px-2.5 py-1.5 text-xs text-zinc-500 md:flex">
              {running ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Activity className="h-3.5 w-3.5" />}
              {running ? "Running" : "Idle"}
            </div>
            <Button variant="outline" size="sm" disabled={!activeId} onClick={() => void deleteActiveSession()}>
              <Trash2 size={14} />
              Delete
            </Button>
            <Button variant="destructive" size="sm" disabled={!running} onClick={() => void stopSession()}>
              <Square size={13} />
              Stop
            </Button>
          </div>
        </header>

        <div ref={viewportRef} className="flex-1 overflow-y-auto">
          <div className="mx-auto flex w-full max-w-5xl flex-col px-6 py-6">
            {error ? <ErrorBanner message={error} /> : null}
            {!activeSession ? (
              <EmptyState />
            ) : visibleMessages(messages).length === 0 && streamItems.length === 0 ? (
              <SessionEmpty projectDir={activeSession.project_dir} />
            ) : (
              <>
                {visibleMessages(messages).map((message) => (
                  <TranscriptItem key={message.id ?? `${message.type}-${message.created_at}`} message={message} />
                ))}
                <StreamTranscript items={streamItems} />
              </>
            )}
          </div>
        </div>

        <form onSubmit={sendMessage} className="border-t border-zinc-200 bg-[#fbfbf8]/95 px-5 py-4">
          <div className="mx-auto flex max-w-5xl flex-col gap-2">
            <div className="flex items-center justify-between">
              <button
                type="button"
                disabled={!activeId || running}
                className={cn(
                  "inline-flex h-8 items-center gap-2 rounded-md border px-3 text-xs font-medium transition disabled:pointer-events-none disabled:opacity-50",
                  imageFeedbackEnabled
                    ? "border-emerald-200 bg-emerald-50 text-emerald-900"
                    : "border-zinc-200 bg-white text-zinc-600 hover:bg-zinc-50",
                )}
                onClick={() => setImageFeedbackEnabled(!imageFeedbackEnabled)}
                title="开启后，本次回复结束时会调用火山方舟生成一张图像反馈"
              >
                <ImageIcon size={14} />
                图像反馈
                <span className="rounded bg-white/70 px-1.5 py-0.5">{imageFeedbackEnabled ? "开" : "关"}</span>
              </button>
              <span className="text-xs text-zinc-400">
                {imageFeedbackEnabled ? "将使用火山方舟生图" : "仅生成文字回复"}
              </span>
            </div>
            <div className="flex gap-3">
              <Textarea
                value={draft}
                disabled={!activeId || running}
                placeholder={activeId ? "Ask AgentV2 to inspect, edit, or run something..." : "Create or select a session first"}
                onChange={(event) => setDraft(event.target.value)}
                onKeyDown={(event) => {
                  if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
                    event.currentTarget.form?.requestSubmit();
                  }
                }}
                className="min-h-[70px] bg-white"
              />
              <Button className="h-[70px] w-20" disabled={!activeId || running || !draft.trim()}>
                {running ? <Loader2 className="animate-spin" size={16} /> : <Send size={16} />}
              </Button>
            </div>
          </div>
        </form>
      </section>

      <Dialog open={newSessionOpen} onOpenChange={setNewSessionOpen} title="New session" description="Choose an existing absolute local directory for this session sandbox.">
        <form onSubmit={createSession} className="space-y-3">
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-zinc-600">Name</label>
            <Input value={newName} placeholder="新会话" onChange={(event) => setNewName(event.target.value)} />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-zinc-600">Project directory</label>
            <Input
              value={newProject}
              placeholder="/absolute/path/to/project"
              onChange={(event) => setNewProject(event.target.value)}
            />
            <div className="rounded-md bg-zinc-50 px-2.5 py-2 text-xs leading-5 text-zinc-500">
              Sessions do not use a default folder. Enter an existing absolute path to keep file edits and commands inside the intended sandbox.
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="ghost" onClick={() => setNewSessionOpen(false)}>Cancel</Button>
            <Button type="submit" disabled={!newProject.trim()}>Create</Button>
          </div>
        </form>
      </Dialog>

      <Dialog open={settingsOpen} onOpenChange={setSettingsOpen} title="Model settings" description="Saved to the project .env and applied to this running server.">
        <form onSubmit={saveSettings} className="space-y-3">
          <div className="rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2 text-xs text-zinc-500">
            Current key: {settings?.api_key_masked || "not saved"}
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-zinc-600">API Key</label>
            <Input
              type="password"
              value={settingsForm.api_key}
              placeholder="Leave blank to keep current key"
              onChange={(event) => setSettingsForm({ ...settingsForm, api_key: event.target.value })}
            />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-zinc-600">Base URL</label>
            <Input value={settingsForm.base_url} onChange={(event) => setSettingsForm({ ...settingsForm, base_url: event.target.value })} />
          </div>
          <div className="space-y-1.5">
            <label className="text-xs font-medium text-zinc-600">Model</label>
            <Input value={settingsForm.model} onChange={(event) => setSettingsForm({ ...settingsForm, model: event.target.value })} />
          </div>
          <div className="grid grid-cols-2 gap-2">
            <Button
              type="button"
              variant={settingsForm.model === "deepseek-v4-flash" ? "default" : "outline"}
              onClick={() => setSettingsForm({
                ...settingsForm,
                base_url: settingsForm.base_url || "https://api.deepseek.com",
                model: "deepseek-v4-flash",
              })}
            >
              Flash
            </Button>
            <Button
              type="button"
              variant={settingsForm.model === "deepseek-v4-pro" ? "default" : "outline"}
              onClick={() => setSettingsForm({
                ...settingsForm,
                base_url: settingsForm.base_url || "https://api.deepseek.com",
                model: "deepseek-v4-pro",
              })}
            >
              Pro
            </Button>
          </div>
          <button
            type="button"
            className={cn(
              "flex w-full items-center justify-between rounded-lg border px-3 py-2 text-sm transition",
              thinkingEnabled ? "border-emerald-200 bg-emerald-50 text-emerald-900" : "border-zinc-200 bg-zinc-50 text-zinc-600",
            )}
            onClick={() => setThinkingEnabled(!thinkingEnabled)}
          >
            <span>Thinking mode</span>
            <span className="text-xs">{thinkingEnabled ? "Enabled" : "Disabled"}</span>
          </button>
          <div className="mt-4 border-t border-zinc-200 pt-4">
            <div className="mb-2 flex items-center gap-2 text-sm font-semibold text-zinc-800">
              <ImageIcon size={15} />
              火山方舟生图
            </div>
            <div className="mb-3 rounded-lg border border-zinc-200 bg-zinc-50 px-3 py-2 text-xs text-zinc-500">
              Current Ark key: {settings?.ark_image_api_key_masked || "not saved"}
            </div>
            <div className="space-y-3">
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-zinc-600">Ark API Key</label>
                <Input
                  type="password"
                  value={settingsForm.ark_image_api_key}
                  placeholder="Leave blank to keep current Ark key"
                  onChange={(event) => setSettingsForm({ ...settingsForm, ark_image_api_key: event.target.value })}
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-xs font-medium text-zinc-600">Ark Image URL</label>
                <Input
                  value={settingsForm.ark_image_base_url}
                  onChange={(event) => setSettingsForm({ ...settingsForm, ark_image_base_url: event.target.value })}
                />
              </div>
              <div className="grid grid-cols-2 gap-2">
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-zinc-600">Image model</label>
                  <Input
                    value={settingsForm.ark_image_model}
                    onChange={(event) => setSettingsForm({ ...settingsForm, ark_image_model: event.target.value })}
                  />
                </div>
                <div className="space-y-1.5">
                  <label className="text-xs font-medium text-zinc-600">Size</label>
                  <Input
                    value={settingsForm.ark_image_size}
                    onChange={(event) => setSettingsForm({ ...settingsForm, ark_image_size: event.target.value })}
                  />
                </div>
              </div>
              <button
                type="button"
                className={cn(
                  "flex w-full items-center justify-between rounded-lg border px-3 py-2 text-sm transition",
                  arkImageWatermark ? "border-emerald-200 bg-emerald-50 text-emerald-900" : "border-zinc-200 bg-zinc-50 text-zinc-600",
                )}
                onClick={() => setArkImageWatermark(!arkImageWatermark)}
              >
                <span>Watermark</span>
                <span className="text-xs">{arkImageWatermark ? "Enabled" : "Disabled"}</span>
              </button>
            </div>
          </div>
          <div className="flex justify-end gap-2 pt-2">
            <Button type="button" variant="ghost" onClick={() => setSettingsOpen(false)}>Cancel</Button>
            <Button type="submit">Save</Button>
          </div>
        </form>
      </Dialog>

      <Dialog
        open={pendingConfirmation !== null}
        onOpenChange={(open) => {
          if (!open) void resolveConfirmation(false);
        }}
        title="Confirm command"
        description="The agent wants to run a command in this session sandbox."
      >
        {pendingConfirmation ? (
          <div className="space-y-4">
            <div className="rounded-lg border border-amber-200 bg-amber-50 p-3">
              <div className="flex items-center gap-2 text-sm font-medium text-amber-900">
                <Terminal size={16} />
                {pendingConfirmation.name}
              </div>
              <pre className="mt-3 max-h-48 overflow-auto rounded-md bg-zinc-950 p-3 text-xs leading-5 text-zinc-100">
                {JSON.stringify(pendingConfirmation.arguments, null, 2)}
              </pre>
              <div className="mt-2 truncate text-xs text-amber-800">{pendingConfirmation.project_dir}</div>
            </div>
            <div className="flex justify-end gap-2">
              <Button variant="outline" onClick={() => void resolveConfirmation(false)}>
                <X size={14} />
                Cancel
              </Button>
              <Button onClick={() => void resolveConfirmation(true)}>
                <Check size={14} />
                Run command
              </Button>
            </div>
          </div>
        ) : null}
      </Dialog>
    </main>
  );
}

function TranscriptItem({ message }: { message: MessageRecord }) {
  if (message.type === "image_feedback") {
    return <ImageFeedbackItem message={message} />;
  }
  if (message.type !== "user" && message.type !== "assistant_final" && message.type !== "error" && message.type !== "stopped") {
    return null;
  }
  const isUser = message.type === "user";
  const isAssistant = message.type === "assistant_final";
  return (
    <>
      {isAssistant && message.reasoning_content ? (
        <ReasoningItem content={message.reasoning_content} step={message.step} />
      ) : null}
      <article className={cn("flex w-full gap-3 py-3", isUser ? "justify-end" : "justify-start")}>
        {!isUser ? <Avatar icon={isAssistant ? Bot : X} tone={isAssistant ? "agent" : "error"} /> : null}
        <div className={cn("flex max-w-[78%] flex-col", isUser ? "items-end" : "items-start")}>
          <div
            className={cn(
              "rounded-2xl px-4 py-3 text-sm leading-6 shadow-sm",
              isUser
                ? "rounded-br-md bg-zinc-950 text-white"
                : message.type === "error"
                  ? "rounded-bl-md border border-red-200 bg-red-50 text-red-900"
                  : "rounded-bl-md border border-zinc-200 bg-white text-zinc-900",
            )}
          >
            <div className="whitespace-pre-wrap break-words">{message.content}</div>
          </div>
          <div className="mt-1 px-1 text-[11px] text-zinc-400">{formatTime(message.created_at)}</div>
        </div>
        {isUser ? <Avatar icon={User} tone="user" /> : null}
      </article>
    </>
  );
}

function ImageFeedbackItem({ message }: { message: MessageRecord }) {
  const urls = message.urls ?? [];
  return (
    <article className="flex w-full justify-start gap-3 py-3">
      <Avatar icon={ImageIcon} tone="agent" />
      <div className="flex max-w-[78%] flex-col items-start">
        <div className="rounded-2xl rounded-bl-md border border-zinc-200 bg-white p-3 shadow-sm">
          <div className="mb-2 flex items-center gap-2 text-xs font-medium text-zinc-500">
            <ImageIcon size={13} />
            图像反馈
          </div>
          {message.error ? (
            <div className="rounded-lg border border-red-200 bg-red-50 px-3 py-2 text-sm leading-6 text-red-800">
              {message.error}
            </div>
          ) : (
            <div className={cn("grid gap-2", urls.length > 1 ? "grid-cols-2" : "grid-cols-1")}>
              {urls.map((url) => (
                <a key={url} href={url} target="_blank" rel="noreferrer" className="block overflow-hidden rounded-lg border border-zinc-200 bg-zinc-50">
                  <img src={url} alt="图像反馈" className="aspect-video w-full object-cover" />
                </a>
              ))}
            </div>
          )}
          <details className="mt-2 text-xs text-zinc-500">
            <summary className="cursor-pointer">Prompt</summary>
            <div className="mt-2 max-h-32 overflow-auto whitespace-pre-wrap rounded-md bg-zinc-50 p-2 leading-5">
              {message.prompt}
            </div>
          </details>
        </div>
        <div className="mt-1 px-1 text-[11px] text-zinc-400">{formatTime(message.created_at)}</div>
      </div>
    </article>
  );
}

function StreamTranscript({ items }: { items: StreamItem[] }) {
  if (items.length === 0) return null;
  return (
    <>
      {items.map((item) => (
        item.type === "reasoning_stream" ? (
          <ReasoningItem key={item.id} content={item.content} step={item.step} streaming />
        ) : (
          <AssistantStreamItem key={item.id} content={item.content} />
        )
      ))}
    </>
  );
}

function AssistantStreamItem({ content }: { content: string }) {
  return (
    <article className="flex w-full justify-start gap-3 py-3">
      <Avatar icon={Bot} tone="agent" />
      <div className="flex max-w-[78%] flex-col items-start">
        <div className="rounded-2xl rounded-bl-md border border-zinc-200 bg-white px-4 py-3 text-sm leading-6 text-zinc-900 shadow-sm">
          <div className="whitespace-pre-wrap break-words">
            {content}
            <span className="ml-1 inline-flex align-middle"><Loader2 className="h-3 w-3 animate-spin text-zinc-400" /></span>
          </div>
        </div>
      </div>
    </article>
  );
}

function ReasoningItem({ content, step, streaming = false }: { content: string; step?: number; streaming?: boolean }) {
  return (
    <article className="flex w-full justify-start gap-3 py-2">
      <div className="mt-1 h-8 w-8 shrink-0" />
      <div className="max-w-[78%]">
        <details
          className="max-w-full rounded-xl border border-amber-200 bg-amber-50/70 text-amber-950 shadow-sm"
          open={streaming}
        >
          <summary className="cursor-pointer px-3 py-2 text-xs font-medium">
            思考过程{step ? ` · Step ${step}` : ""}{streaming ? " · streaming" : ""}
          </summary>
          <div className="max-h-56 overflow-auto whitespace-pre-wrap border-t border-amber-200 px-3 py-2 text-xs leading-5">
            {content}
          </div>
        </details>
      </div>
    </article>
  );
}

function Avatar({ icon: Icon, tone }: { icon: IconComponent; tone: "agent" | "user" | "error" }) {
  return (
    <div
      className={cn(
        "mt-1 grid h-8 w-8 shrink-0 place-items-center rounded-full border",
        tone === "user" && "border-zinc-800 bg-zinc-950 text-white",
        tone === "agent" && "border-emerald-200 bg-emerald-50 text-emerald-800",
        tone === "error" && "border-red-200 bg-red-50 text-red-700",
      )}
    >
      <Icon size={15} />
    </div>
  );
}

function EmptyState() {
  return (
    <div className="grid min-h-[calc(100vh-220px)] place-items-center">
      <div className="max-w-md text-center">
        <div className="mx-auto grid h-12 w-12 place-items-center rounded-xl border border-zinc-200 bg-white shadow-sm">
          <Bot className="h-6 w-6 text-zinc-700" />
        </div>
        <h2 className="mt-4 text-lg font-semibold">AgentV2 Web</h2>
        <p className="mt-2 text-sm leading-6 text-zinc-500">Create or select a session to start a local coding-agent conversation.</p>
      </div>
    </div>
  );
}

function SessionEmpty({ projectDir }: { projectDir: string }) {
  return (
    <div className="grid min-h-[calc(100vh-220px)] place-items-center">
      <div className="max-w-lg rounded-xl border border-zinc-200 bg-white p-6 text-center shadow-sm">
        <Play className="mx-auto h-7 w-7 text-emerald-700" />
        <h2 className="mt-3 text-base font-semibold">Ready to work</h2>
        <p className="mt-2 text-sm leading-6 text-zinc-500">The agent will read files and run tools inside this project sandbox.</p>
        <div className="mt-3 truncate rounded-md bg-zinc-100 px-3 py-2 text-xs text-zinc-600">{projectDir}</div>
      </div>
    </div>
  );
}

function ErrorBanner({ message }: { message: string }) {
  return (
    <div className="mb-4 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-sm text-red-800">
      {message}
    </div>
  );
}

function visibleMessages(messages: MessageRecord[]) {
  return messages.filter((message) => (
    message.type === "user"
    || message.type === "assistant_final"
    || message.type === "image_feedback"
    || message.type === "error"
    || message.type === "stopped"
  ));
}

function statusColor(status: string) {
  if (status === "running") return "text-emerald-400";
  if (status === "waiting_confirmation") return "text-amber-400";
  if (status === "error") return "text-red-400";
  return "text-zinc-600";
}

function formatTime(value?: string) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return date.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" });
}

async function api<T = unknown>(url: string, init: RequestInit = {}): Promise<T> {
  const response = await fetch(url, {
    ...init,
    headers: {
      "Content-Type": "application/json",
      ...(init.headers ?? {}),
    },
  });
  if (!response.ok) throw new Error(await readError(response));
  return response.json() as Promise<T>;
}

async function readError(response: Response) {
  try {
    const data = await response.json();
    return data.detail ?? JSON.stringify(data);
  } catch {
    return `${response.status} ${response.statusText}`;
  }
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <App />
  </React.StrictMode>,
);

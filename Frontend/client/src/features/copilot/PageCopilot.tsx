import { useState, useEffect, useRef, useCallback } from "react";
import { Bot, Send, X, Loader2, User, Sparkles, RotateCcw } from "lucide-react";
import { chatWithCopilot } from "@/lib/api";
import type { ChatMessage, CopilotPage } from "@/lib/api";
import { friendlyError } from "@/lib/errors";
import ReactMarkdown from "react-markdown";
import remarkGfm from "remark-gfm";
// ─── Types ─────────────────────────────────────────────────────────────────

interface ChatMsg extends ChatMessage {
  pending?: boolean;
}

export interface PageCopilotProps {
  /** Which page this copilot is mounted on */
  page: CopilotPage;
  /** Label shown in the header (e.g. "Data Assistant") */
  title: string;
  /** Short subtitle shown when ready */
  subtitle?: string;
  /** Disabled state — e.g. when no data is loaded */
  disabled?: boolean;
  /** Placeholder text when disabled */
  disabledPlaceholder?: string;
  /** Suggestive quick-action buttons shown on the empty state */
  quickActions?: string[];
  /** Live context object sent to the backend with every message */
  pageContext?: Record<string, unknown>;
  /**
   * Called after the backend returns an action.
   * The component calls the API action for the "modify" page internally (via backend).
   * For all other pages, the parent receives the action and executes it.
   */
  onAction?: (action: Record<string, unknown>) => Promise<void>;
  /**
   * If provided, the copilot calls this AFTER executing an action when
   * graph_refreshed is true (e.g. to re-fetch the demand preview).
   */
  onRefresh?: () => Promise<void>;
}

// ─── Status bubble text injected for "get_status" on training page ──────────

function buildStatusMessage(context: Record<string, unknown>): string {
  const status = String(context.status ?? "idle");
  const ep = context.current_episode ?? 0;
  const total = context.total_episodes ?? 0;
  const best = context.best_reward !== undefined ? Number(context.best_reward).toFixed(2) : "n/a";
  const avg = context.avg_reward_last_50 !== undefined ? Number(context.avg_reward_last_50).toFixed(2) : "n/a";

  if (status === "idle") return "Training has not started yet. Ask me to kick it off!";
  if (status === "running")
    return `🏃 Training is running — **episode ${ep}/${total}**. Best reward so far: **${best}**, avg last 50: **${avg}**.`;
  if (status === "completed")
    return `✅ Training completed ${total} episodes. Best reward: **${best}**, avg last 50: **${avg}**.`;
  if (status === "stopped")
    return `🛑 Training was stopped at episode ${ep}/${total}. Best reward: **${best}**.`;
  if (status === "failed")
    return "❌ Training failed. Check the training page for details, then try restarting.";
  return `Status: ${status}`;
}

// ─── Main Component ──────────────────────────────────────────────────────────

export function PageCopilot({
  page,
  title,
  subtitle,
  disabled = false,
  disabledPlaceholder = "Not available yet...",
  quickActions = [],
  pageContext = {},
  onAction,
  onRefresh,
}: PageCopilotProps) {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [loading, setLoading] = useState(false);
  const [hasUnread, setHasUnread] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Reset conversation when page changes (keeps scope clean)
  useEffect(() => {
    setMessages([]);
    setOpen(false);
    setHasUnread(false);
  }, [page]);

  // Scroll to bottom on new messages
  useEffect(() => {
    if (open) chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, open]);

  // Focus input when panel opens
  useEffect(() => {
    if (open) {
      setTimeout(() => inputRef.current?.focus(), 200);
      setHasUnread(false);
    }
  }, [open]);

  const handleSend = useCallback(async (text?: string) => {
    const message = (text ?? input).trim();
    if (!message || loading || disabled) return;

    setInput("");
    const userMsg: ChatMsg = { role: "user", content: message };
    const pendingMsg: ChatMsg = { role: "assistant", content: "", pending: true };
    setMessages(prev => [...prev, userMsg, pendingMsg]);
    setLoading(true);

    const history = messages.filter(m => !m.pending);

    try {
      const res = await chatWithCopilot(page, message, history, pageContext);
      const action = res.action;

      // Special case: training status query → inject live status into message
      let assistantContent = res.assistant_message;
      if (action.action === "get_status") {
        assistantContent = buildStatusMessage(pageContext);
      }

      const assistantMsg: ChatMsg = { role: "assistant", content: assistantContent };
      setMessages(prev => [...prev.slice(0, -1), assistantMsg]);

      // Execute the action on the parent (except modify — backend does it)
      if (page !== "modify" && onAction && action.action !== "unknown" && action.action !== "explain" && action.action !== "explain_results" && action.action !== "explain_decision" && action.action !== "get_status") {
        await onAction(action);
      }

      // Navigate actions
      const actionName = action.action as string;
      if (actionName.startsWith("navigate_to_")) {
        const navTarget = actionName.replace("navigate_to_", "");
        let route = "/upload";
        if (navTarget === "modify") route = "/modify";
        if (navTarget === "train") route = "/train";
        if (navTarget === "evaluate") route = "/evaluate";
        if (navTarget === "deploy") route = "/deploy";
        
        setTimeout(() => window.location.href = route, 1200);
      }

      if (res.graph_refreshed && onRefresh) {
        await onRefresh();
      }

      if (!open) setHasUnread(true);
    } catch (err: unknown) {
      const errMsg: ChatMsg = {
        role: "assistant",
        content: `⚠️ ${friendlyError(err, "chatbot")}`,
      };
      setMessages(prev => [...prev.slice(0, -1), errMsg]);
    } finally {
      setLoading(false);
    }
  }, [input, loading, messages, page, pageContext, onAction, onRefresh, open, disabled]);

  const handleKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  const isReady = !disabled;
  const readyLabel = subtitle ?? (isReady ? "● Ready" : "○ Waiting...");

  return (
    <div className="fixed bottom-6 right-6 z-[60] flex flex-col items-end gap-4 pointer-events-none">

      {/* ── Floating Chat Panel ── */}
      <div
        className={`origin-bottom-right transition-all duration-300 ease-out flex flex-col w-[360px] h-[520px] rounded-xl glass shadow-2xl overflow-hidden ${
          open ? "scale-100 opacity-100 translate-y-0 pointer-events-auto" : "scale-95 opacity-0 translate-y-8 pointer-events-none"
        }`}
        {...(!open ? { inert: "true" } as any : {})}
      >
        {/* Header */}
        <div className="shrink-0 px-4 py-3 bg-muted/80 backdrop-blur-md border-b border-border flex items-center gap-3">
          <div className="w-8 h-8 rounded-md bg-primary/20 border border-primary/30 flex items-center justify-center shrink-0">
            <Sparkles className="w-4 h-4 text-primary" />
          </div>
          <div className="flex-1">
            <div className="text-[11px] font-bold tracking-widest text-foreground uppercase">
              {title}
            </div>
            <div className={`text-[10px] tracking-wide mt-0.5 ${isReady ? "text-primary/80" : "text-muted-foreground"}`}>
              {readyLabel}
            </div>
          </div>
          <button
            onClick={() => setOpen(false)}
            className="text-muted-foreground hover:text-foreground transition-colors bg-transparent border-none p-1 cursor-pointer"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Chat Area */}
        <div className="flex-1 overflow-y-auto w-full p-4 flex flex-col gap-4 bg-background/40">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center gap-4 animate-in fade-in duration-500">
              <div className="w-12 h-12 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center">
                <Bot className="w-6 h-6 text-primary/80" />
              </div>
              <p className="text-xs text-muted-foreground text-center leading-relaxed max-w-[200px]">
                Ask me anything about this page, or use the quick actions below.
              </p>

              {quickActions.length > 0 && (
                <div className="w-full flex flex-col gap-2 mt-2">
                  {quickActions.map(q => (
                    <button
                      key={q}
                      onClick={() => handleSend(q)}
                      disabled={!isReady || loading}
                      className="text-left text-xs px-3 py-2.5 rounded-lg border border-border bg-muted/30 text-muted-foreground cursor-pointer transition-all duration-200 hover:bg-muted hover:text-foreground hover:border-primary/50 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-muted/30 disabled:hover:border-border"
                    >
                      {q}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : (
            messages.map((msg, i) => <CopilotChatBubble key={i} msg={msg} />)
          )}
          <div ref={chatEndRef} className="h-1" />
        </div>

        {/* Footer / Input */}
        <div className="shrink-0 p-3 bg-muted/50 backdrop-blur-md border-t border-border">
          <div className="flex gap-2 items-center">
            <input
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKey}
              placeholder={isReady ? "Ask me anything..." : disabledPlaceholder}
              disabled={!isReady || loading}
              className="flex-1 h-10 rounded-md border border-border bg-background text-foreground text-xs px-3 outline-none transition-colors focus:border-primary/50 disabled:opacity-50"
            />
            <button
              onClick={() => handleSend()}
              disabled={!input.trim() || !isReady || loading}
              className={`w-10 h-10 rounded-md border-none flex items-center justify-center shrink-0 transition-all duration-200 ${
                input.trim() && isReady && !loading
                  ? "bg-primary text-primary-foreground cursor-pointer shadow-md shadow-primary/20 hover:shadow-primary/40 hover:scale-105 active:scale-95"
                  : "bg-muted text-muted-foreground cursor-not-allowed"
              }`}
            >
              {loading ? (
                <Loader2 className="w-4 h-4 animate-spin" />
              ) : (
                <Send className="w-4 h-4" />
              )}
            </button>
          </div>

          {messages.length > 0 && (
            <button
              onClick={() => setMessages([])}
              className="mt-2 text-[10px] text-muted-foreground flex items-center gap-1.5 hover:text-foreground transition-colors bg-transparent border-none p-0 cursor-pointer mx-auto"
            >
              <RotateCcw className="w-3 h-3" />
              Clear conversation
            </button>
          )}
        </div>
      </div>

      {/* ── Trigger FAB (Floating Action Button) ── */}
      <div className="pointer-events-auto flex justify-end group mt-2">
        <button
          onClick={() => setOpen(o => !o)}
          aria-label={`Toggle ${title}`}
          className={`relative h-14 rounded-full flex items-center border border-primary/20 cursor-pointer active:scale-95 bg-primary text-primary-foreground shadow-xl shadow-primary/20 z-50 overflow-hidden transition-all duration-500 ease-[cubic-bezier(0.25,1,0.5,1)] ${
            open ? "w-14 justify-center hover:scale-105" : "w-14 hover:w-[280px] group-hover:w-[280px] pr-4"
          }`}
        >
          {/* Soft hover background */}
          <div
            className={`absolute inset-0 pointer-events-none transition-opacity duration-[800ms] ${open ? "hidden opacity-0" : "opacity-0 group-hover:opacity-100"}`}
            style={{ backgroundColor: "#e0f2fe" }}
          />

          {/* Unread ping */}
          {hasUnread && !open && (
            <span className="absolute left-0 top-0 w-14 h-14 rounded-full border-2 border-primary/50 animate-[ping_2s_cubic-bezier(0,0,0.2,1)_infinite] z-0" />
          )}

          <div className="w-14 h-14 shrink-0 flex items-center justify-center relative z-10">
            <div className={`transition-transform duration-300 ${open ? "rotate-90 scale-0 opacity-0 absolute" : "rotate-0 scale-100 opacity-100 absolute"} flex items-center justify-center`}>
              <Sparkles className="w-6 h-6 text-primary-foreground group-hover:text-black transition-colors duration-300" />
              {hasUnread && (
                <span className="absolute top-3 right-3 w-2.5 h-2.5 rounded-full bg-destructive border-2 border-primary" />
              )}
            </div>
            <div className={`transition-transform duration-300 ${open ? "rotate-0 scale-100 opacity-100 absolute" : "-rotate-90 scale-0 opacity-0 absolute"} flex items-center justify-center`}>
              <X className="w-6 h-6 text-primary-foreground" />
            </div>
          </div>

          <div className={`flex flex-col items-start whitespace-nowrap overflow-hidden transition-opacity duration-300 relative z-10 ${open ? "opacity-0 hidden" : "opacity-0 group-hover:opacity-100 delay-150"}`}>
            <span className="text-[13px] font-bold tracking-wider uppercase text-black">{title}</span>
            <span className="text-[10px] text-black/80 font-medium opacity-90">AI-powered assistant</span>
          </div>
        </button>
      </div>
    </div>
  );
}

// ─── Chat Bubble sub-components ──────────────────────────────────────────────

function StreamingMessage({ content, isUser }: { content: string; isUser: boolean }) {
  const [displayed, setDisplayed] = useState(isUser ? content : "");

  useEffect(() => {
    if (isUser) { setDisplayed(content); return; }
    const startDelay = setTimeout(() => {
      let i = 0;
      const tick = setInterval(() => {
        setDisplayed(content.substring(0, i));
        i += 2;
        if (i > content.length + 1) { clearInterval(tick); setDisplayed(content); }
      }, 15);
      return () => clearInterval(tick);
    }, 150);
    return () => clearTimeout(startDelay);
  }, [content, isUser]);

  return (
    <div className="leading-relaxed relative markdown-body [&>p:last-child]:inline">
      {isUser ? (
        <span className="whitespace-pre-wrap">{displayed}</span>
      ) : (
        <ReactMarkdown
          remarkPlugins={[remarkGfm]}
          components={{
            h1: ({node, ...props}) => <h1 className="text-sm font-bold mt-3 mb-1.5 text-primary" {...props} />,
            h2: ({node, ...props}) => <h2 className="text-[13px] font-bold mt-2.5 mb-1 text-primary/90" {...props} />,
            h3: ({node, ...props}) => <h3 className="text-[12px] font-bold mt-2 mb-1 text-foreground" {...props} />,
            p: ({node, ...props}) => <p className="mb-2 last:mb-0" {...props} />,
            ul: ({node, ...props}) => <ul className="list-disc pl-4 mb-2 space-y-1 marker:text-primary/60" {...props} />,
            ol: ({node, ...props}) => <ol className="list-decimal pl-4 mb-2 space-y-1 marker:text-primary/60" {...props} />,
            li: ({node, ...props}) => <li className="pl-0.5" {...props} />,
            a: ({node, ...props}) => <a className="text-primary font-medium underline underline-offset-2 hover:text-primary/80 transition-colors" target="_blank" rel="noopener noreferrer" {...props} />,
            blockquote: ({node, ...props}) => <blockquote className="border-l-2 border-primary/40 pl-3 italic text-muted-foreground my-2.5 bg-muted/40 py-1.5 pr-2 rounded-r-md" {...props} />,
            code: ({node, inline, ...props}: any) => 
              inline ? 
                <code className="bg-background border border-border rounded px-1.5 py-[2px] text-[10px] font-mono font-medium text-primary/90 shadow-sm" {...props} /> :
                <pre className="bg-zinc-950 text-zinc-50 border border-zinc-800 rounded-md p-3 overflow-x-auto my-3 text-[10.5px] font-mono shadow-md leading-relaxed selection:bg-primary/30"><code {...props} /></pre>,
            table: ({node, ...props}) => <div className="overflow-x-auto my-3 border border-border rounded-md shadow-sm"><table className="w-full text-left border-collapse text-[10.5px]" {...props} /></div>,
            th: ({node, ...props}) => <th className="border-b border-border/80 py-1.5 px-3 font-semibold bg-muted/80 text-foreground" {...props} />,
            td: ({node, ...props}) => <td className="border-b border-border/30 py-1.5 px-3 text-muted-foreground" {...props} />
          }}
        >
          {displayed}
        </ReactMarkdown>
      )}
      {!isUser && displayed.length < content.length && (
        <span className="inline-block w-1.5 h-2.5 ml-1 bg-primary/70 animate-pulse align-baseline" />
      )}
    </div>
  );
}

function CopilotChatBubble({ msg }: { msg: ChatMsg }) {
  const isUser = msg.role === "user";
  return (
    <div className={`flex gap-3 items-start ${isUser ? "flex-row-reverse" : "flex-row"}`}>
      <div className={`w-6 h-6 rounded-full shrink-0 flex items-center justify-center mt-0.5 border shadow-sm ${isUser ? "bg-primary/20 border-primary/30" : "bg-muted border-border"}`}>
        {isUser ? <User className="w-3 h-3 text-primary" /> : <Bot className="w-3 h-3 text-foreground" />}
      </div>
      <div className={`max-w-[85%] px-3.5 py-2.5 text-[11px] whitespace-pre-wrap ${isUser ? "rounded-2xl rounded-tr-sm bg-primary/20 border border-primary/30 text-foreground" : "rounded-2xl rounded-tl-sm bg-muted/80 border border-border text-foreground shadow-sm"}`}>
        {msg.pending ? (
          <span className="flex gap-1.5 items-center text-muted-foreground">
            <Loader2 className="w-3.5 h-3.5 animate-spin text-primary" />
            <span className="bg-gradient-to-r from-muted-foreground via-primary/80 to-muted-foreground bg-clip-text text-transparent animate-pulse">
              Generating...
            </span>
          </span>
        ) : (
          <StreamingMessage content={msg.content} isUser={isUser} />
        )}
      </div>
    </div>
  );
}

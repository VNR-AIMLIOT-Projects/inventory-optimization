import { useState, useEffect, useRef, useCallback } from "react";
import { Bot, Send, X, Loader2, User, Sparkles, RotateCcw } from "lucide-react";
import { chatWithCopilot } from "@/lib/api";
import type { ChatMessage, CopilotPage } from "@/lib/api";
import { friendlyError } from "@/lib/errors";
import { cn } from "@/lib/utils";

// ─── Types ─────────────────────────────────────────────────────────────────

interface ChatMsg extends ChatMessage {
  pending?: boolean;
}

export interface PageCopilotProps {
  page: CopilotPage;
  title: string;
  subtitle?: string;
  disabled?: boolean;
  disabledPlaceholder?: string;
  quickActions?: string[];
  pageContext?: Record<string, unknown>;
  onAction?: (action: Record<string, unknown>) => Promise<void>;
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
    return ` Training is running — **episode ${ep}/${total}**. Best reward so far: **${best}**, avg last 50: **${avg}**.`;
  if (status === "completed")
    return `✅ Training completed ${total} episodes. Best reward: **${best}**, avg last 50: **${avg}**.`;
  if (status === "stopped")
    return ` Training was stopped at episode ${ep}/${total}. Best reward: **${best}**.`;
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

  useEffect(() => {
    setMessages([]);
    setOpen(false);
    setHasUnread(false);
  }, [page]);

  useEffect(() => {
    if (open) chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, open]);

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

      let assistantContent = res.assistant_message;
      if (action.action === "get_status") {
        assistantContent = buildStatusMessage(pageContext);
      }

      const assistantMsg: ChatMsg = { role: "assistant", content: assistantContent };
      setMessages(prev => [...prev.slice(0, -1), assistantMsg]);

      if (page !== "modify" && onAction && action.action !== "unknown" && action.action !== "explain" && action.action !== "explain_results" && action.action !== "explain_decision" && action.action !== "get_status") {
        await onAction(action);
      }

      if (action.action === "navigate_to_modify") {
        setTimeout(() => window.location.href = "/modify", 1200);
      } else if (action.action === "navigate_to_deploy") {
        setTimeout(() => window.location.href = "/deploy", 1200);
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
        className={cn(
          "origin-bottom-right transition-all duration-500 ease-spring flex flex-col w-[380px] h-[540px] rounded-3xl glass shadow-amber-lg overflow-hidden",
          open ? "scale-100 opacity-100 translate-y-0 pointer-events-auto" : "scale-95 opacity-0 translate-y-8 pointer-events-none"
        )}
        {...(!open ? { inert: "true" } as any : {})}
      >
        {/* Header */}
        <div className="shrink-0 px-5 py-4 bg-background/80 backdrop-blur-xl border-b border-border/50 flex items-center gap-3">
          <div className="w-9 h-9 rounded-xl bg-primary/20 border border-primary/30 flex items-center justify-center shrink-0 shadow-inner-top">
            <Sparkles className="w-4.5 h-4.5 text-primary" />
          </div>
          <div className="flex-1">
            <div className="text-[13px] font-bold tracking-wide text-foreground font-display">
              {title}
            </div>
            <div className={cn("text-[11px] tracking-wide mt-0.5", isReady ? "text-primary font-medium" : "text-muted-foreground")}>
              {readyLabel}
            </div>
          </div>
          <button
            onClick={() => setOpen(false)}
            className="w-8 h-8 rounded-full flex items-center justify-center text-muted-foreground hover:text-foreground hover:bg-muted/50 transition-colors"
          >
            <X className="w-4 h-4" />
          </button>
        </div>

        {/* Chat Area */}
        <div className="flex-1 overflow-y-auto w-full p-5 flex flex-col gap-5 bg-background/40 noise relative">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center gap-5 animate-in fade-in duration-500 z-10 relative">
              <div className="w-14 h-14 rounded-2xl bg-primary/10 border border-primary/20 flex items-center justify-center shadow-inner-top">
                <Bot className="w-7 h-7 text-primary/80" />
              </div>
              <p className="text-sm text-muted-foreground text-center leading-relaxed max-w-[220px]">
                Ask me anything about this page, or use the quick actions below.
              </p>

              {quickActions.length > 0 && (
                <div className="w-full flex flex-col gap-2.5 mt-4">
                  {quickActions.map(q => (
                    <button
                      key={q}
                      onClick={() => handleSend(q)}
                      disabled={!isReady || loading}
                      className={cn(
                        "text-left text-xs font-medium px-4 py-3 rounded-xl border transition-all duration-200",
                        "border-border/60 bg-card/60 shadow-sm backdrop-blur-sm",
                        "hover:bg-muted/80 hover:text-foreground hover:border-primary/50 hover:-translate-y-0.5 hover:shadow-md",
                        "disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:translate-y-0 disabled:hover:shadow-none"
                      )}
                    >
                      {q}
                    </button>
                  ))}
                </div>
              )}
            </div>
          ) : (
            <div className="z-10 relative flex flex-col gap-5">
              {messages.map((msg, i) => <CopilotChatBubble key={i} msg={msg} />)}
            </div>
          )}
          <div ref={chatEndRef} className="h-1" />
        </div>

        {/* Footer / Input */}
        <div className="shrink-0 p-4 bg-background/80 backdrop-blur-xl border-t border-border/50">
          <div className="flex gap-2 items-center">
            <input
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKey}
              placeholder={isReady ? "Ask me anything..." : disabledPlaceholder}
              disabled={!isReady || loading}
              className="flex-1 h-11 rounded-xl border border-border/60 bg-muted/30 text-foreground text-[13px] px-4 outline-none transition-all focus:border-primary/50 focus:bg-background shadow-inner disabled:opacity-50"
            />
            <button
              onClick={() => handleSend()}
              disabled={!input.trim() || !isReady || loading}
              className={cn(
                "w-11 h-11 rounded-xl flex items-center justify-center shrink-0 transition-all duration-300",
                input.trim() && isReady && !loading
                  ? "bg-primary text-primary-foreground shadow-lg shadow-primary/30 hover:shadow-primary/50 hover:scale-105 active:scale-95"
                  : "bg-muted text-muted-foreground opacity-50"
              )}
            >
              {loading ? (
                <Loader2 className="w-5 h-5 animate-spin" />
              ) : (
                <Send className="w-4.5 h-4.5 translate-x-0.5" />
              )}
            </button>
          </div>

          {messages.length > 0 && (
            <button
              onClick={() => setMessages([])}
              className="mt-3 text-[11px] font-medium text-muted-foreground flex items-center gap-1.5 hover:text-foreground transition-colors mx-auto"
            >
              <RotateCcw className="w-3.5 h-3.5" />
              Clear conversation
            </button>
          )}
        </div>
      </div>

      {/* ── Trigger FAB ── */}
      <div className="pointer-events-auto flex justify-end group mt-2">
        <button
          onClick={() => setOpen(o => !o)}
          aria-label={`Toggle ${title}`}
          className={cn(
            "relative h-14 rounded-full flex items-center border border-primary/20 bg-primary text-primary-foreground shadow-xl shadow-primary/30 z-50 overflow-hidden transition-all duration-500 ease-spring focus:outline-none focus:ring-2 focus:ring-primary focus:ring-offset-2 focus:ring-offset-background",
            open ? "w-14 justify-center hover:scale-105" : "w-14 hover:w-[260px] pr-5"
          )}
        >
          {/* Unread ping */}
          {hasUnread && !open && (
            <span className="absolute left-0 top-0 w-14 h-14 rounded-full border-2 border-primary/50 animate-ping z-0" />
          )}

          <div className="w-14 h-14 shrink-0 flex items-center justify-center relative z-10">
            <div className={cn("transition-transform duration-500 ease-spring absolute flex items-center justify-center", open ? "rotate-180 scale-0 opacity-0" : "rotate-0 scale-100 opacity-100")}>
              <Sparkles className="w-6 h-6" />
              {hasUnread && (
                <span className="absolute top-3 right-3 w-3 h-3 rounded-full bg-background border-[3px] border-primary" />
              )}
            </div>
            <div className={cn("transition-transform duration-500 ease-spring absolute flex items-center justify-center", open ? "rotate-0 scale-100 opacity-100" : "-rotate-180 scale-0 opacity-0")}>
              <X className="w-6 h-6" />
            </div>
          </div>

          <div className={cn(
            "flex flex-col items-start whitespace-nowrap overflow-hidden transition-opacity duration-300 relative z-10 pl-1",
            open ? "opacity-0 hidden" : "opacity-0 hover:opacity-100"
          )}>
            <style>{`
              button:hover > div:last-child { opacity: 1 !important; }
            `}</style>
            <span className="text-[13px] font-bold tracking-wider uppercase font-display">{title}</span>
            <span className="text-[11px] font-medium opacity-80">AI-powered assistant</span>
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

  const parseMarkdown = (text: string) => {
    const parts = text.split(/(\*\*.*?\*\*|`.*?`)/g);
    return parts.map((part, index) => {
      if (part.startsWith("**") && part.endsWith("**"))
        return <strong key={index} className="font-semibold text-foreground">{part.slice(2, -2)}</strong>;
      if (part.startsWith("`") && part.endsWith("`"))
        return <code key={index} className="bg-muted border border-border/50 rounded-md px-1.5 py-0.5 text-[11px] font-mono font-medium text-foreground">{part.slice(1, -1)}</code>;
      return <span key={index}>{part}</span>;
    });
  };

  return (
    <>
      <span className="leading-relaxed text-[13px]">{parseMarkdown(displayed)}</span>
      {!isUser && displayed.length < content.length && (
        <span className="inline-block w-1.5 h-3.5 ml-1 bg-primary/70 animate-pulse align-baseline rounded-full" />
      )}
    </>
  );
}

function CopilotChatBubble({ msg }: { msg: ChatMsg }) {
  const isUser = msg.role === "user";
  return (
    <div className={cn("flex gap-3 items-end", isUser ? "flex-row-reverse" : "flex-row")}>
      <div className={cn(
        "w-8 h-8 rounded-xl flex items-center justify-center shrink-0 border shadow-inner-top",
        isUser ? "bg-primary/20 border-primary/30 text-primary" : "bg-card border-border/60 text-foreground"
      )}>
        {isUser ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4" />}
      </div>
      <div className={cn(
        "max-w-[82%] px-4 py-3 whitespace-pre-wrap rounded-2xl shadow-sm border",
        isUser
          ? "rounded-br-sm bg-primary border-primary text-primary-foreground shadow-primary/20"
          : "rounded-bl-sm bg-card border-border/60 text-card-foreground shadow-amber"
      )}>
        {msg.pending ? (
          <span className="flex gap-2 items-center text-muted-foreground text-[13px] font-medium">
            <Loader2 className="w-4 h-4 animate-spin text-primary" />
            <span className="bg-gradient-to-r from-muted-foreground via-foreground to-muted-foreground bg-clip-text text-transparent animate-pulse">
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

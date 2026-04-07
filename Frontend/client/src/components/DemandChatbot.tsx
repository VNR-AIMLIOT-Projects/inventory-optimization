import { useState, useEffect, useRef, useCallback } from "react";
import { Bot, Send, Wand2, X, Loader2, User, Sparkles, RotateCcw } from "lucide-react";
import { chatWithDemandAgent } from "@/lib/api";
import type { ChatMessage, DetectedParams } from "@/lib/api";
import { friendlyError } from "@/lib/errors";

const QUICK_ACTIONS = [
  "Set avg demand to 200 units",
  "Add a spike of 500 units on 2025-06-15",
  "Scale demand up by 20%",
  "Reset to original data",
];

interface DemandChatbotProps {
  params: DetectedParams | null;
  onRefresh: () => Promise<void>;
}

interface ChatMsg extends ChatMessage {
  pending?: boolean;
}

export function DemandChatbot({ params, onRefresh }: DemandChatbotProps) {
  const [open, setOpen] = useState(false);
  const [input, setInput] = useState("");
  const [messages, setMessages] = useState<ChatMsg[]>([]);
  const [loading, setLoading] = useState(false);
  const [hasUnread, setHasUnread] = useState(false);
  const chatEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLInputElement>(null);

  // Scroll to bottom on new messages
  useEffect(() => {
    if (open) chatEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages, open]);

  // Focus input when panel opens
  useEffect(() => {
    if (open) setTimeout(() => inputRef.current?.focus(), 200);
    if (open) setHasUnread(false);
  }, [open]);

  const handleSend = useCallback(async (text?: string) => {
    const message = (text ?? input).trim();
    if (!message || loading || !params) return;

    setInput("");
    const userMsg: ChatMsg = { role: "user", content: message };
    const pendingMsg: ChatMsg = { role: "assistant", content: "", pending: true };
    setMessages(prev => [...prev, userMsg, pendingMsg]);
    setLoading(true);

    const history = messages.filter(m => !m.pending);

    try {
      const res = await chatWithDemandAgent(message, history);
      const assistantMsg: ChatMsg = { role: "assistant", content: res.assistant_message };
      setMessages(prev => [...prev.slice(0, -1), assistantMsg]);

      if (res.graph_refreshed) {
        await onRefresh();
      }
      if (!open) setHasUnread(true);
    } catch (err: any) {
      const errMsg: ChatMsg = {
        role: "assistant",
        content: `⚠️ ${friendlyError(err, "chatbot")}`,
      };
      setMessages(prev => [...prev.slice(0, -1), errMsg]);
    } finally {
      setLoading(false);
    }
  }, [input, loading, messages, params, open, onRefresh]);

  const handleKey = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="fixed bottom-6 right-6 z-[60] flex flex-col items-end gap-4 pointer-events-none">

      {/* ── Floating Chat Panel ── */}
      <div
        className={`pointer-events-auto origin-bottom-right transition-all duration-300 ease-out flex flex-col w-[360px] h-[520px] rounded-xl glass shadow-2xl overflow-hidden ${open ? "scale-100 opacity-100 translate-y-0" : "scale-95 opacity-0 translate-y-8 pointer-events-none"
          }`}
        aria-hidden={!open}
      >
        {/* Header */}
        <div className="shrink-0 px-4 py-3 bg-muted/80 backdrop-blur-md border-b border-border flex items-center gap-3">
          <div className="w-8 h-8 rounded-md bg-primary/20 border border-primary/30 flex items-center justify-center shrink-0">
            <Sparkles className="w-4 h-4 text-primary" />
          </div>
          <div className="flex-1">
            <div className="text-[11px] font-bold tracking-widest text-foreground uppercase">
              AI Demand Assistant
            </div>
            <div className={`text-[10px] tracking-wide mt-0.5 ${params ? "text-primary/80" : "text-muted-foreground"}`}>
              {params ? "● Ready · Data loaded" : "○ Waiting for data"}
            </div>
          </div>
          <span className="text-[9px] font-bold tracking-widest text-primary/80 bg-primary/10 border border-primary/20 rounded px-1.5 py-0.5 uppercase">
            v1.0
          </span>
        </div>

        {/* Chat Area */}
        <div className="flex-1 overflow-y-auto w-full p-4 flex flex-col gap-4 bg-background/40">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center gap-4 animate-in fade-in duration-500">
              <div className="w-12 h-12 rounded-full bg-primary/10 border border-primary/20 flex items-center justify-center">
                <Bot className="w-6 h-6 text-primary/80" />
              </div>
              <p className="text-xs text-muted-foreground text-center leading-relaxed max-w-[200px]">
                Describe any change to demand in plain English
              </p>

              <div className="w-full flex flex-col gap-2 mt-2">
                {QUICK_ACTIONS.map(q => (
                  <button
                    key={q}
                    onClick={() => handleSend(q)}
                    disabled={!params || loading}
                    className="text-left text-xs px-3 py-2.5 rounded-lg border border-border bg-muted/30 text-muted-foreground cursor-pointer transition-all duration-200 hover:bg-muted hover:text-foreground hover:border-primary/50 disabled:opacity-40 disabled:cursor-not-allowed disabled:hover:bg-muted/30 disabled:hover:border-border"
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((msg, i) => <ChatBubble key={i} msg={msg} />)
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
              placeholder={params ? "e.g. Add a spike on June 15..." : "Upload demand data first..."}
              disabled={!params || loading}
              className="flex-1 h-10 rounded-md border border-border bg-background text-foreground text-xs px-3 outline-none transition-colors focus:border-primary/50 disabled:opacity-50"
            />
            <button
              onClick={() => handleSend()}
              disabled={!input.trim() || !params || loading}
              className={`w-10 h-10 rounded-md border-none flex items-center justify-center shrink-0 transition-all duration-200 ${input.trim() && params && !loading
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
          aria-label="Toggle AI Demand Assistant"
          className={`relative h-14 rounded-full flex items-center border border-primary/20 cursor-pointer active:scale-95 bg-primary text-primary-foreground shadow-xl shadow-primary/20 z-50 overflow-hidden transition-all duration-500 ease-[cubic-bezier(0.25,1,0.5,1)] ${open ? "w-14 justify-center hover:scale-105" : "w-14 hover:w-[260px] group-hover:w-[260px] pr-4"
            }`}
        >
          {/* Soft Blueish Hover Background Layer */}
          <div 
            className={`absolute inset-0 pointer-events-none transition-opacity duration-[800ms] ${open ? "hidden opacity-0" : "opacity-0 group-hover:opacity-100"}`}
            style={{ backgroundColor: "#e0f2fe" }}
          />

          {/* Unread Glow Ring */}
          {hasUnread && !open && (
            <span className="absolute left-0 top-0 w-14 h-14 rounded-full border-2 border-primary/50 animate-[ping_2s_cubic-bezier(0,0,0.2,1)_infinite] z-0" />
          )}

          <div className="w-14 h-14 shrink-0 flex items-center justify-center relative z-10">
            <div className={`transition-transform duration-300 ${open ? "rotate-90 scale-0 opacity-0 absolute" : "rotate-0 scale-100 opacity-100 absolute"} flex items-center justify-center`}>
              <Wand2 className="w-6 h-6 text-primary-foreground group-hover:text-black transition-colors duration-300" />
              {hasUnread && (
                <span className="absolute top-3 right-3 w-2.5 h-2.5 rounded-full bg-destructive border-2 border-primary" />
              )}
            </div>
            <div className={`transition-transform duration-300 ${open ? "rotate-0 scale-100 opacity-100 absolute" : "-rotate-90 scale-0 opacity-0 absolute"} flex items-center justify-center`}>
              <X className="w-6 h-6 text-primary-foreground" />
            </div>
          </div>

          <div className={`flex flex-col items-start whitespace-nowrap overflow-hidden transition-opacity duration-300 relative z-10 ${open ? "opacity-0 hidden" : "opacity-0 group-hover:opacity-100 delay-150"}`}>
            <span className="text-[13px] font-bold tracking-wider uppercase text-black">AI Demand Assistant</span>
            <span className="text-[10px] text-black/80 font-medium opacity-90">Just say it. The AI will do your job.</span>
          </div>
        </button>
      </div>

    </div>
  );
}

// ─── Chat Bubble & Streaming Message ──────────────────────────────────────────

function StreamingMessage({ content, isUser }: { content: string, isUser: boolean }) {
  const [displayed, setDisplayed] = useState(isUser ? content : "");

  useEffect(() => {
    if (isUser) {
      setDisplayed(content);
      return;
    }

    // Slight initial delay to feel like "generation starting"
    const startDelay = setTimeout(() => {
      let i = 0;
      const tick = setInterval(() => {
        setDisplayed(content.substring(0, i));
        i += 2; // Stream 2 chars at a time for speed
        if (i > content.length + 1) {
          clearInterval(tick);
          setDisplayed(content);
        }
      }, 15);
      return () => clearInterval(tick);
    }, 150);

    return () => clearTimeout(startDelay);
  }, [content, isUser]);

  // Barebones markdown parser for text formatting
  const parseMarkdown = (text: string) => {
    const parts = text.split(/(\*\*.*?\*\*|`.*?`)/g);
    return parts.map((part, index) => {
      if (part.startsWith('**') && part.endsWith('**')) {
        return <strong key={index} className="font-semibold text-primary">{part.slice(2, -2)}</strong>;
      }
      if (part.startsWith('`') && part.endsWith('`')) {
        return <code key={index} className="bg-background border border-border rounded px-1 py-[1px] text-[10px] font-mono font-medium">{part.slice(1, -1)}</code>;
      }
      return <span key={index}>{part}</span>;
    });
  };

  return (
    <>
      <span className="leading-relaxed">{parseMarkdown(displayed)}</span>
      {!isUser && displayed.length < content.length && (
        <span className="inline-block w-1.5 h-2.5 ml-0.5 bg-primary/70 animate-pulse align-baseline shadow-[0_0_8px_rgba(var(--primary),0.6)]" />
      )}
    </>
  );
}

function ChatBubble({ msg }: { msg: ChatMsg }) {
  const isUser = msg.role === "user";

  return (
    <div className={`flex gap-3 items-start ${isUser ? "flex-row-reverse" : "flex-row"}`}>
      {/* Avatar */}
      <div className={`w-6 h-6 rounded-full shrink-0 flex items-center justify-center mt-0.5 border shadow-sm ${isUser
          ? "bg-primary/20 border-primary/30"
          : "bg-muted border-border"
        }`}>
        {isUser
          ? <User className="w-3 h-3 text-primary" />
          : <Bot className="w-3 h-3 text-foreground" />
        }
      </div>

      {/* Bubble */}
      <div className={`max-w-[85%] px-3.5 py-2.5 text-[11px] whitespace-pre-wrap ${isUser
          ? "rounded-2xl rounded-tr-sm bg-primary/20 border border-primary/30 text-foreground"
          : "rounded-2xl rounded-tl-sm bg-muted/80 border border-border text-foreground shadow-sm"
        }`}>
        {msg.pending ? (
          <span className="flex gap-1.5 items-center text-muted-foreground relative overflow-hidden">
            <Loader2 className="w-3.5 h-3.5 animate-spin text-primary" />
            <span className="bg-gradient-to-r from-muted-foreground via-primary/80 to-muted-foreground bg-clip-text text-transparent animate-pulse delay-150">
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

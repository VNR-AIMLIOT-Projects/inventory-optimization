/**
 * DemandChatbot — Floating AI Assistant
 *
 * Design: Industrial Command Terminal
 * - Collapsed: vertical pill tab pinned to right edge of viewport
 * - Expanded: panel slides in from the right with glassmorphism treatment
 * - Aesthetic: dark, precise, utilitarian with violet/emerald accent system
 */

import { useState, useEffect, useRef, useCallback } from "react";
import { Bot, Send, Wand2, X, Loader2, User, Sparkles, RotateCcw } from "lucide-react";
import { chatWithDemandAgent } from "@/lib/api";
import type { ChatMessage, DetectedParams } from "@/lib/api";
import { friendlyError } from "@/lib/errors";

// ─── Quick-action chips ────────────────────────────────────────────────────
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
  const [open, setOpen]             = useState(false);
  const [input, setInput]           = useState("");
  const [messages, setMessages]     = useState<ChatMsg[]>([]);
  const [loading, setLoading]       = useState(false);
  const [hasUnread, setHasUnread]   = useState(false);
  const [mounted, setMounted]       = useState(false);
  const chatEndRef                  = useRef<HTMLDivElement>(null);
  const inputRef                    = useRef<HTMLInputElement>(null);

  // Mount trigger for CSS animation
  useEffect(() => { setMounted(true); }, []);

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
    const userMsg: ChatMsg    = { role: "user", content: message };
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
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); handleSend(); }
  };

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <>
      {/* ── Side-edge tab (collapsed trigger) ── */}
      <button
        onClick={() => setOpen(o => !o)}
        aria-label="Toggle AI Demand Assistant"
        style={{
          position: "fixed",
          right: open ? "344px" : "0px",
          top: "50%",
          transform: "translateY(-50%)",
          transition: "right 0.35s cubic-bezier(0.4, 0, 0.2, 1)",
          zIndex: 50,
          border: "none",
          padding: 0,
          cursor: "pointer",
          borderRadius: "12px 0 0 12px",
          background: "linear-gradient(160deg, hsl(265,80%,55%) 0%, hsl(160,70%,40%) 100%)",
          width: "36px",
          height: "96px",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: "6px",
          boxShadow: open
            ? "-4px 0 24px hsla(265,80%,55%,0.35)"
            : "-4px 0 16px hsla(265,80%,55%,0.2)",
        }}
      >
        {/* Glow ring when unread */}
        {hasUnread && !open && (
          <span style={{
            position: "absolute",
            inset: "-4px",
            borderRadius: "14px 0 0 14px",
            animation: "pulse-ring 1.8s ease-out infinite",
            background: "transparent",
            border: "2px solid hsla(265,80%,70%,0.6)",
          }} />
        )}

        {open
          ? <X style={{ width: 14, height: 14, color: "#fff", flexShrink: 0 }} />
          : (
            <>
              <Wand2 style={{ width: 14, height: 14, color: "#fff", flexShrink: 0 }} />
              <span style={{
                writingMode: "vertical-rl",
                textOrientation: "mixed",
                transform: "rotate(180deg)",
                fontSize: "9px",
                fontWeight: 700,
                letterSpacing: "0.12em",
                color: "rgba(255,255,255,0.9)",
                textTransform: "uppercase",
              }}>
                AI
              </span>
              {hasUnread && (
                <span style={{
                  position: "absolute",
                  top: 6,
                  left: 6,
                  width: 7,
                  height: 7,
                  borderRadius: "50%",
                  background: "hsl(0,90%,60%)",
                  border: "1px solid hsl(265,80%,55%)",
                }} />
              )}
            </>
          )
        }
      </button>

      {/* ── Floating panel ── */}
      <div
        aria-hidden={!open}
        style={{
          position: "fixed",
          top: "50%",
          right: 0,
          transform: `translateY(-50%) translateX(${open ? "0%" : "100%"})`,
          transition: "transform 0.35s cubic-bezier(0.4, 0, 0.2, 1)",
          width: "340px",
          height: "500px",
          zIndex: 49,
          display: "flex",
          flexDirection: "column",
          borderRadius: "16px 0 0 16px",
          overflow: "hidden",
          background: "hsl(222, 22%, 8%)",
          border: "1px solid hsla(265,60%,60%,0.18)",
          borderRight: "none",
          boxShadow: "-12px 0 48px hsla(265,70%,40%,0.25), -4px 0 16px hsla(0,0%,0%,0.5)",
        }}
      >
        {/* Header */}
        <div style={{
          padding: "14px 16px 12px",
          background: "linear-gradient(135deg, hsla(265,60%,18%,0.8) 0%, hsla(160,60%,14%,0.6) 100%)",
          borderBottom: "1px solid hsla(265,60%,60%,0.12)",
          display: "flex",
          alignItems: "center",
          gap: "10px",
          flexShrink: 0,
        }}>
          {/* Animated logo mark */}
          <div style={{
            width: 28,
            height: 28,
            borderRadius: 8,
            background: "linear-gradient(135deg, hsla(265,80%,55%,0.3), hsla(160,70%,40%,0.3))",
            border: "1px solid hsla(265,60%,60%,0.25)",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            flexShrink: 0,
          }}>
            <Sparkles style={{ width: 13, height: 13, color: "hsl(265,80%,75%)" }} />
          </div>

          <div style={{ flex: 1 }}>
            <div style={{
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: "0.06em",
              color: "hsl(0,0%,90%)",
              textTransform: "uppercase",
            }}>
              AI Demand Assistant
            </div>
            <div style={{
              fontSize: 9,
              color: params ? "hsl(160,60%,45%)" : "hsl(0,0%,35%)",
              letterSpacing: "0.03em",
              marginTop: 1,
            }}>
              {params ? "● Ready · Demand data loaded" : "○ Waiting for demand data"}
            </div>
          </div>

          {/* Model badge */}
          <span style={{
            fontSize: 8,
            fontWeight: 700,
            letterSpacing: "0.08em",
            color: "hsla(265,80%,75%,0.7)",
            background: "hsla(265,60%,50%,0.1)",
            border: "1px solid hsla(265,60%,60%,0.2)",
            borderRadius: 4,
            padding: "2px 5px",
            textTransform: "uppercase",
          }}>
            2.5 Flash
          </span>
        </div>

        {/* Chat area */}
        <div style={{
          flex: 1,
          overflowY: "auto",
          padding: "12px 14px",
          display: "flex",
          flexDirection: "column",
          gap: 10,
        }}>
          {messages.length === 0 ? (
            // Empty state
            <div style={{
              height: "100%",
              display: "flex",
              flexDirection: "column",
              alignItems: "center",
              justifyContent: "center",
              gap: 14,
            }}>
              <div style={{
                width: 36,
                height: 36,
                borderRadius: "50%",
                background: "linear-gradient(135deg, hsla(265,80%,55%,0.15), hsla(160,70%,40%,0.15))",
                border: "1px solid hsla(265,60%,60%,0.2)",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
              }}>
                <Bot style={{ width: 18, height: 18, color: "hsl(265,80%,70%)" }} />
              </div>
              <p style={{
                fontSize: 11,
                color: "hsl(0,0%,45%)",
                textAlign: "center",
                lineHeight: 1.6,
                margin: 0,
              }}>
                Describe any change to demand<br />in plain English
              </p>

              {/* Quick action chips */}
              <div style={{ width: "100%", display: "flex", flexDirection: "column", gap: 5 }}>
                {QUICK_ACTIONS.map(q => (
                  <button
                    key={q}
                    onClick={() => handleSend(q)}
                    disabled={!params || loading}
                    style={{
                      textAlign: "left",
                      fontSize: 10,
                      padding: "7px 10px",
                      borderRadius: 7,
                      border: "1px solid hsla(265,40%,60%,0.15)",
                      background: "hsla(265,30%,30%,0.08)",
                      color: "hsl(0,0%,55%)",
                      cursor: params ? "pointer" : "not-allowed",
                      transition: "all 0.15s",
                      opacity: params ? 1 : 0.4,
                    }}
                    onMouseEnter={e => {
                      if (params) {
                        (e.target as HTMLButtonElement).style.background = "hsla(265,40%,40%,0.18)";
                        (e.target as HTMLButtonElement).style.color = "hsl(0,0%,80%)";
                        (e.target as HTMLButtonElement).style.borderColor = "hsla(265,60%,60%,0.3)";
                      }
                    }}
                    onMouseLeave={e => {
                      (e.target as HTMLButtonElement).style.background = "hsla(265,30%,30%,0.08)";
                      (e.target as HTMLButtonElement).style.color = "hsl(0,0%,55%)";
                      (e.target as HTMLButtonElement).style.borderColor = "hsla(265,40%,60%,0.15)";
                    }}
                  >
                    {q}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            messages.map((msg, i) => (
              <ChatBubble key={i} msg={msg} />
            ))
          )}
          <div ref={chatEndRef} />
        </div>

        {/* Footer / Input */}
        <div style={{
          padding: "10px 12px 12px",
          borderTop: "1px solid hsla(265,40%,60%,0.1)",
          background: "hsla(222,22%,6%,0.8)",
          flexShrink: 0,
        }}>
          <div style={{ display: "flex", gap: 7, alignItems: "center" }}>
            <input
              ref={inputRef}
              value={input}
              onChange={e => setInput(e.target.value)}
              onKeyDown={handleKey}
              placeholder={params ? "e.g. Add a spike on June 15…" : "Upload demand data first…"}
              disabled={!params || loading}
              style={{
                flex: 1,
                height: 34,
                borderRadius: 8,
                border: "1px solid hsla(265,40%,60%,0.18)",
                background: "hsla(222,22%,11%,0.9)",
                color: "hsl(0,0%,88%)",
                fontSize: 11,
                padding: "0 10px",
                outline: "none",
                transition: "border-color 0.15s",
              }}
              onFocus={e => { e.target.style.borderColor = "hsla(265,80%,65%,0.5)"; }}
              onBlur={e => { e.target.style.borderColor = "hsla(265,40%,60%,0.18)"; }}
            />
            <button
              onClick={() => handleSend()}
              disabled={!input.trim() || !params || loading}
              style={{
                width: 34,
                height: 34,
                borderRadius: 8,
                border: "none",
                background: input.trim() && params && !loading
                  ? "linear-gradient(135deg, hsl(265,80%,55%), hsl(160,70%,40%))"
                  : "hsla(265,20%,30%,0.3)",
                color: "#fff",
                cursor: input.trim() && params && !loading ? "pointer" : "not-allowed",
                display: "flex",
                alignItems: "center",
                justifyContent: "center",
                flexShrink: 0,
                transition: "all 0.15s",
              }}
            >
              {loading
                ? <Loader2 style={{ width: 13, height: 13, animation: "spin 1s linear infinite" }} />
                : <Send style={{ width: 13, height: 13 }} />
              }
            </button>
          </div>

          {messages.length > 0 && (
            <button
              onClick={() => setMessages([])}
              style={{
                marginTop: 7,
                fontSize: 9,
                color: "hsl(0,0%,30%)",
                background: "none",
                border: "none",
                cursor: "pointer",
                padding: 0,
                display: "flex",
                alignItems: "center",
                gap: 3,
                transition: "color 0.15s",
              }}
              onMouseEnter={e => { (e.currentTarget).style.color = "hsl(0,0%,50%)"; }}
              onMouseLeave={e => { (e.currentTarget).style.color = "hsl(0,0%,30%)"; }}
            >
              <RotateCcw style={{ width: 8, height: 8 }} />
              Clear conversation
            </button>
          )}
        </div>
      </div>

      {/* Global keyframe styles */}
      <style>{`
        @keyframes pulse-ring {
          0%   { transform: scale(1); opacity: 0.8; }
          100% { transform: scale(1.25); opacity: 0; }
        }
        @keyframes spin {
          to { transform: rotate(360deg); }
        }
      `}</style>
    </>
  );
}

// ─── Chat Bubble ─────────────────────────────────────────────────────────────
function ChatBubble({ msg }: { msg: ChatMsg }) {
  const isUser = msg.role === "user";

  return (
    <div style={{
      display: "flex",
      gap: 7,
      flexDirection: isUser ? "row-reverse" : "row",
      alignItems: "flex-start",
    }}>
      {/* Avatar */}
      <div style={{
        width: 20,
        height: 20,
        borderRadius: "50%",
        flexShrink: 0,
        display: "flex",
        alignItems: "center",
        justifyContent: "center",
        background: isUser
          ? "hsla(265,60%,60%,0.15)"
          : "hsla(160,60%,40%,0.15)",
        border: `1px solid ${isUser ? "hsla(265,60%,60%,0.2)" : "hsla(160,60%,40%,0.2)"}`,
        marginTop: 2,
      }}>
        {isUser
          ? <User style={{ width: 10, height: 10, color: "hsl(265,80%,70%)" }} />
          : <Bot  style={{ width: 10, height: 10, color: "hsl(160,70%,50%)" }} />
        }
      </div>

      {/* Bubble */}
      <div style={{
        maxWidth: "80%",
        padding: "7px 10px",
        borderRadius: isUser ? "10px 2px 10px 10px" : "2px 10px 10px 10px",
        fontSize: 11,
        lineHeight: 1.55,
        whiteSpace: "pre-wrap",
        background: isUser
          ? "hsla(265,50%,50%,0.15)"
          : "hsla(222,22%,14%,0.9)",
        border: `1px solid ${isUser ? "hsla(265,60%,60%,0.15)" : "hsla(222,22%,22%,0.5)"}`,
        color: "hsl(0,0%,82%)",
      }}>
        {msg.pending ? (
          <span style={{ display: "flex", gap: 4, alignItems: "center", color: "hsl(0,0%,40%)" }}>
            <Loader2 style={{ width: 10, height: 10, animation: "spin 1s linear infinite" }} />
            Thinking…
          </span>
        ) : (
          msg.content
        )}
      </div>
    </div>
  );
}

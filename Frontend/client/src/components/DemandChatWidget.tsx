import { useState, useRef, useEffect } from "react";
import { MessageSquare, Send, X, Terminal, Loader2, Minimize2, Maximize2 } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { chatModifyDemand, DetectedParams } from "@/lib/api";
import { useToast } from "@/hooks/use-toast";

interface Message {
  role: "user" | "system";
  content: string;
  paramsChanged?: boolean;
}

interface DemandChatWidgetProps {
  currentParams: DetectedParams | null;
  onParamsUpdated: (newParams: Partial<DetectedParams>) => void;
}

export function DemandChatWidget({ currentParams, onParamsUpdated }: DemandChatWidgetProps) {
  const [isOpen, setIsOpen] = useState(false);
  const [isMinimized, setIsMinimized] = useState(false);
  const [messages, setMessages] = useState<Message[]>([
    { role: "system", content: "$ SYSTEM: LLM Parameter Modification initialized.\n$ Waiting for command... (e.g. 'increase the summer peak by 20%')" }
  ]);
  const [inputMsg, setInputMsg] = useState("");
  const [isProcessing, setIsProcessing] = useState(false);
  const { toast } = useToast();
  
  const endOfMessagesRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    if (isOpen && !isMinimized) {
      endOfMessagesRef.current?.scrollIntoView({ behavior: "smooth" });
    }
  }, [messages, isOpen, isMinimized]);

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!inputMsg.trim() || !currentParams || isProcessing) return;

    const userMessage = inputMsg;
    setInputMsg("");
    setMessages(prev => [...prev, { role: "user", content: `> ${userMessage}` }]);
    setIsProcessing(true);

    try {
      const response = await chatModifyDemand({
        message: userMessage,
        current_params: currentParams
      });
      
      setMessages(prev => [...prev, { 
        role: "system", 
        content: `$ SUCCESS: ${response.reply}`,
        paramsChanged: true
      }]);
      
      // Update the parent component's params
      if (Object.keys(response.updated_params).length > 0) {
        onParamsUpdated(response.updated_params);
      }
      
    } catch (err: any) {
      setMessages(prev => [...prev, { 
        role: "system", 
        content: `! ERROR: ${err.message || 'Operation failed. Check syntax and try again.'}` 
      }]);
    } finally {
      setIsProcessing(false);
    }
  };

  // If floating button state
  if (!isOpen) {
    return (
      <Button 
        onClick={() => { setIsOpen(true); setIsMinimized(false); }}
        className="fixed bottom-6 right-6 w-14 h-14 rounded-none border-2 border-primary bg-background text-primary hover:bg-primary/10 shadow-[4px_4px_0_0_hsl(var(--primary))]"
        size="icon"
      >
        <Terminal className="w-6 h-6" />
      </Button>
    );
  }

  // Widget state (Industrial Utilitarian UI)
  return (
    <div 
      className={`fixed bottom-6 right-6 flex flex-col border-2 border-border bg-card shadow-[8px_8px_0_0_hsl(var(--border)_/_0.5)] transition-all duration-300 z-50 ${isMinimized ? 'w-80 h-14' : 'w-96 h-[500px]'}`}
    >
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 border-b-2 border-border bg-muted/30">
        <div className="flex items-center gap-2">
          <Terminal className="w-4 h-4 text-primary" />
          <span className="font-mono text-xs font-bold uppercase tracking-widest text-foreground">Param_Console_v1.0</span>
        </div>
        <div className="flex items-center gap-1 text-muted-foreground">
          <button onClick={() => setIsMinimized(!isMinimized)} className="p-1 hover:text-foreground transition-colors hover:bg-border/50">
            {isMinimized ? <Maximize2 className="w-4 h-4" /> : <Minimize2 className="w-4 h-4" />}
          </button>
          <button onClick={() => setIsOpen(false)} className="p-1 hover:text-red-400 transition-colors hover:bg-red-400/10">
            <X className="w-4 h-4" />
          </button>
        </div>
      </div>

      {/* Body */}
      {!isMinimized && (
        <>
          <div className="flex-1 overflow-y-auto p-4 space-y-4 font-mono text-xs bg-black/40">
            {messages.map((m, i) => (
              <div key={i} className={`whitespace-pre-wrap ${m.role === 'system' ? (m.content.startsWith('!') ? 'text-red-400' : 'text-emerald-400') : 'text-muted-foreground'}`}>
                {m.content}
                {m.paramsChanged && (
                  <div className="mt-2 text-[10px] text-primary/70 border-l border-primary/30 pl-2 ml-2">
                    Variables updated. UI graphs refreshing...
                  </div>
                )}
              </div>
            ))}
            {isProcessing && (
              <div className="flex items-center gap-2 text-primary animate-pulse">
                <Loader2 className="w-3 h-3 animate-spin" />
                <span>Processing instruction...</span>
              </div>
            )}
            <div ref={endOfMessagesRef} />
          </div>

          {/* Input */}
          <div className="p-3 border-t-2 border-border bg-muted/20">
            <form onSubmit={handleSubmit} className="flex gap-2">
              <Input
                value={inputMsg}
                onChange={(e) => setInputMsg(e.target.value)}
                placeholder="Enter command..."
                disabled={isProcessing || !currentParams}
                className="font-mono text-xs rounded-none border-border focus-visible:ring-primary focus-visible:ring-offset-0 bg-transparent h-10"
              />
              <Button 
                type="submit" 
                disabled={isProcessing || !currentParams || !inputMsg.trim()}
                className="rounded-none border-2 border-primary bg-primary/10 text-primary hover:bg-primary/20 h-10 w-10 px-0"
              >
                <Send className="w-4 h-4" />
              </Button>
            </form>
          </div>
        </>
      )}
    </div>
  );
}

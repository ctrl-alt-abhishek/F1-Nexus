"use client";

import { useState, useRef, useEffect } from "react";
import { fetchApi } from "@/lib/api";
import { Spinner } from "@/components/ui/spinner";
import { Send, Bot, User, Sparkles } from "lucide-react";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  sql?: string;
  data?: any[];
}

const CURRENT_YEAR = new Date().getFullYear();
const LAST_YEAR = CURRENT_YEAR - 1;

const FALLBACK_SUGGESTIONS = [
  `Who had the fastest lap at Monaco ${LAST_YEAR}?`,
  `Compare VER and NOR tyre degradation at Silverstone ${CURRENT_YEAR}`,
  `Which circuit had the most safety car periods in ${LAST_YEAR}?`,
  `What was LEC's average qualifying gap to pole in ${CURRENT_YEAR}?`,
  `Which driver had the most pit stops in the ${CURRENT_YEAR} season?`,
  `What is the average lap time difference between SOFT and HARD compounds at Spa?`,
];

export default function ChatPage() {
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [input, setInput] = useState("");
  const [loading, setLoading] = useState(false);
  const [suggestions, setSuggestions] = useState<string[]>(FALLBACK_SUGGESTIONS);
  const messagesEndRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  useEffect(() => {
    async function getSuggestions() {
      try {
        const result = await fetchApi<{suggestions: string[]}>("/chat/suggestions", { requireAuth: true });
        if (result.suggestions?.length > 0) {
          setSuggestions(result.suggestions);
        }
      } catch (err) {
        console.debug("Using fallback suggestions:", err);
      }
    }
    getSuggestions();
  }, []);

  const handleSend = async (text: string) => {
    if (!text.trim() || loading) return;

    const userMessage: ChatMessage = { role: "user", content: text };
    setMessages((prev) => [...prev, userMessage]);
    setInput("");
    setLoading(true);

    try {
      const response = await fetchApi<{answer: string; sql: string; row_count: number; data: any[]}>("/chat/query", {
        method: "POST",
        body: JSON.stringify({ question: text }),
        requireAuth: true,
      });
      setMessages((prev) => [...prev, {
        role: "assistant",
        content: response.answer,
        sql: response.sql,
        data: response.data,
      }]);
    } catch (err: any) {
      const errorMsg = err.message?.includes("401") || err.message?.includes("Unauthorized")
        ? "Authentication required. Please configure Firebase credentials to use the AI chat."
        : `Error: ${err.message}`;
      setMessages((prev) => [...prev, { role: "assistant", content: errorMsg }]);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="h-[calc(100vh-8rem)] max-w-5xl mx-auto flex flex-col justify-between animate-in fade-in duration-500 gap-6">
      {/* Header */}
      <div>
        <h1 className="text-5xl font-bold tracking-tight text-white font-space flex items-center gap-3">
          <Sparkles className="text-primary w-10 h-10 animate-pulse" />
          Nexus AI
        </h1>
        <p className="text-on-surface-variant mt-3 text-lg font-space">
          Ask strategy questions, query telemetry, or review tyre degradation models using NLP.
        </p>
      </div>

      {/* Main Glass Viewport */}
      <div className="flex-1 glass-card flex flex-col overflow-hidden relative border border-white/5">
        <div className="flex-1 overflow-y-auto p-6 space-y-6 custom-scrollbar">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center space-y-8 max-w-xl mx-auto">
              <div className="w-16 h-16 rounded-2xl bg-white/5 border border-white/5 flex items-center justify-center shadow-lg shadow-black/20">
                <Bot className="w-8 h-8 text-primary" />
              </div>
              <div>
                <h3 className="text-2xl font-bold text-white font-space">How can I help you today?</h3>
                <p className="text-sm text-on-surface-variant mt-2 font-space">
                  I query real-time race sessions, historical lap times, tyre stint durations, and Monte Carlo models.
                </p>
              </div>
              <div className="flex flex-wrap justify-center gap-2 mt-4 font-mono">
                {suggestions.map((s, i) => (
                  <button 
                    key={i} 
                    className="border border-white/10 bg-white/5 hover:border-primary/50 hover:bg-glass-hover text-on-surface-variant hover:text-white py-2.5 px-4 rounded-xl text-[10px] font-bold uppercase tracking-wider transition-all"
                    onClick={() => handleSend(s)}
                  >
                    {s}
                  </button>
                ))}
              </div>
            </div>
          ) : (
            <div className="space-y-6">
              {messages.map((msg, idx) => (
                <div key={idx} className={`flex gap-4 ${msg.role === "user" ? "flex-row-reverse" : ""}`}>
                  <div className={`w-9 h-9 rounded-xl flex items-center justify-center shrink-0 border select-none ${
                    msg.role === "user" 
                      ? "bg-primary border-primary text-white" 
                      : "bg-white/5 border-white/10 text-on-surface-variant"
                  }`}>
                    {msg.role === "user" ? <User className="w-4.5 h-4.5" /> : <Bot className="w-4.5 h-4.5 text-primary" />}
                  </div>
                  <div className={`rounded-2xl px-5 py-4 max-w-[80%] border ${
                    msg.role === "user" 
                      ? "bg-primary/10 border-primary/20 text-white font-sans" 
                      : "bg-white/5 border-white/5 text-on-surface font-sans"
                  }`}>
                    <div className="whitespace-pre-wrap text-sm leading-relaxed">{msg.content}</div>
                    
                    {/* Nested SQL details */}
                    {msg.sql && (
                      <details className="mt-4 text-xs font-mono border-t border-white/5 pt-3 group">
                        <summary className="text-on-surface-variant/60 cursor-pointer hover:text-primary transition-colors uppercase tracking-widest text-[9px] font-bold">
                          View generated SQL
                        </summary>
                        <pre className="mt-2.5 p-3.5 bg-black/50 border border-white/5 rounded-xl text-primary font-bold overflow-x-auto whitespace-pre-wrap">
                          {msg.sql}
                        </pre>
                      </details>
                    )}
                    
                    {/* Nested raw data details */}
                    {msg.data && msg.data.length > 0 && (
                      <details className="mt-2 text-xs font-mono group">
                        <summary className="text-on-surface-variant/60 cursor-pointer hover:text-primary transition-colors uppercase tracking-widest text-[9px] font-bold">
                          View raw results ({msg.data.length} rows)
                        </summary>
                        <pre className="mt-2.5 p-3.5 bg-black/50 border border-white/5 rounded-xl text-on-surface-variant/80 overflow-x-auto max-h-48 custom-scrollbar">
                          {JSON.stringify(msg.data, null, 2)}
                        </pre>
                      </details>
                    )}
                  </div>
                </div>
              ))}
              
              {loading && (
                <div className="flex gap-4">
                  <div className="w-9 h-9 rounded-xl bg-white/5 border border-white/10 text-on-surface-variant flex items-center justify-center shrink-0">
                    <Bot className="w-4.5 h-4.5 text-primary" />
                  </div>
                  <div className="rounded-2xl px-5 py-4 bg-white/5 border border-white/5">
                    <Spinner size="sm" className="text-primary" />
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </div>

        {/* Form Input Footer */}
        <div className="p-4 border-t border-white/5 bg-black/20">
          <form 
            className="flex w-full gap-3"
            onSubmit={(e) => {
              e.preventDefault();
              handleSend(input);
            }}
          >
            <input 
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="ASK ABOUT TYRE DEGRADATION AT SPA..."
              className="flex-1 bg-black/40 border border-white/10 rounded-xl px-4 py-3.5 text-sm focus:ring-1 focus:ring-primary focus:border-primary outline-none text-white placeholder-on-surface-variant font-mono uppercase tracking-wide transition-all"
              disabled={loading}
            />
            <button 
              type="submit" 
              disabled={!input.trim() || loading} 
              className="w-14 h-12 bg-primary/10 border border-primary/20 rounded-xl hover:bg-primary/20 transition-all flex items-center justify-center text-primary disabled:opacity-30 disabled:hover:bg-primary/10 shrink-0"
            >
              <Send className="w-5 h-5" />
            </button>
          </form>
        </div>
      </div>
    </div>
  );
}

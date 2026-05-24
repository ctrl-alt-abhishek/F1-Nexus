"use client";

import { useState, useRef, useEffect } from "react";
import { fetchApi } from "@/lib/api";
import { Card, CardContent, CardFooter } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Spinner } from "@/components/ui/spinner";
import { Send, Bot, User, Sparkles } from "lucide-react";
import { Badge } from "@/components/ui/badge";

interface ChatMessage {
  role: "user" | "assistant";
  content: string;
  sql?: string;
  data?: any[];
}

// Default suggestions (matching backend _DEFAULT_SUGGESTIONS) for when the API is unreachable
const FALLBACK_SUGGESTIONS = [
  "Who had the fastest lap at Monaco 2023?",
  "Compare VER and NOR tyre degradation at Silverstone 2024",
  "Which circuit had the most safety car periods in 2023?",
  "What was LEC's average qualifying gap to pole in 2024?",
  "Which driver had the most pit stops in the 2024 season?",
  "What is the average lap time difference between SOFT and HARD compounds at Spa?",
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
    // Try to fetch personalized suggestions (requires auth — will silently fallback)
    async function getSuggestions() {
      try {
        const result = await fetchApi<{suggestions: string[]}>("/chat/suggestions", { requireAuth: true });
        if (result.suggestions?.length > 0) {
          setSuggestions(result.suggestions);
        }
      } catch (err) {
        // Auth or network error — use fallback suggestions (already set)
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
    <div className="h-[calc(100vh-8rem)] max-w-4xl mx-auto flex flex-col animate-in fade-in">
      <div className="mb-4">
        <h1 className="text-3xl font-bold flex items-center gap-3">
          <Sparkles className="text-red-500 w-8 h-8" />
          Nexus AI
        </h1>
        <p className="text-slate-400 mt-1">Ask questions about F1 strategy, telemetry, and history.</p>
      </div>

      <Card className="flex-1 glass flex flex-col overflow-hidden">
        <CardContent className="flex-1 overflow-y-auto p-4 space-y-4">
          {messages.length === 0 ? (
            <div className="h-full flex flex-col items-center justify-center text-center space-y-6">
              <div className="w-16 h-16 rounded-full bg-slate-800 flex items-center justify-center">
                <Bot className="w-8 h-8 text-red-500" />
              </div>
              <div>
                <h3 className="text-xl font-bold text-slate-200">How can I help you today?</h3>
                <p className="text-sm text-slate-400 mt-2 max-w-sm">
                  I can analyze telemetry data, explain tyre strategies, or look up historical race results.
                </p>
              </div>
              <div className="flex flex-wrap justify-center gap-2 max-w-lg mt-4">
                {suggestions.map((s, i) => (
                  <Badge 
                    key={i} 
                    variant="outline" 
                    className="cursor-pointer hover:bg-slate-800 py-1.5 px-3 text-xs"
                    onClick={() => handleSend(s)}
                  >
                    {s}
                  </Badge>
                ))}
              </div>
            </div>
          ) : (
            <div className="space-y-6">
              {messages.map((msg, idx) => (
                <div key={idx} className={`flex gap-4 ${msg.role === "user" ? "flex-row-reverse" : ""}`}>
                  <div className={`w-8 h-8 rounded flex items-center justify-center shrink-0 ${
                    msg.role === "user" ? "bg-red-600 text-white" : "bg-slate-800 text-slate-300 border border-slate-700"
                  }`}>
                    {msg.role === "user" ? <User className="w-4 h-4" /> : <Bot className="w-4 h-4 text-red-400" />}
                  </div>
                  <div className={`rounded-lg px-4 py-3 max-w-[80%] ${
                    msg.role === "user" ? "bg-red-900/20 border border-red-900/50 text-slate-200" : "bg-slate-800/50 border border-slate-700/50 text-slate-300"
                  }`}>
                    <div className="whitespace-pre-wrap text-sm leading-relaxed">{msg.content}</div>
                    {msg.sql && (
                      <details className="mt-3 text-xs">
                        <summary className="text-slate-500 cursor-pointer hover:text-slate-400">View generated SQL</summary>
                        <pre className="mt-2 p-2 bg-slate-900 rounded text-slate-400 overflow-x-auto">{msg.sql}</pre>
                      </details>
                    )}
                    {msg.data && msg.data.length > 0 && (
                      <details className="mt-2 text-xs">
                        <summary className="text-slate-500 cursor-pointer hover:text-slate-400">View raw data ({msg.data.length} rows)</summary>
                        <pre className="mt-2 p-2 bg-slate-900 rounded text-slate-400 overflow-x-auto max-h-40">
                          {JSON.stringify(msg.data, null, 2)}
                        </pre>
                      </details>
                    )}
                  </div>
                </div>
              ))}
              {loading && (
                <div className="flex gap-4">
                  <div className="w-8 h-8 rounded bg-slate-800 text-slate-300 border border-slate-700 flex items-center justify-center shrink-0">
                    <Bot className="w-4 h-4 text-red-400" />
                  </div>
                  <div className="rounded-lg px-4 py-3 bg-slate-800/50 border border-slate-700/50">
                    <Spinner size="sm" className="text-slate-400" />
                  </div>
                </div>
              )}
              <div ref={messagesEndRef} />
            </div>
          )}
        </CardContent>
        <CardFooter className="p-4 border-t border-slate-800 bg-slate-900/80">
          <form 
            className="flex w-full gap-2"
            onSubmit={(e) => {
              e.preventDefault();
              handleSend(input);
            }}
          >
            <Input 
              value={input}
              onChange={(e) => setInput(e.target.value)}
              placeholder="Ask about tyre degradation at Spa..."
              className="flex-1 bg-slate-950 border-slate-700"
              disabled={loading}
            />
            <Button type="submit" disabled={!input.trim() || loading} className="w-12 px-0">
              <Send className="w-4 h-4" />
            </Button>
          </form>
        </CardFooter>
      </Card>
    </div>
  );
}

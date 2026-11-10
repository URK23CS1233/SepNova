"use client";
import { useState, useRef, useEffect } from "react";
import { MessageSquare, X, Send, Bot, User, Loader2 } from "lucide-react";
import { useAuth } from "@/contexts/AuthContext";
import { supabase } from "@/lib/supabase";
import { cn } from "@/lib/utils";

interface Message {
  role: "user" | "assistant";
  content: string;
}

interface Props {
  patientId?: string;
}

export function ChatPanel({ patientId }: Props) {
  const { profile, role } = useAuth();
  const [open, setOpen]         = useState(false);
  const [messages, setMessages] = useState<Message[]>([]);
  const [input, setInput]       = useState("");
  const [loading, setLoading]   = useState(false);
  const bottomRef = useRef<HTMLDivElement>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [messages]);

  // Reset conversation when patient changes
  useEffect(() => {
    setMessages([]);
  }, [patientId]);

  async function send() {
    if (!input.trim() || loading) return;

    const userMsg: Message = { role: "user", content: input.trim() };
    const newHistory = [...messages, userMsg];
    setMessages(newHistory);
    setInput("");
    setLoading(true);

    try {
      const { data: { session } } = await supabase.auth.getSession();
      const token = session?.access_token;
      if (!token) throw new Error("Not authenticated");

      const res = await fetch(
        `${process.env.NEXT_PUBLIC_API_URL}/api/v1/chat`,
        {
          method: "POST",
          headers: {
            "Content-Type": "application/json",
            "Authorization": `Bearer ${token}`,
          },
          body: JSON.stringify({
            patient_id: patientId ?? null,
            messages: newHistory,
          }),
        }
      );

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail ?? "Chat failed");
      }

      const data = await res.json();
      setMessages((prev) => [...prev, { role: "assistant", content: data.reply }]);
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Something went wrong";
      setMessages((prev) => [...prev, {
        role: "assistant",
        content: `⚠️ Error: ${msg}`,
      }]);
    } finally {
      setLoading(false);
    }
  }

  return (
    <>
      {/* Floating button */}
      <button onClick={() => setOpen(!open)} className="fab" title="SepChat — Clinical AI">
        {open ? <X className="h-5 w-5" /> : <MessageSquare className="h-5 w-5" />}
      </button>

      {/* Panel */}
      {open && (
        <div className="chat-panel">
          {/* Header */}
          <div className="chat-panel__header">
            <div className="chat-avatar">
              <Bot className="h-4 w-4" />
            </div>
            <div className="flex-1">
              <p className="chat-title">SepChat</p>
              <p className="chat-sub">
                {patientId ? `Patient ${patientId}` : "General — no patient selected"}
              </p>
            </div>
            {role && (
              <span className={cn("chat-role-badge", `chat-role-badge--${role}`)}>
                {role.replace("_", " ")}
              </span>
            )}
          </div>

          {/* Scope notice */}
          {messages.length === 0 && (
            <div className="chat-scope">
              <p className="chat-scope__title">Your data scope</p>
              <p className="chat-scope__body">
                {role === "intensivist" && "Full patient access: vitals, labs, risk scores, notes, medications."}
                {role === "surgeon" && "Surgical data: BP, HR, coagulation labs, surgical notes."}
                {role === "nurse" && "Vitals, medications, basic labs, and alerts."}
                {role === "anesthesiologist" && "Hemodynamics, ABG, anesthesia records, airway status."}
                {role === "lab_technician" && "Lab results only."}
                {role === "admin" && "No patient data. Admin functions only."}
              </p>
            </div>
          )}

          {/* Messages */}
          <div className="chat-body">
            {messages.length === 0 && (
              <div className="chat-empty">
                <Bot className="h-8 w-8 mx-auto mb-2 text-slate-300" />
                <p className="text-sm font-medium">Ask about this patient</p>
                <p className="text-xs mt-1">e.g. "What are the latest vitals?" or "Is the patient at risk?"</p>
              </div>
            )}
            {messages.map((m, i) => (
              <div key={i} className={cn("msg", m.role === "user" ? "msg--user" : "msg--assistant")}>
                {m.role === "assistant" && (
                  <div className="msg__avatar msg__avatar--bot">
                    <Bot className="h-3.5 w-3.5" />
                  </div>
                )}
                <div className="msg__bubble">{m.content}</div>
                {m.role === "user" && (
                  <div className="msg__avatar msg__avatar--user">
                    <User className="h-3.5 w-3.5" />
                  </div>
                )}
              </div>
            ))}
            {loading && (
              <div className="msg msg--assistant">
                <div className="msg__avatar msg__avatar--bot">
                  <Bot className="h-3.5 w-3.5" />
                </div>
                <div className="msg__bubble">
                  <Loader2 className="h-4 w-4 animate-spin text-slate-400" />
                </div>
              </div>
            )}
            <div ref={bottomRef} />
          </div>

          {/* Input */}
          <div className="chat-input-bar">
            <input
              type="text"
              value={input}
              onChange={(e) => setInput(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !e.shiftKey && send()}
              placeholder="Ask about this patient…"
              disabled={loading}
              className="chat-input"
            />
            <button onClick={send} disabled={loading || !input.trim()} className="chat-send">
              <Send className="h-4 w-4" />
            </button>
          </div>
        </div>
      )}
    </>
  );
}

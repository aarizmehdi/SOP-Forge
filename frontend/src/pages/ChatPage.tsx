import {
  ArrowLeft,
  ArrowUp,
  FileUp,
  Landmark,
  Laptop,
  MessageCircleQuestion,
  Mic,
  Paperclip,
  Receipt,
  RotateCcw,
  ShieldCheck,
  Square,
} from "lucide-react";
import {
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type FormEvent,
} from "react";
import { useNavigate } from "react-router-dom";
import { api } from "../lib/api";
import type {
  AllowedAction,
  AssistantResponse,
  ConversationDomain,
  ConversationLanguage,
  ConversationUIState,
  TerminalResult,
} from "../types/api";
import { Button, PageHeader, useToast } from "../components/ui";

type Message = { id: number; role: "assistant" | "user"; text: string };
const domains: {
  id: ConversationDomain;
  title: string;
  description: string;
  icon: typeof Landmark;
}[] = [
  {
    id: "leave_hr",
    title: "Leave & HR",
    description: "Time off, balances and workplace policy",
    icon: Landmark,
  },
  {
    id: "expenses_finance",
    title: "Expenses & Finance",
    description: "Reimbursements, receipts and eligibility",
    icon: Receipt,
  },
  {
    id: "it_system_access",
    title: "IT & System Access",
    description: "Systems, permissions and duration",
    icon: Laptop,
  },
  {
    id: "policies_general",
    title: "Policies & General",
    description: "Ask about an organizational policy",
    icon: MessageCircleQuestion,
  },
];
export function ChatPage() {
  const [state, setState] = useState<ConversationUIState>("DOMAIN_SELECTION");
  const [domain, setDomain] = useState<ConversationDomain | null>(null);
  const [language, setLanguage] = useState<ConversationLanguage | null>(null);
  const [conversationId, setConversationId] = useState<string | null>(null);
  const [actions, setActions] = useState<AllowedAction[]>([]);
  const [messages, setMessages] = useState<Message[]>([]);
  const [text, setText] = useState("");
  const [busy, setBusy] = useState(false);
  const [terminal, setTerminal] = useState<TerminalResult | null>(null);
  const [file, setFile] = useState<File | null>(null);
  const [recording, setRecording] = useState(false);
  const recognition = useRef<SpeechRecognition | null>(null);
  const manualSpeechStop = useRef(false);
  const finalSpeechText = useRef("");
  const currentSpeechText = useRef("");
  const endRef = useRef<HTMLDivElement>(null);
  const notify = useToast();
  const nav = useNavigate();
  useEffect(
    () => endRef.current?.scrollIntoView({ behavior: "smooth" }),
    [messages, state],
  );
  useEffect(
    () => () => {
      manualSpeechStop.current = false;
      const instance = recognition.current;
      recognition.current = null;
      instance?.stop();
    },
    [],
  );
  function apply(result: AssistantResponse) {
    setState(result.ui_state);
    setActions(result.allowed_actions);
    setTerminal(result.terminal ?? null);
    if (result.conversation_id) setConversationId(result.conversation_id);
    setMessages((v) => [
      ...v,
      { id: Date.now(), role: "assistant", text: result.message },
    ]);
  }
  function chooseDomain(value: ConversationDomain) {
    setDomain(value);
    setState("LANGUAGE_SELECTION");
  }
  async function chooseLanguage(value: ConversationLanguage) {
    if (!domain) return;
    setLanguage(value);
    setBusy(true);
    try {
      apply(await api.startConversation(domain, value));
    } catch (e) {
      notify(
        e instanceof Error ? e.message : "Unable to start conversation.",
        "error",
      );
    } finally {
      setBusy(false);
    }
  }
  async function submitMessage(value: string) {
    value = value.trim();
    if (!value || !conversationId || !actions.includes("send_message")) return;
    setMessages((v) => [...v, { id: Date.now(), role: "user", text: value }]);
    setText("");
    setBusy(true);
    try {
      apply(await api.chat(value, conversationId));
    } catch (err) {
      notify(err instanceof Error ? err.message : "Message failed.", "error");
    } finally {
      setBusy(false);
    }
  }
  function send(e?: FormEvent) {
    e?.preventDefault();
    void submitMessage(text);
  }
  async function upload() {
    if (!file || !conversationId) return;
    setBusy(true);
    try {
      apply(await api.uploadDraftEvidence(conversationId, file));
      setFile(null);
    } catch (e) {
      notify(e instanceof Error ? e.message : "Upload failed.", "error");
    } finally {
      setBusy(false);
    }
  }
  async function skip() {
    if (!conversationId) return;
    setBusy(true);
    try {
      apply(await api.skipDraftEvidence(conversationId));
    } catch (e) {
      notify(e instanceof Error ? e.message : "Unable to continue.", "error");
    } finally {
      setBusy(false);
    }
  }
  function reset() {
    manualSpeechStop.current = false;
    const instance = recognition.current;
    recognition.current = null;
    instance?.stop();
    setState("DOMAIN_SELECTION");
    setDomain(null);
    setLanguage(null);
    setConversationId(null);
    setActions([]);
    setMessages([]);
    setTerminal(null);
    setText("");
    setFile(null);
    setRecording(false);
  }
  function mic() {
    const Ctor = window.SpeechRecognition ?? window.webkitSpeechRecognition;
    if (!Ctor) {
      notify("Speech input is not supported in this browser.", "error");
      return;
    }
    if (recording) {
      manualSpeechStop.current = true;
      recognition.current?.stop();
      return;
    }
    const instance = new Ctor();
    recognition.current = instance;
    manualSpeechStop.current = false;
    finalSpeechText.current = text.trim();
    currentSpeechText.current = finalSpeechText.current;
    instance.lang = language === "roman_urdu" ? "ur-PK" : "en-US";
    instance.continuous = true;
    instance.interimResults = true;
    instance.onresult = (e) => {
      let interimText = "";
      for (let index = e.resultIndex; index < e.results.length; index += 1) {
        const result = e.results[index];
        if (!result) continue;
        const phrase = result[0]?.transcript.trim();
        if (!phrase) continue;
        if (result.isFinal) {
          finalSpeechText.current = [finalSpeechText.current, phrase]
            .filter(Boolean)
            .join(" ");
        } else {
          interimText = [interimText, phrase].filter(Boolean).join(" ");
        }
      }
      currentSpeechText.current = [finalSpeechText.current, interimText]
        .filter(Boolean)
        .join(" ");
      setText(currentSpeechText.current);
    };
    instance.onerror = (event) => {
      if (event.error === "aborted" && manualSpeechStop.current) return;
      manualSpeechStop.current = false;
      setRecording(false);
      notify("Speech input could not be captured.", "error");
    };
    instance.onend = () => {
      if (recognition.current !== instance) return;
      recognition.current = null;
      setRecording(false);
      const shouldSubmit = manualSpeechStop.current;
      manualSpeechStop.current = false;
      if (shouldSubmit) void submitMessage(currentSpeechText.current);
    };
    try {
      instance.start();
      setRecording(true);
    } catch {
      recognition.current = null;
      notify("Speech input could not be started.", "error");
    }
  }
  return (
    <>
      <PageHeader
        eyebrow="Governed assistant"
        title="Start with what you need"
        description="The assistant gathers the required facts and shows the next valid action at every step."
      />
      <div className="chat-shell">
        <section className="chat-card">
          <ChatHeader
            state={state}
            domain={domain}
            language={language}
            onBack={() => {
              if (state === "LANGUAGE_SELECTION") {
                setState("DOMAIN_SELECTION");
                setDomain(null);
              }
            }}
          />
          <div className="chat-body">
            {state === "DOMAIN_SELECTION" && (
              <div className="choice-stage">
                <div className="assistant-intro">
                  <img src="/assets/branding/assistant-avatar.svg" alt="" />
                  <div>
                    <h2>How can I help today?</h2>
                    <p>Select a request area to begin.</p>
                  </div>
                </div>
                <div className="domain-grid">
                  {domains.map(({ id, title, description, icon: Icon }) => (
                    <button key={id} onClick={() => chooseDomain(id)}>
                      <Icon />
                      <span>
                        <strong>{title}</strong>
                        <small>{description}</small>
                      </span>
                      <ArrowUp className="choice-arrow" />
                    </button>
                  ))}
                </div>
              </div>
            )}
            {state === "LANGUAGE_SELECTION" && (
              <div className="choice-stage">
                <div className="assistant-intro">
                  <img src="/assets/branding/assistant-avatar.svg" alt="" />
                  <div>
                    <h2>Choose your language</h2>
                    <p>
                      The full conversation will continue in your selection.
                    </p>
                  </div>
                </div>
                <div className="language-grid">
                  <button
                    disabled={busy}
                    onClick={() => void chooseLanguage("en")}
                  >
                    <strong>English</strong>
                    <small>Continue in English</small>
                  </button>
                  <button
                    disabled={busy}
                    onClick={() => void chooseLanguage("roman_urdu")}
                  >
                    <strong>Roman Urdu</strong>
                    <small>Roman Urdu mein jaari rakhein</small>
                  </button>
                </div>
              </div>
            )}
            {["ACTIVE_CHAT", "EVIDENCE_GATE", "TERMINAL"].includes(state) && (
              <>
                <div className="messages" aria-live="polite">
                  {messages.map((message) => (
                    <div className={`message ${message.role}`} key={message.id}>
                      {message.role === "assistant" && (
                        <img
                          src="/assets/branding/assistant-avatar.svg"
                          alt="Assistant"
                        />
                      )}
                      <p>{message.text}</p>
                    </div>
                  ))}
                  {busy && (
                    <div className="message assistant">
                      <img
                        src="/assets/branding/assistant-avatar.svg"
                        alt="Assistant"
                      />
                      <p className="typing">
                        <i />
                        <i />
                        <i />
                      </p>
                    </div>
                  )}
                  <div ref={endRef} />
                </div>
                <ChatControls
                  state={state}
                  actions={actions}
                  terminal={terminal}
                  text={text}
                  setText={setText}
                  send={send}
                  file={file}
                  setFile={setFile}
                  upload={upload}
                  skip={skip}
                  mic={mic}
                  recording={recording}
                  busy={busy}
                  reset={reset}
                  viewRequest={() => terminal?.request_id && nav("/requests")}
                />
              </>
            )}
          </div>
        </section>
        <aside className="chat-trust">
          <ShieldCheck />
          <h2>Policy grounded</h2>
          <p>
            Responses use the current policy library. Decisions and human
            actions are captured in the audit trail.
          </p>
          <div>
            <strong>Conversation state</strong>
            <span>{state.replaceAll("_", " ")}</span>
          </div>
          <div>
            <strong>Request area</strong>
            <span>
              {domains.find((x) => x.id === domain)?.title ?? "Not selected"}
            </span>
          </div>
        </aside>
      </div>
    </>
  );
}
function ChatHeader({
  state,
  domain,
  language,
  onBack,
}: {
  state: ConversationUIState;
  domain: ConversationDomain | null;
  language: ConversationLanguage | null;
  onBack: () => void;
}) {
  return (
    <header className="chat-header">
      {state === "LANGUAGE_SELECTION" ? (
        <button onClick={onBack}>
          <ArrowLeft />
          Back
        </button>
      ) : (
        <img src="/assets/branding/mark.svg" alt="" />
      )}
      <div>
        <strong>SOP Forge Assistant</strong>
        <span>
          {domain
            ? `${domains.find((x) => x.id === domain)?.title}${language ? ` · ${language === "en" ? "English" : "Roman Urdu"}` : ""}`
            : "Ready to help"}
        </span>
      </div>
      <span className="online">
        <i />
        Secure
      </span>
    </header>
  );
}
function ChatControls({
  state,
  actions,
  terminal,
  text,
  setText,
  send,
  file,
  setFile,
  upload,
  skip,
  mic,
  recording,
  busy,
  reset,
  viewRequest,
}: {
  state: ConversationUIState;
  actions: AllowedAction[];
  terminal: TerminalResult | null;
  text: string;
  setText: (v: string) => void;
  send: (e: FormEvent) => void;
  file: File | null;
  setFile: (f: File | null) => void;
  upload: () => void;
  skip: () => void;
  mic: () => void;
  recording: boolean;
  busy: boolean;
  reset: () => void;
  viewRequest: () => void;
}) {
  if (state === "EVIDENCE_GATE")
    return (
      <div className="evidence-controls">
        <label className="file-picker">
          <FileUp />
          <span>
            <strong>{file?.name ?? "Choose evidence"}</strong>
            <small>PDF, JPEG or PNG · maximum 5 MB</small>
          </span>
          <input
            type="file"
            accept=".pdf,.png,.jpg,.jpeg"
            onChange={(e: ChangeEvent<HTMLInputElement>) =>
              setFile(e.target.files?.[0] ?? null)
            }
          />
        </label>
        <div>
          <Button
            disabled={!file || busy || !actions.includes("upload_evidence")}
            onClick={upload}
          >
            <Paperclip />
            Upload evidence
          </Button>
          <Button
            variant="secondary"
            disabled={busy || !actions.includes("skip_evidence")}
            onClick={skip}
          >
            Continue without
          </Button>
        </div>
      </div>
    );
  if (state === "TERMINAL")
    return (
      <div className="terminal-controls">
        <div>
          <strong>
            {terminal?.outcome === "incomplete_conversation"
              ? "Conversation closed"
              : terminal?.decision === "approved"
                ? "Request approved"
                : terminal?.decision === "rejected"
                  ? "Request declined"
                  : "Sent for manager review"}
          </strong>
          <span>
            {terminal?.request_id &&
              `Reference ${terminal.request_id.slice(0, 8)}`}
          </span>
        </div>
        {actions.includes("view_request") && (
          <Button variant="secondary" onClick={viewRequest}>
            View request
          </Button>
        )}
        {actions.includes("start_new_conversation") && (
          <Button onClick={reset}>
            <RotateCcw />
            Start new conversation
          </Button>
        )}
      </div>
    );
  return (
    <form className="composer" onSubmit={send}>
      <textarea
        aria-label="Message"
        rows={1}
        maxLength={4000}
        placeholder="Write your answer…"
        value={text}
        readOnly={recording}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Enter" && !e.shiftKey) {
            e.preventDefault();
            e.currentTarget.form?.requestSubmit();
          }
        }}
      />
      {actions.includes("use_microphone") && (
        <button
          type="button"
          className={recording ? "recording" : ""}
          aria-label={recording ? "Stop recording" : "Use microphone"}
          onClick={mic}
        >
          {recording ? <Square /> : <Mic />}
        </button>
      )}
      <button
        type="submit"
        aria-label="Send message"
        disabled={
          recording || !text.trim() || busy || !actions.includes("send_message")
        }
      >
        <ArrowUp />
      </button>
    </form>
  );
}

declare global {
  interface Window {
    SpeechRecognition?: typeof SpeechRecognition;
    webkitSpeechRecognition?: typeof SpeechRecognition;
  }
  interface SpeechRecognition extends EventTarget {
    lang: string;
    continuous: boolean;
    interimResults: boolean;
    start(): void;
    stop(): void;
    onresult: ((event: SpeechRecognitionEvent) => void) | null;
    onerror: ((event: SpeechRecognitionErrorEvent) => void) | null;
    onend: (() => void) | null;
  }
  interface SpeechRecognitionEvent extends Event {
    resultIndex: number;
    results: {
      length: number;
      [index: number]: {
        isFinal: boolean;
        [index: number]: { transcript: string };
      };
    };
  }
  interface SpeechRecognitionErrorEvent extends Event {
    error: string;
  }
  interface SpeechRecognitionConstructor {
    new (): SpeechRecognition;
  }
  var SpeechRecognition: SpeechRecognitionConstructor;
}

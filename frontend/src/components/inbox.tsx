"use client";

import { useCallback, useDeferredValue, useEffect, useState } from "react";

import type {
  ConversationMessage,
  CustomerOrderHistoryItem,
  OrderDetails,
  PanelSnapshot,
  StoreCutoff,
  StorePulse,
  TodaySummary,
  WhatsAppCard,
} from "@/lib/panel-types";
import { useLivePanelSnapshot } from "@/lib/use-live-panel-snapshot";

type InboxProps = {
  snapshot: PanelSnapshot;
  warning?: string;
};

function onlyDigits(value: string): string {
  return value.replace(/\D+/g, "");
}

function matchesConversation(card: WhatsAppCard, term: string): boolean {
  if (!term) return true;
  const lower = term.toLowerCase();
  if (card.cliente_nome.toLowerCase().includes(lower)) return true;
  if (card.last_message.toLowerCase().includes(lower)) return true;

  const digits = onlyDigits(term);
  if (digits.length >= 2 && onlyDigits(card.phone).includes(digits)) return true;

  for (const message of card.messages) {
    if (message.content.toLowerCase().includes(lower)) return true;
  }
  return false;
}

function messageTone(role: string): string {
  if (role === "ia" || role === "bot") return "bg-sky/60 text-[#153b7a]";
  if (role === "humano") return "bg-[#efe7ff] text-[#4b2f79]";
  if (role === "contexto") return "bg-mist text-cocoa";
  return "bg-[#f8ece4] text-ink";
}

const BACKEND_ERROR_LABELS: Record<string, string> = {
  admin_session_required: "Sessão do admin expirou. Faça login novamente.",
  frontend_proxy_not_configured: "PANEL_BACKEND_URL não configurada no frontend.",
  message_required: "Digite uma mensagem antes de enviar.",
  message_send_failed: "Z-API recusou a mensagem. Verifique ZAPI_TOKEN/ZAPI_BASE e o status do painel Z-API.",
  invalid_backend_response: "Resposta inválida do backend. Veja os logs do FastAPI.",
};

async function extractBackendError(response: Response, fallback: string): Promise<string> {
  try {
    const payload = (await response.json()) as { detail?: string } | null;
    const detail = payload?.detail || "";
    if (detail && BACKEND_ERROR_LABELS[detail]) return BACKEND_ERROR_LABELS[detail];
    if (detail) return `${fallback} (${detail})`;
  } catch {
    // swallow parse error
  }
  return `${fallback} (HTTP ${response.status})`;
}

function isAwaitingReply(card: WhatsAppCard): boolean {
  if (!card.messages || card.messages.length === 0) return false;
  const last = card.messages[card.messages.length - 1];
  return last.role === "cliente";
}

function isAutomationEnabled(card: WhatsAppCard): boolean {
  if (card.is_human_handoff) return false;
  if (card.automation_mode === "manual") return false;
  return true;
}

function formatRemaining(minutes: number): string {
  if (minutes < 0) return "encerrado";
  if (minutes < 60) return `${minutes}m`;
  const hours = Math.floor(minutes / 60);
  const rest = minutes % 60;
  return rest === 0 ? `${hours}h` : `${hours}h${String(rest).padStart(2, "0")}`;
}

function closedReasonLabel(reason: StorePulse["closed_reason"]): string {
  if (reason === "manual") return "Fechada (manual)";
  if (reason === "day_off") return "Fechada hoje";
  if (reason === "outside_hours") return "Fora do horário";
  return "Fechada";
}

function StorePulseStrip({ pulse }: { pulse?: StorePulse }) {
  if (!pulse) return null;

  const statusClass = pulse.is_open
    ? "border-[#bde3c6] bg-[#eaf6ee] text-[#1e6b3a]"
    : "border-[#e89b7e] bg-[#fff1ea] text-[#b44a1f]";
  const dotClass = pulse.is_open ? "bg-[#2d8f4e]" : "bg-[#b44a1f]";
  const statusText = pulse.is_open
    ? pulse.hours_label
      ? `Aberta · ${pulse.hours_label}`
      : "Aberta"
    : closedReasonLabel(pulse.closed_reason);
  const aiSchedule = pulse.ai_schedule;
  const aiEnabled = aiSchedule?.enabled;
  const aiActive = aiSchedule?.active;
  const aiClass =
    aiEnabled && !aiActive
      ? "border-[#e6c488] bg-[#fbe7c6] text-[#7a4e00]"
      : aiEnabled
        ? "border-[#b6d4f2] bg-sky/50 text-[#153b7a]"
        : "border-line bg-white/80 text-cocoa/60";
  const aiDotClass =
    aiEnabled && !aiActive
      ? "bg-[#b77800]"
      : aiEnabled
        ? "bg-[#1f6fd8]"
        : "bg-cocoa/40";
  const aiLabel = aiSchedule
    ? aiEnabled
      ? aiActive
        ? `Trufinha ativa · off ${aiSchedule.off_label}`
        : `Trufinha pausada · volta ${aiSchedule.on_label}`
      : "Trufinha 24/7"
    : null;

  return (
    <div className="flex flex-wrap items-center gap-2">
      <span
        className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold ${statusClass}`}
      >
        <span className={`inline-block h-2 w-2 rounded-full ${dotClass}`} aria-hidden />
        {statusText}
      </span>
      {aiLabel ? (
        <span
          className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold ${aiClass}`}
          title={aiSchedule ? `Janela: off ${aiSchedule.off_label} → on ${aiSchedule.on_label}` : undefined}
        >
          <span className={`inline-block h-2 w-2 rounded-full ${aiDotClass}`} aria-hidden />
          {aiLabel}
        </span>
      ) : null}
      {pulse.cutoffs.map((cutoff: StoreCutoff) => {
        const tone = cutoff.passed
          ? "border-line bg-white/80 text-cocoa/55"
          : cutoff.remaining_minutes <= 60
            ? "border-[#e6c488] bg-[#fbe7c6] text-[#7a4e00]"
            : "border-line bg-white text-cocoa/80";
        return (
          <span
            key={cutoff.label}
            className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-medium ${tone}`}
            title={`Limite ${cutoff.time_label}`}
          >
            <span className="font-semibold">{cutoff.label}</span>
            <span className="opacity-70">{cutoff.time_label}</span>
            <span className="font-semibold">· {formatRemaining(cutoff.remaining_minutes)}</span>
          </span>
        );
      })}
    </div>
  );
}

function HandoffBadge() {
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-[#e89b7e] bg-[#fff1ea] px-2 py-0.5 text-[10px] font-bold uppercase tracking-[0.12em] text-[#b44a1f]">
      <span aria-hidden>⚠</span> Humano
    </span>
  );
}

function ConversationListItem({
  card,
  selected,
  onSelect,
}: {
  card: WhatsAppCard;
  selected: boolean;
  onSelect: (phone: string) => void;
}) {
  const awaiting = isAwaitingReply(card);
  const borderClass = card.is_human_handoff
    ? "border-[#e89b7e] bg-[#fff6f1] ring-1 ring-[#e89b7e]/40"
    : selected
      ? "border-clay bg-white ring-2 ring-[#d88d6f]/35"
      : awaiting
        ? "border-[#bad3ee] bg-white ring-1 ring-[#bad3ee]/50"
        : "border-line bg-white/70 hover:bg-white";

  const nameClass = awaiting && !selected ? "font-black text-ink" : "font-semibold text-ink";
  const messageClass = awaiting && !selected
    ? "mt-2 line-clamp-2 text-sm font-semibold text-ink"
    : "mt-2 line-clamp-2 text-sm text-cocoa/85";

  return (
    <button
      type="button"
      onClick={() => onSelect(card.phone)}
      className={`w-full rounded-2xl border px-4 py-3 text-left transition ${borderClass}`}
    >
      <div className="flex items-baseline justify-between gap-2">
        <p className={`truncate ${nameClass}`}>{card.cliente_nome}</p>
        <div className="flex shrink-0 items-center gap-2">
          {awaiting ? (
            <span
              className="inline-block h-2 w-2 rounded-full bg-[#1f6fd8]"
              aria-label="Aguardando resposta"
            />
          ) : null}
          <span className="text-xs text-cocoa/60">{card.last_seen_label}</span>
        </div>
      </div>
      <div className="mt-1 flex items-center gap-2">
        <p className="font-mono text-xs text-cocoa/70">{card.phone}</p>
        {card.is_human_handoff ? <HandoffBadge /> : null}
        {card.order_id ? (
          <span className="rounded-full border border-line bg-white px-2 py-0.5 text-[10px] font-semibold text-cocoa/70">
            #{card.order_id}
          </span>
        ) : null}
      </div>
      <p className={messageClass}>{card.last_message}</p>
    </button>
  );
}

function ConversationList({
  cards,
  selectedPhone,
  onSelect,
}: {
  cards: WhatsAppCard[];
  selectedPhone: string;
  onSelect: (phone: string) => void;
}) {
  if (cards.length === 0) {
    return (
      <p className="px-2 py-6 text-center text-sm text-cocoa/65">
        Nenhuma conversa encontrada.
      </p>
    );
  }

  return (
    <div className="space-y-2">
      {cards.map((card) => (
        <ConversationListItem
          key={card.phone}
          card={card}
          selected={card.phone === selectedPhone}
          onSelect={onSelect}
        />
      ))}
    </div>
  );
}

function MessageBubble({ message }: { message: ConversationMessage }) {
  return (
    <article className={`rounded-2xl px-4 py-3 ${messageTone(message.role)}`}>
      <div className="flex items-center justify-between gap-3 text-xs opacity-75">
        <span className="font-semibold uppercase tracking-[0.16em]">{message.actor_label}</span>
        {message.timestamp_label ? <span>{message.timestamp_label}</span> : null}
      </div>
      <p className="mt-2 whitespace-pre-wrap text-sm leading-6">{message.content}</p>
    </article>
  );
}

function AutomationToggle({
  card,
  onChanged,
}: {
  card: WhatsAppCard;
  onChanged: () => Promise<void> | void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const enabled = isAutomationEnabled(card);

  async function toggle() {
    if (busy) return;
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(
        `/api/conversations/${encodeURIComponent(card.phone)}/automation`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ enabled: !enabled, notify_customer: false }),
        },
      );
      if (!response.ok) {
        setError(await extractBackendError(response, "Não foi possível alternar a IA."));
        return;
      }
      await onChanged();
    } catch {
      setError("Erro de rede ao alternar a IA.");
    } finally {
      setBusy(false);
    }
  }

  const label = enabled ? "IA ligada" : "Manual";
  const stateClass = enabled
    ? "border-[#b6d4f2] bg-sky/50 text-[#153b7a]"
    : "border-[#e6c488] bg-[#fbe7c6] text-[#7a4e00]";

  return (
    <div className="flex flex-col items-end gap-1">
      <button
        type="button"
        onClick={toggle}
        disabled={busy}
        className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-xs font-semibold transition disabled:opacity-60 ${stateClass}`}
        aria-pressed={enabled}
      >
        <span
          className={`inline-block h-2 w-2 rounded-full ${enabled ? "bg-[#1f6fd8]" : "bg-[#b77800]"}`}
          aria-hidden
        />
        {busy ? "Alternando..." : label}
      </button>
      {error ? <span className="text-[10px] text-[#b44a1f]">{error}</span> : null}
    </div>
  );
}

const ATTENDANT_STORAGE_KEY = "chokobot.panel.attendant";

const ATTENDANT_TEMPLATES: { id: string; label: string; build: (attendant: string) => string }[] = [
  {
    id: "intro",
    label: "Apresentação",
    build: (attendant) =>
      `Oi! Aqui é ${attendant} da Chokodelícia 🍫 Como posso te ajudar?`,
  },
  {
    id: "assumir",
    label: "Assumir chat",
    build: (attendant) =>
      `Oi! A Trufinha me chamou aqui, sou a ${attendant} e vou continuar seu atendimento por aqui 💛`,
  },
  {
    id: "espera",
    label: "Pedir um minuto",
    build: (attendant) =>
      `Aqui é ${attendant}. Me dá um minutinho que já te respondo, tá? 😊`,
  },
];

function MessageComposer({
  phone,
  onSent,
  attendants,
}: {
  phone: string;
  onSent: () => Promise<void> | void;
  attendants: string[];
}) {
  const [value, setValue] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [attendant, setAttendant] = useState<string>(() => attendants[0] || "Atendente");

  useEffect(() => {
    if (typeof window === "undefined") return;
    const stored = window.localStorage.getItem(ATTENDANT_STORAGE_KEY);
    if (stored && (attendants.length === 0 || attendants.includes(stored))) {
      setAttendant(stored);
    } else if (attendants[0]) {
      setAttendant(attendants[0]);
    }
  }, [attendants]);

  useEffect(() => {
    if (typeof window === "undefined" || !attendant) return;
    window.localStorage.setItem(ATTENDANT_STORAGE_KEY, attendant);
  }, [attendant]);

  useEffect(() => {
    setValue("");
    setError(null);
  }, [phone]);

  function applyTemplate(templateId: string) {
    const template = ATTENDANT_TEMPLATES.find((item) => item.id === templateId);
    if (!template) return;
    setValue(template.build(attendant || "Atendente"));
  }

  async function send() {
    const message = value.trim();
    if (!message || busy) return;
    setBusy(true);
    setError(null);
    try {
      const response = await fetch(`/api/conversations/${encodeURIComponent(phone)}/reply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, disable_ai: false, notify_handoff: false }),
      });
      if (!response.ok) {
        setError(await extractBackendError(response, "Não foi possível enviar a mensagem."));
        return;
      }
      setValue("");
      await onSent();
    } catch {
      setError("Erro de rede ao enviar.");
    } finally {
      setBusy(false);
    }
  }

  function onKeyDown(event: React.KeyboardEvent<HTMLTextAreaElement>) {
    if ((event.metaKey || event.ctrlKey) && event.key === "Enter") {
      event.preventDefault();
      void send();
    }
  }

  const disabled = busy || value.trim().length === 0;

  return (
    <div className="border-t border-line bg-paper/80 px-6 py-4">
      {error ? (
        <p className="mb-2 text-xs text-[#b44a1f]">{error}</p>
      ) : null}
      {attendants.length > 0 ? (
        <div className="mb-3 flex flex-wrap items-center gap-2 text-xs">
          <label className="flex items-center gap-2 text-cocoa/75">
            <span className="font-semibold uppercase tracking-[0.14em]">Atendente</span>
            <select
              value={attendant}
              onChange={(event) => setAttendant(event.target.value)}
              className="h-8 rounded-full border border-line bg-white px-3 text-xs font-semibold text-ink outline-none focus:border-clay"
            >
              {attendants.map((name) => (
                <option key={name} value={name}>
                  {name}
                </option>
              ))}
            </select>
          </label>
          <span className="text-cocoa/45">·</span>
          {ATTENDANT_TEMPLATES.map((template) => (
            <button
              key={template.id}
              type="button"
              onClick={() => applyTemplate(template.id)}
              className="rounded-full border border-line bg-white px-3 py-1 text-xs font-medium text-cocoa transition hover:bg-sand"
              title={template.build(attendant || "Atendente")}
            >
              {template.label}
            </button>
          ))}
        </div>
      ) : null}
      <div className="flex items-end gap-3">
        <textarea
          value={value}
          onChange={(event) => setValue(event.target.value)}
          onKeyDown={onKeyDown}
          placeholder="Escreva uma resposta... (⌘/Ctrl+Enter para enviar)"
          rows={2}
          className="min-h-[56px] flex-1 resize-none rounded-2xl border border-line bg-white px-4 py-3 text-sm text-ink outline-none transition focus:border-clay"
        />
        <button
          type="button"
          onClick={send}
          disabled={disabled}
          className="rounded-full bg-ink px-5 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-50"
        >
          {busy ? "Enviando..." : "Enviar"}
        </button>
      </div>
    </div>
  );
}

function ConversationThread({
  card,
  attendants,
  onRefresh,
}: {
  card: WhatsAppCard | null;
  attendants: string[];
  onRefresh: () => Promise<void> | void;
}) {
  if (!card) {
    return (
      <div className="flex flex-1 items-center justify-center p-6 text-sm text-cocoa/60">
        Selecione uma conversa.
      </div>
    );
  }

  return (
    <>
      <header className="flex items-start justify-between gap-4 border-b border-line bg-paper/70 px-6 py-4">
        <div>
          <div className="flex items-center gap-2">
            <p className="text-lg font-semibold text-ink">{card.cliente_nome}</p>
            {card.is_human_handoff ? <HandoffBadge /> : null}
          </div>
          <p className="mt-1 font-mono text-sm text-cocoa/70">{card.phone}</p>
        </div>
        <AutomationToggle card={card} onChanged={onRefresh} />
      </header>
      <div className="flex-1 overflow-y-auto">
        <div className="flex min-h-full flex-col justify-end gap-3 px-6 py-5">
          {card.messages.length === 0 ? (
            <p className="py-10 text-center text-sm text-cocoa/60">
              Sem histórico disponível para esta conversa.
            </p>
          ) : (
            card.messages.map((message, index) => (
              <MessageBubble key={`${card.phone}-${index}`} message={message} />
            ))
          )}
        </div>
      </div>
      <MessageComposer phone={card.phone} onSent={onRefresh} attendants={attendants} />
    </>
  );
}

const STATUS_STEPS: { slug: string; value: string; label: string }[] = [
  { slug: "pendente", value: "pendente", label: "Pendente" },
  { slug: "em_preparo", value: "em preparo", label: "Em preparo" },
  { slug: "entregue", value: "entregue", label: "Entregue" },
];

function normalizeStatus(status?: string | null): string {
  return (status || "pendente").toLowerCase().replace(/\s+/g, "_");
}

function formatBRL(value?: number | null): string | null {
  if (value === null || value === undefined) return null;
  return value.toLocaleString("pt-BR", { style: "currency", currency: "BRL" });
}

function formatServiceDate(value?: string | null): string | null {
  if (!value) return null;
  const match = value.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (match) return `${match[3]}/${match[2]}/${match[1]}`;
  return value;
}

function composeItemLines(order: OrderDetails): string[] {
  const lines: string[] = [];
  const head = [order.produto, order.tamanho].filter(Boolean).join(" · ");
  if (head) lines.push(head);
  else if (order.categoria) lines.push(order.categoria);

  const extras: Array<[string, string | null | undefined]> = [
    ["Massa", order.massa],
    ["Recheio", order.recheio],
    ["Mousse", order.mousse],
    ["Adicional", order.adicional],
    ["Fruta/Nozes", order.fruta_ou_nozes],
  ];
  for (const [label, value] of extras) {
    if (value) lines.push(`${label}: ${value}`);
  }
  if (order.quantidade && order.quantidade > 1) {
    lines.push(`Quantidade: ${order.quantidade}`);
  }
  if (order.serve_pessoas && order.serve_pessoas > 0) {
    lines.push(`Serve: ${order.serve_pessoas} pessoas`);
  }
  return lines;
}

function composeDeliveryLine(order: OrderDetails): string | null {
  const date = formatServiceDate(order.data_entrega);
  const time = order.horario_retirada || order.horario;
  const mode = order.horario_retirada ? "Retirada" : order.horario ? "Entrega" : null;
  const parts = [mode, date, time].filter(Boolean);
  return parts.length > 0 ? parts.join(" · ") : null;
}

function OrderContextPanel({
  orderId,
  customerPhone,
  refreshTick,
}: {
  orderId: number;
  customerPhone: string;
  refreshTick: number;
}) {
  const [order, setOrder] = useState<OrderDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [updatingStatus, setUpdatingStatus] = useState<string | null>(null);

  const loadOrder = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const response = await fetch(`/api/orders/${orderId}`, { cache: "no-store" });
      const payload = (await response.json().catch(() => null)) as { item?: OrderDetails | null } | null;
      if (!response.ok || !payload?.item) {
        setOrder(null);
        setError("Não foi possível carregar o pedido.");
        return;
      }
      setOrder(payload.item);
    } catch {
      setOrder(null);
      setError("Erro de rede ao carregar pedido.");
    } finally {
      setLoading(false);
    }
  }, [orderId]);

  useEffect(() => {
    void loadOrder();
  }, [loadOrder, refreshTick]);

  async function updateStatus(value: string) {
    if (updatingStatus) return;
    setUpdatingStatus(value);
    try {
      const response = await fetch(`/api/orders/${orderId}/status`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: value }),
      });
      if (!response.ok) {
        setError("Falha ao atualizar status.");
        return;
      }
      await loadOrder();
    } catch {
      setError("Erro de rede ao atualizar status.");
    } finally {
      setUpdatingStatus(null);
    }
  }

  if (loading && !order) {
    return (
      <aside className="flex min-h-0 flex-col border-l border-line bg-paper/50 p-5">
        <p className="text-xs text-cocoa/60">Carregando pedido...</p>
      </aside>
    );
  }

  if (!order) {
    return (
      <aside className="flex min-h-0 flex-col border-l border-line bg-paper/50 p-5">
        <p className="text-xs text-[#b44a1f]">{error || "Pedido não encontrado."}</p>
      </aside>
    );
  }

  const currentSlug = normalizeStatus(order.status);
  const itemLines = composeItemLines(order);
  const deliveryLine = composeDeliveryLine(order);
  const priceLabel = formatBRL(order.valor_total ?? null);
  const createdLabel = order.criado_em ? order.criado_em.slice(0, 16).replace("T", " ") : null;

  return (
    <aside className="flex min-h-0 flex-col gap-4 overflow-y-auto border-l border-line bg-paper/50 px-5 py-5">
      <header>
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cocoa/65">Pedido</p>
        <p className="text-xl font-bold text-ink">#{order.id}</p>
        {order.cliente_nome ? (
          <p className="mt-1 text-sm text-cocoa/80">{order.cliente_nome}</p>
        ) : null}
        {order.categoria ? (
          <p className="text-xs uppercase tracking-wide text-cocoa/55">{order.categoria}</p>
        ) : null}
      </header>

      {itemLines.length > 0 ? (
        <section className="rounded-card border border-line bg-white p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-cocoa/55">Item</p>
          <div className="mt-2 space-y-1 text-sm text-ink">
            {itemLines.map((line, index) => (
              <p key={index} className={index === 0 ? "font-semibold" : "text-cocoa/80"}>
                {line}
              </p>
            ))}
          </div>
        </section>
      ) : null}

      {deliveryLine ? (
        <section className="rounded-card border border-line bg-white p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-cocoa/55">Entrega</p>
          <p className="mt-2 text-sm text-ink">{deliveryLine}</p>
        </section>
      ) : null}

      {priceLabel ? (
        <section className="rounded-card border border-line bg-white p-4">
          <p className="text-xs font-semibold uppercase tracking-[0.12em] text-cocoa/55">Valor</p>
          <p className="mt-2 text-lg font-bold text-ink">{priceLabel}</p>
        </section>
      ) : null}

      <section className="rounded-card border border-line bg-white p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-cocoa/55">Status</p>
        <div className="mt-3 flex flex-col gap-2">
          {STATUS_STEPS.map((step) => {
            const isActive = step.slug === currentSlug;
            const isBusy = updatingStatus === step.value;
            const stateClass = isActive
              ? "border-ink bg-ink text-white"
              : "border-line bg-white text-cocoa hover:bg-sand";
            return (
              <button
                key={step.slug}
                type="button"
                onClick={() => updateStatus(step.value)}
                disabled={isActive || Boolean(updatingStatus)}
                className={`rounded-full border px-4 py-2 text-sm font-semibold transition disabled:opacity-70 ${stateClass}`}
              >
                {isBusy ? "Atualizando..." : step.label}
              </button>
            );
          })}
        </div>
        {error ? <p className="mt-2 text-xs text-[#b44a1f]">{error}</p> : null}
      </section>

      <CustomerOrderHistory
        phone={customerPhone}
        currentOrderId={order.id}
        refreshTick={refreshTick}
      />

      {createdLabel ? (
        <p className="text-[11px] text-cocoa/55">Criado em {createdLabel}</p>
      ) : null}
    </aside>
  );
}

function TodaySummaryStrip({ summary }: { summary?: TodaySummary }) {
  if (!summary || summary.orders_count === 0) return null;

  const parts: Array<{ label: string; value: string }> = [
    { label: "pedidos", value: String(summary.orders_count) },
  ];
  if (summary.deliveries_count > 0) {
    parts.push({ label: "entregas", value: String(summary.deliveries_count) });
  }
  if (summary.pickups_count > 0) {
    parts.push({ label: "retiradas", value: String(summary.pickups_count) });
  }
  if (summary.revenue > 0) {
    parts.push({ label: "faturamento", value: summary.revenue_label });
  }
  if (summary.next_time_label) {
    const tipo = summary.next_tipo_label ? ` (${summary.next_tipo_label.toLowerCase()})` : "";
    parts.push({ label: "próxima", value: `${summary.next_time_label}${tipo}` });
  }

  return (
    <div className="flex flex-wrap items-center gap-x-5 gap-y-1 border-b border-line bg-white px-6 py-2 text-xs text-cocoa/80">
      <span className="font-semibold uppercase tracking-[0.16em] text-cocoa/55">Hoje</span>
      {parts.map((part) => (
        <span key={part.label} className="flex items-baseline gap-1.5">
          <span className="font-bold text-ink">{part.value}</span>
          <span className="text-cocoa/60">{part.label}</span>
        </span>
      ))}
    </div>
  );
}

type ConversationFilter = "all" | "handoff" | "with_order" | "awaiting";

function ConversationFilterBar({
  value,
  onChange,
  counts,
}: {
  value: ConversationFilter;
  onChange: (next: ConversationFilter) => void;
  counts: Record<ConversationFilter, number>;
}) {
  const filters: { key: ConversationFilter; label: string }[] = [
    { key: "all", label: "Todas" },
    { key: "awaiting", label: "Aguardando" },
    { key: "handoff", label: "Humano" },
    { key: "with_order", label: "Com pedido" },
  ];

  return (
    <div className="flex flex-wrap gap-1.5">
      {filters.map((f) => {
        const active = f.key === value;
        const count = counts[f.key];
        const toneClass = active
          ? "border-ink bg-ink text-white"
          : "border-line bg-white text-cocoa hover:bg-sand";
        return (
          <button
            key={f.key}
            type="button"
            onClick={() => onChange(f.key)}
            className={`inline-flex items-center gap-1.5 rounded-full border px-3 py-1 text-xs font-semibold transition ${toneClass}`}
          >
            {f.label}
            <span className={active ? "opacity-75" : "opacity-60"}>{count}</span>
          </button>
        );
      })}
    </div>
  );
}

function formatHistoryDate(raw?: string | null): string {
  if (!raw) return "—";
  const match = raw.match(/^(\d{4})-(\d{2})-(\d{2})$/);
  if (match) return `${match[3]}/${match[2]}`;
  const dmy = raw.match(/^(\d{2})\/(\d{2})\/\d{4}$/);
  if (dmy) return `${dmy[1]}/${dmy[2]}`;
  return raw.slice(0, 10);
}

function CustomerOrderHistory({
  phone,
  currentOrderId,
  refreshTick,
}: {
  phone: string;
  currentOrderId: number | null;
  refreshTick: number;
}) {
  const [items, setItems] = useState<CustomerOrderHistoryItem[]>([]);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    let active = true;
    setLoading(true);
    fetch(`/api/customers/${encodeURIComponent(phone)}/orders`, { cache: "no-store" })
      .then((res) => res.json().catch(() => ({ items: [] })))
      .then((payload: { items?: CustomerOrderHistoryItem[] }) => {
        if (!active) return;
        setItems(payload.items || []);
      })
      .catch(() => {
        if (!active) return;
        setItems([]);
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    return () => {
      active = false;
    };
  }, [phone, refreshTick]);

  const past = items.filter((item) => item.id !== currentOrderId);

  if (loading) {
    return (
      <section className="rounded-card border border-line bg-white p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-cocoa/55">Histórico</p>
        <p className="mt-2 text-xs text-cocoa/60">Carregando...</p>
      </section>
    );
  }

  if (past.length === 0) {
    return (
      <section className="rounded-card border border-line bg-white p-4">
        <p className="text-xs font-semibold uppercase tracking-[0.12em] text-cocoa/55">Histórico</p>
        <p className="mt-2 text-xs text-cocoa/60">Sem pedidos anteriores.</p>
      </section>
    );
  }

  return (
    <section className="rounded-card border border-line bg-white p-4">
      <p className="text-xs font-semibold uppercase tracking-[0.12em] text-cocoa/55">
        Histórico · {past.length}
      </p>
      <ul className="mt-2 space-y-1.5">
        {past.slice(0, 5).map((item) => {
          const head = [item.produto, item.tamanho].filter(Boolean).join(" ") || item.categoria || "Pedido";
          const price = formatBRL(item.valor_total ?? null);
          const statusLabel = (item.status || "pendente").toLowerCase();
          const statusTone =
            statusLabel === "entregue"
              ? "text-[#1e6b3a]"
              : statusLabel === "em preparo"
                ? "text-[#7a4e00]"
                : "text-cocoa/70";
          return (
            <li key={item.id} className="text-xs text-cocoa/85">
              <span className="text-cocoa/55">{formatHistoryDate(item.data_entrega)}</span>{" "}
              <span className="font-semibold text-ink">{head}</span>
              {price ? <span className="text-cocoa/70"> · {price}</span> : null}{" "}
              <span className={`font-medium ${statusTone}`}>· {statusLabel}</span>
            </li>
          );
        })}
      </ul>
    </section>
  );
}

export function Inbox({ snapshot, warning }: InboxProps) {
  const live = useLivePanelSnapshot(snapshot, warning);

  const conversations = live.snapshot.conversations;
  const ordered = [...conversations].sort((a, b) => {
    const aFlag = a.is_human_handoff ? 0 : 1;
    const bFlag = b.is_human_handoff ? 0 : 1;
    return aFlag - bFlag;
  });

  const [search, setSearch] = useState("");
  const deferredSearch = useDeferredValue(search);
  const [selectedPhone, setSelectedPhone] = useState(ordered[0]?.phone || "");
  const [filter, setFilter] = useState<ConversationFilter>("all");

  const counts: Record<ConversationFilter, number> = {
    all: ordered.length,
    awaiting: ordered.filter(isAwaitingReply).length,
    handoff: ordered.filter((c) => c.is_human_handoff).length,
    with_order: ordered.filter((c) => c.order_id).length,
  };

  const term = deferredSearch.trim();
  const afterSearch = term
    ? ordered.filter((card) => matchesConversation(card, term))
    : ordered;
  const visible = afterSearch.filter((card) => {
    if (filter === "handoff") return card.is_human_handoff;
    if (filter === "with_order") return Boolean(card.order_id);
    if (filter === "awaiting") return isAwaitingReply(card);
    return true;
  });

  useEffect(() => {
    if (visible.length === 0) {
      if (selectedPhone !== "") {
        setSelectedPhone("");
      }
      return;
    }
    if (!visible.some((card) => card.phone === selectedPhone)) {
      setSelectedPhone(visible[0].phone);
    }
  }, [visible, selectedPhone]);

  const selected = visible.find((card) => card.phone === selectedPhone) || null;
  const handoffCount = ordered.filter((card) => card.is_human_handoff).length;
  const selectedOrderId = selected?.order_id ?? null;
  const [orderRefreshTick, setOrderRefreshTick] = useState(0);
  const gridClass = selectedOrderId
    ? "grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[320px_minmax(0,1fr)_340px]"
    : "grid min-h-0 flex-1 grid-cols-1 lg:grid-cols-[360px_minmax(0,1fr)]";

  const refreshAll = useCallback(async () => {
    await live.refreshSnapshot();
    setOrderRefreshTick((tick) => tick + 1);
  }, [live]);

  return (
    <div className="flex h-screen flex-col overflow-hidden">
      <header className="flex flex-wrap items-center justify-between gap-4 border-b border-line bg-paper/95 px-6 py-4">
        <div className="flex items-center gap-5">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-cocoa/65">
              Chokodelícia
            </p>
            <h1 className="text-lg font-bold text-ink">Atendimento</h1>
          </div>
          <StorePulseStrip pulse={live.snapshot.store_pulse} />
        </div>
        <div className="flex items-center gap-3">
          {handoffCount > 0 ? (
            <span className="inline-flex items-center gap-1 rounded-full border border-[#e89b7e] bg-[#fff1ea] px-3 py-1 text-xs font-semibold text-[#b44a1f]">
              {handoffCount} aguardando humano
            </span>
          ) : null}
          <form action="/api/auth/logout" method="post">
            <button
              type="submit"
              aria-label="Sair do painel"
              className="rounded-full border border-line bg-white px-4 py-2 text-sm font-semibold text-cocoa transition hover:bg-sand"
            >
              Sair
            </button>
          </form>
        </div>
      </header>

      <TodaySummaryStrip summary={live.snapshot.today_summary} />

      {live.warning ? (
        <div className="border-b border-[#efc2a8] bg-[#fff6f1] px-6 py-3 text-sm text-cocoa">
          {live.warning}
        </div>
      ) : null}

      <div className={gridClass}>
        <aside className="flex min-h-0 flex-col border-r border-line bg-paper/60">
          <div className="space-y-3 border-b border-line p-4">
            <label className="block">
              <span className="sr-only">Buscar conversa</span>
              <input
                value={search}
                onChange={(event) => setSearch(event.target.value)}
                placeholder="Buscar por nome, telefone ou mensagem"
                className="h-11 w-full rounded-full border border-line bg-white px-4 text-sm text-ink outline-none transition focus:border-clay"
                type="search"
              />
            </label>
            <ConversationFilterBar value={filter} onChange={setFilter} counts={counts} />
          </div>
          <div className="flex-1 overflow-y-auto p-3">
            <ConversationList
              cards={visible}
              selectedPhone={selectedPhone}
              onSelect={setSelectedPhone}
            />
          </div>
        </aside>

        <section className="flex min-h-0 flex-col bg-white">
          <ConversationThread
            card={selected}
            attendants={live.snapshot.attendants || []}
            onRefresh={refreshAll}
          />
        </section>

        {selectedOrderId && selected ? (
          <OrderContextPanel
            key={selectedOrderId}
            orderId={selectedOrderId}
            customerPhone={selected.phone}
            refreshTick={orderRefreshTick}
          />
        ) : null}
      </div>
    </div>
  );
}

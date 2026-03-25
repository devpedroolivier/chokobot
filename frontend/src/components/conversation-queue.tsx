"use client";

import { FormEvent, useState, useTransition } from "react";

import { useRouter } from "next/navigation";

import type { WhatsAppCard } from "@/lib/panel-types";
import { EmptyState, conversationHref, customerHref, orderHref, riskFlagLabel, stageClasses } from "@/components/admin-workspace";

function messageTone(role: string): string {
  if (role === "ia") {
    return "ml-6 bg-sky/70 text-[#153b7a]";
  }
  if (role === "humano") {
    return "ml-4 bg-[#efe7ff] text-[#4b2f79]";
  }
  if (role === "bot") {
    return "ml-4 bg-[#e3f0ea] text-[#1d5f42]";
  }
  if (role === "contexto") {
    return "bg-mist text-cocoa";
  }
  return "mr-6 bg-[#f8ece4] text-ink";
}

function automationBadge(card: WhatsAppCard): string {
  return card.automation_mode === "manual" ? "stage-human" : "stage-delivery";
}

function AutomationToggleButton({
  card,
  notifyCustomer = false,
  compact = false,
}: {
  card: WhatsAppCard;
  notifyCustomer?: boolean;
  compact?: boolean;
}) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const enabled = card.automation_mode === "manual";

  async function handleClick() {
    const response = await fetch(`/api/conversations/${encodeURIComponent(card.phone)}/automation`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ enabled, notify_customer: notifyCustomer }),
    });
    if (!response.ok) {
      return;
    }
    startTransition(() => {
      router.refresh();
    });
  }

  return (
    <button
      type="button"
      onClick={handleClick}
      disabled={isPending}
      className={`rounded-full border border-line bg-paper font-semibold text-ink transition hover:bg-sand disabled:cursor-not-allowed disabled:opacity-60 ${
        compact ? "px-3 py-1 text-xs" : "px-4 py-2 text-sm"
      }`}
    >
      {isPending ? "Atualizando..." : enabled ? "Reativar IA" : "Assumir manual"}
    </button>
  );
}

export function ConversationList({
  cards,
  selectedPhone,
  onSelect,
}: {
  cards: WhatsAppCard[];
  selectedPhone: string;
  onSelect: (phone: string) => void;
}) {
  if (cards.length === 0) {
    return <EmptyState message="Nenhuma conversa ativa com os filtros atuais." />;
  }

  return (
    <div className="space-y-3">
      {cards.map((card) => {
        const selected = selectedPhone === card.phone;
        return (
          <button
            key={`${card.phone}-${card.agent}`}
            type="button"
            onClick={() => onSelect(card.phone)}
            className={`w-full rounded-[24px] border p-4 text-left shadow-panel transition ${
              selected ? "border-clay bg-white ring-2 ring-[#d88d6f]/35" : "border-line bg-paper/80 hover:bg-white"
            }`}
          >
            <div className="flex items-start justify-between gap-3">
              <div>
                <p className="font-semibold">{card.cliente_nome}</p>
                <p className="mt-1 text-xs uppercase tracking-[0.16em] text-cocoa/55">{card.agent}</p>
              </div>
              <div className="flex flex-col items-end gap-2">
                {card.business_state_label ? (
                  <span className={`rounded-full px-3 py-1 text-xs font-semibold ${stageClasses(card.business_state_class || "stage-cafe")}`}>
                    {card.business_state_label}
                  </span>
                ) : null}
                <span className={`rounded-full px-3 py-1 text-xs font-semibold ${stageClasses(card.stage_class)}`}>
                  {card.stage_label}
                </span>
                <span className={`rounded-full px-3 py-1 text-xs font-semibold ${stageClasses(automationBadge(card))}`}>
                  {card.automation_label || (card.automation_mode === "manual" ? "Manual" : "IA ativa")}
                </span>
              </div>
            </div>
            <p className="mt-3 text-sm text-ink">{card.last_message}</p>
            {card.next_step_hint ? <p className="mt-2 text-xs text-cocoa/70">Próximo passo: {card.next_step_hint}</p> : null}
            <div className="mt-3 flex items-center justify-between text-xs text-cocoa/65">
              <span className="font-mono">{card.phone}</span>
              <span>{card.last_seen_label}</span>
            </div>
          </button>
        );
      })}
    </div>
  );
}

export function ConversationQueue({
  cards,
  emptyMessage,
}: {
  cards: WhatsAppCard[];
  emptyMessage: string;
}) {
  if (cards.length === 0) {
    return <EmptyState message={emptyMessage} />;
  }

  return (
    <div className="space-y-3">
      {cards.map((card) => (
        <article key={`${card.phone}-${card.agent}`} className="rounded-[24px] border border-line bg-white/86 p-4 shadow-panel">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="font-semibold">{card.cliente_nome}</p>
              <p className="mt-1 text-xs uppercase tracking-[0.16em] text-cocoa/55">{card.agent}</p>
            </div>
            <div className="flex flex-col items-end gap-2">
              {card.business_state_label ? (
                <span className={`rounded-full px-3 py-1 text-xs font-semibold ${stageClasses(card.business_state_class || "stage-cafe")}`}>
                  {card.business_state_label}
                </span>
              ) : null}
              <span className={`rounded-full px-3 py-1 text-xs font-semibold ${stageClasses(card.stage_class)}`}>
                {card.stage_label}
              </span>
              <span className={`rounded-full px-3 py-1 text-xs font-semibold ${stageClasses(automationBadge(card))}`}>
                {card.automation_label || (card.automation_mode === "manual" ? "Manual" : "IA ativa")}
              </span>
            </div>
          </div>
          <p className="mt-3 text-sm text-ink">{card.last_message}</p>
          {card.next_step_hint ? <p className="mt-2 text-xs text-cocoa/70">Próximo passo: {card.next_step_hint}</p> : null}
          {(card.risk_flags || []).length > 0 ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {(card.risk_flags || []).slice(0, 2).map((flag) => (
                <span key={flag} className="rounded-full bg-[#fff1e4] px-3 py-1 text-xs font-semibold text-[#9a4d12]">
                  {riskFlagLabel(flag)}
                </span>
              ))}
            </div>
          ) : null}
          <div className="mt-4 flex items-center justify-between gap-3 text-xs text-cocoa/65">
            <span className="font-mono">{card.phone}</span>
            <div className="flex flex-wrap gap-2">
              <AutomationToggleButton card={card} compact />
              <a
                href={conversationHref(card.phone)}
                className="rounded-full border border-line bg-paper px-3 py-1 text-xs font-semibold text-ink transition hover:bg-sand"
              >
                Abrir thread
              </a>
              <a
                href={customerHref(card.phone)}
                className="rounded-full border border-line bg-white px-3 py-1 text-xs font-semibold text-cocoa transition hover:bg-paper"
              >
                Ver cliente
              </a>
            </div>
          </div>
        </article>
      ))}
    </div>
  );
}

export function ConversationThread({ card }: { card: WhatsAppCard | null }) {
  const router = useRouter();
  const [draft, setDraft] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const [busyAction, setBusyAction] = useState<"reply" | "automation" | null>(null);
  const [isPending, startTransition] = useTransition();

  if (!card) {
    return <EmptyState message="Selecione uma conversa para acompanhar cliente e IA." />;
  }

  const activeCard = card;

  async function handleAutomation(enabled: boolean) {
    setFeedback(null);
    setBusyAction("automation");
    try {
      const response = await fetch(`/api/conversations/${encodeURIComponent(activeCard.phone)}/automation`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ enabled, notify_customer: true }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        setFeedback(payload.detail ? `Falha: ${payload.detail}` : "Falha ao atualizar a automação.");
        return;
      }
      setFeedback(enabled ? "IA reativada para esta conversa." : "Atendimento manual assumido no painel.");
      startTransition(() => {
        router.refresh();
      });
    } finally {
      setBusyAction(null);
    }
  }

  async function handleReply(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const message = draft.trim();
    if (!message) {
      return;
    }

    setFeedback(null);
    setBusyAction("reply");
    try {
      const response = await fetch(`/api/conversations/${encodeURIComponent(activeCard.phone)}/reply`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, disable_ai: true, notify_handoff: false }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        setFeedback(payload.detail ? `Falha: ${payload.detail}` : "Falha ao enviar mensagem.");
        return;
      }

      setDraft("");
      setFeedback("Mensagem enviada pelo painel. A conversa segue em modo manual.");
      startTransition(() => {
        router.refresh();
      });
    } finally {
      setBusyAction(null);
    }
  }

  return (
    <section className="rounded-[28px] border border-line bg-white/88 p-5 shadow-panel">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line pb-4">
        <div>
          <p className="text-lg font-bold">{card.cliente_nome}</p>
          <p className="mt-1 text-sm text-cocoa/70">
            {card.agent} • {card.last_seen_label}
          </p>
          <p className="mt-2 font-mono text-xs text-cocoa/60">{card.phone}</p>
        </div>
        <div className="flex flex-wrap gap-2">
          {card.business_state_label ? (
            <span className={`rounded-full px-3 py-1 text-xs font-semibold ${stageClasses(card.business_state_class || "stage-cafe")}`}>
              {card.business_state_label}
            </span>
          ) : null}
          <span className={`rounded-full px-3 py-1 text-xs font-semibold ${stageClasses(card.stage_class)}`}>
            {card.stage_label}
          </span>
          <span className={`rounded-full px-3 py-1 text-xs font-semibold ${stageClasses(card.owner_class)}`}>
            {card.owner_label}
          </span>
          <span className={`rounded-full px-3 py-1 text-xs font-semibold ${stageClasses(automationBadge(card))}`}>
            {card.automation_label || (card.automation_mode === "manual" ? "Manual" : "IA ativa")}
          </span>
        </div>
      </div>

      {card.context_summary || card.next_step_hint || (card.risk_flags || []).length > 0 ? (
        <div className="mt-4 rounded-[22px] border border-line bg-[#fffaf6] px-4 py-4 text-sm text-cocoa">
          <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-cocoa/60">Leitura operacional</p>
          {card.context_summary ? <p className="mt-2 text-ink">{card.context_summary}</p> : null}
          {card.next_step_hint ? <p className="mt-2">Próximo passo: {card.next_step_hint}</p> : null}
          {(card.risk_flags || []).length > 0 ? (
            <div className="mt-3 flex flex-wrap gap-2">
              {(card.risk_flags || []).map((flag) => (
                <span key={flag} className="rounded-full bg-[#fff1e4] px-3 py-1 text-xs font-semibold text-[#9a4d12]">
                  {riskFlagLabel(flag)}
                </span>
              ))}
            </div>
          ) : null}
        </div>
      ) : null}

      <div className="mt-4 rounded-[22px] border border-line bg-paper/90 px-4 py-3 text-sm text-cocoa">
        {card.automation_hint ||
          "Use o painel para assumir manualmente quando precisar. Depois a IA pode voltar automaticamente."}
      </div>

      <div className="mt-4 max-h-[560px] space-y-3 overflow-y-auto pr-2">
        {card.messages.length === 0 ? (
          <EmptyState message="Sem trilha disponível para esta conversa." />
        ) : (
          card.messages.map((message, index) => (
            <article
              key={`${card.phone}-${message.role}-${index}`}
              className={`rounded-[22px] px-4 py-3 ${messageTone(message.role)}`}
            >
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] opacity-75">{message.actor_label}</p>
                {message.timestamp_label ? <span className="text-xs opacity-70">{message.timestamp_label}</span> : null}
              </div>
              <p className="mt-2 whitespace-pre-wrap text-sm leading-6">{message.content}</p>
            </article>
          ))
        )}
      </div>

      <div className="mt-5 flex flex-wrap gap-3">
        <button
          type="button"
          onClick={() => handleAutomation(card.automation_mode === "manual")}
          disabled={busyAction !== null || isPending}
          className="rounded-full border border-line bg-paper px-4 py-2 text-sm font-semibold text-ink transition hover:bg-sand disabled:cursor-not-allowed disabled:opacity-60"
        >
          {busyAction === "automation" ? "Atualizando..." : card.automation_mode === "manual" ? "Reativar IA" : "Assumir manual"}
        </button>
        <a
          href={customerHref(card.phone)}
          className="rounded-full border border-line bg-paper px-4 py-2 text-sm font-semibold text-ink transition hover:bg-sand"
        >
          Ver cliente
        </a>
        <a
          href={conversationHref(card.phone)}
          className="rounded-full border border-line bg-paper px-4 py-2 text-sm font-semibold text-ink transition hover:bg-sand"
        >
          Abrir conversa
        </a>
        <a
          href={orderHref(card.order_id)}
          className="rounded-full border border-line bg-paper px-4 py-2 text-sm font-semibold text-ink transition hover:bg-sand"
        >
          {card.order_id ? "Abrir pedido" : "Ver encomendas"}
        </a>
      </div>

      <form onSubmit={handleReply} className="mt-5 border-t border-line pt-5">
        <label className="flex flex-col gap-2 text-sm font-medium text-cocoa">
          Responder pelo painel
          <textarea
            value={draft}
            onChange={(event) => setDraft(event.target.value)}
            rows={4}
            placeholder="Escreva a resposta manual para o cliente"
            className="min-h-[116px] rounded-[22px] border border-line bg-paper px-4 py-3 text-sm text-ink outline-none transition focus:border-clay focus:ring-2 focus:ring-[#d88d6f]/30"
          />
        </label>
        <div className="mt-3 flex flex-wrap items-center justify-between gap-3">
          <p className="text-xs text-cocoa/65">
            Ao responder por aqui, o painel assume o atendimento manual e evita disputa com a IA.
          </p>
          <button
            type="submit"
            disabled={busyAction !== null || isPending || draft.trim().length === 0}
            className="rounded-full bg-ink px-4 py-2 text-sm font-semibold text-white transition hover:bg-[#2f3136] disabled:cursor-not-allowed disabled:opacity-60"
          >
            {busyAction === "reply" ? "Enviando..." : "Enviar mensagem"}
          </button>
        </div>
        {feedback ? <p className="mt-3 text-sm font-medium text-cocoa">{feedback}</p> : null}
      </form>
    </section>
  );
}

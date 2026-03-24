import type { WhatsAppCard } from "@/lib/panel-types";
import { EmptyState, customerHref, orderHref, stageClasses } from "@/components/admin-workspace";

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
                <span className={`rounded-full px-3 py-1 text-xs font-semibold ${stageClasses(card.stage_class)}`}>
                  {card.stage_label}
                </span>
                <span className={`rounded-full px-3 py-1 text-xs font-semibold ${stageClasses(card.owner_class)}`}>
                  {card.owner_label}
                </span>
              </div>
            </div>
            <p className="mt-3 text-sm text-ink">{card.last_message}</p>
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
              <span className={`rounded-full px-3 py-1 text-xs font-semibold ${stageClasses(card.stage_class)}`}>
                {card.stage_label}
              </span>
              <span className={`rounded-full px-3 py-1 text-xs font-semibold ${stageClasses(card.owner_class)}`}>
                {card.owner_label}
              </span>
            </div>
          </div>
          <p className="mt-3 text-sm text-ink">{card.last_message}</p>
          <div className="mt-4 flex items-center justify-between gap-3 text-xs text-cocoa/65">
            <span className="font-mono">{card.phone}</span>
            <a
              href={customerHref(card.phone)}
              className="rounded-full border border-line bg-paper px-3 py-1 text-xs font-semibold text-ink transition hover:bg-sand"
            >
              Ver cliente
            </a>
          </div>
        </article>
      ))}
    </div>
  );
}

export function ConversationThread({ card }: { card: WhatsAppCard | null }) {
  if (!card) {
    return <EmptyState message="Selecione uma conversa para acompanhar cliente e IA." />;
  }

  return (
    <section className="rounded-[28px] border border-line bg-white/88 p-5 shadow-panel">
      <div className="flex flex-wrap items-start justify-between gap-3 border-b border-line pb-4">
        <div>
          <p className="text-lg font-bold">{card.cliente_nome}</p>
          <p className="mt-1 text-sm text-cocoa/70">
            {card.agent} • {card.last_seen_label}
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <span className={`rounded-full px-3 py-1 text-xs font-semibold ${stageClasses(card.stage_class)}`}>
            {card.stage_label}
          </span>
          <span className={`rounded-full px-3 py-1 text-xs font-semibold ${stageClasses(card.owner_class)}`}>
            {card.owner_label}
          </span>
        </div>
      </div>

      <div className="mt-4 space-y-3">
        {card.messages.length === 0 ? (
          <EmptyState message="Sem trilha disponível para esta conversa." />
        ) : (
          card.messages.map((message, index) => (
            <article
              key={`${card.phone}-${message.role}-${index}`}
              className={`rounded-[22px] px-4 py-3 ${
                message.role === "ia"
                  ? "ml-6 bg-sky/70 text-[#153b7a]"
                  : message.role === "contexto"
                    ? "bg-mist text-cocoa"
                    : "mr-6 bg-[#f8ece4] text-ink"
              }`}
            >
              <div className="flex items-center justify-between gap-3">
                <p className="text-xs font-semibold uppercase tracking-[0.16em] opacity-75">{message.actor_label}</p>
                {message.timestamp_label ? <span className="text-xs opacity-70">{message.timestamp_label}</span> : null}
              </div>
              <p className="mt-2 text-sm leading-6">{message.content}</p>
            </article>
          ))
        )}
      </div>

      <div className="mt-4 flex flex-wrap gap-3">
        <a
          href={customerHref(card.phone)}
          className="rounded-full border border-line bg-paper px-4 py-2 text-sm font-semibold text-ink transition hover:bg-sand"
        >
          Ver cliente
        </a>
        <a
          href={orderHref(card.order_id)}
          className="rounded-full border border-line bg-paper px-4 py-2 text-sm font-semibold text-ink transition hover:bg-sand"
        >
          {card.order_id ? "Abrir pedido" : "Ver encomendas"}
        </a>
      </div>
    </section>
  );
}

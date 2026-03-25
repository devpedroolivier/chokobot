import type { ProcessCard, ProcessSection } from "@/lib/panel-types";
import { EmptyState, conversationHref, customerHref, orderHref, riskFlagLabel, stageClasses } from "@/components/admin-workspace";

function processHref(card: ProcessCard): string {
  if (card.business_state_slug === "confirmed" && card.order_id) {
    return orderHref(card.order_id);
  }
  return conversationHref(card.phone);
}

function processCta(card: ProcessCard): string {
  if (card.business_state_slug === "confirmed" && card.order_id) {
    return "Abrir pedido";
  }
  if (card.business_state_slug === "handoff") {
    return "Assumir conversa";
  }
  return card.action_label || "Abrir conversa";
}

export function ProcessList({
  cards,
  emptyMessage,
}: {
  cards: ProcessCard[];
  emptyMessage: string;
}) {
  if (cards.length === 0) {
    return <EmptyState message={emptyMessage} />;
  }

  return (
    <div className="space-y-3">
      {cards.map((card) => (
        <article key={`${card.phone}-${card.stage_label}-${card.updated_label}`} className="rounded-[24px] border border-line bg-white/86 p-4 shadow-panel">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="font-semibold">{card.cliente_nome}</p>
              <p className="mt-1 text-xs uppercase tracking-[0.16em] text-cocoa/55">{card.process_label}</p>
            </div>
            <div className="flex flex-wrap justify-end gap-2">
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
            </div>
          </div>
          <p className="mt-3 text-sm text-ink">{card.summary}</p>
          {card.next_step_hint ? (
            <div className="mt-3 rounded-[18px] border border-line bg-paper px-3 py-3 text-sm text-cocoa">
              <p className="text-[11px] font-semibold uppercase tracking-[0.16em] text-cocoa/60">Próximo passo</p>
              <p className="mt-1">{card.next_step_hint}</p>
            </div>
          ) : null}
          <div className="mt-3 flex flex-wrap gap-2">
            {card.missing_items.slice(0, 3).map((item) => (
              <span key={item} className="rounded-full bg-mist px-3 py-1 text-xs font-semibold text-cocoa">
                {item}
              </span>
            ))}
            {(card.risk_flags || []).slice(0, 2).map((flag) => (
              <span key={flag} className="rounded-full bg-[#fff1e4] px-3 py-1 text-xs font-semibold text-[#9a4d12]">
                {riskFlagLabel(flag)}
              </span>
            ))}
          </div>
          <div className="mt-4 flex items-end justify-between gap-3 text-xs text-cocoa/65">
            <div className="flex flex-col gap-1">
              <span className="font-mono">{card.phone}</span>
              <span>{card.updated_label}</span>
              {card.owner_hint ? <span className="text-cocoa/75">{card.owner_hint}</span> : null}
            </div>
            <div className="flex flex-wrap justify-end gap-2">
              <a
                href={processHref(card)}
                className="rounded-full border border-line bg-paper px-3 py-1 text-xs font-semibold text-ink transition hover:bg-sand"
              >
                {processCta(card)}
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

export function ProcessStageList({ sections }: { sections: ProcessSection[] }) {
  if (sections.length === 0) {
    return <EmptyState message="Nenhum processo ativo com os filtros atuais." />;
  }

  return (
    <div className="space-y-4">
      {sections.map((section) => (
        <section key={section.title} className="rounded-[28px] border border-line bg-white/85 p-4 shadow-panel">
          <div className="flex items-center justify-between gap-3 border-b border-line pb-3">
            <div>
              <p className="text-sm font-bold">{section.title}</p>
              <p className="text-sm text-cocoa/68">{section.description}</p>
            </div>
            <span className="rounded-full bg-sand px-3 py-1 text-xs font-semibold text-cocoa">{section.count}</span>
          </div>
          <div className="mt-4">
            <ProcessList cards={section.cards.slice(0, 6)} emptyMessage="Nenhum processo nesta faixa." />
          </div>
        </section>
      ))}
    </div>
  );
}

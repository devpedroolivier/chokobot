import type { ProcessCard, ProcessSection } from "@/lib/panel-types";
import { EmptyState, customerHref, orderHref, stageClasses } from "@/components/admin-workspace";

function processHref(card: ProcessCard): string {
  return card.order_id ? orderHref(card.order_id) : customerHref(card.phone);
}

function processCta(card: ProcessCard): string {
  return card.order_id ? "Abrir pedido" : "Ver cliente";
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
              <span className={`rounded-full px-3 py-1 text-xs font-semibold ${stageClasses(card.stage_class)}`}>
                {card.stage_label}
              </span>
              <span className={`rounded-full px-3 py-1 text-xs font-semibold ${stageClasses(card.owner_class)}`}>
                {card.owner_label}
              </span>
            </div>
          </div>
          <p className="mt-3 text-sm text-ink">{card.summary}</p>
          <div className="mt-3 flex flex-wrap gap-2">
            {card.missing_items.slice(0, 3).map((item) => (
              <span key={item} className="rounded-full bg-mist px-3 py-1 text-xs font-semibold text-cocoa">
                {item}
              </span>
            ))}
          </div>
          <div className="mt-4 flex items-center justify-between gap-3 text-xs text-cocoa/65">
            <div className="flex flex-col gap-1">
              <span className="font-mono">{card.phone}</span>
              <span>{card.updated_label}</span>
            </div>
            <a
              href={processHref(card)}
              className="rounded-full border border-line bg-paper px-3 py-1 text-xs font-semibold text-ink transition hover:bg-sand"
            >
              {processCta(card)}
            </a>
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

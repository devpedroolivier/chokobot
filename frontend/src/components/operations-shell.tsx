"use client";

import { useDeferredValue, useState } from "react";

import {
  AdminWorkspace,
  EmptyState,
  FilterPanel,
  KPI,
  PageHeader,
  SectionTitle,
  WarningBanner,
  orderHref,
} from "@/components/admin-workspace";
import { ConversationQueue } from "@/components/conversation-queue";
import { ProcessList } from "@/components/process-card-list";
import type { KanbanItem, PanelSnapshot, ProcessCard } from "@/lib/panel-types";
import { useLivePanelSnapshot } from "@/lib/use-live-panel-snapshot";

type OperationsShellProps = {
  snapshot: PanelSnapshot;
  warning?: string;
};

function flattenProcessCards(snapshot: PanelSnapshot): ProcessCard[] {
  return snapshot.process_sections.flatMap((section) => section.cards);
}

function sortByDate(items: KanbanItem[]): KanbanItem[] {
  return [...items].sort((left, right) => {
    const leftDate = left.data_iso || "9999-12-31";
    const rightDate = right.data_iso || "9999-12-31";
    if (leftDate !== rightDate) return leftDate.localeCompare(rightDate);
    if (left.horario !== right.horario) return left.horario.localeCompare(right.horario);
    return left.id - right.id;
  });
}

function OrderList({ items, emptyMessage }: { items: KanbanItem[]; emptyMessage: string }) {
  if (items.length === 0) {
    return <EmptyState message={emptyMessage} />;
  }

  return (
    <div className="space-y-3">
      {items.map((item) => (
        <article key={item.id} className="rounded-[24px] border border-line bg-white/86 p-4 shadow-panel">
          <div className="flex items-start justify-between gap-3">
            <div>
              <p className="text-sm font-semibold text-cocoa/65">#{item.id}</p>
              <p className="mt-1 font-semibold">{item.cliente_nome}</p>
            </div>
            <span className="rounded-full bg-mist px-3 py-1 text-xs font-semibold text-cocoa">{item.status_label}</span>
          </div>
          <p className="mt-3 text-sm font-medium">{item.produto}</p>
          <div className="mt-3 grid gap-2 text-xs text-cocoa/70">
            <div className="flex items-center justify-between">
              <span>{item.tipo_label}</span>
              <span>{item.data_label}</span>
            </div>
            <div className="flex items-center justify-between">
              <span>{item.horario}</span>
              <span className="font-semibold text-ink">{item.valor_label}</span>
            </div>
          </div>
          <div className="mt-4 flex justify-end">
            <a
              href={orderHref(item.id)}
              className="rounded-full border border-line bg-paper px-3 py-1 text-xs font-semibold text-ink transition hover:bg-sand"
            >
              Abrir pedido
            </a>
          </div>
        </article>
      ))}
    </div>
  );
}

export function OperationsShell({ snapshot, warning }: OperationsShellProps) {
  const live = useLivePanelSnapshot(snapshot, warning);
  const liveSnapshot = live.snapshot;
  const liveWarning = live.warning;
  const [search, setSearch] = useState("");
  const [mode, setMode] = useState("all");
  const deferredSearch = useDeferredValue(search);

  const processCards = flattenProcessCards(liveSnapshot);
  const cafeteriaCards = processCards.filter((card) => `${card.process_label} ${card.stage_label}`.toLowerCase().includes("cafeteria"));
  const logisticsCards = processCards.filter((card) => card.stage_class.includes("delivery"));
  const humanCards = liveSnapshot.whatsapp_cards.filter((card) => card.is_human_handoff || card.owner_slug === "humano");
  const deliveryOrders = sortByDate(
    liveSnapshot.dashboard.kanban_columns.flatMap((column) => column.items).filter((item) => item.tipo_slug === "entrega"),
  );

  const term = deferredSearch.trim().toLowerCase();
  const matches = (value: string) => !term || value.toLowerCase().includes(term);

  const visibleHumanCards = humanCards.filter((card) =>
    matches(`${card.cliente_nome} ${card.phone} ${card.last_message} ${card.agent} ${card.context_summary || ""} ${card.next_step_hint || ""}`),
  );
  const visibleCafeteriaCards = cafeteriaCards.filter((card) =>
    matches(`${card.cliente_nome} ${card.phone} ${card.summary} ${card.next_step_hint || ""}`) &&
    (mode === "all" || mode === "cafeteria"),
  );
  const visibleLogisticsCards = logisticsCards.filter((card) =>
    matches(`${card.cliente_nome} ${card.phone} ${card.summary} ${card.next_step_hint || ""} ${(card.risk_flags || []).join(" ")}`) &&
    (mode === "all" || mode === "logistics"),
  );
  const visibleDeliveryOrders = deliveryOrders.filter((item) =>
    matches(`${item.cliente_nome} ${item.id} ${item.produto}`) && (mode === "all" || mode === "confirmed"),
  );

  return (
    <AdminWorkspace>
      <PageHeader
        eyebrow="Operações"
        title="Fila humana, pendências e execução"
        description="Uma visão seca do que exige ação agora: handoff, processos em aberto e entregas confirmadas por data."
        referenceDate={liveSnapshot.dashboard.reference_date}
        generatedAt={liveSnapshot.dashboard.generated_at}
        actions={
          <a
            href="/"
            className="rounded-full border border-line bg-white px-4 py-2 text-sm font-semibold text-ink transition hover:bg-sand"
          >
            Voltar ao admin
          </a>
        }
      />

      <WarningBanner warning={liveWarning} />

      <section className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <KPI label="Fila humana" value={String(humanCards.length)} hint={live.isRefreshing ? "Atualizando ao vivo" : "Conversas em ação manual"} />
        <KPI label="Cafeteria" value={String(cafeteriaCards.length)} hint="Pedidos em montagem" />
        <KPI label="Logística" value={String(logisticsCards.length)} hint="Endereço, data ou confirmação" />
        <KPI label="Entregas confirmadas" value={String(deliveryOrders.length)} hint="Pedidos já operacionais" />
      </section>

      <FilterPanel>
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_240px]">
          <label className="flex flex-col gap-2 text-sm font-medium text-cocoa">
            Buscar
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="cliente, telefone, pedido"
              className="h-12 rounded-full border border-line bg-paper px-4 text-sm text-ink outline-none transition focus:border-clay focus:ring-2 focus:ring-[#d88d6f]/30"
            />
          </label>
          <label className="flex flex-col gap-2 text-sm font-medium text-cocoa">
            Foco
            <select
              value={mode}
              onChange={(event) => setMode(event.target.value)}
              className="h-12 rounded-full border border-line bg-paper px-4 text-sm text-ink outline-none transition focus:border-clay focus:ring-2 focus:ring-[#d88d6f]/30"
            >
              <option value="all">Tudo</option>
              <option value="cafeteria">Cafeteria</option>
              <option value="logistics">Logística</option>
              <option value="confirmed">Confirmados</option>
            </select>
          </label>
        </div>
      </FilterPanel>

      <section className="mt-6 grid gap-6 xl:grid-cols-3">
        <div>
          <div className="mb-4">
            <SectionTitle eyebrow="Humano" title="Fila de handoff" />
          </div>
          <ConversationQueue cards={visibleHumanCards} emptyMessage="Nenhum handoff humano ativo." />
        </div>

        <div>
          <div className="mb-4">
            <SectionTitle eyebrow="Pendências" title="Cafeteria e logística" />
          </div>
          <div className="space-y-6">
            <div>
              <p className="mb-3 text-sm font-semibold text-cocoa/72">Cafeteria</p>
              <ProcessList cards={visibleCafeteriaCards} emptyMessage="Nenhum fluxo de cafeteria em aberto." />
            </div>
            <div>
              <p className="mb-3 text-sm font-semibold text-cocoa/72">Logística</p>
              <ProcessList cards={visibleLogisticsCards} emptyMessage="Nenhuma pendência logística em aberto." />
            </div>
          </div>
        </div>

        <div>
          <div className="mb-4">
            <SectionTitle eyebrow="Execução" title="Entregas confirmadas por data" />
          </div>
          <OrderList items={visibleDeliveryOrders} emptyMessage="Nenhum pedido de entrega confirmado." />
        </div>
      </section>
    </AdminWorkspace>
  );
}

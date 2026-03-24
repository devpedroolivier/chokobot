"use client";

import { useDeferredValue, useState, useTransition } from "react";

import {
  AdminWorkspace,
  EmptyState,
  FilterPanel,
  KPI,
  PageHeader,
  SectionTitle,
  WarningBanner,
  orderHref,
  toneClasses,
} from "@/components/admin-workspace";
import { ConversationList, ConversationThread } from "@/components/conversation-queue";
import { ProcessStageList } from "@/components/process-card-list";
import type { KanbanColumn, KanbanItem, PanelSnapshot, ProcessCard, WhatsAppCard } from "@/lib/panel-types";

type DashboardShellProps = {
  snapshot: PanelSnapshot;
  warning?: string;
};

type FilterState = {
  search: string;
  status: string;
  type: string;
  conversation: string;
};

const STATUS_META: Record<string, { label: string; badgeClass: string }> = {
  pendente: { label: "Pendente", badgeClass: "bg-[#fff4cd] text-[#8b5d08]" },
  em_preparo: { label: "Em preparo", badgeClass: "bg-sky text-[#1d4ed8]" },
  agendada: { label: "Agendada", badgeClass: "bg-[#dff0e7] text-[#166534]" },
  retirada: { label: "Retirada", badgeClass: "bg-[#dff0e7] text-[#166534]" },
  entregue: { label: "Entregue", badgeClass: "bg-mist text-cocoa" },
};

function orderStatusClasses(statusSlug?: string): string {
  return STATUS_META[statusSlug || "pendente"]?.badgeClass || "bg-mist text-cocoa";
}

function sortKanbanItems(items: KanbanItem[]): KanbanItem[] {
  return [...items].sort((left, right) => {
    const leftDate = left.data_iso || "9999-12-31";
    const rightDate = right.data_iso || "9999-12-31";
    if (leftDate !== rightDate) return leftDate.localeCompare(rightDate);
    if (left.horario !== right.horario) return left.horario.localeCompare(right.horario);
    return left.id - right.id;
  });
}

function normalizeColumns(columns: KanbanColumn[]): KanbanColumn[] {
  return columns.map((column) => ({
    ...column,
    items: sortKanbanItems(column.items),
  }));
}

function flattenProcessCards(snapshot: PanelSnapshot): ProcessCard[] {
  return snapshot.process_sections.flatMap((section) => section.cards);
}

function isConversationVisible(card: WhatsAppCard, search: string, conversation: string): boolean {
  const term = search.trim().toLowerCase();
  const matchesSearch =
    !term ||
    `${card.cliente_nome} ${card.phone} ${card.last_message} ${card.agent}`.toLowerCase().includes(term);

  if (!matchesSearch) {
    return false;
  }

  if (conversation === "human") {
    return card.is_human_handoff || card.owner_slug === "humano";
  }
  if (conversation === "bot") {
    return !card.is_human_handoff && card.owner_slug !== "humano";
  }
  if (conversation === "closing") {
    return card.stage_label.toLowerCase().includes("confirm");
  }
  return true;
}

function isProcessVisible(card: ProcessCard, search: string, conversation: string): boolean {
  const term = search.trim().toLowerCase();
  const matchesSearch =
    !term ||
    `${card.cliente_nome} ${card.phone} ${card.summary} ${card.stage_label} ${card.process_label}`
      .toLowerCase()
      .includes(term);

  if (!matchesSearch) {
    return false;
  }

  if (conversation === "human") {
    return card.owner_class.includes("human");
  }
  if (conversation === "bot") {
    return card.owner_class.includes("delivery");
  }
  if (conversation === "closing") {
    return card.stage_slug === "aguardando_confirmacao" || card.stage_slug === "pagamento_pendente";
  }
  return true;
}

function isOrderVisible(item: KanbanItem, filters: FilterState, search: string): boolean {
  if (filters.status !== "all" && item.status_slug !== filters.status) {
    return false;
  }
  if (filters.type !== "all" && item.tipo_slug !== filters.type) {
    return false;
  }

  const term = search.trim().toLowerCase();
  if (!term) {
    return true;
  }

  return `${item.search_blob || ""} ${item.cliente_nome} ${item.produto} ${item.id}`.toLowerCase().includes(term);
}

function resolveDropStatus(item: KanbanItem, columnKey: string): string {
  if (columnKey === "saida") {
    return item.ready_status || "agendada";
  }
  return columnKey;
}

function findOrder(columns: KanbanColumn[], orderId: number): { item: KanbanItem; columnKey: string } | null {
  for (const column of columns) {
    const item = column.items.find((entry) => entry.id === orderId);
    if (item) {
      return { item, columnKey: column.key };
    }
  }
  return null;
}

function moveOrder(columns: KanbanColumn[], orderId: number, targetKey: string): KanbanColumn[] {
  const found = findOrder(columns, orderId);
  if (!found || found.columnKey === targetKey) {
    return columns;
  }

  const nextStatus = resolveDropStatus(found.item, targetKey);
  const nextMeta = STATUS_META[nextStatus] || STATUS_META.pendente;
  const movedItem: KanbanItem = {
    ...found.item,
    status_slug: nextStatus,
    status_label: nextMeta.label,
    status_badge_class: nextMeta.badgeClass,
  };

  return normalizeColumns(
    columns.map((column) => {
      if (column.key === found.columnKey) {
        return { ...column, items: column.items.filter((item) => item.id !== orderId) };
      }
      if (column.key === targetKey) {
        return { ...column, items: [...column.items, movedItem] };
      }
      return column;
    }),
  );
}

function KanbanBoard({
  columns,
  draggingId,
  onDragStart,
  onDrop,
}: {
  columns: KanbanColumn[];
  draggingId: number | null;
  onDragStart: (id: number) => void;
  onDrop: (id: number, columnKey: string) => void;
}) {
  if (columns.every((column) => column.items.length === 0)) {
    return <EmptyState message="Nenhum pedido encontrado com os filtros atuais." />;
  }

  return (
    <div className="grid gap-4 xl:grid-cols-4">
      {columns.map((column) => (
        <section
          key={column.key}
          onDragOver={(event) => event.preventDefault()}
          onDrop={(event) => {
            event.preventDefault();
            const orderId = Number(event.dataTransfer.getData("text/plain"));
            if (orderId) {
              onDrop(orderId, column.key);
            }
          }}
          className="rounded-[30px] border border-line bg-paper/92 p-4 shadow-panel"
        >
          <div className="border-b border-line pb-4">
            <div className="flex items-center justify-between gap-3">
              <div>
                <p className="text-lg font-bold">{column.title}</p>
                <p className="text-sm text-cocoa/70">{column.description}</p>
              </div>
              <span className="rounded-full bg-white px-3 py-1 text-xs font-semibold text-cocoa">
                {column.items.length}
              </span>
            </div>
          </div>
          <div className="mt-4 space-y-3">
            {column.items.length === 0 ? (
              <div className="rounded-[22px] border border-dashed border-line bg-white/70 px-3 py-6 text-center text-sm text-cocoa/65">
                Solte um pedido aqui
              </div>
            ) : (
              column.items.map((item) => (
                <article
                  key={item.id}
                  draggable
                  onDragStart={(event) => {
                    event.dataTransfer.setData("text/plain", String(item.id));
                    onDragStart(item.id);
                  }}
                  className={`rounded-[24px] border border-line bg-white p-4 transition ${
                    draggingId === item.id ? "opacity-60" : ""
                  }`}
                >
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <p className="text-sm font-semibold text-cocoa/65">#{item.id}</p>
                      <p className="mt-1 font-semibold">{item.cliente_nome}</p>
                    </div>
                    <span className={`rounded-full px-3 py-1 text-xs font-semibold ${orderStatusClasses(item.status_slug)}`}>
                      {item.status_label}
                    </span>
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
              ))
            )}
          </div>
        </section>
      ))}
    </div>
  );
}

export function DashboardShell({ snapshot, warning }: DashboardShellProps) {
  const [columns, setColumns] = useState(() => normalizeColumns(snapshot.dashboard.kanban_columns));
  const [filters, setFilters] = useState<FilterState>({
    search: "",
    status: "all",
    type: "all",
    conversation: "all",
  });
  const [selectedPhone, setSelectedPhone] = useState(snapshot.whatsapp_cards[0]?.phone || "");
  const [draggingId, setDraggingId] = useState<number | null>(null);
  const [feedback, setFeedback] = useState<string>("");
  const [isPending, startTransition] = useTransition();
  const deferredSearch = useDeferredValue(filters.search);

  const allProcessCards = flattenProcessCards(snapshot);
  const readyToClose = allProcessCards.filter(
    (card) => card.stage_slug === "aguardando_confirmacao" || card.stage_slug === "pagamento_pendente",
  ).length;
  const humanHandoffs = snapshot.whatsapp_cards.filter(
    (card) => card.is_human_handoff || card.owner_slug === "humano",
  ).length;
  const orderItems = columns.flatMap((column) => column.items);
  const activeOrderCount = orderItems.filter((item) => item.status_slug !== "entregue").length;
  const dueToday = orderItems.filter((item) => item.schedule_bucket === "today").length;

  const visibleConversations = snapshot.whatsapp_cards.filter((card) =>
    isConversationVisible(card, deferredSearch, filters.conversation),
  );
  const selectedConversation =
    visibleConversations.find((card) => card.phone === selectedPhone) || visibleConversations[0] || null;

  const visibleSections = snapshot.process_sections
    .map((section) => ({
      ...section,
      cards: section.cards.filter((card) => isProcessVisible(card, deferredSearch, filters.conversation)),
    }))
    .filter((section) => section.cards.length > 0);

  const visibleColumns = columns.map((column) => ({
    ...column,
    items: column.items.filter((item) => isOrderVisible(item, filters, deferredSearch)),
  }));

  async function persistStatus(orderId: number, nextStatus: string) {
    const response = await fetch(`/api/orders/${orderId}/status`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ status: nextStatus }),
    });

    if (!response.ok) {
      throw new Error(`status_update_failed_${response.status}`);
    }
  }

  async function handleDrop(orderId: number, columnKey: string) {
    const previousColumns = columns;
    const found = findOrder(previousColumns, orderId);
    if (!found || found.columnKey === columnKey) {
      setDraggingId(null);
      return;
    }

    const nextStatus = resolveDropStatus(found.item, columnKey);
    const nextColumns = moveOrder(previousColumns, orderId, columnKey);

    startTransition(() => {
      setColumns(nextColumns);
      setFeedback(`Pedido #${orderId} movido para ${STATUS_META[nextStatus]?.label || nextStatus}.`);
    });

    try {
      await persistStatus(orderId, nextStatus);
    } catch {
      startTransition(() => {
        setColumns(previousColumns);
        setFeedback(`Nao foi possivel atualizar o pedido #${orderId}.`);
      });
    } finally {
      setDraggingId(null);
    }
  }

  return (
    <AdminWorkspace>
      <PageHeader
        eyebrow="Admin operacional"
        title="Somente o que pede decisao"
        description="KPI direto, etapas do processo, conversa cliente + IA e kanban de pedidos na mesma leitura."
        referenceDate={snapshot.dashboard.reference_date}
        generatedAt={snapshot.dashboard.generated_at}
        actions={
          <>
            <a
              href="/conversas"
              className="rounded-full border border-line bg-white px-4 py-2 text-sm font-semibold text-ink transition hover:bg-sand"
            >
              Ver conversas
            </a>
            <a
              href="/encomendas"
              className="rounded-full border border-line bg-white px-4 py-2 text-sm font-semibold text-ink transition hover:bg-sand"
            >
              Ver encomendas
            </a>
          </>
        }
      />

      <WarningBanner warning={warning} />

      {snapshot.sync_overview.alerts.length > 0 ? (
        <section className="mt-4 grid gap-3 lg:grid-cols-2">
          {snapshot.sync_overview.alerts.slice(0, 2).map((alert) => (
            <article
              key={`${alert.title}-${alert.description}`}
              className={`rounded-[24px] border border-line px-4 py-4 shadow-panel ${toneClasses(alert.tone)}`}
            >
              <p className="text-sm font-bold">{alert.title}</p>
              <p className="mt-1 text-sm opacity-85">{alert.description}</p>
            </article>
          ))}
        </section>
      ) : null}

      <section className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <KPI label="Pedidos ativos" value={String(activeOrderCount)} hint="Fila atual de operação" tone="accent" />
        <KPI label="Prontos para fechar" value={String(readyToClose)} hint="Conversas pedindo confirmação" tone="warning" />
        <KPI label="Handoffs humanos" value={String(humanHandoffs)} hint="Casos em ação manual" tone="muted" />
        <KPI label="Hoje" value={String(dueToday)} hint="Pedidos com entrega ou retirada hoje" tone="success" />
      </section>

      <FilterPanel
        summary={
          <>
            <p>{visibleConversations.length} conversas visíveis • {visibleSections.reduce((total, section) => total + section.cards.length, 0)} processos ativos • {visibleColumns.reduce((total, column) => total + column.items.length, 0)} pedidos filtrados</p>
            <p aria-live="polite">{isPending ? "Atualizando kanban..." : feedback}</p>
          </>
        }
      >
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1.6fr)_220px_220px_220px]">
          <label className="flex flex-col gap-2 text-sm font-medium text-cocoa">
            Buscar
            <input
              value={filters.search}
              onChange={(event) => setFilters((current) => ({ ...current, search: event.target.value }))}
              placeholder="cliente, telefone, produto, mensagem"
              className="h-12 rounded-full border border-line bg-paper px-4 text-sm text-ink outline-none transition focus:border-clay focus:ring-2 focus:ring-[#d88d6f]/30"
            />
          </label>

          <label className="flex flex-col gap-2 text-sm font-medium text-cocoa">
            Status do pedido
            <select
              value={filters.status}
              onChange={(event) => setFilters((current) => ({ ...current, status: event.target.value }))}
              className="h-12 rounded-full border border-line bg-paper px-4 text-sm text-ink outline-none transition focus:border-clay focus:ring-2 focus:ring-[#d88d6f]/30"
            >
              <option value="all">Todos</option>
              {(snapshot.dashboard.filters?.statuses || []).map((status) => (
                <option key={status.value} value={status.value}>
                  {status.label}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-2 text-sm font-medium text-cocoa">
            Tipo
            <select
              value={filters.type}
              onChange={(event) => setFilters((current) => ({ ...current, type: event.target.value }))}
              className="h-12 rounded-full border border-line bg-paper px-4 text-sm text-ink outline-none transition focus:border-clay focus:ring-2 focus:ring-[#d88d6f]/30"
            >
              <option value="all">Todos</option>
              {(snapshot.dashboard.filters?.types || []).map((type) => (
                <option key={type.value} value={type.value}>
                  {type.label}
                </option>
              ))}
            </select>
          </label>

          <label className="flex flex-col gap-2 text-sm font-medium text-cocoa">
            Conversa
            <select
              value={filters.conversation}
              onChange={(event) => setFilters((current) => ({ ...current, conversation: event.target.value }))}
              className="h-12 rounded-full border border-line bg-paper px-4 text-sm text-ink outline-none transition focus:border-clay focus:ring-2 focus:ring-[#d88d6f]/30"
            >
              <option value="all">Tudo</option>
              <option value="human">Humano</option>
              <option value="bot">IA / bot</option>
              <option value="closing">Fechamento</option>
            </select>
          </label>
        </div>
      </FilterPanel>

      <section className="mt-6 grid gap-6 xl:grid-cols-[minmax(0,1.1fr)_minmax(340px,0.75fr)]">
        <div>
          <div className="mb-4">
            <SectionTitle eyebrow="Etapas" title="Cada processo no ponto certo" />
          </div>
          <ProcessStageList sections={visibleSections} />
        </div>

        <div className="space-y-4">
          <SectionTitle eyebrow="Conversas ativas" title="Cliente e IA lado a lado" />
          <ConversationThread card={selectedConversation} />
          <ConversationList
            cards={visibleConversations}
            selectedPhone={selectedConversation?.phone || ""}
            onSelect={setSelectedPhone}
          />
        </div>
      </section>

      <section className="mt-8">
        <div className="mb-4 flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
          <SectionTitle eyebrow="Kanban" title="Pedidos por data, com arraste e sync manual" />
          <p className="max-w-2xl text-sm text-cocoa/70">
            O arraste atualiza o status manualmente. O fluxo do cliente com a IA continua sendo a fonte automática de
            progresso antes da confirmação.
          </p>
        </div>
        <KanbanBoard
          columns={visibleColumns}
          draggingId={draggingId}
          onDragStart={setDraggingId}
          onDrop={handleDrop}
        />
      </section>
    </AdminWorkspace>
  );
}

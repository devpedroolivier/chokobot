"use client";

import { useDeferredValue, useState } from "react";

import {
  AdminWorkspace,
  FilterPanel,
  KPI,
  PageHeader,
  SectionTitle,
  WarningBanner,
} from "@/components/admin-workspace";
import { ConversationList, ConversationThread } from "@/components/conversation-queue";
import { ProcessList } from "@/components/process-card-list";
import type { PanelSnapshot, ProcessCard } from "@/lib/panel-types";

type ConversationsShellProps = {
  snapshot: PanelSnapshot;
  warning?: string;
};

function flattenProcessCards(snapshot: PanelSnapshot): ProcessCard[] {
  return snapshot.process_sections.flatMap((section) => section.cards);
}

export function ConversationsShell({ snapshot, warning }: ConversationsShellProps) {
  const [search, setSearch] = useState("");
  const [mode, setMode] = useState("all");
  const deferredSearch = useDeferredValue(search);

  const processCards = flattenProcessCards(snapshot);
  const visibleConversations = snapshot.whatsapp_cards.filter((card) => {
    const term = deferredSearch.trim().toLowerCase();
    const matchesSearch =
      !term ||
      `${card.cliente_nome} ${card.phone} ${card.last_message} ${card.agent}`.toLowerCase().includes(term);

    if (!matchesSearch) {
      return false;
    }

    if (mode === "human") {
      return card.is_human_handoff || card.owner_slug === "humano";
    }
    if (mode === "bot") {
      return !card.is_human_handoff && card.owner_slug !== "humano";
    }
    if (mode === "closing") {
      return card.stage_label.toLowerCase().includes("confirm");
    }
    return true;
  });

  const [selectedPhone, setSelectedPhone] = useState(snapshot.whatsapp_cards[0]?.phone || "");
  const selectedConversation =
    visibleConversations.find((card) => card.phone === selectedPhone) || visibleConversations[0] || null;

  const readyToClose = processCards.filter(
    (card) => card.stage_slug === "aguardando_confirmacao" || card.stage_slug === "pagamento_pendente",
  );
  const humanFollowUp = processCards.filter((card) => card.owner_class.includes("human"));

  const filteredReadyToClose = readyToClose.filter((card) =>
    `${card.cliente_nome} ${card.phone} ${card.summary}`.toLowerCase().includes(deferredSearch.trim().toLowerCase()),
  );
  const filteredHumanFollowUp = humanFollowUp.filter((card) =>
    `${card.cliente_nome} ${card.phone} ${card.summary}`.toLowerCase().includes(deferredSearch.trim().toLowerCase()),
  );

  return (
    <AdminWorkspace>
      <PageHeader
        eyebrow="Conversas"
        title="Cliente, IA e decisão humana"
        description="Visão mínima para acompanhar contexto, handoff e os fluxos que estão prontos para virar pedido."
        referenceDate={snapshot.dashboard.reference_date}
        generatedAt={snapshot.dashboard.generated_at}
        actions={
          <a
            href="/"
            className="rounded-full border border-line bg-white px-4 py-2 text-sm font-semibold text-ink transition hover:bg-sand"
          >
            Voltar ao admin
          </a>
        }
      />

      <WarningBanner warning={warning} />

      <section className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <KPI label="Conversas ativas" value={String(snapshot.whatsapp_cards.length)} hint="Sessoes ainda em andamento" />
        <KPI label="Handoffs" value={String(snapshot.whatsapp_cards.filter((card) => card.is_human_handoff).length)} hint="Casos sob acao humana" />
        <KPI label="Prontos para fechar" value={String(readyToClose.length)} hint="Aguardando confirmacao final" />
        <KPI label="Processos ativos" value={String(processCards.length)} hint="Trilha persistida no painel" />
      </section>

      <FilterPanel>
        <div className="grid gap-4 lg:grid-cols-[minmax(0,1fr)_240px]">
          <label className="flex flex-col gap-2 text-sm font-medium text-cocoa">
            Buscar
            <input
              value={search}
              onChange={(event) => setSearch(event.target.value)}
              placeholder="cliente, telefone, agente, mensagem"
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
              <option value="human">Humano</option>
              <option value="bot">IA / bot</option>
              <option value="closing">Fechamento</option>
            </select>
          </label>
        </div>
      </FilterPanel>

      <section className="mt-6 grid gap-6 xl:grid-cols-[minmax(320px,0.78fr)_minmax(0,1.15fr)]">
        <div className="space-y-4">
          <SectionTitle eyebrow="Fila viva" title="Conversas ativas" />
          <ConversationList cards={visibleConversations} selectedPhone={selectedConversation?.phone || ""} onSelect={setSelectedPhone} />
        </div>

        <div className="space-y-6">
          <SectionTitle eyebrow="Thread" title="Leitura do atendimento" />
          <ConversationThread card={selectedConversation} />
        </div>
      </section>

      <section className="mt-8 grid gap-6 xl:grid-cols-2">
        <div>
          <div className="mb-4">
            <SectionTitle eyebrow="Conversão" title="Prontos para fechar" />
          </div>
          <ProcessList cards={filteredReadyToClose} emptyMessage="Nenhum fluxo aguardando confirmação final." />
        </div>

        <div>
          <div className="mb-4">
            <SectionTitle eyebrow="Follow-up" title="Casos que dependem de humano" />
          </div>
          <ProcessList cards={filteredHumanFollowUp} emptyMessage="Nenhum caso manual pendente." />
        </div>
      </section>
    </AdminWorkspace>
  );
}

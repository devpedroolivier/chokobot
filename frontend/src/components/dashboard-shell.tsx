import type { PanelSnapshot } from "@/lib/panel-types";
import { AdminNav } from "@/components/admin-nav";

type DashboardShellProps = {
  snapshot: PanelSnapshot;
  warning?: string;
};

function toneClasses(tone?: string): string {
  switch (tone) {
    case "danger":
      return "bg-rose text-[#8d2941]";
    case "warning":
      return "bg-honey text-[#8a5b00]";
    case "success":
      return "bg-[#dff0e7] text-[#166534]";
    case "accent":
      return "bg-blush text-clay";
    case "muted":
      return "bg-mist text-cocoa";
    default:
      return "bg-mist text-cocoa";
  }
}

function stageClasses(stageClass: string): string {
  if (stageClass.includes("cake")) return "bg-[#fde6df] text-[#a63d22]";
  if (stageClass.includes("sweet")) return "bg-[#ffe7ef] text-[#a11d48]";
  if (stageClass.includes("cafe")) return "bg-[#f4ead8] text-[#8a5b00]";
  if (stageClass.includes("gift")) return "bg-[#efe2ff] text-[#6d28d9]";
  if (stageClass.includes("delivery")) return "bg-sky text-[#1d4ed8]";
  return "bg-mist text-cocoa";
}

function statusBadgeClasses(statusBadgeClass: string): string {
  if (statusBadgeClass.includes("pending")) return "bg-[#fff4cd] text-[#8b5d08]";
  if (statusBadgeClass.includes("progress")) return "bg-sky text-[#1d4ed8]";
  if (statusBadgeClass.includes("pickup")) return "bg-[#dff0e7] text-[#166534]";
  if (statusBadgeClass.includes("done")) return "bg-mist text-cocoa";
  return "bg-white text-cocoa";
}

function customerHref(phone: string): string {
  return `/clientes?q=${encodeURIComponent(phone)}`;
}

function processActionHref(phone: string, orderId?: number | null): string {
  if (orderId) {
    return `/encomendas/${orderId}`;
  }
  return customerHref(phone);
}

function processActionText(orderId?: number | null): string {
  return orderId ? "Abrir pedido" : "Ver cliente";
}

export function DashboardShell({ snapshot, warning }: DashboardShellProps) {
  return (
    <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      <AdminNav />

      <header className="rounded-panel border border-line bg-paper/90 px-6 py-6 shadow-panel backdrop-blur">
        <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-cocoa/70">
              Chokodelícia Admin
            </p>
            <h1 className="mt-2 text-3xl font-black tracking-tight sm:text-5xl">
              Operação, atendimento e monitoramento
            </h1>
            <p className="mt-3 max-w-3xl text-sm text-cocoa/75">
              Base moderna em Next.js para evoluir o painel operacional sem perder o fluxo atual do FastAPI.
            </p>
            <p className="mt-2 text-xs uppercase tracking-[0.18em] text-clay">
              referência {snapshot.dashboard.reference_date} • atualizado às {snapshot.dashboard.generated_at}
            </p>
          </div>
          <div className="flex flex-wrap gap-3">
            <a
              href="/api/panel/snapshot"
              className="rounded-full border border-line bg-white px-4 py-2 text-sm font-semibold text-ink transition hover:bg-sand"
            >
              Ver snapshot JSON
            </a>
          </div>
        </div>
      </header>

      {warning ? (
        <section className="mt-6 rounded-card border border-[#efc2a8] bg-[#fff6f1] px-5 py-4 text-sm text-cocoa shadow-panel">
          {warning}
        </section>
      ) : null}

      <section className="mt-6 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        {snapshot.sync_overview.metrics.map((metric) => (
          <article key={metric.label} className="rounded-card border border-line bg-paper/95 p-5 shadow-panel">
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cocoa/65">{metric.label}</p>
            <div className="mt-3 flex items-center justify-between gap-3">
              <p className="text-3xl font-black">{metric.value}</p>
              <span className={`rounded-full px-3 py-1 text-xs font-semibold ${toneClasses(metric.tone)}`}>
                {metric.label}
              </span>
            </div>
            <p className="mt-2 text-sm text-cocoa/70">{metric.hint}</p>
          </article>
        ))}
      </section>

      {snapshot.sync_overview.alerts.length > 0 ? (
        <section className="mt-4 grid gap-3 xl:grid-cols-3">
          {snapshot.sync_overview.alerts.map((alert) => (
            <article
              key={`${alert.title}-${alert.description}`}
              className={`rounded-card border p-4 shadow-panel ${toneClasses(alert.tone)}`}
            >
              <p className="text-sm font-bold">{alert.title}</p>
              <p className="mt-1 text-sm opacity-85">{alert.description}</p>
            </article>
          ))}
        </section>
      ) : null}

      <section className="mt-8">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cocoa/65">Atendimento</p>
            <h2 className="mt-1 text-2xl font-bold">Sync de processos</h2>
          </div>
        </div>

        <div className="space-y-5">
          {snapshot.process_sections.map((section) => (
            <div key={section.title}>
              <div className="mb-3 flex items-center justify-between gap-3">
                <div>
                  <p className="text-lg font-bold">{section.title}</p>
                  <p className="text-sm text-cocoa/70">{section.description}</p>
                </div>
                <span className="rounded-full border border-line bg-white px-3 py-1 text-xs font-semibold text-cocoa/80">
                  {section.count}
                </span>
              </div>
              <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
                {section.cards.map((card) => (
                  <article key={`${card.phone}-${card.stage_label}`} className="rounded-card border border-line bg-paper/95 p-4 shadow-panel">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="font-bold">{card.cliente_nome}</p>
                        <p className="mt-1 text-xs uppercase tracking-[0.18em] text-cocoa/60">{card.process_label}</p>
                      </div>
                      <div className="flex flex-col items-end gap-2">
                        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${stageClasses(card.origin_class)}`}>
                          {card.origin_label}
                        </span>
                        <span className={`rounded-full px-3 py-1 text-xs font-semibold ${stageClasses(card.stage_class)}`}>
                          {card.stage_label}
                        </span>
                      </div>
                    </div>
                    <p className="mt-4 text-sm text-ink">{card.summary}</p>
                    <div className="mt-4 flex flex-wrap gap-2">
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${stageClasses(card.owner_class)}`}>
                        {card.owner_label}
                      </span>
                      <span className="rounded-full bg-blush px-3 py-1 text-xs font-semibold text-clay">
                        {card.action_label}
                      </span>
                      {card.missing_items.map((item) => (
                        <span key={item} className="rounded-full bg-mist px-3 py-1 text-xs font-semibold text-cocoa">
                          {item}
                        </span>
                      ))}
                    </div>
                    <p className="mt-3 text-xs text-cocoa/65">{card.owner_hint}</p>
                    <div className="mt-4 flex items-center justify-between gap-3 text-xs text-cocoa/65">
                      <div className="flex flex-col gap-1">
                        <span className="font-mono">{card.phone}</span>
                        <span>{card.updated_label}</span>
                      </div>
                      <a
                        href={processActionHref(card.phone, card.order_id)}
                        className="rounded-full border border-line bg-white px-3 py-1 text-xs font-semibold text-ink transition hover:bg-sand"
                      >
                        {processActionText(card.order_id)}
                      </a>
                    </div>
                  </article>
                ))}
              </div>
            </div>
          ))}
        </div>
      </section>

      <section className="mt-8">
        <div className="mb-4">
          <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cocoa/65">WhatsApp</p>
          <h2 className="mt-1 text-2xl font-bold">Conversas em andamento</h2>
        </div>

        <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
          {snapshot.whatsapp_cards.map((card) => (
            <article key={`${card.phone}-${card.agent}`} className="rounded-card border border-line bg-paper/95 p-4 shadow-panel">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <p className="font-bold">{card.cliente_nome}</p>
                  <p className="mt-1 text-xs uppercase tracking-[0.18em] text-cocoa/60">WhatsApp</p>
                </div>
                <div className="flex flex-col items-end gap-2">
                  {card.is_human_handoff ? (
                    <span className="rounded-full bg-mist px-3 py-1 text-xs font-semibold text-cocoa">
                      Handoff humano
                    </span>
                  ) : null}
                  <span className={`rounded-full px-3 py-1 text-xs font-semibold ${stageClasses(card.owner_class)}`}>
                    {card.owner_label}
                  </span>
                  <span className={`rounded-full px-3 py-1 text-xs font-semibold ${stageClasses(card.stage_class)}`}>
                    {card.stage_label}
                  </span>
                </div>
              </div>
              <p className="mt-4 text-sm text-ink">{card.last_message}</p>
              <div className="mt-4 flex items-center justify-between gap-3 text-xs text-cocoa/65">
                <div className="flex flex-col gap-1">
                  <span>{card.agent}</span>
                  <span>{card.last_seen_label}</span>
                </div>
                <a
                  href={customerHref(card.phone)}
                  className="rounded-full border border-line bg-white px-3 py-1 text-xs font-semibold text-ink transition hover:bg-sand"
                >
                  Ver cliente
                </a>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="mt-8">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.18em] text-cocoa/65">Operação</p>
            <h2 className="mt-1 text-2xl font-bold">Kanban de pedidos confirmados</h2>
          </div>
          <div className="rounded-full bg-blush px-4 py-2 text-sm font-semibold text-clay">
            {snapshot.dashboard.metrics.find((metric) => metric.label === "Em operação")?.value || "0"} pedidos ativos
          </div>
        </div>

        <div className="grid gap-4 xl:grid-cols-4">
          {snapshot.dashboard.kanban_columns.map((column) => (
            <article key={column.key} className="rounded-panel border border-line bg-paper/95 p-4 shadow-panel">
              <div className="mb-4 border-b border-line pb-4">
                <div className="flex items-center justify-between gap-3">
                  <div>
                    <p className="text-lg font-bold">{column.title}</p>
                    <p className="text-sm text-cocoa/70">{column.description}</p>
                  </div>
                  <span className="rounded-full bg-sand px-3 py-1 text-xs font-semibold text-cocoa">
                    {column.items.length}
                  </span>
                </div>
              </div>
              <div className="space-y-3">
                {column.items.map((item) => (
                  <article key={item.id} className="rounded-card border border-line bg-white p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <p className="text-sm font-semibold text-cocoa/65">#{item.id}</p>
                        <p className="mt-1 font-bold">{item.cliente_nome}</p>
                      </div>
                      <span className={`rounded-full px-3 py-1 text-xs font-semibold ${statusBadgeClasses(item.status_badge_class)}`}>
                        {item.status_label}
                      </span>
                    </div>
                    <p className="mt-3 text-sm font-medium">{item.produto}</p>
                    <p className="mt-1 text-sm text-cocoa/70">{item.categoria_label}</p>
                    <div className="mt-4 grid gap-2 text-xs text-cocoa/65">
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
                        href={`/encomendas/${item.id}`}
                        className="rounded-full border border-line bg-paper px-3 py-1 text-xs font-semibold text-ink transition hover:bg-sand"
                      >
                        Abrir pedido
                      </a>
                    </div>
                  </article>
                ))}
              </div>
            </article>
          ))}
        </div>
      </section>
    </main>
  );
}

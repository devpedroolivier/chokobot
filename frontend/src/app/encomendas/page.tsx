import { AdminNav } from "@/components/admin-nav";
import { requireAdminPageSession } from "@/lib/admin-session";
import { OrdersTable } from "@/components/orders-table";
import { fetchOrdersSnapshot } from "@/lib/panel-api";

type OrdersPageProps = {
  searchParams?: Promise<{ q?: string; status?: string; categoria?: string }>;
};

export default async function OrdersPage({ searchParams }: OrdersPageProps) {
  await requireAdminPageSession();
  const { data, warning } = await fetchOrdersSnapshot();
  const filters = (await searchParams) || {};

  return (
    <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      <AdminNav />

      <header className="rounded-panel border border-line bg-paper/90 px-6 py-6 shadow-panel backdrop-blur">
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-cocoa/70">Encomendas</p>
        <h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">Leitura operacional de pedidos</h1>
        <p className="mt-2 text-sm text-cocoa/70">
          Tabela moderna para evolução do back-office sem depender do template legado.
        </p>
      </header>

      {warning ? (
        <section className="mt-6 rounded-card border border-[#efc2a8] bg-[#fff6f1] px-5 py-4 text-sm text-cocoa shadow-panel">
          {warning}
        </section>
      ) : null}

      <section className="mt-6 rounded-panel border border-line bg-paper/95 p-5 shadow-panel">
        <div className="mb-4 flex items-center justify-between gap-3">
          <div>
            <p className="text-lg font-bold">Encomendas cadastradas</p>
            <p className="text-sm text-cocoa/70">Primeira camada de leitura via snapshot do FastAPI.</p>
          </div>
          <div className="flex items-center gap-3">
            <span className="rounded-full bg-blush px-4 py-2 text-sm font-semibold text-clay">
              {data.count} pedido(s)
            </span>
            <a
              href="/encomendas/nova"
              className="rounded-full border border-line bg-white px-4 py-2 text-sm font-semibold text-ink transition hover:bg-sand"
            >
              Nova encomenda
            </a>
          </div>
        </div>

        <OrdersTable
          data={data}
          initialQuery={filters.q || ""}
          initialStatusFilter={filters.status || "todos"}
          initialCategoryFilter={filters.categoria || "todas"}
        />
      </section>
    </main>
  );
}

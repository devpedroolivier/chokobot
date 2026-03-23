import { AdminNav } from "@/components/admin-nav";
import { requireAdminPageSession } from "@/lib/admin-session";
import { CustomersTable } from "@/components/customers-table";
import { fetchCustomersSnapshot } from "@/lib/panel-api";

type CustomersPageProps = {
  searchParams?: Promise<{ q?: string }>;
};

export default async function CustomersPage({ searchParams }: CustomersPageProps) {
  await requireAdminPageSession();
  const { data, warning } = await fetchCustomersSnapshot();
  const filters = (await searchParams) || {};

  return (
    <main className="mx-auto max-w-7xl px-4 py-6 sm:px-6 lg:px-8">
      <AdminNav />

      <header className="rounded-panel border border-line bg-paper/90 px-6 py-6 shadow-panel backdrop-blur">
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-cocoa/70">Clientes</p>
        <h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">Base de clientes</h1>
        <p className="mt-2 text-sm text-cocoa/70">
          Visualização moderna da carteira de clientes para o back-office.
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
            <p className="text-lg font-bold">Clientes cadastrados</p>
            <p className="text-sm text-cocoa/70">Leitura vinda do FastAPI por snapshot JSON.</p>
          </div>
          <div className="flex items-center gap-3">
            <span className="rounded-full bg-blush px-4 py-2 text-sm font-semibold text-clay">
              {data.count} cliente(s)
            </span>
            <a
              href="/clientes/novo"
              className="rounded-full border border-line bg-white px-4 py-2 text-sm font-semibold text-ink transition hover:bg-sand"
            >
              Novo cliente
            </a>
          </div>
        </div>

        <CustomersTable data={data} initialQuery={filters.q || ""} />
      </section>
    </main>
  );
}

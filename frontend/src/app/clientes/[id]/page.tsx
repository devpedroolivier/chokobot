import { AdminNav } from "@/components/admin-nav";
import { CustomerForm } from "@/components/customer-form";
import { requireAdminPageSession } from "@/lib/admin-session";
import { fetchCustomerDetailsSnapshot } from "@/lib/panel-api";

type CustomerDetailsPageProps = {
  params: Promise<{ id: string }>;
};

export default async function CustomerDetailsPage({ params }: CustomerDetailsPageProps) {
  await requireAdminPageSession();
  const { id } = await params;
  const { data, warning } = await fetchCustomerDetailsSnapshot(id);
  const customer = data.item;

  return (
    <main className="mx-auto max-w-4xl px-4 py-6 sm:px-6 lg:px-8">
      <AdminNav />
      <header className="rounded-panel border border-line bg-paper/90 px-6 py-6 shadow-panel backdrop-blur">
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-cocoa/70">Clientes</p>
        <h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">
          {customer ? `Editar cliente #${customer.id}` : "Cliente não encontrado"}
        </h1>
      </header>
      {warning ? (
        <section className="mt-6 rounded-card border border-[#efc2a8] bg-[#fff6f1] px-5 py-4 text-sm text-cocoa shadow-panel">
          {warning}
        </section>
      ) : null}
      {!customer ? (
        <section className="mt-6 rounded-card border border-line bg-paper/95 px-5 py-8 text-center text-cocoa/75 shadow-panel">
          Nenhum cliente encontrado para esse ID.
        </section>
      ) : (
        <section className="mt-6">
          <CustomerForm mode="edit" customer={customer} />
        </section>
      )}
    </main>
  );
}

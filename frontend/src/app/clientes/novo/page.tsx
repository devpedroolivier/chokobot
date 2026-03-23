import { AdminNav } from "@/components/admin-nav";
import { CustomerForm } from "@/components/customer-form";
import { requireAdminPageSession } from "@/lib/admin-session";

export default async function NewCustomerPage() {
  await requireAdminPageSession();

  return (
    <main className="mx-auto max-w-4xl px-4 py-6 sm:px-6 lg:px-8">
      <AdminNav />
      <header className="rounded-panel border border-line bg-paper/90 px-6 py-6 shadow-panel backdrop-blur">
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-cocoa/70">Clientes</p>
        <h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">Novo cliente</h1>
      </header>
      <section className="mt-6">
        <CustomerForm mode="create" />
      </section>
    </main>
  );
}

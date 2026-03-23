import { AdminNav } from "@/components/admin-nav";
import { OrderForm } from "@/components/order-form";
import { requireAdminPageSession } from "@/lib/admin-session";

export default async function NewOrderPage() {
  await requireAdminPageSession();

  return (
    <main className="mx-auto max-w-5xl px-4 py-6 sm:px-6 lg:px-8">
      <AdminNav />
      <header className="rounded-panel border border-line bg-paper/90 px-6 py-6 shadow-panel backdrop-blur">
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-cocoa/70">Encomendas</p>
        <h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">Nova encomenda</h1>
      </header>
      <section className="mt-6">
        <OrderForm />
      </section>
    </main>
  );
}

import { AdminNav } from "@/components/admin-nav";
import { OrderDeleteAction } from "@/components/order-delete-action";
import { OrderStatusActions } from "@/components/order-status-actions";
import { requireAdminPageSession } from "@/lib/admin-session";
import { fetchOrderDetailsSnapshot } from "@/lib/panel-api";

type OrderDetailsPageProps = {
  params: Promise<{ id: string }>;
};

function detailValue(value: string | number | boolean | null | undefined) {
  if (value === null || value === undefined || value === "") {
    return "-";
  }
  if (typeof value === "boolean") {
    return value ? "Sim" : "Não";
  }
  return String(value);
}

export default async function OrderDetailsPage({ params }: OrderDetailsPageProps) {
  await requireAdminPageSession();
  const { id } = await params;
  const { data, warning } = await fetchOrderDetailsSnapshot(id);
  const order = data.item;

  return (
    <main className="mx-auto max-w-5xl px-4 py-6 sm:px-6 lg:px-8">
      <AdminNav />

      <header className="rounded-panel border border-line bg-paper/90 px-6 py-6 shadow-panel backdrop-blur">
        <p className="text-xs font-semibold uppercase tracking-[0.24em] text-cocoa/70">Detalhe da encomenda</p>
        <h1 className="mt-2 text-3xl font-black tracking-tight sm:text-4xl">
          {order ? `Encomenda #${order.id}` : "Encomenda não encontrada"}
        </h1>
        <p className="mt-2 text-sm text-cocoa/70">
          Visão de detalhe para evolução do fluxo operacional no novo admin.
        </p>
      </header>

      {warning ? (
        <section className="mt-6 rounded-card border border-[#efc2a8] bg-[#fff6f1] px-5 py-4 text-sm text-cocoa shadow-panel">
          {warning}
        </section>
      ) : null}

      {!order ? (
        <section className="mt-6 rounded-card border border-line bg-paper/95 px-5 py-8 text-center text-cocoa/75 shadow-panel">
          Nenhuma encomenda encontrada para esse ID.
        </section>
      ) : (
        <section className="mt-6 grid gap-4 md:grid-cols-2">
          <article className="rounded-card border border-line bg-paper/95 p-5 shadow-panel">
            <p className="text-lg font-bold">Cliente e status</p>
            <div className="mt-4 grid gap-3 text-sm">
              <p><span className="font-semibold">Cliente:</span> {detailValue(order.cliente_nome)}</p>
              <p><span className="font-semibold">Status:</span> {detailValue(order.status)}</p>
              <p><span className="font-semibold">Criado em:</span> {detailValue(order.criado_em)}</p>
              <p><span className="font-semibold">Valor total:</span> {detailValue(order.valor_total)}</p>
            </div>
          </article>

          <article className="rounded-card border border-line bg-paper/95 p-5 shadow-panel">
            <p className="text-lg font-bold">Agenda</p>
            <div className="mt-4 grid gap-3 text-sm">
              <p><span className="font-semibold">Data:</span> {detailValue(order.data_entrega)}</p>
              <p><span className="font-semibold">Horário:</span> {detailValue(order.horario_retirada || order.horario)}</p>
              <p><span className="font-semibold">Serve pessoas:</span> {detailValue(order.serve_pessoas)}</p>
              <p><span className="font-semibold">Quantidade:</span> {detailValue(order.quantidade)}</p>
            </div>
          </article>

          <article className="rounded-card border border-line bg-paper/95 p-5 shadow-panel">
            <p className="text-lg font-bold">Pedido</p>
            <div className="mt-4 grid gap-3 text-sm">
              <p><span className="font-semibold">Categoria:</span> {detailValue(order.categoria)}</p>
              <p><span className="font-semibold">Produto:</span> {detailValue(order.produto)}</p>
              <p><span className="font-semibold">Descrição:</span> {detailValue(order.descricao)}</p>
              <p><span className="font-semibold">Tamanho:</span> {detailValue(order.tamanho)}</p>
              <p><span className="font-semibold">Kit Festou:</span> {detailValue(order.kit_festou)}</p>
            </div>
          </article>

          <article className="rounded-card border border-line bg-paper/95 p-5 shadow-panel">
            <p className="text-lg font-bold">Composição</p>
            <div className="mt-4 grid gap-3 text-sm">
              <p><span className="font-semibold">Massa:</span> {detailValue(order.massa)}</p>
              <p><span className="font-semibold">Recheio:</span> {detailValue(order.recheio)}</p>
              <p><span className="font-semibold">Mousse:</span> {detailValue(order.mousse)}</p>
              <p><span className="font-semibold">Adicional:</span> {detailValue(order.adicional)}</p>
              <p><span className="font-semibold">Fruta ou nozes:</span> {detailValue(order.fruta_ou_nozes)}</p>
            </div>
          </article>

          <div className="md:col-span-2">
            <OrderStatusActions orderId={order.id} currentStatus={order.status} />
            <OrderDeleteAction orderId={order.id} />
          </div>
        </section>
      )}
    </main>
  );
}

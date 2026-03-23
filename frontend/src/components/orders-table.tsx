"use client";

import { useState } from "react";

import type { OrderListSnapshot } from "@/lib/panel-types";

type OrdersTableProps = {
  data: OrderListSnapshot;
  initialQuery?: string;
  initialStatusFilter?: string;
  initialCategoryFilter?: string;
};

export function OrdersTable({
  data,
  initialQuery = "",
  initialStatusFilter = "todos",
  initialCategoryFilter = "todas",
}: OrdersTableProps) {
  const [query, setQuery] = useState(initialQuery);
  const [statusFilter, setStatusFilter] = useState(initialStatusFilter);
  const [categoryFilter, setCategoryFilter] = useState(initialCategoryFilter);

  const statusOptions = ["todos", ...new Set(data.items.map((order) => order.status).filter(Boolean))];
  const categoryOptions = ["todas", ...new Set(data.items.map((order) => order.categoria).filter(Boolean))];
  const normalizedQuery = query.trim().toLowerCase();
  const rows = data.items.filter((order) => {
    if (statusFilter !== "todos" && order.status !== statusFilter) {
      return false;
    }
    if (categoryFilter !== "todas" && order.categoria !== categoryFilter) {
      return false;
    }
    if (!normalizedQuery) {
      return true;
    }
    return [
      String(order.id),
      order.cliente_nome,
      order.cliente_telefone,
      order.categoria,
      order.tamanho,
      order.entrega,
      order.status
    ]
      .filter(Boolean)
      .join(" ")
      .toLowerCase()
      .includes(normalizedQuery);
  });

  return (
    <div className="overflow-hidden rounded-card border border-line">
      <div className="flex flex-col gap-3 border-b border-line bg-sand px-4 py-3 lg:flex-row">
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Buscar por cliente, telefone, categoria, entrega ou ID"
          className="w-full rounded-full border border-line bg-white px-4 py-2 text-sm outline-none transition focus:border-clay"
        />
        <select
          value={statusFilter}
          onChange={(event) => setStatusFilter(event.target.value)}
          className="rounded-full border border-line bg-white px-4 py-2 text-sm outline-none transition focus:border-clay"
        >
          {statusOptions.map((status) => (
            <option key={status} value={status}>
              {status === "todos" ? "Todos os status" : status}
            </option>
          ))}
        </select>
        <select
          value={categoryFilter}
          onChange={(event) => setCategoryFilter(event.target.value)}
          className="rounded-full border border-line bg-white px-4 py-2 text-sm outline-none transition focus:border-clay"
        >
          {categoryOptions.map((category) => (
            <option key={String(category)} value={String(category)}>
              {category === "todas" ? "Todas as categorias" : category}
            </option>
          ))}
        </select>
      </div>
      {normalizedQuery || statusFilter !== "todos" || categoryFilter !== "todas" ? (
        <div className="flex flex-wrap gap-2 border-b border-line bg-white px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-cocoa/60">
          {normalizedQuery ? <span>Busca: {query}</span> : null}
          {statusFilter !== "todos" ? <span>Status: {statusFilter}</span> : null}
          {categoryFilter !== "todas" ? <span>Categoria: {categoryFilter}</span> : null}
        </div>
      ) : null}
      <table className="min-w-full divide-y divide-line text-sm">
        <thead className="bg-sand">
          <tr className="text-left text-cocoa/75">
            <th className="px-4 py-3 font-semibold">ID</th>
            <th className="px-4 py-3 font-semibold">Cliente</th>
            <th className="px-4 py-3 font-semibold">Telefone</th>
            <th className="px-4 py-3 font-semibold">Categoria</th>
            <th className="px-4 py-3 font-semibold">Status</th>
            <th className="px-4 py-3 font-semibold">Tamanho</th>
            <th className="px-4 py-3 font-semibold">Entrega</th>
            <th className="px-4 py-3 font-semibold">Criado em</th>
            <th className="px-4 py-3 font-semibold">Ação</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line bg-white">
          {rows.map((order) => (
            <tr key={order.id}>
              <td className="px-4 py-3 font-mono text-xs text-cocoa/70">{order.id}</td>
              <td className="px-4 py-3 font-semibold text-ink">{order.cliente_nome || "-"}</td>
              <td className="px-4 py-3 text-cocoa/80">{order.cliente_telefone || "-"}</td>
              <td className="px-4 py-3 text-cocoa/80">{order.categoria || "-"}</td>
              <td className="px-4 py-3 text-cocoa/80">{order.status || "-"}</td>
              <td className="px-4 py-3 text-cocoa/80">{order.tamanho || "-"}</td>
              <td className="px-4 py-3 text-cocoa/80">{order.entrega || "-"}</td>
              <td className="px-4 py-3 text-cocoa/70">{order.criado_em || "-"}</td>
              <td className="px-4 py-3">
                <a
                  href={`/encomendas/${order.id}`}
                  className="rounded-full border border-line bg-white px-3 py-1 text-xs font-semibold text-ink transition hover:bg-sand"
                >
                  Abrir
                </a>
              </td>
            </tr>
          ))}
          {rows.length === 0 ? (
            <tr>
              <td colSpan={9} className="px-4 py-8 text-center text-cocoa/70">
                Nenhuma encomenda encontrada para esse filtro.
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </div>
  );
}

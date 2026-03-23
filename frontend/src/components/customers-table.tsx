"use client";

import { useState } from "react";

import type { CustomerListSnapshot } from "@/lib/panel-types";

type CustomersTableProps = {
  data: CustomerListSnapshot;
  initialQuery?: string;
};

export function CustomersTable({ data, initialQuery = "" }: CustomersTableProps) {
  const [query, setQuery] = useState(initialQuery);
  const normalizedQuery = query.trim().toLowerCase();
  const rows = data.items.filter((customer) => {
    if (!normalizedQuery) {
      return true;
    }
    return [customer.nome, customer.telefone, String(customer.id)]
      .filter(Boolean)
      .join(" ")
      .toLowerCase()
      .includes(normalizedQuery);
  });

  return (
    <div className="overflow-hidden rounded-card border border-line">
      <div className="border-b border-line bg-sand px-4 py-3">
        <input
          value={query}
          onChange={(event) => setQuery(event.target.value)}
          placeholder="Buscar por nome, telefone ou ID"
          className="w-full rounded-full border border-line bg-white px-4 py-2 text-sm outline-none transition focus:border-clay"
        />
      </div>
      {normalizedQuery ? (
        <div className="border-b border-line bg-white px-4 py-2 text-xs font-semibold uppercase tracking-[0.18em] text-cocoa/60">
          Filtro ativo: {query}
        </div>
      ) : null}
      <table className="min-w-full divide-y divide-line text-sm">
        <thead className="bg-sand">
          <tr className="text-left text-cocoa/75">
            <th className="px-4 py-3 font-semibold">ID</th>
            <th className="px-4 py-3 font-semibold">Nome</th>
            <th className="px-4 py-3 font-semibold">Telefone</th>
            <th className="px-4 py-3 font-semibold">Criado em</th>
            <th className="px-4 py-3 font-semibold">Ação</th>
          </tr>
        </thead>
        <tbody className="divide-y divide-line bg-white">
          {rows.map((customer) => (
            <tr key={customer.id}>
              <td className="px-4 py-3 font-mono text-xs text-cocoa/70">{customer.id}</td>
              <td className="px-4 py-3 font-semibold text-ink">{customer.nome}</td>
              <td className="px-4 py-3 text-cocoa/80">{customer.telefone}</td>
              <td className="px-4 py-3 text-cocoa/70">{customer.criado_em || "-"}</td>
              <td className="px-4 py-3">
                <a
                  href={`/clientes/${customer.id}`}
                  className="rounded-full border border-line bg-white px-3 py-1 text-xs font-semibold text-ink transition hover:bg-sand"
                >
                  Abrir
                </a>
              </td>
            </tr>
          ))}
          {rows.length === 0 ? (
            <tr>
              <td colSpan={5} className="px-4 py-8 text-center text-cocoa/70">
                Nenhum cliente encontrado para esse filtro.
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </div>
  );
}

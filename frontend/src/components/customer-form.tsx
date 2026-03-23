"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

import type { CustomerDetailsSnapshot } from "@/lib/panel-types";

type CustomerFormProps = {
  mode: "create" | "edit";
  customer?: CustomerDetailsSnapshot["item"];
};

export function CustomerForm({ mode, customer }: CustomerFormProps) {
  const router = useRouter();
  const [nome, setNome] = useState(customer?.nome || "");
  const [telefone, setTelefone] = useState(customer?.telefone || "");
  const [feedback, setFeedback] = useState("");
  const [isPending, startTransition] = useTransition();

  function handleSubmit() {
    setFeedback("");
    startTransition(async () => {
      const response = await fetch(
        mode === "create" ? "/api/customers" : `/api/customers/${customer?.id}`,
        {
          method: mode === "create" ? "POST" : "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ nome, telefone }),
        },
      );
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        setFeedback(payload.detail ? `Falha: ${payload.detail}` : "Falha ao salvar cliente.");
        return;
      }
      if (mode === "create" && payload.item?.id) {
        router.push(`/clientes/${payload.item.id}`);
        return;
      }
      setFeedback("Cliente atualizado com sucesso.");
      router.refresh();
    });
  }

  function handleDelete() {
    if (!customer?.id || !window.confirm("Deseja realmente excluir este cliente?")) {
      return;
    }
    setFeedback("");
    startTransition(async () => {
      const response = await fetch(`/api/customers/${customer.id}`, { method: "DELETE" });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        setFeedback(payload.detail ? `Falha: ${payload.detail}` : "Falha ao excluir cliente.");
        return;
      }
      router.push("/clientes");
    });
  }

  return (
    <section className="rounded-panel border border-line bg-paper/95 p-5 shadow-panel">
      <div className="grid gap-4">
        <label className="block">
          <span className="mb-2 block text-sm font-semibold text-ink">Nome</span>
          <input
            value={nome}
            onChange={(event) => setNome(event.target.value)}
            className="w-full rounded-2xl border border-line bg-white px-4 py-3 text-sm outline-none transition focus:border-clay"
            placeholder="Nome do cliente"
            disabled={isPending}
          />
        </label>
        <label className="block">
          <span className="mb-2 block text-sm font-semibold text-ink">Telefone</span>
          <input
            value={telefone}
            onChange={(event) => setTelefone(event.target.value)}
            className="w-full rounded-2xl border border-line bg-white px-4 py-3 text-sm outline-none transition focus:border-clay"
            placeholder="5511999999999"
            disabled={isPending}
          />
        </label>
      </div>

      <div className="mt-6 flex flex-wrap gap-3">
        <button
          type="button"
          onClick={handleSubmit}
          disabled={isPending}
          className="rounded-full bg-ink px-5 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isPending ? "Salvando..." : mode === "create" ? "Criar cliente" : "Salvar cliente"}
        </button>
        {mode === "edit" && customer?.id ? (
          <button
            type="button"
            onClick={handleDelete}
            disabled={isPending}
            className="rounded-full border border-[#dcb7b2] bg-[#fff4f2] px-5 py-3 text-sm font-semibold text-[#a63d22] transition hover:bg-[#fde6df] disabled:cursor-not-allowed disabled:opacity-60"
          >
            Excluir cliente
          </button>
        ) : null}
      </div>

      {feedback ? <p className="mt-4 text-sm text-cocoa/75">{feedback}</p> : null}
    </section>
  );
}

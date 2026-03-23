"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

const STATUS_OPTIONS = [
  { value: "pendente", label: "Pendente" },
  { value: "em_preparo", label: "Em preparo" },
  { value: "agendada", label: "Agendada" },
  { value: "retirada", label: "Retirada" },
  { value: "entregue", label: "Entregue" },
];

type OrderStatusActionsProps = {
  orderId: number;
  currentStatus: string | null;
};

export function OrderStatusActions({ orderId, currentStatus }: OrderStatusActionsProps) {
  const router = useRouter();
  const [selectedStatus, setSelectedStatus] = useState(currentStatus || "pendente");
  const [feedback, setFeedback] = useState<string>("");
  const [isPending, startTransition] = useTransition();

  function handleSubmit() {
    setFeedback("");
    startTransition(async () => {
      const response = await fetch(`/api/orders/${orderId}/status`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ status: selectedStatus }),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        setFeedback(payload.detail ? `Falha: ${payload.detail}` : "Falha ao atualizar status.");
        return;
      }
      setFeedback("Status atualizado com sucesso.");
      router.refresh();
    });
  }

  return (
    <div className="mt-4 rounded-card border border-line bg-white p-4">
      <p className="text-sm font-semibold text-ink">Atualizar status operacional</p>
      <div className="mt-3 flex flex-col gap-3 sm:flex-row">
        <select
          value={selectedStatus}
          onChange={(event) => setSelectedStatus(event.target.value)}
          className="rounded-full border border-line bg-paper px-4 py-2 text-sm outline-none transition focus:border-clay"
          disabled={isPending}
        >
          {STATUS_OPTIONS.map((option) => (
            <option key={option.value} value={option.value}>
              {option.label}
            </option>
          ))}
        </select>
        <button
          type="button"
          onClick={handleSubmit}
          disabled={isPending}
          className="rounded-full bg-ink px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isPending ? "Atualizando..." : "Salvar status"}
        </button>
      </div>
      {feedback ? <p className="mt-3 text-sm text-cocoa/75">{feedback}</p> : null}
    </div>
  );
}

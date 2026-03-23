"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

type OrderDeleteActionProps = {
  orderId: number;
};

export function OrderDeleteAction({ orderId }: OrderDeleteActionProps) {
  const router = useRouter();
  const [feedback, setFeedback] = useState("");
  const [isPending, startTransition] = useTransition();

  function handleDelete() {
    if (!window.confirm("Deseja realmente excluir esta encomenda?")) {
      return;
    }
    setFeedback("");
    startTransition(async () => {
      const response = await fetch(`/api/orders/${orderId}`, { method: "DELETE" });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        setFeedback(payload.detail ? `Falha: ${payload.detail}` : "Falha ao excluir encomenda.");
        return;
      }
      router.push("/encomendas");
    });
  }

  return (
    <div className="mt-4 rounded-card border border-[#dcb7b2] bg-[#fff4f2] p-4">
      <p className="text-sm font-semibold text-[#a63d22]">Zona de exclusão</p>
      <button
        type="button"
        onClick={handleDelete}
        disabled={isPending}
        className="mt-3 rounded-full bg-[#a63d22] px-4 py-2 text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
      >
        {isPending ? "Excluindo..." : "Excluir encomenda"}
      </button>
      {feedback ? <p className="mt-3 text-sm text-[#8d2941]">{feedback}</p> : null}
    </div>
  );
}

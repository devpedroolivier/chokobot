"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

const CATEGORY_OPTIONS = [
  { value: "", label: "Selecione" },
  { value: "tradicional", label: "Tradicional" },
  { value: "ingles", label: "Gourmet Inglês" },
  { value: "redondo", label: "Gourmet Redondo" },
  { value: "torta", label: "Torta" },
  { value: "simples", label: "Linha Simples" },
];

export function OrderForm() {
  const router = useRouter();
  const [form, setForm] = useState({
    nome: "",
    telefone: "",
    produto: "",
    categoria: "",
    linha: "tradicional",
    tamanho: "",
    massa: "",
    recheio: "",
    mousse: "",
    adicional: "",
    fruta_ou_nozes: "",
    valor_total: "",
    data_entrega: "",
    horario: "",
    horario_retirada: "",
  });
  const [feedback, setFeedback] = useState("");
  const [isPending, startTransition] = useTransition();

  function updateField(name: keyof typeof form, value: string) {
    setForm((current) => ({ ...current, [name]: value }));
  }

  function handleSubmit() {
    setFeedback("");
    startTransition(async () => {
      const response = await fetch("/api/orders", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const payload = await response.json().catch(() => ({}));
      if (!response.ok) {
        setFeedback(payload.detail ? `Falha: ${payload.detail}` : "Falha ao criar encomenda.");
        return;
      }
      if (payload.id) {
        router.push(`/encomendas/${payload.id}`);
        return;
      }
      setFeedback("Encomenda criada com sucesso.");
    });
  }

  return (
    <section className="rounded-panel border border-line bg-paper/95 p-5 shadow-panel">
      <div className="grid gap-4 md:grid-cols-2">
        <label className="block">
          <span className="mb-2 block text-sm font-semibold text-ink">Nome do cliente</span>
          <input value={form.nome} onChange={(e) => updateField("nome", e.target.value)} className="w-full rounded-2xl border border-line bg-white px-4 py-3 text-sm outline-none transition focus:border-clay" disabled={isPending} />
        </label>
        <label className="block">
          <span className="mb-2 block text-sm font-semibold text-ink">Telefone</span>
          <input value={form.telefone} onChange={(e) => updateField("telefone", e.target.value)} className="w-full rounded-2xl border border-line bg-white px-4 py-3 text-sm outline-none transition focus:border-clay" disabled={isPending} />
        </label>
        <label className="block">
          <span className="mb-2 block text-sm font-semibold text-ink">Categoria</span>
          <select value={form.categoria} onChange={(e) => updateField("categoria", e.target.value)} className="w-full rounded-2xl border border-line bg-white px-4 py-3 text-sm outline-none transition focus:border-clay" disabled={isPending}>
            {CATEGORY_OPTIONS.map((option) => (
              <option key={option.value || "empty"} value={option.value}>{option.label}</option>
            ))}
          </select>
        </label>
        <label className="block">
          <span className="mb-2 block text-sm font-semibold text-ink">Produto</span>
          <input value={form.produto} onChange={(e) => updateField("produto", e.target.value)} className="w-full rounded-2xl border border-line bg-white px-4 py-3 text-sm outline-none transition focus:border-clay" disabled={isPending} />
        </label>
        <label className="block">
          <span className="mb-2 block text-sm font-semibold text-ink">Tamanho</span>
          <input value={form.tamanho} onChange={(e) => updateField("tamanho", e.target.value)} className="w-full rounded-2xl border border-line bg-white px-4 py-3 text-sm outline-none transition focus:border-clay" disabled={isPending} />
        </label>
        <label className="block">
          <span className="mb-2 block text-sm font-semibold text-ink">Valor total</span>
          <input value={form.valor_total} onChange={(e) => updateField("valor_total", e.target.value)} className="w-full rounded-2xl border border-line bg-white px-4 py-3 text-sm outline-none transition focus:border-clay" placeholder="120,00" disabled={isPending} />
        </label>
        <label className="block">
          <span className="mb-2 block text-sm font-semibold text-ink">Data de entrega</span>
          <input type="date" value={form.data_entrega} onChange={(e) => updateField("data_entrega", e.target.value)} className="w-full rounded-2xl border border-line bg-white px-4 py-3 text-sm outline-none transition focus:border-clay" disabled={isPending} />
        </label>
        <label className="block">
          <span className="mb-2 block text-sm font-semibold text-ink">Horário</span>
          <input value={form.horario} onChange={(e) => updateField("horario", e.target.value)} className="w-full rounded-2xl border border-line bg-white px-4 py-3 text-sm outline-none transition focus:border-clay" placeholder="14:00" disabled={isPending} />
        </label>
        <label className="block">
          <span className="mb-2 block text-sm font-semibold text-ink">Massa</span>
          <input value={form.massa} onChange={(e) => updateField("massa", e.target.value)} className="w-full rounded-2xl border border-line bg-white px-4 py-3 text-sm outline-none transition focus:border-clay" disabled={isPending} />
        </label>
        <label className="block">
          <span className="mb-2 block text-sm font-semibold text-ink">Recheio</span>
          <input value={form.recheio} onChange={(e) => updateField("recheio", e.target.value)} className="w-full rounded-2xl border border-line bg-white px-4 py-3 text-sm outline-none transition focus:border-clay" disabled={isPending} />
        </label>
        <label className="block">
          <span className="mb-2 block text-sm font-semibold text-ink">Mousse</span>
          <input value={form.mousse} onChange={(e) => updateField("mousse", e.target.value)} className="w-full rounded-2xl border border-line bg-white px-4 py-3 text-sm outline-none transition focus:border-clay" disabled={isPending} />
        </label>
        <label className="block">
          <span className="mb-2 block text-sm font-semibold text-ink">Adicional</span>
          <input value={form.adicional} onChange={(e) => updateField("adicional", e.target.value)} className="w-full rounded-2xl border border-line bg-white px-4 py-3 text-sm outline-none transition focus:border-clay" disabled={isPending} />
        </label>
      </div>
      <div className="mt-6">
        <button
          type="button"
          onClick={handleSubmit}
          disabled={isPending}
          className="rounded-full bg-ink px-5 py-3 text-sm font-semibold text-white transition hover:opacity-90 disabled:cursor-not-allowed disabled:opacity-60"
        >
          {isPending ? "Criando..." : "Criar encomenda"}
        </button>
      </div>
      {feedback ? <p className="mt-4 text-sm text-cocoa/75">{feedback}</p> : null}
    </section>
  );
}

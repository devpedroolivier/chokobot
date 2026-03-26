import type { ReactNode } from "react";

import { AdminNav } from "@/components/admin-nav";

export function toneClasses(tone?: string): string {
  switch (tone) {
    case "danger":
      return "bg-rose text-[#8d2941]";
    case "warning":
      return "bg-honey text-[#8a5b00]";
    case "success":
      return "bg-[#dff0e7] text-[#166534]";
    case "accent":
      return "bg-blush text-clay";
    default:
      return "bg-mist text-cocoa";
  }
}

export function toneTextClasses(tone?: string): string {
  switch (tone) {
    case "danger":
      return "text-[#8d2941]";
    case "warning":
      return "text-[#8a5b00]";
    case "success":
      return "text-[#166534]";
    case "accent":
      return "text-clay";
    default:
      return "text-cocoa/65";
  }
}

export function stageClasses(stageClass: string): string {
  if (stageClass.includes("cake")) return "bg-[#fde6df] text-[#a63d22]";
  if (stageClass.includes("sweet")) return "bg-[#ffe7ef] text-[#a11d48]";
  if (stageClass.includes("cafe")) return "bg-[#f4ead8] text-[#8a5b00]";
  if (stageClass.includes("gift")) return "bg-[#efe2ff] text-[#6d28d9]";
  if (stageClass.includes("delivery")) return "bg-sky text-[#1d4ed8]";
  if (stageClass.includes("human")) return "bg-mist text-cocoa";
  return "bg-mist text-cocoa";
}

export function riskFlagLabel(flag: string): string {
  switch (flag) {
    case "rascunho_ia":
      return "Rascunho IA";
    case "nao_confirmado":
      return "Nao confirmado";
    case "aguardando_confirmacao":
      return "Aguardando confirmacao";
    case "dados_incompletos":
      return "Dados incompletos";
    default:
      return flag.replaceAll("_", " ");
  }
}

export function customerHref(phone: string): string {
  return `/clientes?q=${encodeURIComponent(phone)}`;
}

export function conversationHref(phone: string): string {
  return `/conversas?phone=${encodeURIComponent(phone)}`;
}

export function orderHref(orderId?: number | null): string {
  return orderId ? `/encomendas/${orderId}` : "/encomendas";
}

export function EmptyState({ message }: { message: string }) {
  return (
    <div className="rounded-[24px] border border-dashed border-line bg-white/70 px-4 py-8 text-center text-sm text-cocoa/70">
      {message}
    </div>
  );
}

export function KPI({
  label,
  value,
  hint,
  tone,
}: {
  label: string;
  value: string;
  hint: string;
  tone?: string;
}) {
  return (
    <article className="rounded-[28px] border border-line bg-paper/90 p-5 shadow-panel">
      <div className="flex items-start justify-between gap-3">
        <div>
          <p className="text-[11px] font-semibold uppercase tracking-[0.18em] text-cocoa/60">{label}</p>
          <p className="mt-3 text-3xl font-black">{value}</p>
        </div>
        {tone ? <span className={`rounded-full px-3 py-1 text-xs font-semibold ${toneClasses(tone)}`}>{label}</span> : null}
      </div>
      <p className="mt-2 text-sm text-cocoa/70">{hint}</p>
    </article>
  );
}

export function SectionTitle({
  eyebrow,
  title,
  tone,
}: {
  eyebrow: string;
  title: string;
  tone?: string;
}) {
  return (
    <div>
      <p className={`text-xs font-semibold uppercase tracking-[0.18em] ${toneTextClasses(tone)}`}>{eyebrow}</p>
      <h2 className="mt-1 text-2xl font-bold">{title}</h2>
    </div>
  );
}

export function FilterPanel({
  children,
  summary,
}: {
  children: ReactNode;
  summary?: ReactNode;
}) {
  return (
    <section className="mt-6 rounded-[30px] border border-line bg-white/78 p-4 shadow-panel">
      {children}
      {summary ? <div className="mt-4 flex flex-wrap items-center justify-between gap-3 text-sm text-cocoa/72">{summary}</div> : null}
    </section>
  );
}

export function PageHeader({
  eyebrow,
  title,
  description,
  referenceDate,
  generatedAt,
  actions,
}: {
  eyebrow: string;
  title: string;
  description: string;
  referenceDate: string;
  generatedAt: string;
  actions?: ReactNode;
}) {
  return (
    <header className="rounded-[34px] border border-line bg-paper/92 px-6 py-6 shadow-panel backdrop-blur">
      <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-cocoa/65">{eyebrow}</p>
          <h1 className="mt-2 text-3xl font-black tracking-tight sm:text-5xl">{title}</h1>
          <p className="mt-3 max-w-3xl text-sm text-cocoa/74">{description}</p>
          <p className="mt-2 text-xs uppercase tracking-[0.16em] text-clay">
            referência {referenceDate} • atualizado às {generatedAt}
          </p>
        </div>
        {actions ? <div className="flex flex-wrap gap-3">{actions}</div> : null}
      </div>
    </header>
  );
}

export function WarningBanner({ warning }: { warning?: string }) {
  if (!warning) {
    return null;
  }

  return (
    <section className="mt-6 rounded-[24px] border border-[#efc2a8] bg-[#fff6f1] px-5 py-4 text-sm text-cocoa shadow-panel">
      {warning}
    </section>
  );
}

export function AdminWorkspace({ children }: { children: ReactNode }) {
  return (
    <main className="mx-auto max-w-[1500px] px-4 py-6 sm:px-6 lg:px-8">
      <AdminNav />
      {children}
    </main>
  );
}

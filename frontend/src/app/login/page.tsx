import { redirect } from "next/navigation";

import { getAdminSession, getAdminSessionConfigError } from "@/lib/admin-session";

type LoginPageProps = {
  searchParams?: Promise<{ error?: string; next?: string; logged_out?: string }>;
};

const ERROR_MESSAGES: Record<string, string> = {
  session_required: "Faça login para acessar o admin moderno.",
  missing_credentials: "Informe usuário e senha do painel.",
  invalid_credentials: "Credenciais inválidas para o painel.",
  backend_not_configured: "PANEL_BACKEND_URL não está configurado no frontend.",
  session_secret_not_configured: "ADMIN_SESSION_SECRET não está configurado no frontend.",
  session_creation_failed: "Não foi possível criar a sessão segura do admin.",
  backend_http_503: "O backend recusou a autenticação porque o painel está indisponível ou mal configurado.",
};

function resolveMessage(error?: string, loggedOut?: string): string | null {
  if (loggedOut === "1") {
    return "Sessão encerrada com sucesso.";
  }
  if (!error) {
    return null;
  }
  return ERROR_MESSAGES[error] || "Não foi possível concluir o login no admin.";
}

export default async function LoginPage({ searchParams }: LoginPageProps) {
  const session = await getAdminSession();
  if (session) {
    redirect("/");
  }

  const params = (await searchParams) || {};
  const configError = getAdminSessionConfigError();
  const message = resolveMessage(params.error || configError || undefined, params.logged_out);
  const nextPath = params.next && params.next.startsWith("/") && !params.next.startsWith("//")
    ? params.next
    : "/";

  return (
    <main className="mx-auto flex min-h-screen max-w-6xl items-center px-4 py-10 sm:px-6 lg:px-8">
      <section className="grid w-full gap-6 lg:grid-cols-[1.1fr_0.9fr]">
        <article className="rounded-panel border border-line bg-paper/95 p-8 shadow-panel">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-cocoa/70">
            Chokodelícia Admin
          </p>
          <h1 className="mt-3 text-4xl font-black tracking-tight text-ink sm:text-5xl">
            Painel moderno com sessão segura
          </h1>
          <p className="mt-4 max-w-2xl text-sm leading-6 text-cocoa/75">
            O acesso do Next.js agora passa por sessão HTTP-only no próprio admin moderno.
            As credenciais do painel não ficam expostas no browser e as ações operacionais
            seguem protegidas antes do rollout completo do frontend novo.
          </p>
          <div className="mt-8 grid gap-4 sm:grid-cols-3">
            <div className="rounded-card border border-line bg-white p-4">
              <p className="text-sm font-bold text-ink">Dashboard</p>
              <p className="mt-2 text-sm text-cocoa/70">Atendimento, sync e operação no mesmo fluxo.</p>
            </div>
            <div className="rounded-card border border-line bg-white p-4">
              <p className="text-sm font-bold text-ink">Pedidos</p>
              <p className="mt-2 text-sm text-cocoa/70">Ações de status e leitura operacional por etapa.</p>
            </div>
            <div className="rounded-card border border-line bg-white p-4">
              <p className="text-sm font-bold text-ink">Clientes</p>
              <p className="mt-2 text-sm text-cocoa/70">Busca rápida por telefone para acompanhar o atendimento.</p>
            </div>
          </div>
        </article>

        <article className="rounded-panel border border-line bg-white p-8 shadow-panel">
          <p className="text-xs font-semibold uppercase tracking-[0.24em] text-cocoa/70">Login</p>
          <h2 className="mt-2 text-2xl font-bold text-ink">Entrar no admin moderno</h2>
          <p className="mt-2 text-sm text-cocoa/70">
            Use as mesmas credenciais do painel protegido pelo FastAPI.
          </p>

          {message ? (
            <div className="mt-6 rounded-card border border-[#efc2a8] bg-[#fff6f1] px-4 py-3 text-sm text-cocoa">
              {message}
            </div>
          ) : null}

          <form action="/api/auth/login" method="post" className="mt-6 space-y-4">
            <input type="hidden" name="next" value={nextPath} />
            <label className="block">
              <span className="mb-2 block text-sm font-semibold text-ink">Usuário</span>
              <input
                name="username"
                type="text"
                autoComplete="username"
                className="w-full rounded-2xl border border-line bg-paper px-4 py-3 text-sm outline-none transition focus:border-clay"
                placeholder="admin"
              />
            </label>
            <label className="block">
              <span className="mb-2 block text-sm font-semibold text-ink">Senha</span>
              <input
                name="password"
                type="password"
                autoComplete="current-password"
                className="w-full rounded-2xl border border-line bg-paper px-4 py-3 text-sm outline-none transition focus:border-clay"
                placeholder="••••••••"
              />
            </label>
            <button
              type="submit"
              className="w-full rounded-full bg-ink px-4 py-3 text-sm font-semibold text-white transition hover:opacity-90"
            >
              Entrar no painel
            </button>
          </form>
        </article>
      </section>
    </main>
  );
}

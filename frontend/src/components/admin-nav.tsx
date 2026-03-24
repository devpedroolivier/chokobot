const links = [
  { href: "/", label: "Dashboard" },
  { href: "/operacoes", label: "Operações" },
  { href: "/conversas", label: "Conversas" },
  { href: "/clientes", label: "Clientes" },
  { href: "/encomendas", label: "Encomendas" }
];

export function AdminNav() {
  return (
    <nav className="mb-6 flex flex-wrap items-center justify-between gap-3">
      <div className="flex flex-wrap gap-2">
        {links.map((link) => (
          <a
            key={link.href}
            href={link.href}
            className="rounded-full border border-line bg-white px-4 py-2 text-sm font-semibold text-ink transition hover:bg-sand"
          >
            {link.label}
          </a>
        ))}
      </div>
      <form action="/api/auth/logout" method="post">
        <button
          type="submit"
          className="rounded-full border border-line bg-paper px-4 py-2 text-sm font-semibold text-cocoa transition hover:bg-sand"
        >
          Sair
        </button>
      </form>
    </nav>
  );
}

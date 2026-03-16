from __future__ import annotations

import os
from pathlib import Path

from app.security import ai_learning_enabled, security_audit
from app.services.precos import KIT_FESTOU_PRECO, TRADICIONAL_BASE


class LocalCatalogGateway:
    def _learnings_path(self) -> Path:
        return Path(os.getenv("AI_LEARNINGS_PATH", "app/ai/knowledge/learnings.md"))

    def _load_menu_text(self) -> str:
        return Path("app/ai/knowledge/menus.md").read_text(encoding="utf-8")

    def _normalize_category(self, category: str | None) -> str:
        raw = (category or "todas").strip().lower()
        aliases = {
            "todas": "todas",
            "geral": "todas",
            "menu": "todas",
            "completo": "todas",
            "pronta entrega": "pronta_entrega",
            "pronta_entrega": "pronta_entrega",
            "pronta": "pronta_entrega",
            "vitrine": "pronta_entrega",
            "cafeteria": "pronta_entrega",
            "doces": "pronta_entrega",
            "avulsos": "pronta_entrega",
            "encomenda": "encomendas",
            "encomendas": "encomendas",
            "personalizado": "encomendas",
            "personalizados": "encomendas",
            "bolo personalizado": "encomendas",
            "bolos": "encomendas",
            "tortas": "encomendas",
            "cestas": "encomendas",
        }
        return aliases.get(raw, "todas")

    def _build_ready_delivery_summary(self) -> str:
        b3 = TRADICIONAL_BASE["B3"]
        b4 = TRADICIONAL_BASE["B4"]
        return (
            "🛍️ Pronta Entrega\n"
            "- Mostrar apenas itens prontos do dia, cafeteria e bolos de pronta entrega.\n"
            "- Nao misturar com encomendas personalizadas.\n\n"
            "🎂 Bolos Pronta Entrega\n"
            f"- B3 (ate {b3['serve']} pessoas): R${b3['preco']:.2f} | sabor padrao: Mesclado com Brigadeiro + Ninho\n"
            f"- B4 (ate {b4['serve']} pessoas): R${b4['preco']:.2f} | sabor padrao: Mesclado com Brigadeiro + Ninho\n"
            f"🎉 Kit Festou opcional: +R${KIT_FESTOU_PRECO:.2f}\n"
            "- Regra atual: pronta entrega segue como retirada na loja no fluxo interno.\n\n"
            "☕ Cafeteria e Vitrine\n"
            "- Cardapio Cafeteria: http://bit.ly/44ZlKlZ\n"
            "- A vitrine pode variar no dia.\n"
            "- Entregas sao realizadas ate 17:30.\n"
        )

    def _slice_section(self, text: str, start: str, end: str | None = None) -> str:
        start_idx = text.find(start)
        if start_idx == -1:
            return ""
        end_idx = text.find(end, start_idx) if end else -1
        if end_idx == -1:
            return text[start_idx:].strip()
        return text[start_idx:end_idx].strip()

    def get_menu(self, category: str = "todas") -> str:
        try:
            text = self._load_menu_text()
            normalized = self._normalize_category(category)

            if normalized == "pronta_entrega":
                return self._build_ready_delivery_summary()

            if normalized == "encomendas":
                encomendas = self._slice_section(text, "## Encomendas", "## Entregas e Pagamento")
                pagamentos = self._slice_section(text, "## Entregas e Pagamento")
                return f"{encomendas}\n\n{pagamentos}".strip()

            return text
        except Exception as exc:
            return "Erro ao carregar cardapio: " + str(exc)

    def get_learnings(self) -> str:
        try:
            with self._learnings_path().open("r", encoding="utf-8") as handle:
                return handle.read()
        except Exception:
            return ""

    def save_learning(self, aprendizado: str) -> str:
        if not ai_learning_enabled():
            security_audit("ai_learning_blocked")
            return "Aprendizado persistente desativado neste ambiente."

        path = self._learnings_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(f"- {aprendizado}\n")
        security_audit("ai_learning_saved")
        return "Aprendizado salvo com sucesso! Vou me lembrar disso."

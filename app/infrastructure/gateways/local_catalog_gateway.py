from __future__ import annotations

from pathlib import Path

from app.security import ai_learning_enabled, security_audit
from app.services.precos import KIT_FESTOU_PRECO, TRADICIONAL_BASE
from app.services.store_schedule import GIFT_CATALOG_SUMMARY, READY_DELIVERY_SUMMARY, STORE_HOURS_SUMMARY
from app.settings import get_settings


class LocalCatalogGateway:
    def _learnings_path(self) -> Path:
        return Path(get_settings().ai_learnings_path)

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
            "presentes": "encomendas",
            "flores": "encomendas",
        }
        return aliases.get(raw, "todas")

    def _build_ready_delivery_summary(self) -> str:
        b3 = TRADICIONAL_BASE["B3"]
        b4 = TRADICIONAL_BASE["B4"]
        cafeteria_url = get_settings().cafeteria_url
        return (
            "🛍️ Pronta Entrega\n"
            f"- Antes de seguir, identifique qual pronta entrega o cliente quer: {READY_DELIVERY_SUMMARY}.\n"
            "- Mostrar apenas itens prontos do dia.\n"
            "- Nao misturar com encomendas personalizadas.\n"
            "- Se o detalhe nao estiver cadastrado aqui, nao inventar: informar que a disponibilidade varia no dia.\n\n"
            "🎂 Bolos Pronta Entrega\n"
            f"- B3 (ate {b3['serve']} pessoas): R${b3['preco']:.2f} | sabor padrao: Mesclado com Brigadeiro + Ninho\n"
            f"- B4 (ate {b4['serve']} pessoas): R${b4['preco']:.2f} | sabor padrao: Mesclado com Brigadeiro + Ninho\n"
            "- Regra atual: pronta entrega segue como retirada na loja no fluxo interno.\n\n"
            "🎉 Kit Festou\n"
            f"- 25 brigadeiros + 1 balao personalizado: +R${KIT_FESTOU_PRECO:.2f}\n"
            "- Confirme se o cliente quer somente o Kit Festou ou bolo com Kit Festou.\n\n"
            "🥚 Ovos Pronta Entrega\n"
            "- Identifique primeiro se o cliente quer ovos pronta entrega.\n"
            "- Sabores e disponibilidade variam no dia.\n"
            "- Catalogo oficial de Pascoa: https://pascoachoko.goomer.app\n\n"
            "☕ Cafeteria e Vitrine\n"
            f"- Cardapio Cafeteria: {cafeteria_url}\n"
            "- A vitrine pode variar no dia.\n"
            f"- Horario de funcionamento: {STORE_HOURS_SUMMARY}\n"
            "- Nao fazemos pedidos, retiradas ou encomendas para domingo.\n"
            "- Entregas sao realizadas ate 17:30.\n"
            f"\n🎁 Presentes\n- Oferecemos {GIFT_CATALOG_SUMMARY}.\n"
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

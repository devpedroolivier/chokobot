from __future__ import annotations

import json
import re
import unicodedata
from difflib import SequenceMatcher
from functools import lru_cache
from pathlib import Path

from app.security import ai_learning_enabled, security_audit
from app.services.commercial_rules import (
    CROISSANT_PREP_MINUTES,
    DELIVERY_CUTOFF_LABEL,
    STORE_OPERATION_RULE_LINE,
    SUNDAY_RULE_LINE,
)
from app.services.precos import KIT_FESTOU_PRECO, LINHA_SIMPLES, TRADICIONAL_BASE
from app.services.store_schedule import GIFT_CATALOG_SUMMARY, READY_DELIVERY_SUMMARY, STORE_HOURS_SUMMARY
from app.settings import get_settings


CATALOG_LABELS = {
    "cafeteria": "Cafeteria",
    "encomendas": "Encomendas",
    "presentes": "Presentes Especiais",
    "pascoa": "Páscoa",
    "pascoa_presentes": "Mimos e Presentes de Páscoa",
}

SECTION_LABELS = {
    "salgados_e_lanches": "Salgados e Lanches",
    "sobremesas": "Sobremesas",
    "cafes_quentes": "Cafés Quentes",
    "gelados_e_bebidas": "Gelados e Bebidas",
    "doceria_cafeteria": "Doceria da Cafeteria",
    "lancamentos_premium": "Lançamentos Premium",
    "ovos_especiais": "Ovos Especiais",
    "ovos_trufados": "Ovos Trufados",
    "ovos_crocantes": "Ovos Crocantes",
    "ovos_de_colher": "Ovos de Colher",
    "ovos_verticais": "Ovos Verticais",
    "trios_de_colher": "Trios de Colher",
    "boxes": "Boxes",
    "ovos_tablete": "Ovos Tablete",
    "mini_ovos": "Mini Ovos",
    "barras_e_cakes": "Barras e Cakes",
    "presentes": "Presentes",
    "pelucias": "Pelúcias",
    "linha_simples": "Linha Simples",
    "cestas_box": "Cestas Box",
    "caixinhas": "Caixinhas",
    "flores": "Flores",
}

CATALOG_ITEM_RUNTIME_NOTES = {
    ("cafeteria", "Croissant"): f"Tempo medio de preparo: {CROISSANT_PREP_MINUTES} minutos.",
}

LOOKUP_STOPWORDS = {
    "a",
    "ao",
    "aos",
    "as",
    "com",
    "da",
    "das",
    "de",
    "do",
    "dos",
    "e",
    "em",
    "o",
    "os",
    "ou",
    "para",
    "por",
    "um",
    "uma",
    "tem",
    "teria",
    "vcs",
    "voce",
    "voces",
    "quero",
    "queria",
    "gostaria",
    "manda",
    "me",
    "ver",
    "mostrar",
    "mostra",
    "menu",
    "cardapio",
    "catalogo",
    "opcao",
    "opcoes",
    "sabor",
    "sabores",
    "valor",
    "valores",
    "preco",
    "precos",
    "grama",
    "gramas",
    "peso",
    "item",
    "itens",
    "disponivel",
    "disponiveis",
    "bolo",
}

LINE_SIMPLE_LOOKUP_ALIASES = {
    "linha simples",
    "bolo simples",
    "simples",
    "bolo caseiro",
    "caseiro",
    "caseirinho",
    "bolo caseirinho",
}


def _format_brl(value: float | int | None) -> str:
    if value is None:
        return ""
    return f"R${value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")


def _normalize_text(value: str | None) -> str:
    normalized = unicodedata.normalize("NFKD", value or "")
    without_accents = "".join(char for char in normalized if not unicodedata.combining(char))
    return re.sub(r"\s+", " ", without_accents).strip().casefold()


def _tokenize_lookup(value: str | None) -> list[str]:
    tokens = re.findall(r"[a-z0-9]+", _normalize_text(value))
    return [token for token in tokens if token and token not in LOOKUP_STOPWORDS]


def _fuzzy_token_match(token: str, candidates: set[str], *, threshold: float = 0.82) -> tuple[bool, float]:
    if token in candidates:
        return True, 1.0
    best = 0.0
    for candidate in candidates:
        ratio = SequenceMatcher(None, token, candidate).ratio()
        if ratio > best:
            best = ratio
        if ratio >= threshold:
            return True, ratio
    return False, best


@lru_cache(maxsize=1)
def _load_structured_catalog_items() -> tuple[dict, ...]:
    catalog_paths = (
        Path("app/ai/knowledge/catalogo_produtos.json"),
        Path("app/ai/knowledge/catalogo_presentes_regulares.json"),
    )
    items: list[dict] = []
    for catalog_path in catalog_paths:
        payload = json.loads(catalog_path.read_text(encoding="utf-8"))
        items.extend(payload.get("items", []))
    return tuple(items)


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
            "cafeteria": "cafeteria",
            "doces": "pronta_entrega",
            "avulsos": "pronta_entrega",
            "cardapio cafeteria": "cafeteria",
            "menu cafeteria": "cafeteria",
            "cafeteria_detalhada": "cafeteria",
            "cafeteria_detalhado": "cafeteria",
            "cafeteria_menu": "cafeteria",
            "páscoa": "pascoa",
            "pascoa": "pascoa",
            "ovos de pascoa": "pascoa",
            "cardapio de pascoa": "pascoa",
            "menu de pascoa": "pascoa",
            "pascoa_presentes": "pascoa_presentes",
            "mimos pascoa": "pascoa_presentes",
            "presentes pascoa": "pascoa_presentes",
            "presente pascoa": "pascoa_presentes",
            "mimos": "pascoa_presentes",
            "presente de pascoa": "pascoa_presentes",
            "presentes de pascoa": "pascoa_presentes",
            "presentes especiais": "presentes",
            "encomenda": "encomendas",
            "encomendas": "encomendas",
            "personalizado": "encomendas",
            "personalizados": "encomendas",
            "bolo personalizado": "encomendas",
            "bolos": "encomendas",
            "tortas": "encomendas",
            "cestas": "presentes",
            "presentes": "presentes",
            "flores": "presentes",
            "cestas box": "presentes",
            "cesta box": "presentes",
            "caixinha de chocolate": "presentes",
        }
        return aliases.get(raw, "todas")

    def _humanize_catalog(self, catalog: str) -> str:
        return CATALOG_LABELS.get(catalog, catalog.replace("_", " ").title())

    def _humanize_section(self, section: str) -> str:
        return SECTION_LABELS.get(section, section.replace("_", " ").title())

    def _runtime_note_for_item(self, catalog: str, name: str) -> str | None:
        return CATALOG_ITEM_RUNTIME_NOTES.get((catalog, name))

    def _catalog_scope(self, catalog: str) -> tuple[str, ...]:
        normalized = _normalize_text(catalog or "auto")
        aliases = {
            "auto": ("cafeteria", "pascoa", "pascoa_presentes"),
            "todos": ("cafeteria", "pascoa", "pascoa_presentes", "presentes"),
            "todas": ("cafeteria", "pascoa", "pascoa_presentes", "presentes"),
            "pronta_entrega": ("cafeteria", "pascoa"),
            "pronta entrega": ("cafeteria", "pascoa"),
            "cafeteria": ("cafeteria",),
            "pascoa": ("pascoa",),
            "pascoa_presentes": ("pascoa_presentes",),
            "mimos pascoa": ("pascoa_presentes",),
            "presentes pascoa": ("pascoa_presentes",),
            "presentes": ("presentes",),
            "encomendas": ("encomendas",),
        }
        return aliases.get(normalized, ("cafeteria", "pascoa", "pascoa_presentes", "presentes"))

    def _looks_like_simple_cake_lookup(self, query: str) -> bool:
        normalized = _normalize_text(query)
        if any(alias in normalized for alias in LINE_SIMPLE_LOOKUP_ALIASES):
            return True
        return (
            "bolo" in normalized
            and any(token in normalized for token in ("cenoura", "chocolate"))
            and any(token in normalized for token in ("vulcao", "vulcão", "simples"))
        )

    def _build_simple_cake_lookup(self, query: str) -> str:
        normalized = _normalize_text(query)
        selected_flavors = [flavor for flavor in LINHA_SIMPLES["sabores"] if _normalize_text(flavor) in normalized]
        selected_coverages = [
            coverage for coverage in LINHA_SIMPLES["coberturas"] if _normalize_text(coverage) in normalized
        ]
        flavor_line = ", ".join(selected_flavors) if selected_flavors else ", ".join(LINHA_SIMPLES["sabores"])
        coverage_parts = [
            f"{coverage} {_format_brl(price)}" for coverage, price in LINHA_SIMPLES["coberturas"].items()
        ]
        if selected_coverages:
            coverage_parts = [
                f"{coverage} {_format_brl(LINHA_SIMPLES['coberturas'][coverage])}" for coverage in selected_coverages
            ]
        return "\n".join(
            [
                f"Resultados catalogados para '{query}':",
                "Use estes dados para responder sem inventar.",
                f"- Encomendas: Linha Simples / Bolo Caseiro / Caseirinho | serve {LINHA_SIMPLES['serve_pessoas']} fatias",
                f"  Sabores: {flavor_line}",
                "  Coberturas: " + " | ".join(coverage_parts),
                "  Observacao: bolo simples, bolo caseiro e caseirinho referem-se a mesma linha de encomenda.",
            ]
        )

    def _structured_items(self, *catalogs: str) -> list[dict]:
        allowed = set(catalogs)
        return [item for item in _load_structured_catalog_items() if item.get("catalog") in allowed]

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
            "- So mencionar quando o contexto for bolo pronta entrega ou encomenda de bolo.\n"
            "- Se houver bolo, confirme se o cliente quer bolo com Kit Festou.\n\n"
            "🥚 Ovos Pronta Entrega\n"
            "- Identifique primeiro se o cliente quer ovos pronta entrega.\n"
            "- Sabores e disponibilidade variam no dia.\n"
            "- Catalogo oficial de Pascoa: https://pascoachoko.goomer.app\n\n"
            "☕ Cafeteria e Vitrine\n"
            f"- Cardapio Cafeteria: {cafeteria_url}\n"
            "- A vitrine pode variar no dia.\n"
            f"- {STORE_OPERATION_RULE_LINE}\n"
            f"- {SUNDAY_RULE_LINE}.\n"
            f"- Entregas sao realizadas ate {DELIVERY_CUTOFF_LABEL}.\n"
            "- Se o cliente pedir o cardapio completo da cafeteria, consulte get_menu('cafeteria').\n"
            "- Se o cliente pedir opcoes/sabores/gramagem de um item especifico, consulte lookup_catalog_items.\n"
            f"\n🎁 Presentes\n- Oferecemos {GIFT_CATALOG_SUMMARY}.\n"
        )

    def _build_structured_menu(self, *, catalogs: tuple[str, ...], title: str, intro: str) -> str:
        sections: dict[tuple[str, str], list[dict]] = {}

        for item in self._structured_items(*catalogs):
            key = (item.get("catalog", ""), item.get("section", ""))
            sections.setdefault(key, []).append(item)

        lines = [title, intro]

        for (catalog, section), items in sections.items():
            lines.append(f"\n{self._humanize_catalog(catalog)} | {self._humanize_section(section)}")

            grouped: dict[str, list[dict]] = {}
            ordered_names: list[str] = []
            for item in items:
                name = item.get("name", "Item sem nome")
                if name not in grouped:
                    ordered_names.append(name)
                grouped.setdefault(name, []).append(item)

            for name in ordered_names:
                variants = grouped[name]
                base_item = next((item for item in variants if not item.get("variant")), variants[0])
                variant_lines = []
                for item in variants:
                    variant = (item.get("variant") or "").strip()
                    if not variant or variant == "sabores destacados":
                        continue
                    price = _format_brl(item.get("price_brl"))
                    variant_lines.append(f"{variant} {price}".strip())

                if variant_lines:
                    line = f"- {name}: {' | '.join(variant_lines)}"
                else:
                    parts = [f"- {name}"]
                    if base_item.get("price_brl") is not None:
                        parts.append(_format_brl(base_item.get("price_brl")))
                    weight = (base_item.get("weight_approx") or "").strip()
                    if weight:
                        parts.append(weight)
                    line = " | ".join(parts)

                if any(item.get("options") for item in variants):
                    line += " | consulte opcoes/sabores"
                runtime_note = self._runtime_note_for_item(base_item.get("catalog", ""), name)
                if runtime_note:
                    line += f" | {runtime_note}"
                lines.append(line)

        return "\n".join(lines).strip()

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

            if normalized == "cafeteria":
                return self._build_structured_menu(
                    catalogs=("cafeteria",),
                    title="☕ Cardápio da Cafeteria",
                    intro=(
                        "Use este retorno quando o cliente pedir cardápio/menu da cafeteria. "
                        "Se ele pedir opcoes, sabores, gramagem ou perguntar por um item especifico, "
                        "consulte lookup_catalog_items."
                    ),
                )

            if normalized == "pascoa":
                return self._build_structured_menu(
                    catalogs=("pascoa",),
                    title="🐇 Cardápio de Páscoa",
                    intro=(
                        "Use este retorno para mostrar as linhas de Páscoa de forma geral. "
                        "Para sabores/opcoes de um item especifico, consulte lookup_catalog_items. "
                        "Link oficial: https://pascoachoko.goomer.app"
                    ),
                )

            if normalized == "pascoa_presentes":
                return self._build_structured_menu(
                    catalogs=("pascoa_presentes",),
                    title="🎁 Mimos e Presentes de Páscoa",
                    intro=(
                        "Use este retorno quando o cliente pedir presentes ou mimos de Páscoa. "
                        "Para composicao detalhada de um item especifico, consulte lookup_catalog_items. "
                        "Link oficial: https://pascoachoko.goomer.app"
                    ),
                )

            if normalized == "presentes":
                return self._build_structured_menu(
                    catalogs=("presentes",),
                    title="🎁 Presentes Especiais",
                    intro=(
                        "Use este retorno quando o cliente pedir cestas box, caixinha de chocolate, flores ou presentes do catalogo regular. "
                        "Para composicao detalhada ou busca de item especifico, consulte lookup_catalog_items em `catalog=\"presentes\"`. "
                        "Catalogo regular: https://bit.ly/presenteschoko"
                    ),
                )

            if normalized == "encomendas":
                encomendas = self._slice_section(text, "## Encomendas", "## Entregas e Pagamento")
                pagamentos = self._slice_section(text, "## Entregas e Pagamento")
                return f"{encomendas}\n\n{pagamentos}".strip()

            return text
        except Exception as exc:
            return "Erro ao carregar cardapio: " + str(exc)

    def lookup_catalog_items(self, query: str, catalog: str = "auto") -> str:
        normalized_query = _normalize_text(query)
        query_tokens = _tokenize_lookup(query)
        if not normalized_query:
            return "Consulta vazia. Informe o nome do item ou a opcao que deseja procurar."

        if self._looks_like_simple_cake_lookup(query):
            return self._build_simple_cake_lookup(query)

        catalogs = self._catalog_scope(catalog)
        matches: list[tuple[float, dict]] = []

        for item in self._structured_items(*catalogs):
            name = item.get("name", "")
            variant = item.get("variant", "")
            options = item.get("options") or []
            aliases = item.get("aliases") or []
            searchable_text = " ".join(
                [
                    name,
                    variant,
                    " ".join(str(alias) for alias in aliases),
                    item.get("section", ""),
                    item.get("description", ""),
                    item.get("availability_note", ""),
                    item.get("weight_approx", ""),
                    " ".join(options),
                ]
            )
            searchable_normalized = _normalize_text(searchable_text)
            searchable_tokens = set(_tokenize_lookup(searchable_text))
            name_tokens = set(_tokenize_lookup(" ".join([name, variant, *[str(alias) for alias in aliases]])))

            score = 0.0
            if normalized_query in searchable_normalized:
                score += 6.0
            if normalized_query in _normalize_text(" ".join([name, variant, *[str(alias) for alias in aliases]])):
                score += 8.0

            matched_tokens = 0
            for token in query_tokens:
                matched, ratio = _fuzzy_token_match(token, searchable_tokens)
                if not matched:
                    continue
                matched_tokens += 1
                if token in name_tokens:
                    score += 3.0
                elif _fuzzy_token_match(token, name_tokens)[0]:
                    score += 2.5
                else:
                    score += 1.5 if ratio < 1.0 else 2.0

            if query_tokens and matched_tokens == len(query_tokens):
                score += 4.0
            elif query_tokens and matched_tokens < max(1, len(query_tokens) // 2):
                score = 0.0

            if score <= 0:
                name_ratio = SequenceMatcher(
                    None,
                    normalized_query,
                    _normalize_text(" ".join([name, variant, *[str(alias) for alias in aliases]])),
                ).ratio()
                if name_ratio >= 0.78:
                    score = name_ratio * 5

            if score > 0:
                matches.append((score, item))

        if not matches:
            return (
                "Nao encontrei esse item no catalogo estruturado consultado. "
                "Nao invente resposta. Se for Pascoa, ofereca o link oficial "
                "https://pascoachoko.goomer.app ou diga que vai confirmar."
            )

        matches.sort(key=lambda entry: (-entry[0], entry[1].get("catalog", ""), entry[1].get("name", "")))
        selected = []
        seen_keys: set[tuple[str, str, str]] = set()
        for _score, item in matches:
            key = (
                item.get("catalog", ""),
                item.get("name", ""),
                item.get("variant", "") or item.get("weight_approx", ""),
            )
            if key in seen_keys:
                continue
            seen_keys.add(key)
            selected.append(item)
            if len(selected) == 6:
                break

        lines = [
            f"Resultados catalogados para '{query}':",
            "Use estes dados para responder sem inventar. Se o cliente pediu cardapio geral, use get_menu em vez desta busca.",
        ]

        for item in selected:
            parts = [
                f"- {self._humanize_catalog(item.get('catalog', ''))}: {item.get('name', 'Item sem nome')}",
            ]
            variant = (item.get("variant") or "").strip()
            if variant:
                parts.append(variant)
            if item.get("price_brl") is not None:
                parts.append(_format_brl(item.get("price_brl")))
            weight = (item.get("weight_approx") or "").strip()
            if weight and weight != variant:
                parts.append(weight)
            lines.append(" | ".join(parts))

            if item.get("description"):
                lines.append(f"  Descricao: {item['description']}")
            if item.get("options"):
                lines.append("  Opcoes: " + "; ".join(item["options"]))
            if item.get("availability_note"):
                lines.append(f"  Observacao: {item['availability_note']}")
            runtime_note = self._runtime_note_for_item(item.get("catalog", ""), item.get("name", ""))
            if runtime_note:
                lines.append(f"  Observacao operacional: {runtime_note}")

        return "\n".join(lines)

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

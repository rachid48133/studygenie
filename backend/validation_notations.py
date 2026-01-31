# backend/validation_notations.py
"""
Module de validation des notations mathématiques
Utilisé par rag_engine.py pour assurer cohérence des notations
"""

import re
from typing import Dict, List, Any


# ==================================================
# 1. Extraction des notations depuis le contexte
# ==================================================

def extract_math_notations_from_context(context: str) -> Dict[str, List[str]]:
    """
    Extrait les notations mathématiques du contexte du cours
    """
    notations = {
        "variables": [],
        "formulas": [],
        "units": []
    }

    if not context:
        return notations

    # Formules simples (ex: U = R × I)
    formula_pattern = r'([A-Z][a-z]?\s*=\s*[^.;\n]+)'
    formulas = re.findall(formula_pattern, context)
    notations["formulas"] = list(dict.fromkeys(f.strip() for f in formulas))[:10]

    # Variables (lettres majuscules isolées)
    var_pattern = r'\b([A-Z])\b'
    variables = re.findall(var_pattern, context)
    notations["variables"] = list(set(variables))[:20]

    # Unités entre parenthèses (V), (A), (Ω), etc.
    unit_pattern = r'\(([A-ZΩ])\)'
    units = re.findall(unit_pattern, context)
    notations["units"] = list(set(units))[:10]

    return notations


# ==================================================
# 2. Validation de la cohérence des notations
# ==================================================

def validate_notation_consistency(
    response: str,
    notations: Dict[str, List[str]]
) -> Dict[str, Any]:
    """
    Vérifie que la réponse respecte les notations du cours
    """
    issues = []
    score = 100

    if not response:
        return {
            "score": 0,
            "is_complete": False,
            "issues_count": 1,
            "issues": ["Réponse vide"]
        }

    # Vérifier présence de formules si le cours en contient
    if notations.get("formulas") and len(response) > 100:
        has_any_formula = any(f.split("=")[0].strip() in response for f in notations["formulas"])
        if not has_any_formula:
            issues.append("Formule attendue absente de la réponse")
            score -= 20

    # Vérifier exactitude des formules utilisées
    for formula in notations.get("formulas", []):
        lhs = formula.split("=")[0].strip()
        if lhs in response and formula not in response:
            # tolérer les espaces
            if formula.replace(" ", "") not in response.replace(" ", ""):
                issues.append(f"Formule modifiée ou incomplète : {formula}")
                score -= 15

    is_complete = score >= 50

    return {
        "score": score,
        "is_complete": is_complete,
        "issues_count": len(issues),
        "issues": issues
    }


# ==================================================
# 3. Prompt enrichi par notations
# ==================================================

def build_notation_aware_prompt(context: str, question: str) -> str:
    """
    Construit des instructions explicites sur les notations à respecter
    """
    notations = extract_math_notations_from_context(context)

    if not any(notations.values()):
        return ""

    lines = ["\n\n📝 NOTATIONS IMPORTANTES DU COURS :"]

    if notations["formulas"]:
        lines.append("\nFormules exactes :")
        for f in notations["formulas"][:5]:
            lines.append(f"- {f}")

    if notations["variables"]:
        lines.append(f"\nVariables utilisées : {', '.join(notations['variables'][:10])}")

    if notations["units"]:
        lines.append(f"\nUnités : {', '.join(notations['units'][:5])}")

    lines.append("\n⚠️ IMPORTANT : Utilise STRICTEMENT ces notations. Aucune équivalence n’est autorisée.\n")

    return "\n".join(lines)


# ==================================================
# 4. FONCTION MANQUANTE (CAUSE DU BUG)
# ==================================================

def convert_latex_to_unicode(text: str) -> str:
    """
    Convertit quelques commandes LaTeX courantes en Unicode lisible.
    Utilisée par rag_engine.py.
    """
    if not text:
        return text

    replacements = {
        r"\times": "×",
        r"\cdot": "·",
        r"\le": "≤",
        r"\ge": "≥",
        r"\neq": "≠",
        r"\approx": "≈",
        r"\sqrt": "√",
        r"\pi": "π",
        r"\Omega": "Ω",
    }

    for latex, uni in replacements.items():
        text = text.replace(latex, uni)

    return text


# ==================================================
# Export explicite
# ==================================================

__all__ = [
    "extract_math_notations_from_context",
    "validate_notation_consistency",
    "build_notation_aware_prompt",
    "convert_latex_to_unicode",
]

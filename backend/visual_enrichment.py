# backend/visual_enrichment.py - VERSION INTELLIGENTE
"""
Système d'enrichissement visuel INTELLIGENT pour StudyGenie.
Analyse le contenu réel et génère des visuels SPÉCIFIQUES au contexte.
"""

import re
from typing import Dict, List, Tuple, Optional

class IntelligentVisualEnrichment:
    """Enrichissement visuel basé sur l'analyse sémantique du contenu"""
    
    def __init__(self):
        self.visual_counter = 0
    
    def enrich(self, content: str, content_type: str = "general") -> str:
        """
        Enrichit le contenu avec des visuels spécifiques au contexte.
        Analyse phrase par phrase pour détecter ce qui nécessite un visuel.
        """
        # Protection contre contenu vide ou None
        if not content or not isinstance(content, str):
            return content if content else ""
        
        self.visual_counter = 0
        
        try:
            # Découper en phrases (plus granulaire que paragraphes)
            sentences = self._split_into_sentences(content)
            
            if not sentences:
                return content
            
            enriched_content = []
            
            i = 0
            while i < len(sentences):
                sentence = sentences[i]
                enriched_content.append(sentence)
                
                # Analyser si cette phrase nécessite un visuel
                try:
                    context = sentences[i:min(i+3, len(sentences))]
                    visual = self._analyze_and_generate(sentence, context)
                    
                    if visual:
                        enriched_content.append("\n" + visual)
                except Exception as e:
                    # Si une phrase cause une erreur, on continue sans visuel
                    print(f"⚠️ Erreur analyse phrase: {e}")
                
                i += 1
            
            return '\n'.join(enriched_content)
        
        except Exception as e:
            # En cas d'erreur globale, retourner le contenu original
            print(f"⚠️ Erreur enrichissement: {e}")
            return content
    
    def _split_into_sentences(self, text: str) -> List[str]:
        """Découpe le texte en phrases intelligemment"""
        if not text or not text.strip():
            return []
        
        # Méthode simple et robuste
        # Séparer par double retour ligne d'abord (paragraphes)
        paragraphs = text.split('\n\n')
        sentences = []
        
        for para in paragraphs:
            if not para.strip():
                continue
            
            # Séparer chaque paragraphe en phrases
            # Utiliser regex pour split sur . ! ? mais pas dans les formules
            parts = re.split(r'(?<=[.!?])\s+(?=[A-Z])', para)
            
            for part in parts:
                if part.strip():
                    sentences.append(part.strip())
        
        # Fallback: si aucune phrase détectée, retourner le texte complet
        if not sentences:
            sentences = [text]
        
        return sentences
    
    def _analyze_and_generate(self, sentence: str, context: List[str]) -> Optional[str]:
        """
        Analyse une phrase et son contexte pour générer un visuel spécifique.
        Retourne le visuel ou None.
        """
        if not sentence or not sentence.strip():
            return None
        
        try:
            sentence_lower = sentence.lower()
            full_context = ' '.join(context).lower() if context else sentence_lower
            
            # 1. FORMULE MATHÉMATIQUE/PHYSIQUE → Graphe ou encadré
            if self._contains_formula(sentence):
                return self._generate_formula_visual(sentence, full_context)
            
            # 2. CHAMP ÉLECTRIQUE avec charges spécifiques
            if 'champ électrique' in sentence_lower or 'lignes de champ' in sentence_lower:
                return self._generate_electric_field_from_text(sentence, full_context)
            
            # 3. FORCES (attraction/répulsion)
            if ('force' in sentence_lower and ('répulsion' in sentence_lower or 'attraction' in sentence_lower)):
                return self._generate_force_diagram(sentence)
            
            # 4. MOLÉCULE spécifique (H2O, CO2, etc.)
            if self._contains_molecule(sentence):
                return self._generate_molecule_structure(sentence)
            
            # 5. PROCESSUS avec étapes explicites
            if self._contains_explicit_steps(sentence, context):
                return self._generate_specific_process(sentence, context)
            
            # 6. COMPARAISON avec éléments précis
            if self._contains_comparison(sentence):
                return self._generate_specific_comparison(sentence, full_context)
            
            # 7. VARIATION/ÉVOLUTION d'une grandeur
            if self._describes_variation(sentence):
                return self._generate_variation_diagram(sentence)
            
            # 8. STRUCTURE/HIÉRARCHIE avec éléments nommés
            if self._contains_structure(sentence, context):
                return self._generate_specific_structure(sentence, context)
            
            return None
        
        except Exception as e:
            print(f"⚠️ Erreur analyse: {e}")
            return None
    
    def _contains_formula(self, text: str) -> bool:
        """Détecte si le texte contient une formule"""
        return bool(re.search(r'[A-Z]\s*=\s*[^\.]+', text))
    
    def _generate_formula_visual(self, sentence: str, context: str) -> str:
        """Génère un visuel pour une formule spécifique"""
        self.visual_counter += 1
        
        # Extraire la formule
        formula_match = re.search(r'([A-Z][a-z]?\s*=\s*[^\.,]+)', sentence)
        if not formula_match:
            return ""
        
        formula = formula_match.group(1).strip()
        
        # Détecter si c'est une relation quadratique, linéaire, etc.
        context_lower = context.lower()
        
        if 'r²' in formula or 'r^2' in formula:
            # Relation en 1/r²
            return f"""
```
📐 FORMULE ET GRAPHE #{self.visual_counter}

{formula}

Graphe: 1/r²
     │
   ∞ │╲
     │ ╲
     │  ╲___
     │      ────____
     └──────────────── r
     0              ∞

💡 Décroît rapidement quand r augmente
```
"""
        
        elif '²' in formula or '^2' in formula:
            # Relation quadratique
            return f"""
```
📐 FORMULE ET GRAPHE #{self.visual_counter}

{formula}

Graphe: x²
     │    ╱
     │   ╱
     │  ╱
     │ ╱
     │╱
     └────────── x

💡 Croissance parabolique
```
"""
        
        else:
            # Formule générique
            return f"""
```
📐 FORMULE CLÉ #{self.visual_counter}

╔════════════════════════╗
║  {formula:<22}║
╚════════════════════════╝
```
"""
    
    def _generate_electric_field_from_text(self, sentence: str, context: str) -> str:
        """Génère un champ électrique basé sur ce qui est décrit"""
        self.visual_counter += 1
        
        has_positive = 'positive' in context or 'charge +' in context
        has_negative = 'négative' in context or 'charge -' in context
        
        if has_positive and has_negative:
            # Dipôle
            return f"""
```
⚡ CHAMP ÉLECTRIQUE (dipôle) #{self.visual_counter}

      ↗↗↗
    ↗     ↗
  [+]  →  [-]
    ↘     ↘
      ↘↘↘

Les lignes partent du + et arrivent au -
```
"""
        elif has_positive:
            # Charge positive seule
            return f"""
```
⚡ CHAMP ÉLECTRIQUE (charge +) #{self.visual_counter}

    ↗  ↑  ↖
  →   [+]   ←
    ↘  ↓  ↙

Lignes divergentes depuis la charge
```
"""
        elif has_negative:
            # Charge négative seule
            return f"""
```
⚡ CHAMP ÉLECTRIQUE (charge -) #{self.visual_counter}

    ↙  ↓  ↘
  ←   [-]   →
    ↖  ↑  ↗

Lignes convergentes vers la charge
```
"""
        
        return ""
    
    def _generate_force_diagram(self, sentence: str) -> str:
        """Génère un diagramme de forces basé sur le texte"""
        self.visual_counter += 1
        
        if 'répulsion' in sentence.lower():
            return f"""
```
⚡ FORCES DE RÉPULSION #{self.visual_counter}

[+]  ←→  [+]
 F₁      F₂

Les charges de même signe se repoussent
```
"""
        elif 'attraction' in sentence.lower():
            return f"""
```
⚡ FORCES D'ATTRACTION #{self.visual_counter}

[+]  →←  [-]
 F₁      F₂

Les charges opposées s'attirent
```
"""
        
        return ""
    
    def _contains_molecule(self, text: str) -> bool:
        """Détecte une molécule spécifique"""
        return bool(re.search(r'H2O|CO2|CH4|NH3|O2|N2', text, re.IGNORECASE))
    
    def _generate_molecule_structure(self, sentence: str) -> str:
        """Génère la structure d'une molécule spécifique"""
        self.visual_counter += 1
        
        if 'H2O' in sentence or 'eau' in sentence.lower():
            return f"""
```
🧪 STRUCTURE H₂O #{self.visual_counter}

    H
     ╲
      O  (104.5°)
     ╱
    H

2 atomes H, 1 atome O
Molécule coudée
```
"""
        
        elif 'CO2' in sentence:
            return f"""
```
🧪 STRUCTURE CO₂ #{self.visual_counter}

O═C═O  (180°)

Molécule linéaire
Double liaisons
```
"""
        
        return ""
    
    def _contains_explicit_steps(self, sentence: str, context: List[str]) -> bool:
        """Détecte un processus avec étapes numérotées ou séquentielles"""
        full_text = ' '.join(context)
        return bool(re.search(r'd\'abord|ensuite|puis|enfin|étape \d', full_text, re.IGNORECASE))
    
    def _generate_specific_process(self, sentence: str, context: List[str]) -> str:
        """Génère un processus basé sur les étapes réelles du texte"""
        self.visual_counter += 1
        
        full_text = ' '.join(context)
        
        # Extraire les étapes
        steps = []
        if "d'abord" in full_text.lower():
            match = re.search(r"d'abord[,:]?\s*([^\.]+)", full_text, re.IGNORECASE)
            if match:
                steps.append(match.group(1).strip()[:30])
        
        if 'ensuite' in full_text.lower():
            match = re.search(r'ensuite[,:]?\s*([^\.]+)', full_text, re.IGNORECASE)
            if match:
                steps.append(match.group(1).strip()[:30])
        
        if 'puis' in full_text.lower():
            match = re.search(r'puis[,:]?\s*([^\.]+)', full_text, re.IGNORECASE)
            if match:
                steps.append(match.group(1).strip()[:30])
        
        if len(steps) < 2:
            return ""
        
        diagram = f"\n```\n🔄 PROCESSUS #{self.visual_counter}\n\n"
        
        for i, step in enumerate(steps, 1):
            diagram += f"┌{'─'*35}┐\n"
            diagram += f"│ {i}. {step:<32}│\n"
            diagram += f"└{'─'*35}┘\n"
            if i < len(steps):
                diagram += "          ↓\n"
        
        diagram += "```\n"
        return diagram
    
    def _contains_comparison(self, text: str) -> bool:
        """Détecte une comparaison explicite"""
        return bool(re.search(r'différence entre|comparé à|contrairement à|tandis que', text, re.IGNORECASE))
    
    def _generate_specific_comparison(self, sentence: str, context: str) -> str:
        """Génère une comparaison basée sur les éléments du texte"""
        self.visual_counter += 1
        
        # Essayer d'extraire les éléments comparés
        match = re.search(r'différence entre\s+([^et]+)\s+et\s+([^\.]+)', context, re.IGNORECASE)
        
        if match:
            elem1 = match.group(1).strip()[:20]
            elem2 = match.group(2).strip()[:20]
            
            return f"""
```
📊 COMPARAISON #{self.visual_counter}

┌──────────────────┬──────────────────┐
│ {elem1:<16} │ {elem2:<16} │
├──────────────────┼──────────────────┤
│ [Aspect 1]       │ [Aspect 1]       │
│ [Aspect 2]       │ [Aspect 2]       │
└──────────────────┴──────────────────┘
```
"""
        
        return ""
    
    def _describes_variation(self, text: str) -> bool:
        """Détecte une description de variation"""
        return bool(re.search(r'augmente|diminue|croît|décroît|varie', text, re.IGNORECASE))
    
    def _generate_variation_diagram(self, sentence: str) -> str:
        """Génère un diagramme de variation"""
        self.visual_counter += 1
        
        if 'augmente' in sentence.lower() or 'croît' in sentence.lower():
            return f"""
```
📈 VARIATION #{self.visual_counter}

     │      ╱
     │    ╱
     │  ╱
     │╱
     └────────
     
↗ Augmentation
```
"""
        elif 'diminue' in sentence.lower() or 'décroît' in sentence.lower():
            return f"""
```
📉 VARIATION #{self.visual_counter}

     │╲
     │ ╲
     │  ╲
     │   ╲
     └────────
     
↘ Diminution
```
"""
        
        return ""
    
    def _contains_structure(self, sentence: str, context: List[str]) -> bool:
        """Détecte une structure/hiérarchie"""
        full_text = ' '.join(context).lower()
        return bool(re.search(r'composé de|constitué de|contient', full_text))
    
    def _generate_specific_structure(self, sentence: str, context: List[str]) -> str:
        """Génère une structure basée sur les éléments du texte"""
        self.visual_counter += 1
        
        full_text = ' '.join(context)
        
        # Tenter d'extraire les composants
        match = re.search(r'(contient|composé de|constitué de)[:\s]+([^\.]+)', full_text, re.IGNORECASE)
        
        if match:
            components = match.group(2).strip()
            
            return f"""
```
🏗️ STRUCTURE #{self.visual_counter}

        ┌──────────┐
        │ Système  │
        └────┬─────┘
             │
        {components[:40]}
```
"""
        
        return ""


# ============================================
# FONCTIONS HELPER POUR INTÉGRATION
# ============================================

def auto_enrich_content(content: str, content_type: str = "general") -> str:
    """Enrichit automatiquement avec analyse intelligente"""
    enricher = IntelligentVisualEnrichment()
    return enricher.enrich(content, content_type)

def enrich_summary(summary: str) -> str:
    """Enrichit un résumé"""
    return auto_enrich_content(summary, "summary")

def enrich_explanation(explanation: str) -> str:
    """Enrichit une explication"""
    return auto_enrich_content(explanation, "explanation")

def enrich_qa_response(response: str) -> str:
    """Enrichit une réponse Q&A"""
    return auto_enrich_content(response, "qa")


# ============================================
# TEST
# ============================================

if __name__ == "__main__":
    test = """
Le champ électrique est créé par des charges électriques. Il peut être calculé avec la formule E = k·Q/r².

Les lignes de champ électrique partent des charges positives et arrivent aux charges négatives.

Deux charges de même signe exercent une force de répulsion l'une sur l'autre.
    """
    
    print("=== TEST ENRICHISSEMENT INTELLIGENT ===")
    enriched = auto_enrich_content(test)
    print(enriched)

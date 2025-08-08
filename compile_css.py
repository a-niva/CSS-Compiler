#!/usr/bin/env python3
"""
Script de compilation CSS avec un VRAI parseur CSS.
Utilise tinycss2 pour parser correctement le CSS sans regex fragiles.

Installation requise:
    pip install tinycss2

Usage:
    python compile_css.py frontend/styles.css -o frontend/styles_compiled.css
"""

import sys
import json
from pathlib import Path
from collections import OrderedDict
from typing import List, Dict, Tuple, Optional, Any

try:
    import tinycss2
    from tinycss2 import serialize
except ImportError:
    print("❌ ERREUR: tinycss2 n'est pas installé!")
    print("📦 Installation: pip install tinycss2")
    sys.exit(1)


class CSSRule:
    """Représente une règle CSS complète."""
    
    def __init__(self, selector: str):
        self.selector = selector.strip()
        self.properties = OrderedDict()  # Clé -> Valeur
        self.source_order = 0  # Pour maintenir l'ordre de la cascade
        
    def add_property(self, prop: str, value: str):
        """Ajoute ou écrase une propriété."""
        self.properties[prop.strip()] = value.strip()
        
    def merge_with(self, other_rule: 'CSSRule'):
        """Fusionne avec une autre règle (l'autre écrase)."""
        for prop, value in other_rule.properties.items():
            self.properties[prop] = value
            
    def to_css(self, indent: str = "    ") -> str:
        """Génère le CSS formaté."""
        if not self.properties:
            return ""
        
        lines = [f"{self.selector} {{"]
        for prop, value in self.properties.items():
            lines.append(f"{indent}{prop}: {value};")
        lines.append("}")
        
        return "\n".join(lines)


class RobustCSSCompiler:
    """Compilateur CSS utilisant un vrai parseur."""
    
    def __init__(self, 
                 input_file: str = 'styles.css',
                 output_file: str = 'styles_compiled.css',
                 alphabetical_order: bool = False,
                 safe_mode: bool = True):
        self.input_file = Path(input_file)
        self.output_file = Path(output_file)
        self.alphabetical_order = alphabetical_order
        self.safe_mode = safe_mode
        
        # Stockage structuré
        self.rules = OrderedDict()  # selector -> CSSRule
        self.at_rules = []  # @keyframes, @import, etc.
        self.media_queries = OrderedDict()  # media condition -> OrderedDict(selector -> CSSRule)
        
        # Statistiques
        self.stats = {
            'rules_parsed': 0,
            'selectors_split': 0,
            'properties_merged': 0,
            'at_rules': 0,
            'media_queries': 0,
            'parse_errors': 0
        }
        
    def compile(self):
        """Lance la compilation complète."""
        print("="*60)
        print("🚀 COMPILATION CSS ROBUSTE (avec parseur)")
        print("="*60)
        
        # Lire le fichier
        print(f"\n📚 Lecture de {self.input_file}...")
        css_content = self.read_file()
        original_size = len(css_content)
        
        # Parser le CSS avec tinycss2
        print("🔍 Parsing du CSS avec tinycss2...")
        stylesheet = tinycss2.parse_stylesheet(css_content, skip_whitespace=True, skip_comments=True)
        
        # Traiter les règles
        print("📋 Traitement des règles CSS...")
        self.process_stylesheet(stylesheet)
        
        # Optionnel : tri alphabétique
        if self.alphabetical_order:
            print("🔤 Tri alphabétique des sélecteurs...")
            self.sort_rules()
        
        # Générer le CSS final
        print("📝 Génération du CSS compilé...")
        output_css = self.generate_output()
        
        # Écrire le fichier
        print(f"💾 Écriture dans {self.output_file}...")
        self.write_file(output_css)
        final_size = len(output_css)
        
        # Rapport
        print("\n" + "="*60)
        print("✅ COMPILATION TERMINÉE!")
        print("="*60)
        print(f"📊 Statistiques:")
        print(f"   - Taille originale: {original_size:,} octets")
        print(f"   - Taille finale: {final_size:,} octets")
        print(f"   - Réduction: {original_size - final_size:,} octets")
        print(f"   - Règles parsées: {self.stats['rules_parsed']}")
        print(f"   - Sélecteurs séparés: {self.stats['selectors_split']}")
        print(f"   - Propriétés fusionnées: {self.stats['properties_merged']}")
        print(f"   - At-rules préservées: {self.stats['at_rules']}")
        print(f"   - Media queries: {self.stats['media_queries']}")
        
        if self.stats['parse_errors'] > 0:
            print(f"   ⚠️  Erreurs de parsing: {self.stats['parse_errors']}")
    
    def read_file(self) -> str:
        """Lit le fichier CSS."""
        try:
            with open(self.input_file, 'r', encoding='utf-8') as f:
                return f.read()
        except FileNotFoundError:
            print(f"❌ ERREUR: Le fichier {self.input_file} n'existe pas!")
            sys.exit(1)
        except Exception as e:
            print(f"❌ ERREUR lors de la lecture: {e}")
            sys.exit(1)
    
    def write_file(self, content: str):
        """Écrit le fichier CSS avec backup."""
        # Backup si le fichier existe
        if self.output_file.exists():
            backup_file = self.output_file.with_suffix('.backup.css')
            print(f"📦 Création du backup: {backup_file}")
            self.output_file.rename(backup_file)
        
        try:
            with open(self.output_file, 'w', encoding='utf-8') as f:
                f.write(content)
        except Exception as e:
            print(f"❌ ERREUR lors de l'écriture: {e}")
            sys.exit(1)
    
    def process_stylesheet(self, stylesheet):
        """Traite toutes les règles du stylesheet."""
        for rule in stylesheet:
            self.process_node(rule, media_condition=None)
    
    def process_node(self, node, media_condition: Optional[str] = None):
        """Traite un nœud CSS (règle, at-rule, etc.)."""
        if node.type == 'qualified-rule':
            # C'est une règle CSS normale
            self.process_qualified_rule(node, media_condition)
            
        elif node.type == 'at-rule':
            # C'est une at-rule (@media, @keyframes, etc.)
            self.process_at_rule(node)
            
        elif node.type == 'error':
            self.stats['parse_errors'] += 1
            print(f"   ⚠️  Erreur de parsing ligne {node.source_line}: {node.message}")
    
    def process_qualified_rule(self, rule, media_condition: Optional[str] = None):
        """Traite une règle CSS normale."""
        self.stats['rules_parsed'] += 1
        
        # Extraire le sélecteur
        selector_tokens = rule.prelude
        selector = self.serialize_tokens(selector_tokens).strip()
        
        if not selector:
            return
        
        # Extraire les propriétés
        properties = self.parse_declaration_block(rule.content)
        
        if not properties:
            return
        
        # Séparer les sélecteurs multiples
        selectors = self.split_selectors(selector)
        
        # Stocker dans la bonne structure
        target_dict = self.media_queries.setdefault(media_condition, OrderedDict()) if media_condition else self.rules
        
        for sel in selectors:
            sel = sel.strip()
            if not sel:
                continue
                
            self.stats['selectors_split'] += 1
            
            # Créer ou récupérer la règle
            if sel not in target_dict:
                target_dict[sel] = CSSRule(sel)
            
            # Ajouter les propriétés
            for prop, value in properties.items():
                target_dict[sel].add_property(prop, value)
                self.stats['properties_merged'] += 1
    
    def process_at_rule(self, at_rule):
        """Traite une at-rule."""
        keyword = at_rule.lower_at_keyword
        
        if keyword == 'media':
            # Media query
            self.stats['media_queries'] += 1
            media_condition = self.serialize_tokens(at_rule.prelude).strip()
            
            # Parser le contenu de la media query
            if at_rule.content:
                content_stylesheet = tinycss2.parse_stylesheet(
                    self.serialize_tokens(at_rule.content),
                    skip_whitespace=True,
                    skip_comments=True
                )
                
                for rule in content_stylesheet:
                    if rule.type == 'qualified-rule':
                        self.process_qualified_rule(rule, media_condition)
        elif keyword == 'keyframes':
            # NOUVEAU : Éviter les doublons de keyframes
            self.stats['at_rules'] += 1
            keyframe_name = self.serialize_tokens(at_rule.prelude).strip()
            keyframe_content = self.serialize_node(at_rule)
            
            # Vérifier si ce keyframe existe déjà
            existing_keyframe = next(
                (ar for ar in self.at_rules 
                if ar['keyword'] == 'keyframes' and ar['name'] == keyframe_name),
                None
            )
            
            if existing_keyframe:
                # Remplacer l'ancien par le nouveau (cascade CSS)
                existing_keyframe['content'] = keyframe_content
            else:
                self.at_rules.append({
                    'keyword': keyword,
                    'name': keyframe_name,
                    'content': keyframe_content
                })
        else:
            # Autres at-rules (@keyframes, @import, etc.)
            self.stats['at_rules'] += 1
            self.at_rules.append({
                'keyword': keyword,
                'content': self.serialize_node(at_rule)
            })
    
    def parse_declaration_block(self, tokens) -> OrderedDict:
        """Parse un bloc de déclarations CSS."""
        properties = OrderedDict()
        
        declarations = tinycss2.parse_declaration_list(tokens, skip_whitespace=True, skip_comments=True)
        
        for decl in declarations:
            if decl.type == 'declaration':
                prop = decl.lower_name
                value = self.serialize_tokens(decl.value).strip()
                
                # NOUVEAU : Préserver le flag !important
                if decl.important:
                    value += ' !important'
                
                properties[prop] = value
            elif decl.type == 'error':
                self.stats['parse_errors'] += 1
        
        return properties
        
    def serialize_tokens(self, tokens) -> str:
        """Sérialise une liste de tokens en string CSS."""
        result = serialize(tokens)
        # FIX: Nettoyer les commentaires vides dans les sélecteurs
        result = result.replace('/**/', '')
        return result
    
    def serialize_node(self, node) -> str:
        """Sérialise un nœud complet."""
        return serialize([node])
    
    def split_selectors(self, selector: str) -> List[str]:
        """Sépare les sélecteurs multiples intelligemment."""
        # Protection contre les fonctions CSS
        result = []
        current = []
        depth = 0  # Compteur unifié pour (), [], etc.
        in_string = False
        quote_char = None
        
        for i, char in enumerate(selector):
            # Gestion des strings
            if char in ('"', "'") and (i == 0 or selector[i-1] != '\\'):
                if not in_string:
                    in_string = True
                    quote_char = char
                elif char == quote_char:
                    in_string = False
                    quote_char = None
            
            # Si on est dans une string, on ne traite pas
            if in_string:
                current.append(char)
                continue
            
            # Gestion de la profondeur
            if char in '([{':
                depth += 1
            elif char in ')]}':
                depth -= 1
            elif char == ',' and depth == 0:
                if current:
                    sel = ''.join(current).strip()
                    if sel:
                        result.append(sel)
                    current = []
                continue
            
            current.append(char)
        
        # Dernier sélecteur
        if current:
            sel = ''.join(current).strip()
            if sel:
                result.append(sel)
        
        return result
    
    def sort_rules(self):
        """Trie les règles alphabétiquement (avec protection)."""
        if self.safe_mode:
            # Séparer les règles dangereuses
            dangerous_patterns = [
                ':link', ':visited', ':hover', ':focus', ':active',
                ':first-child', ':last-child', ':nth-'
            ]
            
            def is_dangerous(selector: str) -> bool:
                return any(pattern in selector for pattern in dangerous_patterns)
            
            # Trier seulement les règles sûres
            safe_rules = OrderedDict()
            dangerous_rules = OrderedDict()
            
            for selector, rule in self.rules.items():
                if is_dangerous(selector):
                    dangerous_rules[selector] = rule
                else:
                    safe_rules[selector] = rule
            
            # Reconstruire avec tri
            self.rules = OrderedDict()
            self.rules.update(dangerous_rules)  # D'abord les dangereuses (ordre préservé)
            sorted_safe = OrderedDict(sorted(safe_rules.items(), key=lambda x: x[0].lower()))
            self.rules.update(sorted_safe)
            
            # Faire de même pour les media queries
            for media_condition in self.media_queries:
                rules = self.media_queries[media_condition]
                safe_mq = OrderedDict()
                dangerous_mq = OrderedDict()
                
                for selector, rule in rules.items():
                    if is_dangerous(selector):
                        dangerous_mq[selector] = rule
                    else:
                        safe_mq[selector] = rule
                
                sorted_safe_mq = OrderedDict(sorted(safe_mq.items(), key=lambda x: x[0].lower()))
                self.media_queries[media_condition] = OrderedDict()
                self.media_queries[media_condition].update(dangerous_mq)
                self.media_queries[media_condition].update(sorted_safe_mq)
        else:
            # Mode YOLO
            self.rules = OrderedDict(sorted(self.rules.items(), key=lambda x: x[0].lower()))
            for media_condition in self.media_queries:
                rules = self.media_queries[media_condition]
                self.media_queries[media_condition] = OrderedDict(
                    sorted(rules.items(), key=lambda x: x[0].lower())
                )
    
    def generate_output(self) -> str:
        """Génère le CSS compilé final."""
        output = []
        
        # En-tête
        output.append("/* ================================================== */\n")
        output.append("/* CSS COMPILÉ AVEC PARSEUR ROBUSTE */\n")
        output.append("/* ================================================== */\n\n")
        
        # At-rules préservées (keyframes, import, etc.)
        if self.at_rules:
            output.append("/* ===== AT-RULES PRÉSERVÉES ===== */\n")
            
            # Dédupliquer les keyframes par nom
            seen_keyframes = {}
            deduplicated_at_rules = []
            
            for at_rule in self.at_rules:
                if at_rule['keyword'] == 'keyframes':
                    # Extraire le nom du keyframe
                    name = at_rule.get('name', '')
                    if not name:
                        # Essayer d'extraire du content
                        content = at_rule['content']
                        import re
                        match = re.match(r'@keyframes\s+(\S+)', content)
                        if match:
                            name = match.group(1)
                    
                    if name:
                        # Si on a déjà vu ce keyframe, on le remplace
                        if name in seen_keyframes:
                            # Remplacer l'ancien
                            idx = seen_keyframes[name]
                            deduplicated_at_rules[idx] = at_rule
                        else:
                            # Nouveau keyframe
                            seen_keyframes[name] = len(deduplicated_at_rules)
                            deduplicated_at_rules.append(at_rule)
                    else:
                        # Pas de nom trouvé, on garde tel quel
                        deduplicated_at_rules.append(at_rule)
                else:
                    # Autres at-rules
                    deduplicated_at_rules.append(at_rule)
            
            # Écrire les at-rules dédupliquées
            for at_rule in deduplicated_at_rules:
                content = at_rule['content']
                # Nettoyer les commentaires vides
                content = content.replace('/**/', '')
                output.append(content)
                if not content.endswith('\n'):
                    output.append('\n')
            output.append("\n")
        
        # Variables CSS (:root)
        root_rules = OrderedDict()
        for k, v in self.rules.items():
            if k.startswith(':root'):
                root_rules[k] = v
        
        if root_rules:
            output.append("/* ===== VARIABLES CSS ===== */\n")
            for selector, rule in root_rules.items():
                output.append(rule.to_css() + "\n\n")
        
        # Reset et base (*, html, body, etc.)
        base_selectors = ['*', 'html', 'body']
        base_rules = OrderedDict()
        
        for k, v in self.rules.items():
            # Vérifier si c'est une règle de base
            if k in base_selectors or k.startswith('::'):
                base_rules[k] = v
        
        if base_rules:
            output.append("/* ===== RESET ET BASE ===== */\n")
            # Ordre spécifique pour les règles de base
            ordered_base = ['*', 'html', 'body']
            
            # D'abord les règles dans l'ordre spécifié
            for selector in ordered_base:
                if selector in base_rules:
                    output.append(base_rules[selector].to_css() + "\n\n")
            
            # Puis les pseudo-éléments
            for selector, rule in base_rules.items():
                if selector not in ordered_base:
                    output.append(rule.to_css() + "\n\n")
        
        # Règles principales (tout le reste sauf :root et base)
        main_rules = OrderedDict()
        for k, v in self.rules.items():
            if k not in root_rules and k not in base_rules:
                main_rules[k] = v
        
        if main_rules:
            output.append("/* ===== RÈGLES PRINCIPALES ===== */\n")
            
            # Grouper par type d'élément pour une meilleure organisation
            headings = OrderedDict()
            classes = OrderedDict()
            ids = OrderedDict()
            elements = OrderedDict()
            pseudos = OrderedDict()
            
            for selector, rule in main_rules.items():
                if selector.startswith('h1') or selector.startswith('h2') or \
                selector.startswith('h3') or selector.startswith('h4') or \
                selector.startswith('h5') or selector.startswith('h6'):
                    headings[selector] = rule
                elif selector.startswith('.'):
                    classes[selector] = rule
                elif selector.startswith('#'):
                    ids[selector] = rule
                elif ':' in selector:
                    pseudos[selector] = rule
                else:
                    elements[selector] = rule
            
            # Écrire dans l'ordre logique
            for rules_group in [headings, elements, classes, ids, pseudos]:
                for selector, rule in rules_group.items():
                    css = rule.to_css()
                    # Nettoyer les commentaires vides dans le CSS
                    css = css.replace('/**/', '')
                    output.append(css + "\n\n")
        
        # Media queries
        if self.media_queries:
            output.append("/* ===== MEDIA QUERIES ===== */\n")
            
            # Fusionner les media queries identiques
            merged_queries = OrderedDict()
            
            for condition, rules in self.media_queries.items():
                # Normaliser la condition (espaces, parenthèses)
                normalized = ' '.join(condition.split())
                normalized = normalized.replace(' :', ':').replace(': ', ':')
                normalized = normalized.replace(' (', '(').replace('( ', '(')
                normalized = normalized.replace(' )', ')').replace(') ', ')')
                
                if normalized not in merged_queries:
                    merged_queries[normalized] = OrderedDict()
                
                # Fusionner les règles
                for selector, rule in rules.items():
                    if selector in merged_queries[normalized]:
                        # Fusionner avec l'existant (la nouvelle écrase)
                        merged_queries[normalized][selector].merge_with(rule)
                    else:
                        merged_queries[normalized][selector] = rule
            
            # Organiser par type de media query
            desktop_queries = OrderedDict()  # min-width sans max-width
            tablet_queries = OrderedDict()   # entre 768px et 1024px
            mobile_queries = OrderedDict()   # max-width <= 768px  
            print_queries = OrderedDict()    # print
            preference_queries = OrderedDict()  # prefers-*
            other_queries = OrderedDict()    # autres
            
            for condition, rules in merged_queries.items():
                if 'print' in condition:
                    print_queries[condition] = rules
                elif 'prefers-' in condition:
                    preference_queries[condition] = rules
                elif 'max-width' in condition:
                    # Extraire la valeur
                    import re
                    match = re.search(r'max-width:\s*(\d+)', condition)
                    if match:
                        width = int(match.group(1))
                        if width <= 768:
                            mobile_queries[condition] = rules
                        elif width <= 1024:
                            tablet_queries[condition] = rules
                        else:
                            other_queries[condition] = rules
                    else:
                        other_queries[condition] = rules
                elif 'min-width' in condition and 'max-width' not in condition:
                    desktop_queries[condition] = rules
                else:
                    other_queries[condition] = rules
            
            # Écrire dans l'ordre approprié (du plus large au plus étroit)
            sections = [
                ("--- DESKTOP ---", desktop_queries),
                ("--- MOBILE ---", mobile_queries),
                ("--- AUTRES ---", other_queries)
            ]
            
            for section_name, queries in sections:
                if queries:
                    output.append(f"\n/* {section_name} */\n")
                    
                    # Trier par largeur si possible
                    sorted_queries = []
                    for condition, rules in queries.items():
                        import re
                        # Extraire la largeur pour le tri
                        width_match = re.search(r'(max-width|min-width):\s*(\d+)', condition)
                        if width_match:
                            width = int(width_match.group(2))
                            is_max = width_match.group(1) == 'max-width'
                            # Pour max-width, on veut du plus grand au plus petit
                            # Pour min-width, on veut du plus petit au plus grand
                            sort_key = -width if is_max else width
                        else:
                            sort_key = 0
                        sorted_queries.append((sort_key, condition, rules))
                    
                    # Trier et écrire
                    sorted_queries.sort(key=lambda x: x[0])
                    
                    for _, condition, rules in sorted_queries:
                        output.append(f"@media {condition} {{\n")
                        
                        # Appliquer la même organisation que pour les règles principales
                        for selector, rule in rules.items():
                            if rule.properties:  # Seulement si la règle a des propriétés
                                # Indenter correctement
                                css_lines = rule.to_css(indent="        ").split('\n')
                                for line in css_lines:
                                    if line.strip():
                                        # Nettoyer les commentaires vides
                                        line = line.replace('/**/', '')
                                        output.append(f"    {line}\n")
                                output.append("\n")
                        
                        output.append("}\n\n")
            
            # Media queries de préférence utilisateur à la fin
            if preference_queries:
                output.append("\n/* --- PRÉFÉRENCES UTILISATEUR --- */\n")
                for condition, rules in preference_queries.items():
                    output.append(f"@media {condition} {{\n")
                    for selector, rule in rules.items():
                        if rule.properties:
                            css_lines = rule.to_css(indent="        ").split('\n')
                            for line in css_lines:
                                if line.strip():
                                    line = line.replace('/**/', '')
                                    output.append(f"    {line}\n")
                            output.append("\n")
                    output.append("}\n\n")
            
            # Print media à la toute fin
            if print_queries:
                output.append("\n/* --- PRINT --- */\n")
                for condition, rules in print_queries.items():
                    output.append(f"@media {condition} {{\n")
                    for selector, rule in rules.items():
                        if rule.properties:
                            css_lines = rule.to_css(indent="        ").split('\n')
                            for line in css_lines:
                                if line.strip():
                                    line = line.replace('/**/', '')
                                    output.append(f"    {line}\n")
                            output.append("\n")
                    output.append("}\n\n")
        
        # Nettoyer le résultat final
        result = ''.join(output)
        
        # Supprimer les lignes vides multiples
        import re
        result = re.sub(r'\n{3,}', '\n\n', result)
        
        # S'assurer que le fichier se termine par une nouvelle ligne
        if not result.endswith('\n'):
            result += '\n'
        
        return result


def main():
    """Point d'entrée principal."""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="Compilateur CSS robuste avec vrai parseur"
    )
    parser.add_argument(
        'input',
        nargs='?',
        default='styles.css',
        help='Fichier CSS à compiler'
    )
    parser.add_argument(
        '-o', '--output',
        default='styles_compiled.css',
        help='Fichier de sortie'
    )
    parser.add_argument(
        '-a', '--alphabetical',
        action='store_true',
        help='Trier alphabétiquement'
    )
    parser.add_argument(
        '--unsafe',
        action='store_true',
        help='Mode non sécurisé pour le tri'
    )
    
    args = parser.parse_args()
    
    # Vérifier tinycss2
    try:
        import tinycss2
    except ImportError:
        print("❌ tinycss2 n'est pas installé!")
        print("\n📦 Installation:")
        print("   pip install tinycss2")
        print("\nOu si vous utilisez Anaconda:")
        print("   conda install -c conda-forge tinycss2")
        sys.exit(1)
    
    # Compiler
    compiler = RobustCSSCompiler(
        input_file=args.input,
        output_file=args.output,
        alphabetical_order=args.alphabetical,
        safe_mode=not args.unsafe
    )
    
    try:
        compiler.compile()
        print("\n✨ Succès! CSS compilé avec le parseur robuste.")
    except KeyboardInterrupt:
        print("\n\n⚠️  Compilation interrompue")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ ERREUR: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
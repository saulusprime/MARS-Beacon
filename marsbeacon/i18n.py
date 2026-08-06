# -*- coding: utf-8 -*-
"""Cataloghi i18n dei referti (--lang): cornice e rilievi.

Una tabella per lingua, stesso meccanismo chiave+parametri della
v1.43.0: i testi italiani restano canonici (storico e ancore
invariati), le altre lingue si risolvono al rendering con fallback
dichiarato campo per campo. Il namespace pubblico resta
mars_audit, questo modulo e' interno.
"""

from __future__ import annotations

from typing import Dict
from typing import List

from marsbeacon.audits import _strip_md_links
from marsbeacon.audits import lh_locale_catalog
from marsbeacon.base import AREA_LEX
from marsbeacon.base import AREA_RRF
from marsbeacon.base import AREA_SD
from marsbeacon.base import AREA_SEM
from marsbeacon.base import AREA_TECH
from marsbeacon.base import Finding


# Lingue dei referti (--lang, formati html/text/md/csv). La cornice
# HTML passa da _HTML_I18N, quella di text/md/csv da _FRAME_I18N
# (chiave = testo italiano canonico) via frame_text(); i rilievi
# da una tabella per lingua (_FINDINGS_EN/FR/DE/ES) via
# finding_texts(). Le evidenze citate dal sito auditato restano
# nella lingua del sito (nota dichiarata nel referto).
HTML_LANGS = ("it", "en", "fr", "de", "es")


_HTML_I18N: Dict[str, Dict[str, str]] = {
    "it": {
        "hero.ring": "Punteggio complessivo %.0f su 100: %s",
        "hero.of100": "su 100",
        "hero.thresholds": "buono &ge; 70 &middot; da migliorare "
                           "40&ndash;69 &middot; critico &lt; 40",
        "verdict.Buono": "Buono",
        "verdict.Da migliorare": "Da migliorare",
        "verdict.Critico": "Critico",
        "tile.critical": "Critici",
        "tile.warning": "Avvertenze",
        "tile.info": "Informazioni",
        "hero.donut_aria": "%d pagine: %d senza rilievi, %d con "
                           "rilievi, %d in errore",
        "hero.pages": "pagine",
        "hero.clean": "%d senza rilievi",
        "hero.flagged": "%d con rilievi",
        "hero.broken": "%d in errore",
        "meta.line": "Pagine analizzate: %d &middot; chunk "
                     "indicizzati: %d &middot; recuperatore "
                     "vettoriale: <code>%s</code>",
        "note.findings_lang": "",
        "top.h": "Top rilievi",
        "top.critical": "CRITICO",
        "top.warning": "AVVISO",
        "gain.index": "+%.1f indice",
        "score.total": "Complessivo",
        "area.Tecnica": "Tecnica",
        "area.Lessicale (BM25)": "Lessicale (BM25)",
        "area.Semantica (vettoriale)": "Semantica (vettoriale)",
        "area.Dati strutturati": "Dati strutturati",
        "area.Simulazione RRF": "Simulazione RRF",
        "delta.h": "Rispetto all'esecuzione precedente",
        "delta.meta": "Confronto con l'audit del %s sullo stesso "
                      "sito: l'audit diventa monitoraggio. Rilievi "
                      "confrontati per tipo (i conteggi nei titoli "
                      "possono variare).",
        "delta.resolved": "Risolti",
        "delta.new": "Nuovi",
        "delta.none": "Nessuno.",
        "cit.h": "Profili di citabilita' per assistente IA",
        "cit.meta": "%s Mercato di riferimento: <b>%s</b> "
                    "(pesi: %s).",
        "cit.assistant": "Assistente",
        "cit.focus": "Cosa premia",
        "cit.score": "Punteggio",
        "cit.index": "Indice composito (mercato %s)",
        "cit.actions_h": "Top %d azioni prioritarie",
        "cit.actions_meta": "Le prime voci del piano di remediation "
                            "con il profilo che ne guadagna di piu' "
                            "(stima in punti profilo, stessa natura "
                            "euristica).",
        "cit.best": " &mdash; guadagna di piu': <b>%s</b> "
                    "(+%.1f punti profilo)",
        "badge.effort": "sforzo: %s",
        "badge.qw": "quick win",
        "badge.cross": "trasversale: %d profili &middot; "
                       "+%.1f indice",
        "judge.h": "Giudizio LLM sulla citabilita'",
        "judge.compare": " Indice euristico: %.1f — scarto "
                         "giudice-euristica: %+.1f.",
        "judge.profile": " Profilo %s: %.1f — scarto "
                         "giudice-profilo: %+.1f.",
        "judge.meta": "Modello <code>%s</code> su %d passaggio/i "
                      "&middot; media <b>%.1f</b>/100.%s %s",
        "judge.query": "Query",
        "judge.score": "Punteggio",
        "judge.reason": "Motivazione",
        "judge.skipped": "Non eseguito: %s",
        "lh.h": "Audit Lighthouse",
        "lh.meta": "Eseguito su %d pagina/e (%s)%s.",
        "lh.fork": ", fork %s",
        "lh.cat": "Categoria",
        "lh.score": "Punteggio",
        "lh.skipped": "Non eseguito: %s",
        "tm.h": "Treemap della superficie contenutistica",
        "tm.meta": "Ogni rettangolo e' una pagina: area "
                   "proporzionale alle parole indicizzabili, "
                   "colore dalla gravita' dei rilievi che citano "
                   "la pagina. Mostrate %d pagine su %d "
                   "analizzabili.",
        "tm.aria": "Treemap delle pagine per parole "
                   "indicizzabili; i dati sono nella tabella "
                   "sottostante",
        "tm.title": "%s — %d parole, %d chunk, %s",
        "tm.table": "Dati della treemap in tabella",
        "tm.page": "Pagina",
        "tm.words": "Parole",
        "tm.chunks": "Chunk",
        "tm.sev": "Rilievi",
        "tm.sev_critical": "rilievi critici sulla pagina",
        "tm.sev_warning": "avvertenze sulla pagina",
        "tm.sev_ok": "nessun rilievo sulla pagina",
        "sc.h": "Ancora di realta' (Brave Search)",
        "sc.meta": "Sito trovato per %d query su %d (primi %d "
                   "risultati).",
        "sc.query": "Query",
        "sc.result": "Posizione reale",
        "sc.rrf": "Consenso RRF",
        "sc.pos": "#%d",
        "sc.absent": "assente dai primi %d",
        "sc.error": "errore: %s",
        "sc.skipped": "Non eseguita: %s",
        "lg.hint": "Con JavaScript attivo: trascina i nodi (la "
                   "fisica segue), clic su un nodo per bloccare "
                   "l'evidenziazione (Esc per liberarla), rotella "
                   "o pulsanti per lo zoom, trascina lo sfondo "
                   "per spostarti.",
        "lg.zin": "Ingrandisci",
        "lg.zout": "Riduci",
        "lg.reset": "Vista iniziale",
        "lg.vforza": "Vista a forza",
        "lg.vanelli": "Anelli di profondità",
        "lg.legend": "Legenda: ● home · ● entro 3 click · "
                     "● oltre 3 click o senza percorso; ampiezza "
                     "= link in ingresso; le frecce seguono la "
                     "direzione del link; negli anelli il cerchio "
                     "marcato è la soglia dei 3 click.",
        "lg.outgoing": "%d in uscita",
        "depth.h": "Profondita' di crawl",
        "depth.meta": "Quanti click servono dalla home per "
                      "raggiungere ogni pagina lungo i link "
                      "interni: oltre 3 click scansione e peso "
                      "calano.",
        "graph.h": "Architettura dei link interni",
        "graph.meta": "Ogni cerchio e' una pagina (ampiezza = link "
                      "in ingresso), la home e' al centro; in ambra "
                      "le pagine oltre 3 click o senza percorso. "
                      "Mostrate %d pagine su %d.",
        "graph.aria": "Grafo dei link interni; orfane e profondita' "
                      "sono nei rilievi dell'area tecnica",
        "graph.clicks": "%d click",
        "graph.sitemap_only": "solo da sitemap",
        "graph.node_title": "%s — %d link in ingresso, %s",
        "math.h": "La matematica del problema",
        "math.meta": "L'RRF premia chi compare in piu' liste con "
                     "piu' passaggi pertinenti: il numero di chunk "
                     "indicizzabili e' il vero moltiplicatore.",
        "math.now": "Superficie attuale",
        "math.now_v": "%d pagine, %d chunk (~%d parole/pagina)",
        "math.pot": "Superficie potenziale",
        "math.pot_v": "~%d chunk (%s)",
        "math.fx": "Effetto sull'RRF",
        "math.mult": "~%.1fx occasioni di comparire nelle liste "
                     "fuse",
        "math.zero": "da 0 addendi a ~%d occasioni di comparire "
                     "nelle liste",
        "plan.h": "Piano di remediation",
        "plan.crit_gain": "gravita' e guadagno di citabilita': in "
                          "testa i problemi trasversali, che "
                          "deprimono piu' profili insieme",
        "plan.crit_weight": "gravita' e peso: si parte da cio' che "
                            "rende di piu' sul punteggio",
        "plan.meta": "%d interventi ordinati per %s. Lo sforzo "
                     "stimato (minuti/ore/giorni) individua i "
                     "quick win%s.",
        "plan.quick_here": " — qui sono %d",
        "rrf.h": "Dettaglio simulazione RRF",
        "rrf.meta": "Le tacche sul consenso sono le soglie del "
                    "giudizio: sotto il 20% e' critico, sotto il "
                    "45% da migliorare.",
        "rrf.query": "Query",
        "rrf.consensus": "Consenso",
        "rrf.top": "Passaggio in testa dopo la fusione",
        "rrf.score": "Punteggio",
        "rrf.of5": "%d su 5",
        "comp.h": "Confronto competitivo",
        "comp.meta": "Share of voice sui primi %d posti delle "
                     "liste fuse, sulle query dei temi del tuo "
                     "sito. La tacca indica la parita' (%.0f%%): "
                     "sopra la tacca si e' sopra la propria quota "
                     "naturale.",
        "comp.site": "Sito",
        "comp.share": "Share",
        "comp.mine": " <strong>(tuo sito)</strong>",
        "comp.bubble_meta": "Mappa: orizzontale la share of voice, "
                            "verticale in quante query su %d il "
                            "sito compare, ampiezza della bolla il "
                            "corpus in chunk.",
        "comp.bubble_aria": "Mappa a bolle del posizionamento "
                            "competitivo; i valori sono nelle "
                            "tabelle",
        "comp.query": "Query",
        "comp.mine_passages": "Tuoi passaggi",
        "comp.best": "Migliore posizione",
        "comp.absent": "<strong>assente</strong>",
        "footer.gen": "Generato da <code>mars_audit.py</code> "
                      "v%s. La formula applicata e' <code>score(d) "
                      "= &Sigma; 1/(k + rank_i(d))</code> con k=%d, "
                      "pesi uguali per ogni lista.",
        "footer.refs": "Riferimenti",
        "anchor.label": "Link a questo rilievo",
    },
    "en": {
        "hero.ring": "Overall score %.0f out of 100: %s",
        "hero.of100": "out of 100",
        "hero.thresholds": "good &ge; 70 &middot; needs work "
                           "40&ndash;69 &middot; critical &lt; 40",
        "verdict.Buono": "Good",
        "verdict.Da migliorare": "Needs work",
        "verdict.Critico": "Critical",
        "tile.critical": "Critical",
        "tile.warning": "Warnings",
        "tile.info": "Notices",
        "hero.donut_aria": "%d pages: %d clean, %d with findings, "
                           "%d failing",
        "hero.pages": "pages",
        "hero.clean": "%d clean",
        "hero.flagged": "%d with findings",
        "hero.broken": "%d failing",
        "meta.line": "Pages analysed: %d &middot; indexed chunks: "
                     "%d &middot; vector retriever: <code>%s</code>",
        "note.findings_lang": "Report in English. Quoted evidence "
                              "from the audited site (URLs, page "
                              "excerpts) and the run-comparison "
                              "titles stay in the site's "
                              "language.",
        "top.h": "Top findings",
        "top.critical": "CRITICAL",
        "top.warning": "WARNING",
        "gain.index": "+%.1f index",
        "score.total": "Overall",
        "area.Tecnica": "Technical",
        "area.Lessicale (BM25)": "Lexical (BM25)",
        "area.Semantica (vettoriale)": "Semantic (vector)",
        "area.Dati strutturati": "Structured data",
        "area.Simulazione RRF": "RRF simulation",
        "delta.h": "Compared with the previous run",
        "delta.meta": "Comparison with the %s audit of the same "
                      "site: the audit becomes monitoring. "
                      "Findings are compared by type (counts in "
                      "titles may vary).",
        "delta.resolved": "Resolved",
        "delta.new": "New",
        "delta.none": "None.",
        "cit.h": "Citability profiles per AI assistant",
        "cit.meta": "%s Reference market: <b>%s</b> "
                    "(weights: %s).",
        "cit.assistant": "Assistant",
        "cit.focus": "What it rewards",
        "cit.score": "Score",
        "cit.index": "Composite index (%s market)",
        "cit.actions_h": "Top %d priority actions",
        "cit.actions_meta": "The first remediation-plan items with "
                            "the profile that gains the most "
                            "(estimate in profile points, same "
                            "heuristic nature).",
        "cit.best": " &mdash; gains the most: <b>%s</b> "
                    "(+%.1f profile points)",
        "badge.effort": "effort: %s",
        "badge.qw": "quick win",
        "badge.cross": "cross-cutting: %d profiles &middot; "
                       "+%.1f index",
        "judge.h": "LLM judgement on citability",
        "judge.compare": " Heuristic index: %.1f — judge-heuristic "
                         "gap: %+.1f.",
        "judge.profile": " Profile %s: %.1f — judge-profile "
                         "gap: %+.1f.",
        "judge.meta": "Model <code>%s</code> on %d passage(s) "
                      "&middot; average <b>%.1f</b>/100.%s %s",
        "judge.query": "Query",
        "judge.score": "Score",
        "judge.reason": "Rationale",
        "judge.skipped": "Not run: %s",
        "lh.h": "Lighthouse audit",
        "lh.meta": "Run on %d page(s) (%s)%s.",
        "lh.fork": ", fork %s",
        "lh.cat": "Category",
        "lh.score": "Score",
        "lh.skipped": "Not run: %s",
        "tm.h": "Content surface treemap",
        "tm.meta": "Each rectangle is a page: area proportional "
                   "to indexable words, colour from the severity "
                   "of the findings referencing the page. Showing "
                   "%d pages out of %d analysable.",
        "tm.aria": "Treemap of pages by indexable words; the "
                   "data is in the table below",
        "tm.title": "%s — %d words, %d chunks, %s",
        "tm.table": "Treemap data as a table",
        "tm.page": "Page",
        "tm.words": "Words",
        "tm.chunks": "Chunks",
        "tm.sev": "Findings",
        "tm.sev_critical": "critical findings on the page",
        "tm.sev_warning": "warnings on the page",
        "tm.sev_ok": "no findings on the page",
        "sc.h": "Reality anchor (Brave Search)",
        "sc.meta": "Site found for %d of %d queries (top %d "
                   "results).",
        "sc.query": "Query",
        "sc.result": "Real position",
        "sc.rrf": "RRF consensus",
        "sc.pos": "#%d",
        "sc.absent": "absent from the top %d",
        "sc.error": "error: %s",
        "sc.skipped": "Not run: %s",
        "lg.hint": "With JavaScript enabled: drag nodes (the "
                   "physics follows), click a node to pin the "
                   "highlight (Esc releases it), mouse wheel or "
                   "buttons to zoom, drag the background to pan.",
        "lg.zin": "Zoom in",
        "lg.zout": "Zoom out",
        "lg.reset": "Initial view",
        "lg.vforza": "Force view",
        "lg.vanelli": "Depth rings",
        "lg.legend": "Legend: ● home · ● within 3 clicks · "
                     "● beyond 3 clicks or unreachable; size = "
                     "incoming links; arrows follow the link "
                     "direction; in the rings view the marked "
                     "circle is the 3-click threshold.",
        "lg.outgoing": "%d outgoing",
        "depth.h": "Crawl depth",
        "depth.meta": "How many clicks from the home page it takes "
                      "to reach each page along internal links: "
                      "beyond 3 clicks crawling and weight "
                      "decline.",
        "graph.h": "Internal link architecture",
        "graph.meta": "Each circle is a page (size = incoming "
                      "links), the home page is at the centre; "
                      "amber marks pages beyond 3 clicks or with "
                      "no path. Showing %d pages out of %d.",
        "graph.aria": "Internal link graph; orphans and depth are "
                      "covered by the technical-area findings",
        "graph.clicks": "%d clicks",
        "graph.sitemap_only": "sitemap only",
        "graph.node_title": "%s — %d incoming links, %s",
        "math.h": "The maths of the problem",
        "math.meta": "RRF rewards sites that appear in more lists "
                     "with more relevant passages: the number of "
                     "indexable chunks is the real multiplier.",
        "math.now": "Current surface",
        "math.now_v": "%d pages, %d chunks (~%d words/page)",
        "math.pot": "Potential surface",
        "math.pot_v": "~%d chunks (%s)",
        "math.fx": "Effect on RRF",
        "math.mult": "~%.1fx opportunities to appear in the fused "
                     "lists",
        "math.zero": "from 0 addends to ~%d opportunities to "
                     "appear in the lists",
        "plan.h": "Remediation plan",
        "plan.crit_gain": "severity and citability gain: "
                          "cross-cutting problems, which depress "
                          "several profiles at once, come first",
        "plan.crit_weight": "severity and weight: starting from "
                            "what yields the most on the score",
        "plan.meta": "%d actions sorted by %s. The estimated "
                     "effort (minutes/hours/days) singles out the "
                     "quick wins%s.",
        "plan.quick_here": " — %d here",
        "rrf.h": "RRF simulation detail",
        "rrf.meta": "The ticks on consensus are the judgement "
                    "thresholds: below 20% critical, below 45% "
                    "needs work.",
        "rrf.query": "Query",
        "rrf.consensus": "Consensus",
        "rrf.top": "Top passage after fusion",
        "rrf.score": "Score",
        "rrf.of5": "%d of 5",
        "comp.h": "Competitive comparison",
        "comp.meta": "Share of voice over the first %d fused "
                     "positions, on queries from your site's "
                     "themes. The tick marks parity (%.0f%%): "
                     "above it you exceed your natural share.",
        "comp.site": "Site",
        "comp.share": "Share",
        "comp.mine": " <strong>(your site)</strong>",
        "comp.bubble_meta": "Map: share of voice horizontally, in "
                            "how many of %d queries the site "
                            "appears vertically, bubble size the "
                            "corpus in chunks.",
        "comp.bubble_aria": "Bubble map of competitive "
                            "positioning; values are in the "
                            "tables",
        "comp.query": "Query",
        "comp.mine_passages": "Your passages",
        "comp.best": "Best position",
        "comp.absent": "<strong>absent</strong>",
        "footer.gen": "Generated by <code>mars_audit.py</code> "
                      "v%s. The applied formula is <code>score(d) "
                      "= &Sigma; 1/(k + rank_i(d))</code> with "
                      "k=%d, equal weights per list.",
        "footer.refs": "References",
        "anchor.label": "Link to this finding",
    },
    "fr": {
        "hero.ring": "Score global %.0f sur 100 : %s",
        "hero.of100": "sur 100",
        "hero.thresholds": "bon &ge; 70 &middot; à améliorer "
                           "40&ndash;69 &middot; critique &lt; 40",
        "verdict.Buono": "Bon",
        "verdict.Da migliorare": "À améliorer",
        "verdict.Critico": "Critique",
        "tile.critical": "Critiques",
        "tile.warning": "Avertissements",
        "tile.info": "Informations",
        "hero.donut_aria": "%d pages : %d sans constats, %d avec "
                           "constats, %d en erreur",
        "hero.pages": "pages",
        "hero.clean": "%d sans constats",
        "hero.flagged": "%d avec constats",
        "hero.broken": "%d en erreur",
        "meta.line": "Pages analysées : %d &middot; chunks "
                     "indexés : %d &middot; récupérateur "
                     "vectoriel : <code>%s</code>",
        "note.findings_lang": "Rapport en français. Les extraits "
                              "cités du site audité (URL, "
                              "extraits de pages) et les titres "
                              "de la comparaison entre exécutions "
                              "restent dans la langue du site.",
        "top.h": "Principaux constats",
        "top.critical": "CRITIQUE",
        "top.warning": "AVERTISSEMENT",
        "gain.index": "+%.1f indice",
        "score.total": "Global",
        "area.Tecnica": "Technique",
        "area.Lessicale (BM25)": "Lexicale (BM25)",
        "area.Semantica (vettoriale)": "Sémantique (vectorielle)",
        "area.Dati strutturati": "Données structurées",
        "area.Simulazione RRF": "Simulation RRF",
        "delta.h": "Par rapport à l'exécution précédente",
        "delta.meta": "Comparaison avec l'audit du %s sur le même "
                      "site : l'audit devient monitoring. "
                      "Constats comparés par type (les comptes "
                      "dans les titres peuvent varier).",
        "delta.resolved": "Résolus",
        "delta.new": "Nouveaux",
        "delta.none": "Aucun.",
        "cit.h": "Profils de citabilité par assistant IA",
        "cit.meta": "%s Marché de référence : <b>%s</b> "
                    "(poids : %s).",
        "cit.assistant": "Assistant",
        "cit.focus": "Ce qu'il récompense",
        "cit.score": "Score",
        "cit.index": "Indice composite (marché %s)",
        "cit.actions_h": "Top %d actions prioritaires",
        "cit.actions_meta": "Les premières entrées du plan de "
                            "remédiation avec le profil qui y "
                            "gagne le plus (estimation en points "
                            "de profil, même nature heuristique).",
        "cit.best": " &mdash; y gagne le plus : <b>%s</b> "
                    "(+%.1f points de profil)",
        "badge.effort": "effort : %s",
        "badge.qw": "quick win",
        "badge.cross": "transversal : %d profils &middot; "
                       "+%.1f indice",
        "judge.h": "Jugement LLM sur la citabilité",
        "judge.compare": " Indice heuristique : %.1f — écart "
                         "juge-heuristique : %+.1f.",
        "judge.profile": " Profil %s : %.1f — écart "
                         "juge-profil : %+.1f.",
        "judge.meta": "Modèle <code>%s</code> sur %d passage(s) "
                      "&middot; moyenne <b>%.1f</b>/100.%s %s",
        "judge.query": "Requête",
        "judge.score": "Score",
        "judge.reason": "Motivation",
        "judge.skipped": "Non exécuté : %s",
        "lh.h": "Audit Lighthouse",
        "lh.meta": "Exécuté sur %d page(s) (%s)%s.",
        "lh.fork": ", fork %s",
        "lh.cat": "Catégorie",
        "lh.score": "Score",
        "lh.skipped": "Non exécuté : %s",
        "tm.h": "Treemap de la surface de contenu",
        "tm.meta": "Chaque rectangle est une page : aire "
                   "proportionnelle aux mots indexables, couleur "
                   "selon la gravité des constats citant la "
                   "page. %d pages affichées sur %d analysables.",
        "tm.aria": "Treemap des pages par mots indexables ; les "
                   "données sont dans le tableau ci-dessous",
        "tm.title": "%s — %d mots, %d chunks, %s",
        "tm.table": "Données de la treemap en tableau",
        "tm.page": "Page",
        "tm.words": "Mots",
        "tm.chunks": "Chunks",
        "tm.sev": "Constats",
        "tm.sev_critical": "constats critiques sur la page",
        "tm.sev_warning": "avertissements sur la page",
        "tm.sev_ok": "aucun constat sur la page",
        "sc.h": "Ancre de réalité (Brave Search)",
        "sc.meta": "Site trouvé pour %d requêtes sur %d (%d "
                   "premiers résultats).",
        "sc.query": "Requête",
        "sc.result": "Position réelle",
        "sc.rrf": "Consensus RRF",
        "sc.pos": "#%d",
        "sc.absent": "absent des %d premiers",
        "sc.error": "erreur : %s",
        "sc.skipped": "Non exécutée : %s",
        "lg.hint": "Avec JavaScript actif : faites glisser les "
                   "nœuds (la physique suit), cliquez sur un "
                   "nœud pour verrouiller la surbrillance (Échap "
                   "la libère), molette ou boutons pour le zoom, "
                   "faites glisser l'arrière-plan pour vous "
                   "déplacer.",
        "lg.zin": "Agrandir",
        "lg.zout": "Réduire",
        "lg.reset": "Vue initiale",
        "lg.vforza": "Vue en force",
        "lg.vanelli": "Anneaux de profondeur",
        "lg.legend": "Légende : ● accueil · ● à moins de 3 "
                     "clics · ● au-delà de 3 clics ou sans "
                     "chemin ; taille = liens entrants ; les "
                     "flèches suivent la direction du lien ; "
                     "dans les anneaux, le cercle marqué est le "
                     "seuil des 3 clics.",
        "lg.outgoing": "%d sortants",
        "depth.h": "Profondeur de crawl",
        "depth.meta": "Combien de clics depuis l'accueil pour "
                      "atteindre chaque page le long des liens "
                      "internes : au-delà de 3 clics, "
                      "exploration et poids déclinent.",
        "graph.h": "Architecture des liens internes",
        "graph.meta": "Chaque cercle est une page (taille = "
                      "liens entrants), l'accueil est au "
                      "centre ; en ambre les pages au-delà de 3 "
                      "clics ou sans chemin. %d pages affichées "
                      "sur %d.",
        "graph.aria": "Graphe des liens internes ; orphelines et "
                      "profondeur sont dans les constats du "
                      "domaine technique",
        "graph.clicks": "%d clics",
        "graph.sitemap_only": "sitemap uniquement",
        "graph.node_title": "%s — %d liens entrants, %s",
        "math.h": "Les mathématiques du problème",
        "math.meta": "Le RRF récompense qui apparaît dans plus "
                     "de listes avec plus de passages "
                     "pertinents : le nombre de chunks "
                     "indexables est le vrai multiplicateur.",
        "math.now": "Surface actuelle",
        "math.now_v": "%d pages, %d chunks (~%d mots/page)",
        "math.pot": "Surface potentielle",
        "math.pot_v": "~%d chunks (%s)",
        "math.fx": "Effet sur le RRF",
        "math.mult": "~%.1fx occasions d'apparaître dans les "
                     "listes fusionnées",
        "math.zero": "de 0 addende à ~%d occasions d'apparaître "
                     "dans les listes",
        "plan.h": "Plan de remédiation",
        "plan.crit_gain": "gravité et gain de citabilité : en "
                          "tête les problèmes transversaux, qui "
                          "dépriment plusieurs profils à la "
                          "fois",
        "plan.crit_weight": "gravité et poids : on part de ce "
                            "qui rapporte le plus au score",
        "plan.meta": "%d interventions triées par %s. L'effort "
                     "estimé (minutes/heures/jours) repère les "
                     "quick wins%s.",
        "plan.quick_here": " — ici %d",
        "rrf.h": "Détail de la simulation RRF",
        "rrf.meta": "Les repères sur le consensus sont les "
                    "seuils du jugement : sous 20 % critique, "
                    "sous 45 % à améliorer.",
        "rrf.query": "Requête",
        "rrf.consensus": "Consensus",
        "rrf.top": "Passage en tête après la fusion",
        "rrf.score": "Score",
        "rrf.of5": "%d sur 5",
        "comp.h": "Comparaison concurrentielle",
        "comp.meta": "Share of voice sur les %d premières places "
                     "des listes fusionnées, sur les requêtes "
                     "des thèmes de votre site. Le repère "
                     "indique la parité (%.0f%%) : au-dessus, "
                     "vous dépassez votre part naturelle.",
        "comp.site": "Site",
        "comp.share": "Part",
        "comp.mine": " <strong>(votre site)</strong>",
        "comp.bubble_meta": "Carte : la share of voice à "
                            "l'horizontale, en vertical dans "
                            "combien de requêtes sur %d le site "
                            "apparaît, taille de la bulle le "
                            "corpus en chunks.",
        "comp.bubble_aria": "Carte à bulles du positionnement "
                            "concurrentiel ; les valeurs sont "
                            "dans les tableaux",
        "comp.query": "Requête",
        "comp.mine_passages": "Vos passages",
        "comp.best": "Meilleure position",
        "comp.absent": "<strong>absent</strong>",
        "footer.gen": "Généré par <code>mars_audit.py</code> "
                      "v%s. La formule appliquée est "
                      "<code>score(d) = &Sigma; 1/(k + "
                      "rank_i(d))</code> avec k=%d, poids égaux "
                      "pour chaque liste.",
        "footer.refs": "Références",
        "anchor.label": "Lien vers ce constat",
    },
    "de": {
        "hero.ring": "Gesamtpunktzahl %.0f von 100: %s",
        "hero.of100": "von 100",
        "hero.thresholds": "gut &ge; 70 &middot; "
                           "verbesserungswürdig 40&ndash;69 "
                           "&middot; kritisch &lt; 40",
        "verdict.Buono": "Gut",
        "verdict.Da migliorare": "Verbesserungswürdig",
        "verdict.Critico": "Kritisch",
        "tile.critical": "Kritisch",
        "tile.warning": "Warnungen",
        "tile.info": "Hinweise",
        "hero.donut_aria": "%d Seiten: %d ohne Befunde, %d mit "
                           "Befunden, %d fehlerhaft",
        "hero.pages": "Seiten",
        "hero.clean": "%d ohne Befunde",
        "hero.flagged": "%d mit Befunden",
        "hero.broken": "%d fehlerhaft",
        "meta.line": "Analysierte Seiten: %d &middot; indexierte "
                     "Chunks: %d &middot; Vektor-Retriever: "
                     "<code>%s</code>",
        "note.findings_lang": "Bericht auf Deutsch. Zitierte "
                              "Belege der geprüften Website "
                              "(URLs, Seitenauszüge) und die "
                              "Titel des Laufvergleichs bleiben "
                              "in der Sprache der Website.",
        "top.h": "Top-Befunde",
        "top.critical": "KRITISCH",
        "top.warning": "WARNUNG",
        "gain.index": "+%.1f Index",
        "score.total": "Gesamt",
        "area.Tecnica": "Technik",
        "area.Lessicale (BM25)": "Lexikalisch (BM25)",
        "area.Semantica (vettoriale)": "Semantisch (vektoriell)",
        "area.Dati strutturati": "Strukturierte Daten",
        "area.Simulazione RRF": "RRF-Simulation",
        "delta.h": "Im Vergleich zum vorherigen Lauf",
        "delta.meta": "Vergleich mit dem Audit vom %s derselben "
                      "Website: das Audit wird zum Monitoring. "
                      "Befunde nach Typ verglichen (Zahlen in "
                      "den Titeln können variieren).",
        "delta.resolved": "Behoben",
        "delta.new": "Neu",
        "delta.none": "Keine.",
        "cit.h": "Zitierbarkeitsprofile je KI-Assistent",
        "cit.meta": "%s Referenzmarkt: <b>%s</b> "
                    "(Gewichte: %s).",
        "cit.assistant": "Assistent",
        "cit.focus": "Was er belohnt",
        "cit.score": "Punktzahl",
        "cit.index": "Kompositindex (Markt %s)",
        "cit.actions_h": "Top %d prioritäre Maßnahmen",
        "cit.actions_meta": "Die ersten Einträge des "
                            "Behebungsplans mit dem Profil, das "
                            "am meisten gewinnt (Schätzung in "
                            "Profilpunkten, gleiche heuristische "
                            "Natur).",
        "cit.best": " &mdash; gewinnt am meisten: <b>%s</b> "
                    "(+%.1f Profilpunkte)",
        "badge.effort": "Aufwand: %s",
        "badge.qw": "Quick Win",
        "badge.cross": "übergreifend: %d Profile &middot; "
                       "+%.1f Index",
        "judge.h": "LLM-Urteil zur Zitierbarkeit",
        "judge.compare": " Heuristischer Index: %.1f — Abstand "
                         "Richter-Heuristik: %+.1f.",
        "judge.profile": " Profil %s: %.1f — Abstand "
                         "Richter-Profil: %+.1f.",
        "judge.meta": "Modell <code>%s</code> auf %d Passage(n) "
                      "&middot; Durchschnitt <b>%.1f</b>/100.%s "
                      "%s",
        "judge.query": "Anfrage",
        "judge.score": "Punktzahl",
        "judge.reason": "Begründung",
        "judge.skipped": "Nicht ausgeführt: %s",
        "lh.h": "Lighthouse-Audit",
        "lh.meta": "Ausgeführt auf %d Seite(n) (%s)%s.",
        "lh.fork": ", Fork %s",
        "lh.cat": "Kategorie",
        "lh.score": "Punktzahl",
        "lh.skipped": "Nicht ausgeführt: %s",
        "tm.h": "Treemap der Inhaltsfläche",
        "tm.meta": "Jedes Rechteck ist eine Seite: Fläche "
                   "proportional zu den indexierbaren Wörtern, "
                   "Farbe nach der Schwere der Befunde, die die "
                   "Seite nennen. %d von %d analysierbaren "
                   "Seiten gezeigt.",
        "tm.aria": "Treemap der Seiten nach indexierbaren "
                   "Wörtern; die Daten stehen in der Tabelle "
                   "darunter",
        "tm.title": "%s — %d Wörter, %d Chunks, %s",
        "tm.table": "Treemap-Daten als Tabelle",
        "tm.page": "Seite",
        "tm.words": "Wörter",
        "tm.chunks": "Chunks",
        "tm.sev": "Befunde",
        "tm.sev_critical": "kritische Befunde auf der Seite",
        "tm.sev_warning": "Warnungen auf der Seite",
        "tm.sev_ok": "keine Befunde auf der Seite",
        "sc.h": "Realitätsanker (Brave Search)",
        "sc.meta": "Website für %d von %d Anfragen gefunden "
                   "(erste %d Ergebnisse).",
        "sc.query": "Anfrage",
        "sc.result": "Reale Position",
        "sc.rrf": "RRF-Konsens",
        "sc.pos": "#%d",
        "sc.absent": "fehlt unter den ersten %d",
        "sc.error": "Fehler: %s",
        "sc.skipped": "Nicht ausgeführt: %s",
        "lg.hint": "Mit aktivem JavaScript: Knoten ziehen (die "
                   "Physik folgt), Klick auf einen Knoten "
                   "fixiert die Hervorhebung (Esc löst sie), "
                   "Mausrad oder Schaltflächen zum Zoomen, "
                   "Hintergrund ziehen zum Verschieben.",
        "lg.zin": "Vergrößern",
        "lg.zout": "Verkleinern",
        "lg.reset": "Ausgangsansicht",
        "lg.vforza": "Kraftansicht",
        "lg.vanelli": "Tiefenringe",
        "lg.legend": "Legende: ● Startseite · ● innerhalb von 3 "
                     "Klicks · ● über 3 Klicks oder ohne Pfad; "
                     "Größe = eingehende Links; Pfeile folgen "
                     "der Linkrichtung; in den Ringen markiert "
                     "der hervorgehobene Kreis die "
                     "3-Klick-Schwelle.",
        "lg.outgoing": "%d ausgehend",
        "depth.h": "Crawl-Tiefe",
        "depth.meta": "Wie viele Klicks von der Startseite nötig "
                      "sind, um jede Seite über interne Links zu "
                      "erreichen: jenseits von 3 Klicks sinken "
                      "Crawling und Gewicht.",
        "graph.h": "Architektur der internen Links",
        "graph.meta": "Jeder Kreis ist eine Seite (Größe = "
                      "eingehende Links), die Startseite liegt "
                      "im Zentrum; bernsteinfarben die Seiten "
                      "über 3 Klicks oder ohne Pfad. %d von %d "
                      "Seiten gezeigt.",
        "graph.aria": "Graph der internen Links; Verwaiste und "
                      "Tiefe stehen in den Befunden des "
                      "Technikbereichs",
        "graph.clicks": "%d Klicks",
        "graph.sitemap_only": "nur über Sitemap",
        "graph.node_title": "%s — %d eingehende Links, %s",
        "math.h": "Die Mathematik des Problems",
        "math.meta": "RRF belohnt, wer in mehr Listen mit mehr "
                     "relevanten Passagen erscheint: die Zahl "
                     "der indexierbaren Chunks ist der wahre "
                     "Multiplikator.",
        "math.now": "Aktuelle Fläche",
        "math.now_v": "%d Seiten, %d Chunks (~%d Wörter/Seite)",
        "math.pot": "Potenzielle Fläche",
        "math.pot_v": "~%d Chunks (%s)",
        "math.fx": "Wirkung auf RRF",
        "math.mult": "~%.1fx Chancen, in den fusionierten Listen "
                     "zu erscheinen",
        "math.zero": "von 0 Summanden zu ~%d Chancen, in den "
                     "Listen zu erscheinen",
        "plan.h": "Behebungsplan",
        "plan.crit_gain": "Schwere und Zitierbarkeitsgewinn: "
                          "vorn die übergreifenden Probleme, die "
                          "mehrere Profile zugleich drücken",
        "plan.crit_weight": "Schwere und Gewicht: begonnen wird "
                            "mit dem, was am meisten Punkte "
                            "bringt",
        "plan.meta": "%d Maßnahmen sortiert nach %s. Der "
                     "geschätzte Aufwand "
                     "(Minuten/Stunden/Tage) markiert die Quick "
                     "Wins%s.",
        "plan.quick_here": " — hier %d",
        "rrf.h": "Detail der RRF-Simulation",
        "rrf.meta": "Die Marken am Konsens sind die "
                    "Urteilsschwellen: unter 20% kritisch, unter "
                    "45% verbesserungswürdig.",
        "rrf.query": "Anfrage",
        "rrf.consensus": "Konsens",
        "rrf.top": "Führende Passage nach der Fusion",
        "rrf.score": "Punktzahl",
        "rrf.of5": "%d von 5",
        "comp.h": "Wettbewerbsvergleich",
        "comp.meta": "Share of Voice über die ersten %d Plätze "
                     "der fusionierten Listen, auf den Anfragen "
                     "zu den Themen Ihrer Website. Die Marke "
                     "zeigt die Parität (%.0f%%): darüber liegen "
                     "Sie über Ihrem natürlichen Anteil.",
        "comp.site": "Website",
        "comp.share": "Anteil",
        "comp.mine": " <strong>(Ihre Website)</strong>",
        "comp.bubble_meta": "Karte: horizontal die Share of "
                            "Voice, vertikal in wie vielen von "
                            "%d Anfragen die Website erscheint, "
                            "Blasengröße der Korpus in Chunks.",
        "comp.bubble_aria": "Blasenkarte der "
                            "Wettbewerbspositionierung; die "
                            "Werte stehen in den Tabellen",
        "comp.query": "Anfrage",
        "comp.mine_passages": "Ihre Passagen",
        "comp.best": "Beste Position",
        "comp.absent": "<strong>fehlt</strong>",
        "footer.gen": "Erzeugt von <code>mars_audit.py</code> "
                      "v%s. Die angewandte Formel ist "
                      "<code>score(d) = &Sigma; 1/(k + "
                      "rank_i(d))</code> mit k=%d, gleiche "
                      "Gewichte je Liste.",
        "footer.refs": "Referenzen",
        "anchor.label": "Link zu diesem Befund",
    },
    "es": {
        "hero.ring": "Puntuación global %.0f sobre 100: %s",
        "hero.of100": "sobre 100",
        "hero.thresholds": "bueno &ge; 70 &middot; mejorable "
                           "40&ndash;69 &middot; crítico &lt; 40",
        "verdict.Buono": "Bueno",
        "verdict.Da migliorare": "Mejorable",
        "verdict.Critico": "Crítico",
        "tile.critical": "Críticos",
        "tile.warning": "Advertencias",
        "tile.info": "Avisos",
        "hero.donut_aria": "%d páginas: %d sin hallazgos, %d con "
                           "hallazgos, %d con error",
        "hero.pages": "páginas",
        "hero.clean": "%d sin hallazgos",
        "hero.flagged": "%d con hallazgos",
        "hero.broken": "%d con error",
        "meta.line": "Páginas analizadas: %d &middot; chunks "
                     "indexados: %d &middot; recuperador "
                     "vectorial: <code>%s</code>",
        "note.findings_lang": "Informe en español. Las "
                              "evidencias citadas del sitio "
                              "auditado (URL, extractos de "
                              "páginas) y los títulos de la "
                              "comparación entre ejecuciones "
                              "permanecen en el idioma del "
                              "sitio.",
        "top.h": "Principales hallazgos",
        "top.critical": "CRÍTICO",
        "top.warning": "ADVERTENCIA",
        "gain.index": "+%.1f índice",
        "score.total": "Global",
        "area.Tecnica": "Técnica",
        "area.Lessicale (BM25)": "Léxica (BM25)",
        "area.Semantica (vettoriale)": "Semántica (vectorial)",
        "area.Dati strutturati": "Datos estructurados",
        "area.Simulazione RRF": "Simulación RRF",
        "delta.h": "Respecto a la ejecución anterior",
        "delta.meta": "Comparación con la auditoría del %s sobre "
                      "el mismo sitio: la auditoría se convierte "
                      "en monitorización. Hallazgos comparados "
                      "por tipo (los recuentos en los títulos "
                      "pueden variar).",
        "delta.resolved": "Resueltos",
        "delta.new": "Nuevos",
        "delta.none": "Ninguno.",
        "cit.h": "Perfiles de citabilidad por asistente de IA",
        "cit.meta": "%s Mercado de referencia: <b>%s</b> "
                    "(pesos: %s).",
        "cit.assistant": "Asistente",
        "cit.focus": "Qué premia",
        "cit.score": "Puntuación",
        "cit.index": "Índice compuesto (mercado %s)",
        "cit.actions_h": "Top %d acciones prioritarias",
        "cit.actions_meta": "Las primeras entradas del plan de "
                            "corrección con el perfil que más "
                            "gana (estimación en puntos de "
                            "perfil, misma naturaleza "
                            "heurística).",
        "cit.best": " &mdash; gana más: <b>%s</b> "
                    "(+%.1f puntos de perfil)",
        "badge.effort": "esfuerzo: %s",
        "badge.qw": "quick win",
        "badge.cross": "transversal: %d perfiles &middot; "
                       "+%.1f índice",
        "judge.h": "Juicio LLM sobre la citabilidad",
        "judge.compare": " Índice heurístico: %.1f — brecha "
                         "juez-heurística: %+.1f.",
        "judge.profile": " Perfil %s: %.1f — brecha "
                         "juez-perfil: %+.1f.",
        "judge.meta": "Modelo <code>%s</code> sobre %d "
                      "pasaje(s) &middot; media "
                      "<b>%.1f</b>/100.%s %s",
        "judge.query": "Consulta",
        "judge.score": "Puntuación",
        "judge.reason": "Motivación",
        "judge.skipped": "No ejecutado: %s",
        "lh.h": "Auditoría Lighthouse",
        "lh.meta": "Ejecutada en %d página(s) (%s)%s.",
        "lh.fork": ", fork %s",
        "lh.cat": "Categoría",
        "lh.score": "Puntuación",
        "lh.skipped": "No ejecutada: %s",
        "tm.h": "Treemap de la superficie de contenido",
        "tm.meta": "Cada rectángulo es una página: área "
                   "proporcional a las palabras indexables, "
                   "color según la gravedad de los hallazgos que "
                   "citan la página. Se muestran %d páginas de "
                   "%d analizables.",
        "tm.aria": "Treemap de las páginas por palabras "
                   "indexables; los datos están en la tabla "
                   "inferior",
        "tm.title": "%s — %d palabras, %d chunks, %s",
        "tm.table": "Datos de la treemap en tabla",
        "tm.page": "Página",
        "tm.words": "Palabras",
        "tm.chunks": "Chunks",
        "tm.sev": "Hallazgos",
        "tm.sev_critical": "hallazgos críticos en la página",
        "tm.sev_warning": "advertencias en la página",
        "tm.sev_ok": "ningún hallazgo en la página",
        "sc.h": "Ancla de realidad (Brave Search)",
        "sc.meta": "Sitio encontrado para %d consultas de %d "
                   "(primeros %d resultados).",
        "sc.query": "Consulta",
        "sc.result": "Posición real",
        "sc.rrf": "Consenso RRF",
        "sc.pos": "#%d",
        "sc.absent": "ausente de los primeros %d",
        "sc.error": "error: %s",
        "sc.skipped": "No ejecutada: %s",
        "lg.hint": "Con JavaScript activo: arrastre los nodos "
                   "(la física sigue), clic en un nodo para "
                   "fijar el resaltado (Esc lo libera), rueda o "
                   "botones para el zoom, arrastre el fondo para "
                   "desplazarse.",
        "lg.zin": "Ampliar",
        "lg.zout": "Reducir",
        "lg.reset": "Vista inicial",
        "lg.vforza": "Vista de fuerzas",
        "lg.vanelli": "Anillos de profundidad",
        "lg.legend": "Leyenda: ● inicio · ● a menos de 3 clics "
                     "· ● más allá de 3 clics o sin camino; "
                     "tamaño = enlaces entrantes; las flechas "
                     "siguen la dirección del enlace; en los "
                     "anillos, el círculo marcado es el umbral "
                     "de los 3 clics.",
        "lg.outgoing": "%d salientes",
        "depth.h": "Profundidad de rastreo",
        "depth.meta": "Cuántos clics hacen falta desde el inicio "
                      "para alcanzar cada página a lo largo de "
                      "los enlaces internos: más allá de 3 "
                      "clics, rastreo y peso decaen.",
        "graph.h": "Arquitectura de los enlaces internos",
        "graph.meta": "Cada círculo es una página (tamaño = "
                      "enlaces entrantes), el inicio está en el "
                      "centro; en ámbar las páginas a más de 3 "
                      "clics o sin camino. Se muestran %d "
                      "páginas de %d.",
        "graph.aria": "Grafo de los enlaces internos; huérfanas "
                      "y profundidad están en los hallazgos del "
                      "área técnica",
        "graph.clicks": "%d clics",
        "graph.sitemap_only": "solo desde sitemap",
        "graph.node_title": "%s — %d enlaces entrantes, %s",
        "math.h": "Las matemáticas del problema",
        "math.meta": "El RRF premia a quien aparece en más "
                     "listas con más pasajes pertinentes: el "
                     "número de chunks indexables es el "
                     "verdadero multiplicador.",
        "math.now": "Superficie actual",
        "math.now_v": "%d páginas, %d chunks (~%d "
                      "palabras/página)",
        "math.pot": "Superficie potencial",
        "math.pot_v": "~%d chunks (%s)",
        "math.fx": "Efecto sobre el RRF",
        "math.mult": "~%.1fx ocasiones de aparecer en las "
                     "listas fusionadas",
        "math.zero": "de 0 sumandos a ~%d ocasiones de aparecer "
                     "en las listas",
        "plan.h": "Plan de corrección",
        "plan.crit_gain": "gravedad y ganancia de citabilidad: "
                          "al frente los problemas "
                          "transversales, que deprimen varios "
                          "perfiles a la vez",
        "plan.crit_weight": "gravedad y peso: se parte de lo que "
                            "más rinde en la puntuación",
        "plan.meta": "%d intervenciones ordenadas por %s. El "
                     "esfuerzo estimado (minutos/horas/días) "
                     "identifica los quick wins%s.",
        "plan.quick_here": " — aquí %d",
        "rrf.h": "Detalle de la simulación RRF",
        "rrf.meta": "Las marcas en el consenso son los umbrales "
                    "del juicio: por debajo del 20% crítico, "
                    "por debajo del 45% mejorable.",
        "rrf.query": "Consulta",
        "rrf.consensus": "Consenso",
        "rrf.top": "Pasaje en cabeza tras la fusión",
        "rrf.score": "Puntuación",
        "rrf.of5": "%d de 5",
        "comp.h": "Comparación competitiva",
        "comp.meta": "Share of voice sobre los primeros %d "
                     "puestos de las listas fusionadas, en las "
                     "consultas de los temas de su sitio. La "
                     "marca indica la paridad (%.0f%%): por "
                     "encima se supera la cuota natural propia.",
        "comp.site": "Sitio",
        "comp.share": "Cuota",
        "comp.mine": " <strong>(su sitio)</strong>",
        "comp.bubble_meta": "Mapa: en horizontal la share of "
                            "voice, en vertical en cuántas "
                            "consultas de %d aparece el sitio, "
                            "tamaño de la burbuja el corpus en "
                            "chunks.",
        "comp.bubble_aria": "Mapa de burbujas del "
                            "posicionamiento competitivo; los "
                            "valores están en las tablas",
        "comp.query": "Consulta",
        "comp.mine_passages": "Sus pasajes",
        "comp.best": "Mejor posición",
        "comp.absent": "<strong>ausente</strong>",
        "footer.gen": "Generado por <code>mars_audit.py</code> "
                      "v%s. La fórmula aplicada es "
                      "<code>score(d) = &Sigma; 1/(k + "
                      "rank_i(d))</code> con k=%d, pesos iguales "
                      "para cada lista.",
        "footer.refs": "Referencias",
        "anchor.label": "Enlace a este hallazgo",
    },
}


# Catalogo inglese dei rilievi: chiave -> template dei testi
# (title/detail/fix/example) con parametri %(nome)s. Contiene SOLO
# l'inglese: l'italiano canonico vive nei punti di creazione dei
# Finding, quindi il referto italiano non passa mai dal catalogo
# (zero rischio di regressione). Le evidenze dinamiche nei params
# (URL, estratti del sito auditato) restano nella lingua del sito.
_FINDINGS_EN: Dict[str, Dict[str, str]] = {
    "tech.robots.missing": {
        "title": "robots.txt not reachable",
        "detail": "Request to %(url)s failed or returned non-200.",
        "fix": "Publish a robots.txt that declares the sitemap.",
    },
    "tech.robots.present": {
        "title": "robots.txt present",
        "detail": "%(n)d lines.",
    },
    "tech.robots.ai_blocked": {
        "title": "AI crawlers blocked: %(agents)s",
        "detail": "These agents cannot access the home page. If "
                  "they are blocked you enter no retrieval list "
                  "and RRF has nothing to fuse.",
        "fix": "Remove the Disallow rules for the agents you want "
               "to be cited by.",
        "example": "# robots.txt - unblock the AI agents\n"
                   "User-agent: GPTBot\nDisallow:\n\n"
                   "User-agent: ClaudeBot\nDisallow:\n\n"
                   "User-agent: PerplexityBot\nDisallow:",
    },
    "tech.robots.ai_allowed": {
        "title": "AI crawlers allowed",
        "detail": "Verified: %(agents)s.",
    },
    "tech.robots.sitemap_ok": {
        "title": "Sitemap declared in robots.txt",
        "detail": "%(urls)s",
    },
    "tech.robots.sitemap_missing": {
        "title": "No sitemap declared in robots.txt",
        "fix": "Add the line 'Sitemap: https://.../sitemap.xml'.",
        "example": "# at the end of robots.txt\n"
                   "Sitemap: https://esempio.it/sitemap.xml",
    },
    "tech.llms.present": {
        "title": "llms.txt present",
        "detail": "%(n)d lines.",
    },
    "tech.llms.missing": {
        "title": "llms.txt missing",
        "detail": "Emerging standard (llmstxt.org): a Markdown "
                  "index of the key content meant for AI agents.",
        "fix": "Consider publishing /llms.txt with your key "
               "content.",
    },
    "tech.links.orphans": {
        "title": "%(n)d page(s) with no incoming internal links "
                 "(orphans)",
        "detail": "Reachable only from the sitemap: %(urls)s. A "
                  "page nobody links to gets fewer crawls and "
                  "less weight.",
        "fix": "Link them from related pages (body copy, menu or "
               "footer).",
        "example": "From the related page:\n"
                   "<a href=\"/servizio-collegato/\">descriptive "
                   "name of the service</a>",
    },
    "tech.links.no_orphans": {
        "title": "Every page has incoming internal links",
    },
    "tech.links.deep": {
        "title": "%(n)d page(s) more than 3 clicks from the home "
                 "page",
        "detail": "%(urls)s.",
        "fix": "Shorten the paths: deep pages get crawled and "
               "weighted less.",
    },
    "tech.links.generic_anchors": {
        "title": "%(n)d generic anchors in internal links",
        "detail": "Texts like \"click here\" or \"read more\" say "
                  "nothing about the destination content.",
        "fix": "Use descriptive anchors with the destination "
               "page's terms.",
    },
    "tech.redirect.http_left": {
        "title": "%(n)d internal URLs still on http",
        "detail": "Redirected to the https version: %(urls)s. "
                  "Every hop wastes crawl budget and dilutes the "
                  "signals.",
        "fix": "Update sitemap and internal links to the final "
               "https URLs.",
        "example": "<!-- before --> <a href=\"http://esempio.it/"
                   "servizio/\">\n<!-- after  --> "
                   "<a href=\"https://esempio.it/servizio/\">",
    },
    "tech.redirect.www_mixed": {
        "title": "%(n)d URLs with mixed www/non-www host",
        "detail": "Redirected to the canonical host: %(urls)s.",
        "fix": "Use a single host (with or without www) in the "
               "sitemap and internal links.",
    },
    "tech.redirect.moved": {
        "title": "%(n)d internal URLs answer with a redirect",
        "detail": "Moved URLs: %(urls)s.",
        "fix": "Update sitemap and internal links to the final "
               "destination of the redirects.",
        "example": "In the sitemap and internal links use the "
                   "landing URL directly:\n<url><loc>https://"
                   "esempio.it/nuova-pagina/</loc></url>",
    },
    "tech.redirect.chains": {
        "title": "%(n)d URLs with a multi-hop redirect chain",
        "detail": "%(urls)s.",
        "fix": "Point every redirect straight to the final "
               "destination (a single hop).",
        "example": "# one hop, not a chain\n"
                   "Redirect 301 /vecchia/ "
                   "https://esempio.it/nuova/\n"
                   "# NOT: /vecchia/ -> /intermedia/ -> /nuova/",
    },
    "tech.redirect.none": {
        "title": "No internal redirects",
        "detail": "Every analysed URL answers directly.",
    },
    "tech.msft.noarchive": {
        "title": "%(n)d page(s) excluded from Copilot (noarchive)",
        "detail": "The noarchive meta excludes the content from "
                  "Bing Chat/Copilot answers and from Microsoft "
                  "model training (classic search is unaffected): "
                  "on these pages citability on the Microsoft "
                  "channel is zero. %(urls)s",
        "fix": "If the exclusion is unintended remove noarchive; "
               "for a partial presence (title, URL and snippet "
               "only) use nocache.",
    },
    "tech.msft.nocache": {
        "title": "%(n)d page(s) with partial presence in Copilot "
                 "(nocache)",
        "detail": "With nocache, Bing Chat/Copilot shows only the "
                  "page's URL, title and snippet and uses only "
                  "those elements for Microsoft training. "
                  "%(urls)s",
        "fix": "A legitimate partial opt-out: just check it is "
               "intended. For full citability on Copilot remove "
               "the meta.",
    },
    "tech.msft.no_optout": {
        "title": "No Microsoft AI opt-out active",
        "detail": "There is no robots.txt token dedicated to "
                  "Microsoft's AI: control goes through the "
                  "noarchive/nocache metas, absent here. Your "
                  "content can therefore be used in Copilot "
                  "answers and Microsoft training; to opt out use "
                  "noarchive (full) or nocache (partial).",
    },
    "tech.anchors.varied": {
        "title": "Varied internal anchor profile",
        "detail": "%(texts)d unique texts over %(pairs)d "
                  "text-destination pairs (%(pct).0f%%; common "
                  "practice threshold: %(threshold).0f%%).",
    },
    "tech.anchors.repetitive": {
        "title": "Repetitive internal anchor profile",
        "detail": "%(texts)d unique texts over %(pairs)d "
                  "text-destination pairs (%(pct).0f%%, common "
                  "practice threshold %(threshold).0f%%): the "
                  "same text leads to different destinations and "
                  "the reader — human or model — cannot predict "
                  "where the link goes. %(examples)s",
        "fix": "Use descriptive anchors, distinct per "
               "destination: the link text must say what is on "
               "the other side.",
        "example": "Before: \"Read more\" -> /servizi, \"Read "
                   "more\" -> /prezzi\n"
                   "After:  \"All lymphatic drainage services\" "
                   "-> /servizi, \"Session prices\" -> /prezzi",
    },
    "tech.meta.charset": {
        "title": "%(n)d page(s) without a declared charset",
        "detail": "%(urls)s",
        "fix": "Declare the encoding at the top of the <head>.",
    },
    "tech.meta.viewport": {
        "title": "%(n)d page(s) without a viewport meta",
        "detail": "Without a viewport the mobile rendering is "
                  "undeclared: %(urls)s",
        "fix": "Add the responsive viewport.",
    },
    "tech.meta.og_missing": {
        "title": "%(n)d page(s) without Open Graph",
        "detail": "Previews in shared links (and in many "
                  "assistant answers) are built from the og:* "
                  "tags: without them, whoever pastes the link "
                  "decides the title and image. %(urls)s",
        "fix": "Add at least the og:title, og:description, "
               "og:image triad.",
    },
    "tech.meta.og_partial": {
        "title": "Incomplete Open Graph on %(n)d page(s)",
        "detail": "%(urls)s",
        "fix": "Complete the og:title, og:description, og:image "
               "triad.",
    },
    "tech.meta.ok": {
        "title": "Basic metas in order",
        "detail": "charset, viewport and Open Graph complete on "
                  "all %(n)d analysed pages.",
    },
    "tech.https.missing": {
        "title": "Site not on HTTPS",
        "fix": "Enable a TLS certificate and redirect everything "
               "to HTTPS.",
    },
    "tech.https.ok": {
        "title": "HTTPS active",
    },
    "tech.pages.broken": {
        "title": "%(n)d URLs unreachable or failing",
        "detail": "%(urls)s",
        "fix": "Fix the failing URLs or remove them from the "
               "sitemap.",
    },
    "tech.pages.soft404": {
        "title": "%(n)d possible soft-404s (200 with \"not "
                 "found\" content)",
        "detail": "They answer 200 but the content says the page "
                  "does not exist: %(urls)s. They enter the index "
                  "as empty pages and dilute the site's signals.",
        "fix": "Make non-existent URLs answer 404 (or 410) and "
               "remove the empty ones from the sitemap.",
        "example": "The non-existent page must answer with status "
                   "404, not 200:\n# Apache (.htaccess)\n"
                   "ErrorDocument 404 /404.html\n"
                   "# no redirect to the home instead of the 404",
    },
    "tech.pages.none": {
        "title": "No analysable page",
        "detail": "No URL returned valid HTML: the site is "
                  "unreachable, blocks the tool's user-agent or "
                  "only responds to JavaScript. The content audit "
                  "was not performed.",
        "fix": "Check that the site responds and does not filter "
               "crawlers.",
    },
    "tech.pages.single": {
        "title": "Minimal indexable surface (1 page)",
        "detail": "With a single document the RRF sum has no "
                  "addends: there are no distinct passages to "
                  "surface.",
        "fix": "Create standalone pages for every topic/service.",
    },
    "tech.pages.few": {
        "title": "Few indexable pages (%(n)d)",
        "fix": "Widen the surface: one page per intent.",
    },
    "tech.pages.ok": {
        "title": "%(n)d indexable pages analysed",
        "detail": "First pages: %(urls)s.",
    },
    "tech.sitemap.missing": {
        "title": "XML sitemap missing or unreadable",
        "detail": "URLs discovered by crawling internal links.",
        "fix": "Publish an XML sitemap and declare it in "
               "robots.txt.",
    },
    "tech.pages.placeholder": {
        "title": "%(n)d indexable placeholder page(s)",
        "detail": "Detected: %(urls)s. They are default CMS "
                  "content: pure noise in the index and a signal "
                  "of an unfinished site.",
        "fix": "Delete them, or set noindex and remove them from "
               "the sitemap.",
    },
    "tech.pages.noindex": {
        "title": "%(n)d page(s) with a noindex robots meta",
        "detail": "%(urls)s",
        "fix": "Check the exclusion is intended.",
        "example": "If the page must be indexed, remove the meta "
                   "or use:\n<meta name=\"robots\" "
                   "content=\"index, follow\">",
    },
    "tech.canonical.missing": {
        "title": "%(n)d page(s) without a canonical",
        "detail": "%(urls)s",
        "fix": "Declare <link rel=\"canonical\"> on every page.",
    },
    "tech.canonical.ok": {
        "title": "Canonicals present",
        "detail": "Declared on all %(n)d analysed pages.",
    },
    "tech.lang.missing": {
        "title": "%(n)d page(s) without a lang attribute",
        "fix": "Set <html lang=\"it\">: it helps language-model "
               "selection during analysis.",
    },
    "tech.js.heavy": {
        "title": "%(n)d page(s) with little text and heavy "
                 "JavaScript",
        "detail": "The content may be rendered client-side and "
                  "not be seen by crawlers.",
        "fix": "Enable server-side rendering or pre-rendering.",
    },
    "tech.js.rendered": {
        "title": "%(n)d page(s) with little text and heavy "
                 "JavaScript",
        "detail": "The content was analysed with JavaScript "
                  "rendering, but crawlers that do not run "
                  "JavaScript (most AI crawlers) still cannot "
                  "see it.",
        "fix": "Enable server-side rendering or pre-rendering.",
    },
    "tech.js.ok": {
        "title": "Content present in the initial HTML",
    },
    "tech.slow": {
        "title": "%(n)d page(s) answering in more than 2 s",
        "detail": "Slowest: %(worst).2f s.",
        "fix": "Optimise caching and TTFB.",
    },
    "tech.hreflang.missing": {
        "title": "Multilingual site without hreflang",
        "detail": "Detected languages: %(langs)s.",
        "fix": "Declare reciprocal hreflang between the "
               "versions.",
    },
    "tech.hreflang.na": {
        "title": "Single-language site: hreflang not needed",
    },
    "lex.clickbait.found": {
        "title": "%(n)d titles or headings with clickbait "
                 "formulas",
        "detail": "Sensationalist formulas and multiple "
                  "exclamation marks attract the click but answer "
                  "nothing: generative engines select informative "
                  "titles. %(examples)s",
        "fix": "Rewrite in an informative style: the benefit or "
               "the answer in the title, no hyperbole.",
        "example": "Before: \"You won't believe what drainage "
                   "does!!\"\nAfter:  \"Lymphatic drainage: "
                   "benefits, duration and cost of a session\"",
    },
    "lex.clickbait.none": {
        "title": "No clickbait formula in titles and headings",
        "detail": "Informative-style titles on all %(n)d analysed "
                  "pages.",
    },
    "lex.title.missing": {
        "title": "%(n)d page(s) without a <title>",
        "fix": "The title is the highest-weight lexical signal.",
    },
    "lex.title.bad": {
        "title": "%(n)d titles not optimised",
        "detail": "Examples: %(examples)s",
        "fix": "Unique title, %(min)d-%(max)d characters, with the "
               "real search terms; avoid the domain name as a "
               "title.",
        "example": "<title>Drenaggio linfatico manuale a Parma | "
                   "Centro Esempio</title>\n"
                   "(52 characters: service + territory + brand)",
    },
    "lex.title.dup": {
        "title": "%(n)d titles duplicated across pages",
        "detail": "%(examples)s",
        "fix": "Every page must have a distinct title.",
    },
    "lex.title.ok": {
        "title": "Titles well set up",
    },
    "lex.desc.missing": {
        "title": "%(n)d page(s) without a meta description",
        "detail": "%(urls)s",
        "fix": "Write %(min)d-%(max)d characters with service and "
               "territory.",
    },
    "lex.desc.short": {
        "title": "%(n)d meta descriptions too short",
        "detail": "Examples: %(examples)s",
        "fix": "A description that only repeats the company name "
               "carries no signal.",
    },
    "lex.desc.long": {
        "title": "%(n)d meta descriptions above %(max)d "
                 "characters",
    },
    "lex.desc.ok": {
        "title": "Meta descriptions present and of adequate "
                 "length",
    },
    "lex.h1.missing": {
        "title": "%(n)d page(s) without an H1",
        "detail": "%(urls)s",
        "fix": "A single H1 per page, with the main terms.",
    },
    "lex.h1.multi": {
        "title": "%(n)d page(s) with multiple H1s",
    },
    "lex.h1.ok": {
        "title": "Correct H1 structure",
    },
    "lex.words.thin": {
        "title": "%(n)d page(s) below %(min)d words",
        "detail": "Site average: %(avg)d words. With so little "
                  "text the useful terms never reach a frequency "
                  "BM25 can reward.",
        "fix": "Bring the key pages towards %(target)d+ words of "
               "informative, non-promotional content.",
        "example": "Typical structure for a service page:\n"
                   "<h2>What is ...?</h2> <h2>How a session "
                   "works</h2>\n<h2>When it is needed</h2> "
                   "<h2>How much it costs</h2> <h2>FAQ</h2>",
    },
    "lex.words.ok": {
        "title": "Adequate text volume",
        "detail": "Average: %(avg)d words per page.",
    },
    "lex.acronyms.bare": {
        "title": "Acronyms used without their expanded form",
        "detail": "Not spelled out: %(list)s.",
        "fix": "Write 'ACRONYM (expanded form)' at least at the "
               "first occurrence: it covers both search "
               "phrasings.",
    },
    "lex.acronyms.ok": {
        "title": "Acronyms accompanied by their expanded form",
        "detail": "%(list)s",
    },
    "lex.slug.bad": {
        "title": "%(n)d slugs that say little",
        "detail": "%(slugs)s",
        "fix": "Use topical slugs with hyphens.",
    },
    "lex.slug.ok": {
        "title": "Topical, readable slugs",
    },
    "lex.alt.partial": {
        "title": "Incomplete alt attributes (%(with_alt)d/"
                 "%(total)d)",
        "fix": "The alt is indexable text as well as "
               "accessibility.",
    },
    "lex.alt.ok": {
        "title": "Alt attributes present (%(with_alt)d/"
                 "%(total)d)",
    },
    "sem.extract.ok": {
        "title": "Good direct extractability",
        "detail": "%(direct)d paragraphs out of %(total)d open "
                  "with an explicit answer in %(min)d-%(max)d "
                  "words (%(pct).0f%% against a common practice "
                  "threshold of %(threshold).0f%%): these are the "
                  "passages an assistant can quote as they are.",
    },
    "sem.extract.low": {
        "title": "Few direct-answer paragraphs",
        "detail": "%(direct)d paragraphs out of %(total)d open "
                  "with an explicit answer in %(min)d-%(max)d "
                  "words (%(pct).0f%% against a common practice "
                  "threshold of %(threshold).0f%%): these are the "
                  "passages an assistant can quote as they are.",
        "fix": "Rewrite the key paragraphs opening with the "
               "answer (\"X is ...\", \"Yes, ...\", \"In short "
               "...\") and keep them between %(min)d and %(max)d "
               "words.",
        "example": "Before: \"In today's wellness landscape, many "
                   "people wonder which path...\"\n"
                   "After:  \"Lymphatic drainage is a gentle "
                   "massage that eases lymph flow: a session "
                   "lasts 45 minutes and costs 40-80 euros.\"",
    },
    "sem.filler.saturated": {
        "title": "%(n)d page(s) saturated with marketing "
                 "formulas",
        "detail": "Filler takes up space without saying anything "
                  "extractable (common practice threshold: at "
                  "least %(min)d formulas and one every 100 "
                  "words). %(examples)s",
        "fix": "Replace the generic formulas with verifiable "
               "information: numbers, durations, prices, "
               "procedures.",
        "example": "Before: \"We are market leaders, quality and "
                   "professionalism at your service.\"\n"
                   "After:  \"Since 2012 we have followed more "
                   "than 400 post-surgery patients; the first "
                   "evaluation is free and takes 30 minutes.\"",
    },
    "sem.filler.ok": {
        "title": "Marketing filler under control",
        "detail": "%(n)d generic formulas across the whole site: "
                  "useful text dominates.",
    },
    "sem.lifecycle.ok": {
        "title": "Topic life cycle covered (%(n)d of 6)",
        "detail": "Sections found in the headings: %(found)s.",
    },
    "sem.lifecycle.partial": {
        "title": "Topic life cycle incomplete (%(n)d of 6)",
        "detail": "A complete treatment covers definition, "
                  "history, use cases, limits, FAQ and outlook: "
                  "it is the content generative engines can cite "
                  "for every angle of a question. %(found)s "
                  "Missing: %(missing)s.",
        "fix": "Add the missing sections with explicit headings "
               "(they can be spread across several pages).",
    },
    "sem.fresh.ok": {
        "title": "Recently updated content",
        "detail": "Most recent declared update: %(date)s on "
                  "%(url)s (%(days)d days ago).",
    },
    "sem.fresh.stale": {
        "title": "Content untouched for over a year",
        "detail": "The most recent declared update is from "
                  "%(date)s (%(days)d days ago). Generative "
                  "engines prefer maintained sources: a frozen "
                  "date signals possibly outdated content. Oldest "
                  "pages: %(stale)s.",
        "fix": "Review the key content and declare the update "
               "with article:modified_time or dateModified in "
               "the JSON-LD.",
    },
    "sem.fresh.very_stale": {
        "title": "Content untouched for over two years",
        "detail": "The most recent declared update is from "
                  "%(date)s (%(days)d days ago). Generative "
                  "engines prefer maintained sources: a frozen "
                  "date signals possibly outdated content. Oldest "
                  "pages: %(stale)s.",
        "fix": "Review the key content and declare the update "
               "with article:modified_time or dateModified in "
               "the JSON-LD.",
    },
    "sem.refs.ok": {
        "title": "References to sources present",
        "detail": "%(context)s (common practice threshold: a "
                  "sources section or at least %(threshold)d "
                  "citations).",
    },
    "sem.refs.missing": {
        "title": "No reference to external sources",
        "detail": "%(context)s. Citing sources strengthens "
                  "E-E-A-T signals and gives AI assistants "
                  "something to verify: referenced content is "
                  "more citable.",
        "fix": "Add a \"Sources\" section with links to "
               "guidelines, studies or official documentation "
               "(or citations in the text).",
    },
    "sem.chunks.none": {
        "title": "No extractable chunk",
        "detail": "The site offers no indexable text passages.",
        "fix": "Write discursive paragraphs of at least 40-50 "
               "words.",
    },
    "sem.chunks.ok": {
        "title": "%(chunks)d indexable chunks across %(pages)d "
                 "pages",
        "detail": "Every chunk is a chance to appear in the "
                  "lists: in the RRF sum the number of relevant "
                  "passages is the real multiplier.",
    },
    "sem.chunks.few": {
        "title": "%(chunks)d indexable chunks across %(pages)d "
                 "pages",
        "detail": "Every chunk is a chance to appear in the "
                  "lists: in the RRF sum the number of relevant "
                  "passages is the real multiplier.",
        "fix": "Increase the number of self-contained topical "
               "passages.",
    },
    "sem.anaphora.high": {
        "title": "%(pct).0f%% of the chunks are not "
                 "self-contained",
        "detail": "They open with an anaphoric reference (this, "
                  "such, that...): extracted on their own they "
                  "answer nothing. Examples: %(examples)s.",
        "fix": "Rewrite the openings naming the subject "
               "explicitly.",
        "example": "Before: \"This treatment is indicated after "
                   "surgery.\"\nAfter:  \"Manual lymphatic "
                   "drainage is indicated after surgery.\"",
    },
    "sem.anaphora.ok": {
        "title": "Chunks largely self-contained (%(pct).0f%% "
                 "anaphoric)",
    },
    "sem.questions.few": {
        "title": "Almost no question-form heading (%(n)d of "
                 "%(total)d)",
        "detail": "It is the format AI engines cite most often: "
                  "an explicit question followed by a direct "
                  "answer.",
        "fix": "Add headings like \"What is X?\", \"How does X "
               "work?\", \"How much does X cost?\" with a crisp "
               "2-3 line answer.",
    },
    "sem.questions.ok": {
        "title": "%(n)d question-form headings (%(pct).0f%%)",
        "detail": "Examples: %(examples)s.",
    },
    "sem.faq.ok": {
        "title": "FAQ section detected",
        "detail": "Detected on %(url)s.",
    },
    "sem.faq.missing": {
        "title": "No FAQ section",
        "detail": "FAQs align a chunk with a precise intent and "
                  "feed both axes at the same time.",
        "fix": "Add per-page FAQs, marked up with FAQPage "
               "JSON-LD.",
    },
    "sem.defs.low": {
        "title": "Content poor in definitions (%(pct).0f%% of "
                 "chunks)",
        "detail": "Without passages explaining *what* something "
                  "is, the embeddings stay far from "
                  "informational queries.",
        "fix": "For every topic add: what it is / how it works / "
               "when it is needed / an example.",
    },
    "sem.defs.ok": {
        "title": "Defining passages present (%(pct).0f%% of "
                 "chunks)",
    },
    "sem.examples.few": {
        "title": "Almost no concrete example",
        "fix": "Examples and case studies are the content with "
               "the highest semantic density.",
    },
    "sem.examples.ok": {
        "title": "%(n)d chunks with concrete examples",
    },
    "sem.vocab.narrow": {
        "title": "Narrow vocabulary (%(n)d distinct terms)",
        "detail": "Little lexical variety means limited semantic "
                  "coverage: you intercept few rephrasings of "
                  "the same question.",
        "fix": "Broaden the topics covered and the phrasings "
               "used.",
    },
    "sem.vocab.ok": {
        "title": "Broad vocabulary (%(n)d distinct terms)",
    },
    "sem.eeat.author.ok": {
        "title": "E-E-A-T: content author declared",
    },
    "sem.eeat.author.missing": {
        "title": "E-E-A-T: no author declared",
        "fix": "Add the author meta or the author property in "
               "the JSON-LD: AI engines weigh who signs the "
               "content.",
    },
    "sem.eeat.dates.ok": {
        "title": "E-E-A-T: publication/update dates present",
    },
    "sem.eeat.dates.missing": {
        "title": "E-E-A-T: no publication or update date",
        "fix": "Expose article:published_time/modified_time or "
               "datePublished/dateModified in the JSON-LD.",
    },
    "sem.eeat.about.ok": {
        "title": "E-E-A-T: \"about us\" page present",
    },
    "sem.eeat.about.missing": {
        "title": "E-E-A-T: no \"about us\" page detected",
        "fix": "A page introducing people and expertise is the "
               "most direct experience signal.",
        "example": "Create /chi-siamo/ with: who curates the "
                   "content, titles and training,\nsince when, "
                   "real photos. Link it from every page's "
                   "footer.",
    },
    "sem.eeat.contact.ok": {
        "title": "E-E-A-T: verifiable contacts present",
    },
    "sem.eeat.contact.missing": {
        "title": "E-E-A-T: no verifiable contact detected",
        "fix": "Expose phone and email (tel:/mailto: links) or a "
               "contact page.",
    },
    "sd.semantic.poor": {
        "title": "%(n)d page(s) without semantic markup",
        "detail": "Fewer than %(min)d sectioning tag types "
                  "(article, section, main, figure...): the "
                  "chunkers of generative engines have fewer "
                  "hooks to segment the content into coherent "
                  "blocks. %(urls)s",
        "fix": "Wrap the main content in <main> and <article>, "
               "topical sections in <section> with their "
               "heading, images and captions in <figure>.",
    },
    "sd.semantic.divitis": {
        "title": "%(n)d page(s) with an excess of <div> "
                 "(divitis)",
        "detail": "More than half the elements are a generic "
                  "<div>: %(urls)s.",
        "fix": "Replace structural <div>s with the equivalent "
               "semantic tags: the markup becomes "
               "self-describing.",
    },
    "sd.semantic.ok": {
        "title": "Semantic markup in use",
        "detail": "All %(n)d analysable pages use sectioning "
                  "tags and keep <div>s below %(max)d%% of the "
                  "elements.",
    },
    "sd.jsonld.none": {
        "title": "No JSON-LD structured data",
        "detail": "Without markup the entity is not recognised "
                  "and the content is not eligible for rich "
                  "results.",
        "fix": "Add at least Organization (or LocalBusiness), "
               "then Service, FAQPage, BreadcrumbList, Article.",
    },
    "sd.jsonld.ok": {
        "title": "JSON-LD present",
        "detail": "Detected types: %(types)s.",
    },
    "sd.entity.missing": {
        "title": "Main entity not declared",
        "fix": "Add Organization or LocalBusiness with name, "
               "address, contacts and tax identifiers.",
    },
    "sd.entity.ok": {
        "title": "Main entity declared",
    },
    "sd.type.faqpage": {
        "title": "FAQPage markup missing",
        "detail": "Marked-up FAQs are the format AI engines cite "
                  "the most.",
        "fix": "Add the FAQPage type where relevant.",
    },
    "sd.type.breadcrumblist": {
        "title": "BreadcrumbList markup missing",
        "detail": "It clarifies the site hierarchy.",
        "fix": "Add the BreadcrumbList type where relevant.",
    },
    "sd.type.website": {
        "title": "WebSite markup missing",
        "detail": "Useful for the sitelinks searchbox.",
        "fix": "Add the WebSite type where relevant.",
    },
    "sd.jsonld.partial": {
        "title": "JSON-LD on only %(covered)d pages out of "
                 "%(total)d",
        "fix": "Extend the markup to all relevant pages.",
    },
    "sd.check.incomplete": {
        "title": "Incomplete JSON-LD for %(n)d type(s)",
        "fix": "Complete the listed properties: without them the "
               "type is not eligible for rich results.",
    },
    "sd.check.faq": {
        "title": "%(n)d incomplete FAQPage question(s)",
        "detail": "Every mainEntity item requires a Question "
                  "with name and an acceptedAnswer with text.",
        "fix": "Complete the question/answer pairs in the "
               "markup.",
    },
    "sd.check.offers": {
        "title": "%(n)d issue(s) in offer prices",
        "fix": "In price only the number with a decimal point "
               "(no currency symbols); the currency in "
               "priceCurrency (ISO 4217 code, e.g. EUR).",
    },
    "sd.check.product": {
        "title": "%(n)d Product without offers or reviews",
        "detail": "A Product without offers, review and "
                  "aggregateRating is not eligible for product "
                  "rich results.",
        "fix": "Add at least offers (with price and "
               "priceCurrency) or review/aggregateRating.",
    },
    "sd.check.rating": {
        "title": "%(n)d inconsistent rating(s)",
        "fix": "ratingValue inside the declared scale (default "
               "1-5) and the review count in reviewCount or "
               "ratingCount.",
    },
    "sd.check.dates": {
        "title": "%(n)d date(s) not in ISO 8601 format",
        "detail": "%(list)s.",
        "fix": "Use YYYY-MM-DD, with the optional time after the "
               "T (e.g. 2026-08-03T09:30:00+02:00).",
    },
    "sd.check.urls": {
        "title": "%(n)d non-absolute media URLs in the markup",
        "detail": "%(list)s.",
        "fix": "image, logo, thumbnailUrl, contentUrl and "
               "embedUrl require full http(s) URLs.",
    },
    "sd.check.ok": {
        "title": "Consistent Schema.org markup (%(n)d types "
                 "verified)",
        "detail": "Verified: %(types)s.",
    },
    "rrf.not_runnable": {
        "title": "RRF simulation not runnable",
        "detail": "At least one chunk and one query are needed.",
    },
    "rrf.consensus.low": {
        "title": "Average consensus between the lists: "
                 "%(avg).1f/%(top_n)d (%(pct).0f%%)",
        "detail": "The two lists point to different passages: no "
                  "document accumulates score on both axes. In "
                  "the RRF formula a document present in both "
                  "lists sums two 1/(k+rank) addends and beats "
                  "one that dominates a single list. Consensus "
                  "per query: %(per_query)s.",
        "fix": "Optimise the same passages on both axes: "
               "explicit terms (BM25) and a complete explanation "
               "(vector).",
        "example": "Before (lexical only): \"Lymphatic drainage. "
                   "Call for info.\"\nAfter (both axes): \"Manual "
                   "lymphatic drainage is a gentle massage\nthat "
                   "eases lymph flow: a session lasts 45 minutes"
                   "\nand the typical cycle is 5 to 10 visits.\"",
    },
    "rrf.consensus.mid": {
        "title": "Average consensus between the lists: "
                 "%(avg).1f/%(top_n)d (%(pct).0f%%)",
        "detail": "Partial consensus between the two retrievers. "
                  "In the RRF formula a document present in both "
                  "lists sums two 1/(k+rank) addends and beats "
                  "one that dominates a single list. Consensus "
                  "per query: %(per_query)s.",
        "fix": "Optimise the same passages on both axes: "
               "explicit terms (BM25) and a complete explanation "
               "(vector).",
    },
    "rrf.consensus.good": {
        "title": "Average consensus between the lists: "
                 "%(avg).1f/%(top_n)d (%(pct).0f%%)",
        "detail": "Good overlap between lexical and vector "
                  "retrieval. In the RRF formula a document "
                  "present in both lists sums two 1/(k+rank) "
                  "addends and beats one that dominates a single "
                  "list. Consensus per query: %(per_query)s.",
    },
    "rrf.uncovered": {
        "title": "%(n)d queries with no result at all",
        "detail": "No chunk of the site answers: %(queries)s.",
        "fix": "Create content dedicated to these intents.",
        "example": "For every uncovered query, a section with a "
                   "heading equal to the question:\n"
                   "<h2>How much does lymphatic drainage cost?"
                   "</h2>\n<p>A session costs on average 40-80 "
                   "euros, depending on duration and treated "
                   "area.</p>",
    },
    "rrf.covered": {
        "title": "All %(n)d queries find at least one passage",
        "detail": "Verified queries: %(queries)s.",
    },
    "rrf.comp.empty": {
        "title": "Competitor %(host)s with no retrievable "
                 "content",
        "detail": "No analysable page: the comparison includes "
                  "it with 0 passages.",
    },
    "rrf.comp.not_runnable": {
        "title": "Competitive comparison not runnable",
        "detail": "At least one chunk and one query are needed.",
    },
    "rrf.share.low": {
        "title": "Share of voice: %(pct).0f%% of the first "
                 "%(top_n)d fused slots (parity %(parity).0f%%)",
        "detail": "Competitors occupy the slots you would need: "
                  "on your own topics you are rarely retrieved. "
                  "Breakdown: %(breakdown)s.",
        "fix": "Strengthen the passages on the queries where "
               "competitors beat you: same explicit terms, "
               "complete answer.",
    },
    "rrf.share.mid": {
        "title": "Share of voice: %(pct).0f%% of the first "
                 "%(top_n)d fused slots (parity %(parity).0f%%)",
        "detail": "You are below parity: on your topics "
                  "competitors get retrieved more often than "
                  "you. Breakdown: %(breakdown)s.",
        "fix": "Strengthen the passages on the queries where "
               "competitors beat you: same explicit terms, "
               "complete answer.",
    },
    "rrf.share.good": {
        "title": "Share of voice: %(pct).0f%% of the first "
                 "%(top_n)d fused slots (parity %(parity).0f%%)",
        "detail": "You hold your own against competitors on your "
                  "topics. Breakdown: %(breakdown)s.",
    },
    "rrf.comp.lost": {
        "title": "%(n)d queries out of %(total)d won entirely by "
                 "competitors",
        "detail": "None of your passages in the first %(top_n)d "
                  "for: %(queries)s.",
        "fix": "Create or rewrite content dedicated to these "
               "intents.",
    },
    "rrf.comp.present": {
        "title": "Present in the first %(top_n)d for all %(n)d "
                 "queries",
        "detail": "Comparison queries: %(queries)s.",
    },
    "tech.robots.own": {
        "title": "Site declared as your own",
        "detail": "The robots.txt Disallow rules are not applied "
                  "to the audited site (--own-site); they still "
                  "apply to any competitors.",
    },
    "tech.robots.forced": {
        "title": "robots.txt Disallow rules ignored on explicit "
                 "request",
        "detail": "Crawling beyond the Disallow rules was "
                  "enabled with --ignore-robots %(ack)s: "
                  "responsibility for the crawl was explicitly "
                  "assumed by the user.",
    },
    "tech.robots.excluded": {
        "title": "%(n)d URLs excluded out of respect for "
                 "robots.txt",
        "detail": "Disallow rules addressed to the %(agent)s "
                  "agent are respected (default behaviour): "
                  "%(urls)s. Use --own-site if the site is "
                  "yours.",
    },
    "tech.render.done": {
        "title": "%(n)d page(s) analysed with JavaScript "
                 "rendering",
        "detail": "Mode --render %(mode)s: the content comes "
                  "from the DOM rendered in a headless browser; "
                  "HTTP status, redirects and timings remain "
                  "those of the original response.",
    },
    "tech.render.failed": {
        "title": "Rendering failed for %(n)d page(s)",
        "detail": "For these pages the static HTML was "
                  "analysed.",
        "fix": "Retry, or raise the timeout if the site is "
               "slow.",
    },
    "tech.pages.duplicates": {
        "title": "%(n)d URLs serve identical content",
        "detail": "The same text is reachable from several "
                  "addresses: %(urls)s. Duplicates add no "
                  "addends to the RRF sum, dilute the signals "
                  "and waste crawl budget.",
        "fix": "Pick one canonical URL and redirect the others "
               "with a 301.",
    },
}


# Cataloghi dei rilievi nelle altre lingue: stesse chiavi e stessi
# campi di _FINDINGS_EN, una tabella per lingua (il TO-DO storico
# "altre lingue del referto"). Popolati piu' sotto.
_FINDINGS_FR: Dict[str, Dict[str, str]] = {
    "tech.robots.missing": {
        "title": "robots.txt inaccessible",
        "detail": "La requête vers %(url)s a échoué ou n'a pas "
                  "renvoyé 200.",
        "fix": "Publiez un robots.txt qui déclare le sitemap.",
    },
    "tech.robots.present": {
        "title": "robots.txt présent",
        "detail": "%(n)d lignes.",
    },
    "tech.robots.ai_blocked": {
        "title": "Robots IA bloqués : %(agents)s",
        "detail": "Ces agents ne peuvent pas accéder à la page "
                  "d'accueil. S'ils sont bloqués, vous n'entrez "
                  "dans aucune liste de récupération et le RRF "
                  "n'a rien à fusionner.",
        "fix": "Supprimez les règles Disallow pour les agents "
               "par lesquels vous voulez être cité.",
        "example": "# robots.txt - débloquer les agents IA\n"
                   "User-agent: GPTBot\nDisallow:\n\n"
                   "User-agent: ClaudeBot\nDisallow:\n\n"
                   "User-agent: PerplexityBot\nDisallow:",
    },
    "tech.robots.ai_allowed": {
        "title": "Robots IA autorisés",
        "detail": "Vérifiés : %(agents)s.",
    },
    "tech.robots.sitemap_ok": {
        "title": "Sitemap déclaré dans le robots.txt",
        "detail": "%(urls)s",
    },
    "tech.robots.sitemap_missing": {
        "title": "Aucun sitemap déclaré dans le robots.txt",
        "fix": "Ajoutez la ligne "
               "'Sitemap: https://.../sitemap.xml'.",
        "example": "# à la fin du robots.txt\n"
                   "Sitemap: https://esempio.it/sitemap.xml",
    },
    "tech.llms.present": {
        "title": "llms.txt présent",
        "detail": "%(n)d lignes.",
    },
    "tech.llms.missing": {
        "title": "llms.txt absent",
        "detail": "Standard émergent (llmstxt.org) : un index "
                  "Markdown des contenus clés destiné aux "
                  "agents IA.",
        "fix": "Envisagez de publier /llms.txt avec vos "
               "contenus clés.",
    },
    "tech.links.orphans": {
        "title": "%(n)d page(s) sans lien interne entrant "
                 "(orphelines)",
        "detail": "Accessibles uniquement depuis le sitemap : "
                  "%(urls)s. Une page vers laquelle personne ne "
                  "pointe est moins explorée et pèse moins.",
        "fix": "Ajoutez des liens depuis les pages liées (corps "
               "du texte, menu ou pied de page).",
        "example": "Depuis la page liée :\n"
                   "<a href=\"/servizio-collegato/\">nom "
                   "descriptif du service</a>",
    },
    "tech.links.no_orphans": {
        "title": "Chaque page a des liens internes entrants",
    },
    "tech.links.deep": {
        "title": "%(n)d page(s) à plus de 3 clics de la page "
                 "d'accueil",
        "detail": "%(urls)s.",
        "fix": "Raccourcissez les parcours : les pages profondes "
               "sont moins explorées et moins pondérées.",
    },
    "tech.links.generic_anchors": {
        "title": "%(n)d ancres génériques dans les liens "
                 "internes",
        "detail": "Des textes comme « cliquez ici » ou « en "
                  "savoir plus » ne disent rien du contenu de "
                  "destination.",
        "fix": "Utilisez des ancres descriptives avec les termes "
               "de la page de destination.",
    },
    "tech.redirect.http_left": {
        "title": "%(n)d URL internes encore en http",
        "detail": "Redirigées vers la version https : %(urls)s. "
                  "Chaque saut gaspille le budget de crawl et "
                  "dilue les signaux.",
        "fix": "Mettez à jour le sitemap et les liens internes "
               "vers les URL https finales.",
        "example": "<!-- avant --> <a href=\"http://esempio.it/"
                   "servizio/\">\n<!-- après  --> "
                   "<a href=\"https://esempio.it/servizio/\">",
    },
    "tech.redirect.www_mixed": {
        "title": "%(n)d URL avec hôte www/non-www mélangé",
        "detail": "Redirigées vers l'hôte canonique : %(urls)s.",
        "fix": "Utilisez un seul hôte (avec ou sans www) dans le "
               "sitemap et les liens internes.",
    },
    "tech.redirect.moved": {
        "title": "%(n)d URL internes répondent par une "
                 "redirection",
        "detail": "URL déplacées : %(urls)s.",
        "fix": "Mettez à jour le sitemap et les liens internes "
               "vers la destination finale des redirections.",
        "example": "Dans le sitemap et les liens internes, "
                   "utilisez directement l'URL d'arrivée :\n"
                   "<url><loc>https://"
                   "esempio.it/nuova-pagina/</loc></url>",
    },
    "tech.redirect.chains": {
        "title": "%(n)d URL avec une chaîne de redirections à "
                 "plusieurs sauts",
        "detail": "%(urls)s.",
        "fix": "Faites pointer chaque redirection directement "
               "vers la destination finale (un seul saut).",
        "example": "# un seul saut, pas une chaîne\n"
                   "Redirect 301 /vecchia/ "
                   "https://esempio.it/nuova/\n"
                   "# PAS : /vecchia/ -> /intermedia/ -> /nuova/",
    },
    "tech.redirect.none": {
        "title": "Aucune redirection interne",
        "detail": "Chaque URL analysée répond directement.",
    },
    "tech.msft.noarchive": {
        "title": "%(n)d page(s) exclue(s) de Copilot "
                 "(noarchive)",
        "detail": "La meta noarchive exclut le contenu des "
                  "réponses de Bing Chat/Copilot et de "
                  "l'entraînement des modèles Microsoft (la "
                  "recherche classique n'est pas concernée) : "
                  "sur ces pages, la citabilité sur le canal "
                  "Microsoft est nulle. %(urls)s",
        "fix": "Si l'exclusion n'est pas voulue, supprimez "
               "noarchive ; pour une présence partielle (titre, "
               "URL et extrait seulement), utilisez nocache.",
    },
    "tech.msft.nocache": {
        "title": "%(n)d page(s) à présence partielle dans "
                 "Copilot (nocache)",
        "detail": "Avec nocache, Bing Chat/Copilot n'affiche que "
                  "l'URL, le titre et l'extrait de la page et "
                  "n'utilise que ces éléments pour "
                  "l'entraînement Microsoft. %(urls)s",
        "fix": "Un opt-out partiel légitime : vérifiez "
               "simplement qu'il est voulu. Pour une citabilité "
               "complète sur Copilot, supprimez la meta.",
    },
    "tech.msft.no_optout": {
        "title": "Aucun opt-out IA Microsoft actif",
        "detail": "Il n'existe pas de jeton robots.txt dédié à "
                  "l'IA de Microsoft : le contrôle passe par les "
                  "meta noarchive/nocache, absentes ici. Vos "
                  "contenus peuvent donc être utilisés dans les "
                  "réponses de Copilot et l'entraînement "
                  "Microsoft ; pour l'opt-out, utilisez "
                  "noarchive (total) ou nocache (partiel).",
    },
    "tech.anchors.varied": {
        "title": "Profil d'ancres internes varié",
        "detail": "%(texts)d textes uniques sur %(pairs)d paires "
                  "texte-destination (%(pct).0f %% ; seuil de "
                  "pratique courante : %(threshold).0f %%).",
    },
    "tech.anchors.repetitive": {
        "title": "Profil d'ancres internes répétitif",
        "detail": "%(texts)d textes uniques sur %(pairs)d paires "
                  "texte-destination (%(pct).0f %%, seuil de "
                  "pratique courante %(threshold).0f %%) : le "
                  "même texte mène à des destinations "
                  "différentes et le lecteur — humain ou modèle "
                  "— ne peut pas prévoir où mène le lien. "
                  "%(examples)s",
        "fix": "Utilisez des ancres descriptives, distinctes par "
               "destination : le texte du lien doit dire ce qui "
               "se trouve de l'autre côté.",
        "example": "Avant : « En savoir plus » -> /servizi, "
                   "« En savoir plus » -> /prezzi\n"
                   "Après : « Tous les services de drainage "
                   "lymphatique » -> /servizi, « Prix des "
                   "séances » -> /prezzi",
    },
    "tech.meta.charset": {
        "title": "%(n)d page(s) sans charset déclaré",
        "detail": "%(urls)s",
        "fix": "Déclarez l'encodage en tête du <head>.",
    },
    "tech.meta.viewport": {
        "title": "%(n)d page(s) sans meta viewport",
        "detail": "Sans viewport, le rendu mobile n'est pas "
                  "déclaré : %(urls)s",
        "fix": "Ajoutez le viewport responsive.",
    },
    "tech.meta.og_missing": {
        "title": "%(n)d page(s) sans Open Graph",
        "detail": "Les aperçus des liens partagés (et de "
                  "nombreuses réponses d'assistants) se "
                  "construisent à partir des balises og:* : sans "
                  "elles, c'est celui qui colle le lien qui "
                  "décide du titre et de l'image. %(urls)s",
        "fix": "Ajoutez au moins la triade og:title, "
               "og:description, og:image.",
    },
    "tech.meta.og_partial": {
        "title": "Open Graph incomplet sur %(n)d page(s)",
        "detail": "%(urls)s",
        "fix": "Complétez la triade og:title, og:description, "
               "og:image.",
    },
    "tech.meta.ok": {
        "title": "Meta de base en ordre",
        "detail": "charset, viewport et Open Graph complets sur "
                  "les %(n)d pages analysées.",
    },
    "tech.https.missing": {
        "title": "Site sans HTTPS",
        "fix": "Activez un certificat TLS et redirigez tout vers "
               "HTTPS.",
    },
    "tech.https.ok": {
        "title": "HTTPS actif",
    },
    "tech.pages.broken": {
        "title": "%(n)d URL inaccessibles ou en erreur",
        "detail": "%(urls)s",
        "fix": "Corrigez les URL en erreur ou retirez-les du "
               "sitemap.",
    },
    "tech.pages.soft404": {
        "title": "%(n)d soft-404 possibles (200 avec contenu "
                 "« page introuvable »)",
        "detail": "Elles répondent 200 mais le contenu dit que "
                  "la page n'existe pas : %(urls)s. Elles "
                  "entrent dans l'index comme pages vides et "
                  "diluent les signaux du site.",
        "fix": "Faites répondre 404 (ou 410) aux URL "
               "inexistantes et retirez les pages vides du "
               "sitemap.",
        "example": "La page inexistante doit répondre avec le "
                   "statut 404, pas 200 :\n# Apache (.htaccess)\n"
                   "ErrorDocument 404 /404.html\n"
                   "# pas de redirection vers l'accueil à la "
                   "place du 404",
    },
    "tech.pages.none": {
        "title": "Aucune page analysable",
        "detail": "Aucune URL n'a renvoyé de HTML valide : le "
                  "site est inaccessible, bloque le user-agent "
                  "de l'outil ou ne répond qu'en JavaScript. "
                  "L'audit de contenu n'a pas été effectué.",
        "fix": "Vérifiez que le site répond et ne filtre pas "
               "les robots.",
    },
    "tech.pages.single": {
        "title": "Surface indexable minimale (1 page)",
        "detail": "Avec un seul document, la somme RRF n'a pas "
                  "d'addendes : il n'y a pas de passages "
                  "distincts à faire émerger.",
        "fix": "Créez des pages autonomes pour chaque "
               "sujet/service.",
    },
    "tech.pages.few": {
        "title": "Peu de pages indexables (%(n)d)",
        "fix": "Élargissez la surface : une page par intention.",
    },
    "tech.pages.ok": {
        "title": "%(n)d pages indexables analysées",
        "detail": "Premières pages : %(urls)s.",
    },
    "tech.sitemap.missing": {
        "title": "Sitemap XML absent ou illisible",
        "detail": "URL découvertes en explorant les liens "
                  "internes.",
        "fix": "Publiez un sitemap XML et déclarez-le dans le "
               "robots.txt.",
    },
    "tech.pages.placeholder": {
        "title": "%(n)d page(s) par défaut indexable(s)",
        "detail": "Détectées : %(urls)s. Ce sont des contenus "
                  "par défaut du CMS : du bruit pur dans l'index "
                  "et le signal d'un site inachevé.",
        "fix": "Supprimez-les, ou mettez noindex et retirez-les "
               "du sitemap.",
    },
    "tech.pages.noindex": {
        "title": "%(n)d page(s) avec meta robots noindex",
        "detail": "%(urls)s",
        "fix": "Vérifiez que l'exclusion est voulue.",
        "example": "Si la page doit être indexée, retirez la "
                   "meta ou utilisez :\n<meta name=\"robots\" "
                   "content=\"index, follow\">",
    },
    "tech.canonical.missing": {
        "title": "%(n)d page(s) sans canonical",
        "detail": "%(urls)s",
        "fix": "Déclarez <link rel=\"canonical\"> sur chaque "
               "page.",
    },
    "tech.canonical.ok": {
        "title": "Canonical présents",
        "detail": "Déclarés sur les %(n)d pages analysées.",
    },
    "tech.lang.missing": {
        "title": "%(n)d page(s) sans attribut lang",
        "fix": "Définissez <html lang=\"it\"> : cela aide le "
               "choix du modèle de langue pendant l'analyse.",
    },
    "tech.js.heavy": {
        "title": "%(n)d page(s) avec peu de texte et beaucoup "
                 "de JavaScript",
        "detail": "Le contenu peut être rendu côté client et "
                  "rester invisible aux robots.",
        "fix": "Activez le rendu côté serveur ou le pré-rendu.",
    },
    "tech.js.rendered": {
        "title": "%(n)d page(s) avec peu de texte et beaucoup "
                 "de JavaScript",
        "detail": "Le contenu a été analysé avec le rendu "
                  "JavaScript, mais les robots qui n'exécutent "
                  "pas JavaScript (la plupart des robots IA) ne "
                  "le voient toujours pas.",
        "fix": "Activez le rendu côté serveur ou le pré-rendu.",
    },
    "tech.js.ok": {
        "title": "Contenu présent dans le HTML initial",
    },
    "tech.slow": {
        "title": "%(n)d page(s) répondant en plus de 2 s",
        "detail": "La plus lente : %(worst).2f s.",
        "fix": "Optimisez le cache et le TTFB.",
    },
    "tech.hreflang.missing": {
        "title": "Site multilingue sans hreflang",
        "detail": "Langues détectées : %(langs)s.",
        "fix": "Déclarez des hreflang réciproques entre les "
               "versions.",
    },
    "tech.hreflang.na": {
        "title": "Site monolingue : hreflang non nécessaire",
    },
    "lex.clickbait.found": {
        "title": "%(n)d titres ou intertitres avec des formules "
                 "racoleuses",
        "detail": "Les formules sensationnalistes et les points "
                  "d'exclamation multiples attirent le clic mais "
                  "ne répondent à rien : les moteurs génératifs "
                  "sélectionnent des titres informatifs. "
                  "%(examples)s",
        "fix": "Réécrivez dans un style informatif : le bénéfice "
               "ou la réponse dans le titre, sans hyperbole.",
        "example": "Avant : « Vous ne croirez pas ce que fait le "
                   "drainage!! »\nAprès : « Drainage "
                   "lymphatique : bénéfices, durée et coût "
                   "d'une séance »",
    },
    "lex.clickbait.none": {
        "title": "Aucune formule racoleuse dans les titres et "
                 "intertitres",
        "detail": "Titres de style informatif sur les %(n)d "
                  "pages analysées.",
    },
    "lex.title.missing": {
        "title": "%(n)d page(s) sans <title>",
        "fix": "Le title est le signal lexical au poids le plus "
               "élevé.",
    },
    "lex.title.bad": {
        "title": "%(n)d title non optimisés",
        "detail": "Exemples : %(examples)s",
        "fix": "Un title unique, de %(min)d à %(max)d caractères, "
               "avec les vrais termes de recherche ; évitez le nom "
               "de domaine comme titre.",
        "example": "<title>Drenaggio linfatico manuale a Parma | "
                   "Centro Esempio</title>\n"
                   "(52 caractères : service + territoire + "
                   "marque)",
    },
    "lex.title.dup": {
        "title": "%(n)d title dupliqués entre pages",
        "detail": "%(examples)s",
        "fix": "Chaque page doit avoir un title distinct.",
    },
    "lex.title.ok": {
        "title": "Title bien construits",
    },
    "lex.desc.missing": {
        "title": "%(n)d page(s) sans meta description",
        "detail": "%(urls)s",
        "fix": "Rédigez %(min)d-%(max)d caractères avec le service "
               "et le territoire.",
    },
    "lex.desc.short": {
        "title": "%(n)d meta descriptions trop courtes",
        "detail": "Exemples : %(examples)s",
        "fix": "Une description qui ne fait que répéter le nom "
               "de l'entreprise ne porte aucun signal.",
    },
    "lex.desc.long": {
        "title": "%(n)d meta descriptions au-delà de %(max)d "
                 "caractères",
    },
    "lex.desc.ok": {
        "title": "Meta descriptions présentes et de longueur "
                 "adéquate",
    },
    "lex.h1.missing": {
        "title": "%(n)d page(s) sans H1",
        "detail": "%(urls)s",
        "fix": "Un seul H1 par page, avec les termes principaux.",
    },
    "lex.h1.multi": {
        "title": "%(n)d page(s) avec plusieurs H1",
    },
    "lex.h1.ok": {
        "title": "Structure H1 correcte",
    },
    "lex.words.thin": {
        "title": "%(n)d page(s) sous %(min)d mots",
        "detail": "Moyenne du site : %(avg)d mots. Avec si peu "
                  "de texte, les termes utiles n'atteignent "
                  "jamais une fréquence que BM25 puisse "
                  "récompenser.",
        "fix": "Portez les pages clés vers %(target)d mots et "
               "plus de contenu informatif, non promotionnel.",
        "example": "Structure type d'une page de service :\n"
                   "<h2>Qu'est-ce que ... ?</h2> <h2>Comment se "
                   "déroule une séance</h2>\n<h2>Quand est-ce "
                   "nécessaire</h2> <h2>Combien ça coûte</h2> "
                   "<h2>FAQ</h2>",
    },
    "lex.words.ok": {
        "title": "Volume de texte adéquat",
        "detail": "Moyenne : %(avg)d mots par page.",
    },
    "lex.acronyms.bare": {
        "title": "Sigles utilisés sans leur forme développée",
        "detail": "Non développés : %(list)s.",
        "fix": "Écrivez « SIGLE (forme développée) » au moins à "
               "la première occurrence : cela couvre les deux "
               "formulations de recherche.",
    },
    "lex.acronyms.ok": {
        "title": "Sigles accompagnés de leur forme développée",
        "detail": "%(list)s",
    },
    "lex.slug.bad": {
        "title": "%(n)d slugs peu parlants",
        "detail": "%(slugs)s",
        "fix": "Utilisez des slugs thématiques avec des tirets.",
    },
    "lex.slug.ok": {
        "title": "Slugs thématiques et lisibles",
    },
    "lex.alt.partial": {
        "title": "Attributs alt incomplets (%(with_alt)d/"
                 "%(total)d)",
        "fix": "L'alt est du texte indexable autant que de "
               "l'accessibilité.",
    },
    "lex.alt.ok": {
        "title": "Attributs alt présents (%(with_alt)d/"
                 "%(total)d)",
    },
    "sem.extract.ok": {
        "title": "Bonne extractibilité directe",
        "detail": "%(direct)d paragraphes sur %(total)d "
                  "s'ouvrent par une réponse explicite en "
                  "%(min)d-%(max)d mots (%(pct).0f %% contre un "
                  "seuil de pratique courante de "
                  "%(threshold).0f %%) : ce sont les passages "
                  "qu'un assistant peut citer tels quels.",
    },
    "sem.extract.low": {
        "title": "Peu de paragraphes à réponse directe",
        "detail": "%(direct)d paragraphes sur %(total)d "
                  "s'ouvrent par une réponse explicite en "
                  "%(min)d-%(max)d mots (%(pct).0f %% contre un "
                  "seuil de pratique courante de "
                  "%(threshold).0f %%) : ce sont les passages "
                  "qu'un assistant peut citer tels quels.",
        "fix": "Réécrivez les paragraphes clés en ouvrant par la "
               "réponse (« X est ... », « Oui, ... », « En "
               "résumé ... ») et gardez-les entre %(min)d et "
               "%(max)d mots.",
        "example": "Avant : « Dans le paysage actuel du "
                   "bien-être, beaucoup se demandent quel "
                   "chemin... »\nAprès : « Le drainage "
                   "lymphatique est un massage doux qui facilite "
                   "l'écoulement de la lymphe : une séance dure "
                   "45 minutes et coûte 40 à 80 euros. »",
    },
    "sem.filler.saturated": {
        "title": "%(n)d page(s) saturée(s) de formules "
                 "marketing",
        "detail": "Le remplissage occupe l'espace sans rien dire "
                  "d'extractible (seuil de pratique courante : "
                  "au moins %(min)d formules et une tous les 100 "
                  "mots). %(examples)s",
        "fix": "Remplacez les formules génériques par des "
               "informations vérifiables : chiffres, durées, "
               "prix, procédures.",
        "example": "Avant : « Leaders du marché, qualité et "
                   "professionnalisme à votre service. »\n"
                   "Après : « Depuis 2012, nous avons suivi plus "
                   "de 400 patients post-opératoires ; la "
                   "première évaluation est gratuite et dure 30 "
                   "minutes. »",
    },
    "sem.filler.ok": {
        "title": "Remplissage marketing sous contrôle",
        "detail": "%(n)d formules génériques sur tout le site : "
                  "le texte utile domine.",
    },
    "sem.lifecycle.ok": {
        "title": "Cycle de vie du sujet couvert (%(n)d sur 6)",
        "detail": "Sections trouvées dans les intertitres : "
                  "%(found)s.",
    },
    "sem.lifecycle.partial": {
        "title": "Cycle de vie du sujet incomplet (%(n)d sur 6)",
        "detail": "Un traitement complet couvre définition, "
                  "histoire, cas d'usage, limites, FAQ et "
                  "perspectives : c'est le contenu que les "
                  "moteurs génératifs peuvent citer pour chaque "
                  "angle d'une question. %(found)s Manquent : "
                  "%(missing)s.",
        "fix": "Ajoutez les sections manquantes avec des "
               "intertitres explicites (elles peuvent être "
               "réparties sur plusieurs pages).",
    },
    "sem.fresh.ok": {
        "title": "Contenus mis à jour récemment",
        "detail": "Mise à jour déclarée la plus récente : "
                  "%(date)s sur %(url)s (il y a %(days)d "
                  "jours).",
    },
    "sem.fresh.stale": {
        "title": "Contenus intouchés depuis plus d'un an",
        "detail": "La mise à jour déclarée la plus récente date "
                  "du %(date)s (il y a %(days)d jours). Les "
                  "moteurs génératifs préfèrent les sources "
                  "entretenues : une date figée signale un "
                  "contenu peut-être obsolète. Pages les plus "
                  "anciennes : %(stale)s.",
        "fix": "Révisez les contenus clés et déclarez la mise à "
               "jour avec article:modified_time ou dateModified "
               "dans le JSON-LD.",
    },
    "sem.fresh.very_stale": {
        "title": "Contenus intouchés depuis plus de deux ans",
        "detail": "La mise à jour déclarée la plus récente date "
                  "du %(date)s (il y a %(days)d jours). Les "
                  "moteurs génératifs préfèrent les sources "
                  "entretenues : une date figée signale un "
                  "contenu peut-être obsolète. Pages les plus "
                  "anciennes : %(stale)s.",
        "fix": "Révisez les contenus clés et déclarez la mise à "
               "jour avec article:modified_time ou dateModified "
               "dans le JSON-LD.",
    },
    "sem.refs.ok": {
        "title": "Références aux sources présentes",
        "detail": "%(context)s (seuil de pratique courante : une "
                  "section sources ou au moins %(threshold)d "
                  "citations).",
    },
    "sem.refs.missing": {
        "title": "Aucune référence à des sources externes",
        "detail": "%(context)s. Citer ses sources renforce les "
                  "signaux E-E-A-T et donne aux assistants IA "
                  "quelque chose à vérifier : un contenu "
                  "référencé est plus citable.",
        "fix": "Ajoutez une section « Sources » avec des liens "
               "vers lignes directrices, études ou "
               "documentation officielle (ou des citations dans "
               "le texte).",
    },
    "sem.chunks.none": {
        "title": "Aucun chunk extractible",
        "detail": "Le site n'offre aucun passage de texte "
                  "indexable.",
        "fix": "Rédigez des paragraphes discursifs d'au moins "
               "40-50 mots.",
    },
    "sem.chunks.ok": {
        "title": "%(chunks)d chunks indexables sur %(pages)d "
                 "pages",
        "detail": "Chaque chunk est une occasion d'apparaître "
                  "dans les listes : dans la somme RRF, le "
                  "nombre de passages pertinents est le vrai "
                  "multiplicateur.",
    },
    "sem.chunks.few": {
        "title": "%(chunks)d chunks indexables sur %(pages)d "
                 "pages",
        "detail": "Chaque chunk est une occasion d'apparaître "
                  "dans les listes : dans la somme RRF, le "
                  "nombre de passages pertinents est le vrai "
                  "multiplicateur.",
        "fix": "Augmentez le nombre de passages thématiques "
               "autonomes.",
    },
    "sem.anaphora.high": {
        "title": "%(pct).0f %% des chunks ne sont pas autonomes",
        "detail": "Ils s'ouvrent par un renvoi anaphorique "
                  "(ceci, tel, cela...) : extraits isolément, "
                  "ils ne répondent à rien. Exemples : "
                  "%(examples)s.",
        "fix": "Réécrivez les ouvertures en nommant "
               "explicitement le sujet.",
        "example": "Avant : « Ce traitement est indiqué après "
                   "une opération. »\nAprès : « Le drainage "
                   "lymphatique manuel est indiqué après une "
                   "opération. »",
    },
    "sem.anaphora.ok": {
        "title": "Chunks largement autonomes (%(pct).0f %% "
                 "anaphoriques)",
    },
    "sem.questions.few": {
        "title": "Presque aucun intertitre sous forme de "
                 "question (%(n)d sur %(total)d)",
        "detail": "C'est le format que les moteurs IA citent le "
                  "plus souvent : une question explicite suivie "
                  "d'une réponse directe.",
        "fix": "Ajoutez des intertitres comme « Qu'est-ce que "
               "X ? », « Comment fonctionne X ? », « Combien "
               "coûte X ? » avec une réponse nette de 2-3 "
               "lignes.",
    },
    "sem.questions.ok": {
        "title": "%(n)d intertitres sous forme de question "
                 "(%(pct).0f %%)",
        "detail": "Exemples : %(examples)s.",
    },
    "sem.faq.ok": {
        "title": "Section FAQ détectée",
        "detail": "Détectée sur %(url)s.",
    },
    "sem.faq.missing": {
        "title": "Aucune section FAQ",
        "detail": "Les FAQ alignent un chunk sur une intention "
                  "précise et nourrissent les deux axes à la "
                  "fois.",
        "fix": "Ajoutez des FAQ par page, balisées avec le "
               "JSON-LD FAQPage.",
    },
    "sem.defs.low": {
        "title": "Contenu pauvre en définitions (%(pct).0f %% "
                 "des chunks)",
        "detail": "Sans passages expliquant *ce qu'est* une "
                  "chose, les embeddings restent loin des "
                  "requêtes informationnelles.",
        "fix": "Pour chaque sujet, ajoutez : ce que c'est / "
               "comment ça marche / quand c'est nécessaire / un "
               "exemple.",
    },
    "sem.defs.ok": {
        "title": "Passages définitoires présents (%(pct).0f %% "
                 "des chunks)",
    },
    "sem.examples.few": {
        "title": "Presque aucun exemple concret",
        "fix": "Exemples et études de cas sont les contenus à "
               "la plus forte densité sémantique.",
    },
    "sem.examples.ok": {
        "title": "%(n)d chunks avec des exemples concrets",
    },
    "sem.vocab.narrow": {
        "title": "Vocabulaire étroit (%(n)d termes distincts)",
        "detail": "Peu de variété lexicale signifie une "
                  "couverture sémantique limitée : vous "
                  "interceptez peu de reformulations de la même "
                  "question.",
        "fix": "Élargissez les sujets couverts et les "
               "formulations employées.",
    },
    "sem.vocab.ok": {
        "title": "Vocabulaire large (%(n)d termes distincts)",
    },
    "sem.eeat.author.ok": {
        "title": "E-E-A-T : auteur des contenus déclaré",
    },
    "sem.eeat.author.missing": {
        "title": "E-E-A-T : aucun auteur déclaré",
        "fix": "Ajoutez la meta author ou la propriété author "
               "dans le JSON-LD : les moteurs IA pèsent qui "
               "signe le contenu.",
    },
    "sem.eeat.dates.ok": {
        "title": "E-E-A-T : dates de publication/mise à jour "
                 "présentes",
    },
    "sem.eeat.dates.missing": {
        "title": "E-E-A-T : aucune date de publication ou de "
                 "mise à jour",
        "fix": "Exposez article:published_time/modified_time ou "
               "datePublished/dateModified dans le JSON-LD.",
    },
    "sem.eeat.about.ok": {
        "title": "E-E-A-T : page « qui sommes-nous » présente",
    },
    "sem.eeat.about.missing": {
        "title": "E-E-A-T : aucune page « qui sommes-nous » "
                 "détectée",
        "fix": "Une page présentant les personnes et les "
               "compétences est le signal d'expérience le plus "
               "direct.",
        "example": "Créez /chi-siamo/ avec : qui édite les "
                   "contenus, titres et formation,\ndepuis "
                   "quand, photos réelles. Liez-la depuis le "
                   "pied de chaque page.",
    },
    "sem.eeat.contact.ok": {
        "title": "E-E-A-T : contacts vérifiables présents",
    },
    "sem.eeat.contact.missing": {
        "title": "E-E-A-T : aucun contact vérifiable détecté",
        "fix": "Exposez téléphone et e-mail (liens "
               "tel:/mailto:) ou une page de contact.",
    },
    "sd.semantic.poor": {
        "title": "%(n)d page(s) sans balisage sémantique",
        "detail": "Moins de %(min)d types de balises de "
                  "sectionnement (article, section, main, "
                  "figure...) : les chunkers des moteurs "
                  "génératifs ont moins de prises pour segmenter "
                  "le contenu en blocs cohérents. %(urls)s",
        "fix": "Enveloppez le contenu principal dans <main> et "
               "<article>, les sections thématiques dans "
               "<section> avec leur intertitre, images et "
               "légendes dans <figure>.",
    },
    "sd.semantic.divitis": {
        "title": "%(n)d page(s) avec un excès de <div> "
                 "(divitis)",
        "detail": "Plus de la moitié des éléments sont des <div> "
                  "génériques : %(urls)s.",
        "fix": "Remplacez les <div> structurels par les balises "
               "sémantiques équivalentes : le balisage devient "
               "auto-descriptif.",
    },
    "sd.semantic.ok": {
        "title": "Balisage sémantique utilisé",
        "detail": "Les %(n)d pages analysables utilisent des "
                  "balises de sectionnement et gardent les <div> "
                  "sous %(max)d %% des éléments.",
    },
    "sd.jsonld.none": {
        "title": "Aucune donnée structurée JSON-LD",
        "detail": "Sans balisage, l'entité n'est pas reconnue et "
                  "le contenu n'est pas éligible aux résultats "
                  "enrichis.",
        "fix": "Ajoutez au moins Organization (ou "
               "LocalBusiness), puis Service, FAQPage, "
               "BreadcrumbList, Article.",
    },
    "sd.jsonld.ok": {
        "title": "JSON-LD présent",
        "detail": "Types détectés : %(types)s.",
    },
    "sd.entity.missing": {
        "title": "Entité principale non déclarée",
        "fix": "Ajoutez Organization ou LocalBusiness avec nom, "
               "adresse, contacts et identifiants fiscaux.",
    },
    "sd.entity.ok": {
        "title": "Entité principale déclarée",
    },
    "sd.type.faqpage": {
        "title": "Balisage FAQPage absent",
        "detail": "Les FAQ balisées sont le format que les "
                  "moteurs IA citent le plus.",
        "fix": "Ajoutez le type FAQPage là où c'est pertinent.",
    },
    "sd.type.breadcrumblist": {
        "title": "Balisage BreadcrumbList absent",
        "detail": "Il clarifie la hiérarchie du site.",
        "fix": "Ajoutez le type BreadcrumbList là où c'est "
               "pertinent.",
    },
    "sd.type.website": {
        "title": "Balisage WebSite absent",
        "detail": "Utile pour la searchbox des sitelinks.",
        "fix": "Ajoutez le type WebSite là où c'est pertinent.",
    },
    "sd.jsonld.partial": {
        "title": "JSON-LD sur seulement %(covered)d pages sur "
                 "%(total)d",
        "fix": "Étendez le balisage à toutes les pages "
               "pertinentes.",
    },
    "sd.check.incomplete": {
        "title": "JSON-LD incomplet pour %(n)d type(s)",
        "fix": "Complétez les propriétés listées : sans elles, "
               "le type n'est pas éligible aux résultats "
               "enrichis.",
    },
    "sd.check.faq": {
        "title": "%(n)d question(s) FAQPage incomplète(s)",
        "detail": "Chaque élément de mainEntity requiert une "
                  "Question avec name et une acceptedAnswer "
                  "avec text.",
        "fix": "Complétez les paires question/réponse dans le "
               "balisage.",
    },
    "sd.check.offers": {
        "title": "%(n)d problème(s) dans les prix des offres",
        "fix": "Dans price, seulement le nombre avec un point "
               "décimal (pas de symbole monétaire) ; la devise "
               "dans priceCurrency (code ISO 4217, p. ex. EUR).",
    },
    "sd.check.product": {
        "title": "%(n)d Product sans offres ni avis",
        "detail": "Un Product sans offers, review ni "
                  "aggregateRating n'est pas éligible aux "
                  "résultats enrichis produit.",
        "fix": "Ajoutez au moins offers (avec price et "
               "priceCurrency) ou review/aggregateRating.",
    },
    "sd.check.rating": {
        "title": "%(n)d note(s) incohérente(s)",
        "fix": "ratingValue dans l'échelle déclarée (par défaut "
               "1-5) et le nombre d'avis dans reviewCount ou "
               "ratingCount.",
    },
    "sd.check.dates": {
        "title": "%(n)d date(s) hors format ISO 8601",
        "detail": "%(list)s.",
        "fix": "Utilisez AAAA-MM-JJ, avec l'heure facultative "
               "après le T (p. ex. 2026-08-03T09:30:00+02:00).",
    },
    "sd.check.urls": {
        "title": "%(n)d URL de médias non absolues dans le "
                 "balisage",
        "detail": "%(list)s.",
        "fix": "image, logo, thumbnailUrl, contentUrl et "
               "embedUrl requièrent des URL http(s) complètes.",
    },
    "sd.check.ok": {
        "title": "Balisage Schema.org cohérent (%(n)d types "
                 "vérifiés)",
        "detail": "Vérifiés : %(types)s.",
    },
    "rrf.not_runnable": {
        "title": "Simulation RRF non exécutable",
        "detail": "Il faut au moins un chunk et une requête.",
    },
    "rrf.consensus.low": {
        "title": "Consensus moyen entre les listes : "
                 "%(avg).1f/%(top_n)d (%(pct).0f %%)",
        "detail": "Les deux listes pointent vers des passages "
                  "différents : aucun document n'accumule de "
                  "score sur les deux axes. Dans la formule RRF, "
                  "un document présent dans les deux listes "
                  "additionne deux addendes 1/(k+rang) et bat "
                  "celui qui domine une seule liste. Consensus "
                  "par requête : %(per_query)s.",
        "fix": "Optimisez les mêmes passages sur les deux axes : "
               "termes explicites (BM25) et explication "
               "complète (vectoriel).",
        "example": "Avant (lexical seulement) : « Drainage "
                   "lymphatique. Appelez pour info. »\n"
                   "Après (les deux axes) : « Le drainage "
                   "lymphatique manuel est un massage doux\nqui "
                   "facilite l'écoulement de la lymphe : une "
                   "séance dure 45 minutes\net le cycle type va "
                   "de 5 à 10 séances. »",
    },
    "rrf.consensus.mid": {
        "title": "Consensus moyen entre les listes : "
                 "%(avg).1f/%(top_n)d (%(pct).0f %%)",
        "detail": "Consensus partiel entre les deux "
                  "récupérateurs. Dans la formule RRF, un "
                  "document présent dans les deux listes "
                  "additionne deux addendes 1/(k+rang) et bat "
                  "celui qui domine une seule liste. Consensus "
                  "par requête : %(per_query)s.",
        "fix": "Optimisez les mêmes passages sur les deux axes : "
               "termes explicites (BM25) et explication "
               "complète (vectoriel).",
    },
    "rrf.consensus.good": {
        "title": "Consensus moyen entre les listes : "
                 "%(avg).1f/%(top_n)d (%(pct).0f %%)",
        "detail": "Bon recouvrement entre récupération lexicale "
                  "et vectorielle. Dans la formule RRF, un "
                  "document présent dans les deux listes "
                  "additionne deux addendes 1/(k+rang) et bat "
                  "celui qui domine une seule liste. Consensus "
                  "par requête : %(per_query)s.",
    },
    "rrf.uncovered": {
        "title": "%(n)d requêtes sans aucun résultat",
        "detail": "Aucun chunk du site ne répond : %(queries)s.",
        "fix": "Créez des contenus dédiés à ces intentions.",
        "example": "Pour chaque requête non couverte, une "
                   "section avec un intertitre égal à la "
                   "question :\n<h2>Combien coûte le drainage "
                   "lymphatique ?</h2>\n<p>Une séance coûte en "
                   "moyenne 40-80 euros, selon la durée et la "
                   "zone traitée.</p>",
    },
    "rrf.covered": {
        "title": "Les %(n)d requêtes trouvent toutes au moins "
                 "un passage",
        "detail": "Requêtes vérifiées : %(queries)s.",
    },
    "rrf.comp.empty": {
        "title": "Concurrent %(host)s sans contenu récupérable",
        "detail": "Aucune page analysable : la comparaison "
                  "l'inclut avec 0 passages.",
    },
    "rrf.comp.not_runnable": {
        "title": "Comparaison concurrentielle non exécutable",
        "detail": "Il faut au moins un chunk et une requête.",
    },
    "rrf.share.low": {
        "title": "Share of voice : %(pct).0f %% des %(top_n)d "
                 "premières places fusionnées (parité "
                 "%(parity).0f %%)",
        "detail": "Les concurrents occupent les places dont "
                  "vous auriez besoin : sur vos propres sujets, "
                  "vous êtes rarement récupéré. Répartition : "
                  "%(breakdown)s.",
        "fix": "Renforcez les passages sur les requêtes où les "
               "concurrents vous battent : mêmes termes "
               "explicites, réponse complète.",
    },
    "rrf.share.mid": {
        "title": "Share of voice : %(pct).0f %% des %(top_n)d "
                 "premières places fusionnées (parité "
                 "%(parity).0f %%)",
        "detail": "Vous êtes sous la parité : sur vos sujets, "
                  "les concurrents sont récupérés plus souvent "
                  "que vous. Répartition : %(breakdown)s.",
        "fix": "Renforcez les passages sur les requêtes où les "
               "concurrents vous battent : mêmes termes "
               "explicites, réponse complète.",
    },
    "rrf.share.good": {
        "title": "Share of voice : %(pct).0f %% des %(top_n)d "
                 "premières places fusionnées (parité "
                 "%(parity).0f %%)",
        "detail": "Vous tenez tête aux concurrents sur vos "
                  "sujets. Répartition : %(breakdown)s.",
    },
    "rrf.comp.lost": {
        "title": "%(n)d requêtes sur %(total)d entièrement "
                 "remportées par les concurrents",
        "detail": "Aucun de vos passages dans les %(top_n)d "
                  "premiers pour : %(queries)s.",
        "fix": "Créez ou réécrivez des contenus dédiés à ces "
               "intentions.",
    },
    "rrf.comp.present": {
        "title": "Présent dans les %(top_n)d premiers pour les "
                 "%(n)d requêtes",
        "detail": "Requêtes de comparaison : %(queries)s.",
    },
    "tech.robots.own": {
        "title": "Site déclaré comme le vôtre",
        "detail": "Les règles Disallow du robots.txt ne sont "
                  "pas appliquées au site audité (--own-site) ; "
                  "elles s'appliquent toujours aux éventuels "
                  "concurrents.",
    },
    "tech.robots.forced": {
        "title": "Règles Disallow du robots.txt ignorées sur "
                 "demande explicite",
        "detail": "L'exploration au-delà des règles Disallow a "
                  "été activée avec --ignore-robots %(ack)s : "
                  "la responsabilité du crawl a été "
                  "explicitement assumée par l'utilisateur.",
    },
    "tech.robots.excluded": {
        "title": "%(n)d URL exclues par respect du robots.txt",
        "detail": "Les règles Disallow adressées à l'agent "
                  "%(agent)s sont respectées (comportement par "
                  "défaut) : %(urls)s. Utilisez --own-site si "
                  "le site est le vôtre.",
    },
    "tech.render.done": {
        "title": "%(n)d page(s) analysée(s) avec rendu "
                 "JavaScript",
        "detail": "Mode --render %(mode)s : le contenu provient "
                  "du DOM rendu dans un navigateur headless ; "
                  "statut HTTP, redirections et temps restent "
                  "ceux de la réponse d'origine.",
    },
    "tech.render.failed": {
        "title": "Rendu échoué pour %(n)d page(s)",
        "detail": "Pour ces pages, le HTML statique a été "
                  "analysé.",
        "fix": "Réessayez, ou augmentez le timeout si le site "
               "est lent.",
    },
    "tech.pages.duplicates": {
        "title": "%(n)d URL servent un contenu identique",
        "detail": "Le même texte est accessible depuis "
                  "plusieurs adresses : %(urls)s. Les doublons "
                  "n'ajoutent aucun addende à la somme RRF, "
                  "diluent les signaux et gaspillent le budget "
                  "de crawl.",
        "fix": "Choisissez une URL canonique et redirigez les "
               "autres en 301.",
    },
}

_FINDINGS_DE: Dict[str, Dict[str, str]] = {
    "tech.robots.missing": {
        "title": "robots.txt nicht erreichbar",
        "detail": "Die Anfrage an %(url)s ist fehlgeschlagen "
                  "oder hat nicht 200 geantwortet.",
        "fix": "Veröffentlichen Sie eine robots.txt, die die "
               "Sitemap deklariert.",
    },
    "tech.robots.present": {
        "title": "robots.txt vorhanden",
        "detail": "%(n)d Zeilen.",
    },
    "tech.robots.ai_blocked": {
        "title": "KI-Crawler blockiert: %(agents)s",
        "detail": "Diese Agents können nicht auf die Startseite "
                  "zugreifen. Sind sie blockiert, erscheinen Sie "
                  "in keiner Retrieval-Liste und RRF hat nichts "
                  "zu fusionieren.",
        "fix": "Entfernen Sie die Disallow-Regeln für die "
               "Agents, von denen Sie zitiert werden wollen.",
        "example": "# robots.txt - KI-Agents freigeben\n"
                   "User-agent: GPTBot\nDisallow:\n\n"
                   "User-agent: ClaudeBot\nDisallow:\n\n"
                   "User-agent: PerplexityBot\nDisallow:",
    },
    "tech.robots.ai_allowed": {
        "title": "KI-Crawler zugelassen",
        "detail": "Geprüft: %(agents)s.",
    },
    "tech.robots.sitemap_ok": {
        "title": "Sitemap in der robots.txt deklariert",
        "detail": "%(urls)s",
    },
    "tech.robots.sitemap_missing": {
        "title": "Keine Sitemap in der robots.txt deklariert",
        "fix": "Ergänzen Sie die Zeile "
               "'Sitemap: https://.../sitemap.xml'.",
        "example": "# am Ende der robots.txt\n"
                   "Sitemap: https://esempio.it/sitemap.xml",
    },
    "tech.llms.present": {
        "title": "llms.txt vorhanden",
        "detail": "%(n)d Zeilen.",
    },
    "tech.llms.missing": {
        "title": "llms.txt fehlt",
        "detail": "Aufkommender Standard (llmstxt.org): ein "
                  "Markdown-Index der Kerninhalte für "
                  "KI-Agents.",
        "fix": "Erwägen Sie, /llms.txt mit Ihren Kerninhalten "
               "zu veröffentlichen.",
    },
    "tech.links.orphans": {
        "title": "%(n)d Seite(n) ohne eingehende interne Links "
                 "(verwaist)",
        "detail": "Nur über die Sitemap erreichbar: %(urls)s. "
                  "Eine Seite, auf die niemand verlinkt, wird "
                  "seltener gecrawlt und geringer gewichtet.",
        "fix": "Verlinken Sie sie aus verwandten Seiten "
               "(Fließtext, Menü oder Footer).",
        "example": "Aus der verwandten Seite:\n"
                   "<a href=\"/servizio-collegato/\">"
                   "beschreibender Name der Leistung</a>",
    },
    "tech.links.no_orphans": {
        "title": "Jede Seite hat eingehende interne Links",
    },
    "tech.links.deep": {
        "title": "%(n)d Seite(n) mehr als 3 Klicks von der "
                 "Startseite entfernt",
        "detail": "%(urls)s.",
        "fix": "Verkürzen Sie die Pfade: tiefe Seiten werden "
               "seltener gecrawlt und geringer gewichtet.",
    },
    "tech.links.generic_anchors": {
        "title": "%(n)d generische Anker in internen Links",
        "detail": "Texte wie \"hier klicken\" oder \"mehr "
                  "lesen\" sagen nichts über den Zielinhalt "
                  "aus.",
        "fix": "Verwenden Sie beschreibende Anker mit den "
               "Begriffen der Zielseite.",
    },
    "tech.redirect.http_left": {
        "title": "%(n)d interne URLs noch auf http",
        "detail": "Auf die https-Version umgeleitet: %(urls)s. "
                  "Jeder Sprung verschwendet Crawl-Budget und "
                  "verwässert die Signale.",
        "fix": "Aktualisieren Sie Sitemap und interne Links auf "
               "die endgültigen https-URLs.",
        "example": "<!-- vorher  --> <a href=\"http://esempio.it/"
                   "servizio/\">\n<!-- nachher --> "
                   "<a href=\"https://esempio.it/servizio/\">",
    },
    "tech.redirect.www_mixed": {
        "title": "%(n)d URLs mit gemischtem www/non-www-Host",
        "detail": "Auf den kanonischen Host umgeleitet: "
                  "%(urls)s.",
        "fix": "Verwenden Sie einen einzigen Host (mit oder "
               "ohne www) in Sitemap und internen Links.",
    },
    "tech.redirect.moved": {
        "title": "%(n)d interne URLs antworten mit einer "
                 "Weiterleitung",
        "detail": "Verschobene URLs: %(urls)s.",
        "fix": "Aktualisieren Sie Sitemap und interne Links auf "
               "das endgültige Ziel der Weiterleitungen.",
        "example": "In Sitemap und internen Links direkt die "
                   "Ziel-URL verwenden:\n<url><loc>https://"
                   "esempio.it/nuova-pagina/</loc></url>",
    },
    "tech.redirect.chains": {
        "title": "%(n)d URLs mit einer mehrstufigen "
                 "Weiterleitungskette",
        "detail": "%(urls)s.",
        "fix": "Lassen Sie jede Weiterleitung direkt auf das "
               "endgültige Ziel zeigen (ein einziger Sprung).",
        "example": "# ein Sprung, keine Kette\n"
                   "Redirect 301 /vecchia/ "
                   "https://esempio.it/nuova/\n"
                   "# NICHT: /vecchia/ -> /intermedia/ -> "
                   "/nuova/",
    },
    "tech.redirect.none": {
        "title": "Keine internen Weiterleitungen",
        "detail": "Jede analysierte URL antwortet direkt.",
    },
    "tech.msft.noarchive": {
        "title": "%(n)d Seite(n) von Copilot ausgeschlossen "
                 "(noarchive)",
        "detail": "Das noarchive-Meta schließt den Inhalt aus "
                  "den Antworten von Bing Chat/Copilot und dem "
                  "Training der Microsoft-Modelle aus (die "
                  "klassische Suche ist nicht betroffen): auf "
                  "diesen Seiten ist die Zitierbarkeit im "
                  "Microsoft-Kanal null. %(urls)s",
        "fix": "Ist der Ausschluss unbeabsichtigt, entfernen "
               "Sie noarchive; für eine Teilpräsenz (nur Titel, "
               "URL und Snippet) verwenden Sie nocache.",
    },
    "tech.msft.nocache": {
        "title": "%(n)d Seite(n) mit Teilpräsenz in Copilot "
                 "(nocache)",
        "detail": "Mit nocache zeigt Bing Chat/Copilot nur URL, "
                  "Titel und Snippet der Seite und verwendet "
                  "nur diese Elemente für das "
                  "Microsoft-Training. %(urls)s",
        "fix": "Ein legitimer Teil-Opt-out: prüfen Sie nur, ob "
               "er beabsichtigt ist. Für volle Zitierbarkeit in "
               "Copilot entfernen Sie das Meta.",
    },
    "tech.msft.no_optout": {
        "title": "Kein Microsoft-KI-Opt-out aktiv",
        "detail": "Es gibt kein eigenes robots.txt-Token für "
                  "Microsofts KI: die Steuerung läuft über die "
                  "noarchive/nocache-Metas, die hier fehlen. "
                  "Ihre Inhalte können daher in "
                  "Copilot-Antworten und im Microsoft-Training "
                  "verwendet werden; für den Opt-out verwenden "
                  "Sie noarchive (vollständig) oder nocache "
                  "(teilweise).",
    },
    "tech.anchors.varied": {
        "title": "Abwechslungsreiches internes Ankerprofil",
        "detail": "%(texts)d eindeutige Texte auf %(pairs)d "
                  "Text-Ziel-Paare (%(pct).0f%%; gängige "
                  "Praxisschwelle: %(threshold).0f%%).",
    },
    "tech.anchors.repetitive": {
        "title": "Repetitives internes Ankerprofil",
        "detail": "%(texts)d eindeutige Texte auf %(pairs)d "
                  "Text-Ziel-Paare (%(pct).0f%%, gängige "
                  "Praxisschwelle %(threshold).0f%%): derselbe "
                  "Text führt zu verschiedenen Zielen, und der "
                  "Leser — Mensch oder Modell — kann nicht "
                  "vorhersehen, wohin der Link führt. "
                  "%(examples)s",
        "fix": "Verwenden Sie beschreibende, je Ziel "
               "unterschiedliche Anker: der Linktext muss "
               "sagen, was auf der anderen Seite liegt.",
        "example": "Vorher:  \"Mehr lesen\" -> /servizi, \"Mehr "
                   "lesen\" -> /prezzi\n"
                   "Nachher: \"Alle Lymphdrainage-Leistungen\" "
                   "-> /servizi, \"Preise der Sitzungen\" -> "
                   "/prezzi",
    },
    "tech.meta.charset": {
        "title": "%(n)d Seite(n) ohne deklarierten Charset",
        "detail": "%(urls)s",
        "fix": "Deklarieren Sie die Kodierung am Anfang des "
               "<head>.",
    },
    "tech.meta.viewport": {
        "title": "%(n)d Seite(n) ohne Viewport-Meta",
        "detail": "Ohne Viewport ist das mobile Rendering nicht "
                  "deklariert: %(urls)s",
        "fix": "Ergänzen Sie den responsiven Viewport.",
    },
    "tech.meta.og_missing": {
        "title": "%(n)d Seite(n) ohne Open Graph",
        "detail": "Vorschauen geteilter Links (und viele "
                  "Assistenten-Antworten) entstehen aus den "
                  "og:*-Tags: ohne sie entscheidet derjenige, "
                  "der den Link einfügt, über Titel und Bild. "
                  "%(urls)s",
        "fix": "Ergänzen Sie mindestens die Trias og:title, "
               "og:description, og:image.",
    },
    "tech.meta.og_partial": {
        "title": "Unvollständiges Open Graph auf %(n)d "
                 "Seite(n)",
        "detail": "%(urls)s",
        "fix": "Vervollständigen Sie die Trias og:title, "
               "og:description, og:image.",
    },
    "tech.meta.ok": {
        "title": "Basis-Metas in Ordnung",
        "detail": "charset, viewport und Open Graph vollständig "
                  "auf allen %(n)d analysierten Seiten.",
    },
    "tech.https.missing": {
        "title": "Website nicht auf HTTPS",
        "fix": "Aktivieren Sie ein TLS-Zertifikat und leiten "
               "Sie alles auf HTTPS um.",
    },
    "tech.https.ok": {
        "title": "HTTPS aktiv",
    },
    "tech.pages.broken": {
        "title": "%(n)d URLs unerreichbar oder fehlerhaft",
        "detail": "%(urls)s",
        "fix": "Beheben Sie die fehlerhaften URLs oder "
               "entfernen Sie sie aus der Sitemap.",
    },
    "tech.pages.soft404": {
        "title": "%(n)d mögliche Soft-404 (200 mit \"nicht "
                 "gefunden\"-Inhalt)",
        "detail": "Sie antworten 200, aber der Inhalt sagt, die "
                  "Seite existiere nicht: %(urls)s. Sie gehen "
                  "als leere Seiten in den Index ein und "
                  "verwässern die Signale der Website.",
        "fix": "Lassen Sie nicht existierende URLs 404 (oder "
               "410) antworten und entfernen Sie die leeren aus "
               "der Sitemap.",
        "example": "Die nicht existierende Seite muss mit "
                   "Status 404 antworten, nicht 200:\n"
                   "# Apache (.htaccess)\n"
                   "ErrorDocument 404 /404.html\n"
                   "# keine Umleitung zur Startseite statt "
                   "des 404",
    },
    "tech.pages.none": {
        "title": "Keine analysierbare Seite",
        "detail": "Keine URL hat gültiges HTML geliefert: die "
                  "Website ist unerreichbar, blockiert den "
                  "User-Agent des Tools oder antwortet nur mit "
                  "JavaScript. Das Inhaltsaudit wurde nicht "
                  "durchgeführt.",
        "fix": "Prüfen Sie, ob die Website antwortet und keine "
               "Crawler filtert.",
    },
    "tech.pages.single": {
        "title": "Minimale indexierbare Fläche (1 Seite)",
        "detail": "Mit einem einzigen Dokument hat die "
                  "RRF-Summe keine Summanden: es gibt keine "
                  "unterschiedlichen Passagen, die auftauchen "
                  "könnten.",
        "fix": "Erstellen Sie eigenständige Seiten für jedes "
               "Thema / jede Leistung.",
    },
    "tech.pages.few": {
        "title": "Wenige indexierbare Seiten (%(n)d)",
        "fix": "Erweitern Sie die Fläche: eine Seite pro "
               "Suchintention.",
    },
    "tech.pages.ok": {
        "title": "%(n)d indexierbare Seiten analysiert",
        "detail": "Erste Seiten: %(urls)s.",
    },
    "tech.sitemap.missing": {
        "title": "XML-Sitemap fehlt oder ist unlesbar",
        "detail": "URLs durch Crawlen der internen Links "
                  "entdeckt.",
        "fix": "Veröffentlichen Sie eine XML-Sitemap und "
               "deklarieren Sie sie in der robots.txt.",
    },
    "tech.pages.placeholder": {
        "title": "%(n)d indexierbare Platzhalterseite(n)",
        "detail": "Erkannt: %(urls)s. Es sind "
                  "CMS-Standardinhalte: reines Rauschen im "
                  "Index und das Signal einer unfertigen "
                  "Website.",
        "fix": "Löschen Sie sie, oder setzen Sie noindex und "
               "entfernen Sie sie aus der Sitemap.",
    },
    "tech.pages.noindex": {
        "title": "%(n)d Seite(n) mit noindex-Robots-Meta",
        "detail": "%(urls)s",
        "fix": "Prüfen Sie, ob der Ausschluss beabsichtigt "
               "ist.",
        "example": "Soll die Seite indexiert werden, entfernen "
                   "Sie das Meta oder verwenden Sie:\n"
                   "<meta name=\"robots\" "
                   "content=\"index, follow\">",
    },
    "tech.canonical.missing": {
        "title": "%(n)d Seite(n) ohne Canonical",
        "detail": "%(urls)s",
        "fix": "Deklarieren Sie <link rel=\"canonical\"> auf "
               "jeder Seite.",
    },
    "tech.canonical.ok": {
        "title": "Canonicals vorhanden",
        "detail": "Auf allen %(n)d analysierten Seiten "
                  "deklariert.",
    },
    "tech.lang.missing": {
        "title": "%(n)d Seite(n) ohne lang-Attribut",
        "fix": "Setzen Sie <html lang=\"it\">: das hilft bei "
               "der Wahl des Sprachmodells während der "
               "Analyse.",
    },
    "tech.js.heavy": {
        "title": "%(n)d Seite(n) mit wenig Text und viel "
                 "JavaScript",
        "detail": "Der Inhalt wird womöglich clientseitig "
                  "gerendert und bleibt Crawlern verborgen.",
        "fix": "Aktivieren Sie Server-Side-Rendering oder "
               "Pre-Rendering.",
    },
    "tech.js.rendered": {
        "title": "%(n)d Seite(n) mit wenig Text und viel "
                 "JavaScript",
        "detail": "Der Inhalt wurde mit JavaScript-Rendering "
                  "analysiert, aber Crawler, die kein "
                  "JavaScript ausführen (die meisten "
                  "KI-Crawler), sehen ihn weiterhin nicht.",
        "fix": "Aktivieren Sie Server-Side-Rendering oder "
               "Pre-Rendering.",
    },
    "tech.js.ok": {
        "title": "Inhalt im initialen HTML vorhanden",
    },
    "tech.slow": {
        "title": "%(n)d Seite(n) mit Antwortzeit über 2 s",
        "detail": "Langsamste: %(worst).2f s.",
        "fix": "Optimieren Sie Caching und TTFB.",
    },
    "tech.hreflang.missing": {
        "title": "Mehrsprachige Website ohne hreflang",
        "detail": "Erkannte Sprachen: %(langs)s.",
        "fix": "Deklarieren Sie wechselseitige hreflang "
               "zwischen den Versionen.",
    },
    "tech.hreflang.na": {
        "title": "Einsprachige Website: hreflang nicht nötig",
    },
    "lex.clickbait.found": {
        "title": "%(n)d Titel oder Überschriften mit "
                 "Clickbait-Formeln",
        "detail": "Reißerische Formeln und mehrfache "
                  "Ausrufezeichen locken den Klick, beantworten "
                  "aber nichts: generative Engines wählen "
                  "informative Titel. %(examples)s",
        "fix": "Schreiben Sie im informativen Stil um: der "
               "Nutzen oder die Antwort im Titel, ohne "
               "Übertreibung.",
        "example": "Vorher:  \"Sie werden nicht glauben, was "
                   "die Drainage bewirkt!!\"\nNachher: "
                   "\"Lymphdrainage: Nutzen, Dauer und Kosten "
                   "einer Sitzung\"",
    },
    "lex.clickbait.none": {
        "title": "Keine Clickbait-Formel in Titeln und "
                 "Überschriften",
        "detail": "Titel im informativen Stil auf allen %(n)d "
                  "analysierten Seiten.",
    },
    "lex.title.missing": {
        "title": "%(n)d Seite(n) ohne <title>",
        "fix": "Der Title ist das lexikalische Signal mit dem "
               "höchsten Gewicht.",
    },
    "lex.title.bad": {
        "title": "%(n)d Title nicht optimiert",
        "detail": "Beispiele: %(examples)s",
        "fix": "Eindeutiger Title, %(min)d-%(max)d Zeichen, mit "
               "den echten Suchbegriffen; vermeiden Sie den "
               "Domainnamen als Titel.",
        "example": "<title>Drenaggio linfatico manuale a Parma "
                   "| Centro Esempio</title>\n"
                   "(52 Zeichen: Leistung + Gebiet + Marke)",
    },
    "lex.title.dup": {
        "title": "%(n)d seitenübergreifend duplizierte Title",
        "detail": "%(examples)s",
        "fix": "Jede Seite braucht einen eigenen Title.",
    },
    "lex.title.ok": {
        "title": "Title gut aufgesetzt",
    },
    "lex.desc.missing": {
        "title": "%(n)d Seite(n) ohne Meta-Description",
        "detail": "%(urls)s",
        "fix": "Schreiben Sie %(min)d-%(max)d Zeichen mit Leistung "
               "und Gebiet.",
    },
    "lex.desc.short": {
        "title": "%(n)d zu kurze Meta-Descriptions",
        "detail": "Beispiele: %(examples)s",
        "fix": "Eine Description, die nur den Firmennamen "
               "wiederholt, trägt kein Signal.",
    },
    "lex.desc.long": {
        "title": "%(n)d Meta-Descriptions über %(max)d Zeichen",
    },
    "lex.desc.ok": {
        "title": "Meta-Descriptions vorhanden und angemessen "
                 "lang",
    },
    "lex.h1.missing": {
        "title": "%(n)d Seite(n) ohne H1",
        "detail": "%(urls)s",
        "fix": "Eine einzige H1 pro Seite, mit den "
               "Hauptbegriffen.",
    },
    "lex.h1.multi": {
        "title": "%(n)d Seite(n) mit mehreren H1",
    },
    "lex.h1.ok": {
        "title": "Korrekte H1-Struktur",
    },
    "lex.words.thin": {
        "title": "%(n)d Seite(n) unter %(min)d Wörtern",
        "detail": "Durchschnitt der Website: %(avg)d Wörter. "
                  "Mit so wenig Text erreichen die nützlichen "
                  "Begriffe nie eine Häufigkeit, die BM25 "
                  "belohnen kann.",
        "fix": "Bringen Sie die Schlüsselseiten auf %(target)d+ "
               "Wörter informativen, nicht werblichen Inhalts.",
        "example": "Typische Struktur einer Leistungsseite:\n"
                   "<h2>Was ist ...?</h2> <h2>Wie eine Sitzung "
                   "abläuft</h2>\n<h2>Wann sie nötig ist</h2> "
                   "<h2>Was sie kostet</h2> <h2>FAQ</h2>",
    },
    "lex.words.ok": {
        "title": "Angemessenes Textvolumen",
        "detail": "Durchschnitt: %(avg)d Wörter pro Seite.",
    },
    "lex.acronyms.bare": {
        "title": "Abkürzungen ohne ausgeschriebene Form "
                 "verwendet",
        "detail": "Nicht ausgeschrieben: %(list)s.",
        "fix": "Schreiben Sie 'ABKÜRZUNG (ausgeschriebene "
               "Form)' mindestens beim ersten Vorkommen: das "
               "deckt beide Suchformulierungen ab.",
    },
    "lex.acronyms.ok": {
        "title": "Abkürzungen mit ausgeschriebener Form",
        "detail": "%(list)s",
    },
    "lex.slug.bad": {
        "title": "%(n)d wenig aussagekräftige Slugs",
        "detail": "%(slugs)s",
        "fix": "Verwenden Sie thematische Slugs mit "
               "Bindestrichen.",
    },
    "lex.slug.ok": {
        "title": "Thematische, lesbare Slugs",
    },
    "lex.alt.partial": {
        "title": "Unvollständige Alt-Attribute (%(with_alt)d/"
                 "%(total)d)",
        "fix": "Das Alt ist indexierbarer Text und zugleich "
               "Barrierefreiheit.",
    },
    "lex.alt.ok": {
        "title": "Alt-Attribute vorhanden (%(with_alt)d/"
                 "%(total)d)",
    },
    "sem.extract.ok": {
        "title": "Gute direkte Extrahierbarkeit",
        "detail": "%(direct)d von %(total)d Absätzen beginnen "
                  "mit einer expliziten Antwort in "
                  "%(min)d-%(max)d Wörtern (%(pct).0f%% "
                  "gegenüber einer gängigen Praxisschwelle von "
                  "%(threshold).0f%%): das sind die Passagen, "
                  "die ein Assistent unverändert zitieren "
                  "kann.",
    },
    "sem.extract.low": {
        "title": "Wenige Absätze mit direkter Antwort",
        "detail": "%(direct)d von %(total)d Absätzen beginnen "
                  "mit einer expliziten Antwort in "
                  "%(min)d-%(max)d Wörtern (%(pct).0f%% "
                  "gegenüber einer gängigen Praxisschwelle von "
                  "%(threshold).0f%%): das sind die Passagen, "
                  "die ein Assistent unverändert zitieren "
                  "kann.",
        "fix": "Schreiben Sie die Schlüsselabsätze so um, dass "
               "sie mit der Antwort beginnen (\"X ist ...\", "
               "\"Ja, ...\", \"Kurz gesagt ...\"), und halten "
               "Sie sie zwischen %(min)d und %(max)d Wörtern.",
        "example": "Vorher:  \"In der heutigen Wellness-Welt "
                   "fragen sich viele, welcher Weg...\"\n"
                   "Nachher: \"Die Lymphdrainage ist eine "
                   "sanfte Massage, die den Lymphfluss "
                   "erleichtert: eine Sitzung dauert 45 Minuten "
                   "und kostet 40-80 Euro.\"",
    },
    "sem.filler.saturated": {
        "title": "%(n)d Seite(n) mit Marketing-Formeln "
                 "gesättigt",
        "detail": "Füllmaterial belegt Raum, ohne etwas "
                  "Extrahierbares zu sagen (gängige "
                  "Praxisschwelle: mindestens %(min)d Formeln "
                  "und eine je 100 Wörter). %(examples)s",
        "fix": "Ersetzen Sie die generischen Formeln durch "
               "überprüfbare Informationen: Zahlen, Dauern, "
               "Preise, Abläufe.",
        "example": "Vorher:  \"Wir sind Marktführer, Qualität "
                   "und Professionalität zu Ihren Diensten.\"\n"
                   "Nachher: \"Seit 2012 haben wir über 400 "
                   "Patienten nach Operationen begleitet; die "
                   "Erstbewertung ist kostenlos und dauert 30 "
                   "Minuten.\"",
    },
    "sem.filler.ok": {
        "title": "Marketing-Füllmaterial unter Kontrolle",
        "detail": "%(n)d generische Formeln auf der ganzen "
                  "Website: der nützliche Text dominiert.",
    },
    "sem.lifecycle.ok": {
        "title": "Themenlebenszyklus abgedeckt (%(n)d von 6)",
        "detail": "In den Überschriften gefundene Abschnitte: "
                  "%(found)s.",
    },
    "sem.lifecycle.partial": {
        "title": "Themenlebenszyklus unvollständig (%(n)d von "
                 "6)",
        "detail": "Eine vollständige Behandlung deckt "
                  "Definition, Geschichte, Anwendungsfälle, "
                  "Grenzen, FAQ und Ausblick ab: das ist der "
                  "Inhalt, den generative Engines für jeden "
                  "Blickwinkel einer Frage zitieren können. "
                  "%(found)s Fehlend: %(missing)s.",
        "fix": "Ergänzen Sie die fehlenden Abschnitte mit "
               "expliziten Überschriften (sie können sich über "
               "mehrere Seiten verteilen).",
    },
    "sem.fresh.ok": {
        "title": "Kürzlich aktualisierte Inhalte",
        "detail": "Jüngste deklarierte Aktualisierung: %(date)s "
                  "auf %(url)s (vor %(days)d Tagen).",
    },
    "sem.fresh.stale": {
        "title": "Inhalte seit über einem Jahr unberührt",
        "detail": "Die jüngste deklarierte Aktualisierung "
                  "stammt vom %(date)s (vor %(days)d Tagen). "
                  "Generative Engines bevorzugen gepflegte "
                  "Quellen: ein eingefrorenes Datum signalisiert "
                  "womöglich veraltete Inhalte. Älteste Seiten: "
                  "%(stale)s.",
        "fix": "Überarbeiten Sie die Kerninhalte und "
               "deklarieren Sie die Aktualisierung mit "
               "article:modified_time oder dateModified im "
               "JSON-LD.",
    },
    "sem.fresh.very_stale": {
        "title": "Inhalte seit über zwei Jahren unberührt",
        "detail": "Die jüngste deklarierte Aktualisierung "
                  "stammt vom %(date)s (vor %(days)d Tagen). "
                  "Generative Engines bevorzugen gepflegte "
                  "Quellen: ein eingefrorenes Datum signalisiert "
                  "womöglich veraltete Inhalte. Älteste Seiten: "
                  "%(stale)s.",
        "fix": "Überarbeiten Sie die Kerninhalte und "
               "deklarieren Sie die Aktualisierung mit "
               "article:modified_time oder dateModified im "
               "JSON-LD.",
    },
    "sem.refs.ok": {
        "title": "Quellenverweise vorhanden",
        "detail": "%(context)s (gängige Praxisschwelle: ein "
                  "Quellenabschnitt oder mindestens "
                  "%(threshold)d Zitate).",
    },
    "sem.refs.missing": {
        "title": "Kein Verweis auf externe Quellen",
        "detail": "%(context)s. Quellenangaben stärken die "
                  "E-E-A-T-Signale und geben KI-Assistenten "
                  "etwas zum Überprüfen: belegte Inhalte sind "
                  "zitierfähiger.",
        "fix": "Ergänzen Sie einen Abschnitt \"Quellen\" mit "
               "Links zu Leitlinien, Studien oder offizieller "
               "Dokumentation (oder Zitate im Text).",
    },
    "sem.chunks.none": {
        "title": "Kein extrahierbarer Chunk",
        "detail": "Die Website bietet keine indexierbaren "
                  "Textpassagen.",
        "fix": "Schreiben Sie ausformulierte Absätze von "
               "mindestens 40-50 Wörtern.",
    },
    "sem.chunks.ok": {
        "title": "%(chunks)d indexierbare Chunks auf %(pages)d "
                 "Seiten",
        "detail": "Jeder Chunk ist eine Chance, in den Listen "
                  "aufzutauchen: in der RRF-Summe ist die Zahl "
                  "der relevanten Passagen der wahre "
                  "Multiplikator.",
    },
    "sem.chunks.few": {
        "title": "%(chunks)d indexierbare Chunks auf %(pages)d "
                 "Seiten",
        "detail": "Jeder Chunk ist eine Chance, in den Listen "
                  "aufzutauchen: in der RRF-Summe ist die Zahl "
                  "der relevanten Passagen der wahre "
                  "Multiplikator.",
        "fix": "Erhöhen Sie die Zahl eigenständiger "
               "thematischer Passagen.",
    },
    "sem.anaphora.high": {
        "title": "%(pct).0f%% der Chunks sind nicht "
                 "eigenständig",
        "detail": "Sie beginnen mit einem anaphorischen Verweis "
                  "(dieser, solcher, jener...): für sich "
                  "extrahiert beantworten sie nichts. "
                  "Beispiele: %(examples)s.",
        "fix": "Schreiben Sie die Einstiege um und nennen Sie "
               "das Subjekt explizit.",
        "example": "Vorher:  \"Diese Behandlung ist nach einer "
                   "Operation angezeigt.\"\nNachher: \"Die "
                   "manuelle Lymphdrainage ist nach einer "
                   "Operation angezeigt.\"",
    },
    "sem.anaphora.ok": {
        "title": "Chunks weitgehend eigenständig (%(pct).0f%% "
                 "anaphorisch)",
    },
    "sem.questions.few": {
        "title": "Fast keine Überschrift in Frageform (%(n)d "
                 "von %(total)d)",
        "detail": "Es ist das Format, das KI-Engines am "
                  "häufigsten zitieren: eine explizite Frage "
                  "gefolgt von einer direkten Antwort.",
        "fix": "Ergänzen Sie Überschriften wie \"Was ist X?\", "
               "\"Wie funktioniert X?\", \"Was kostet X?\" mit "
               "einer knappen Antwort von 2-3 Zeilen.",
    },
    "sem.questions.ok": {
        "title": "%(n)d Überschriften in Frageform "
                 "(%(pct).0f%%)",
        "detail": "Beispiele: %(examples)s.",
    },
    "sem.faq.ok": {
        "title": "FAQ-Bereich erkannt",
        "detail": "Erkannt auf %(url)s.",
    },
    "sem.faq.missing": {
        "title": "Kein FAQ-Bereich",
        "detail": "FAQs richten einen Chunk an einer präzisen "
                  "Intention aus und speisen beide Achsen "
                  "zugleich.",
        "fix": "Ergänzen Sie FAQs je Seite, ausgezeichnet mit "
               "FAQPage-JSON-LD.",
    },
    "sem.defs.low": {
        "title": "Definitionsarmer Inhalt (%(pct).0f%% der "
                 "Chunks)",
        "detail": "Ohne Passagen, die erklären, *was* etwas "
                  "ist, bleiben die Embeddings weit von "
                  "informationellen Anfragen entfernt.",
        "fix": "Ergänzen Sie zu jedem Thema: was es ist / wie "
               "es funktioniert / wann es nötig ist / ein "
               "Beispiel.",
    },
    "sem.defs.ok": {
        "title": "Definierende Passagen vorhanden (%(pct).0f%% "
                 "der Chunks)",
    },
    "sem.examples.few": {
        "title": "Fast kein konkretes Beispiel",
        "fix": "Beispiele und Fallstudien sind die Inhalte mit "
               "der höchsten semantischen Dichte.",
    },
    "sem.examples.ok": {
        "title": "%(n)d Chunks mit konkreten Beispielen",
    },
    "sem.vocab.narrow": {
        "title": "Enger Wortschatz (%(n)d verschiedene "
                 "Begriffe)",
        "detail": "Wenig lexikalische Vielfalt bedeutet "
                  "begrenzte semantische Abdeckung: Sie fangen "
                  "wenige Umformulierungen derselben Frage ab.",
        "fix": "Erweitern Sie die behandelten Themen und die "
               "verwendeten Formulierungen.",
    },
    "sem.vocab.ok": {
        "title": "Breiter Wortschatz (%(n)d verschiedene "
                 "Begriffe)",
    },
    "sem.eeat.author.ok": {
        "title": "E-E-A-T: Autor der Inhalte deklariert",
    },
    "sem.eeat.author.missing": {
        "title": "E-E-A-T: kein Autor deklariert",
        "fix": "Ergänzen Sie das author-Meta oder die "
               "author-Eigenschaft im JSON-LD: KI-Engines "
               "gewichten, wer den Inhalt zeichnet.",
    },
    "sem.eeat.dates.ok": {
        "title": "E-E-A-T: Publikations-/Aktualisierungsdaten "
                 "vorhanden",
    },
    "sem.eeat.dates.missing": {
        "title": "E-E-A-T: kein Publikations- oder "
                 "Aktualisierungsdatum",
        "fix": "Exponieren Sie article:published_time/"
               "modified_time oder datePublished/dateModified "
               "im JSON-LD.",
    },
    "sem.eeat.about.ok": {
        "title": "E-E-A-T: \"Über uns\"-Seite vorhanden",
    },
    "sem.eeat.about.missing": {
        "title": "E-E-A-T: keine \"Über uns\"-Seite erkannt",
        "fix": "Eine Seite, die Menschen und Kompetenzen "
               "vorstellt, ist das direkteste "
               "Erfahrungssignal.",
        "example": "Erstellen Sie /chi-siamo/ mit: wer die "
                   "Inhalte pflegt, Titel und Ausbildung,\nseit "
                   "wann, echte Fotos. Verlinken Sie sie aus "
                   "dem Footer jeder Seite.",
    },
    "sem.eeat.contact.ok": {
        "title": "E-E-A-T: überprüfbare Kontakte vorhanden",
    },
    "sem.eeat.contact.missing": {
        "title": "E-E-A-T: kein überprüfbarer Kontakt erkannt",
        "fix": "Exponieren Sie Telefon und E-Mail "
               "(tel:/mailto:-Links) oder eine Kontaktseite.",
    },
    "sd.semantic.poor": {
        "title": "%(n)d Seite(n) ohne semantisches Markup",
        "detail": "Weniger als %(min)d Arten von "
                  "Gliederungstags (article, section, main, "
                  "figure...): die Chunker generativer Engines "
                  "haben weniger Anhaltspunkte, um den Inhalt "
                  "in kohärente Blöcke zu segmentieren. "
                  "%(urls)s",
        "fix": "Umschließen Sie den Hauptinhalt mit <main> und "
               "<article>, thematische Abschnitte mit <section> "
               "samt Überschrift, Bilder und Bildunterschriften "
               "mit <figure>.",
    },
    "sd.semantic.divitis": {
        "title": "%(n)d Seite(n) mit einem Übermaß an <div> "
                 "(Divitis)",
        "detail": "Mehr als die Hälfte der Elemente sind "
                  "generische <div>: %(urls)s.",
        "fix": "Ersetzen Sie strukturelle <div> durch die "
               "äquivalenten semantischen Tags: das Markup wird "
               "selbstbeschreibend.",
    },
    "sd.semantic.ok": {
        "title": "Semantisches Markup im Einsatz",
        "detail": "Alle %(n)d analysierbaren Seiten verwenden "
                  "Gliederungstags und halten die <div> unter "
                  "%(max)d%% der Elemente.",
    },
    "sd.jsonld.none": {
        "title": "Keine strukturierten JSON-LD-Daten",
        "detail": "Ohne Markup wird die Entität nicht erkannt "
                  "und der Inhalt ist nicht für Rich Results "
                  "geeignet.",
        "fix": "Ergänzen Sie mindestens Organization (oder "
               "LocalBusiness), dann Service, FAQPage, "
               "BreadcrumbList, Article.",
    },
    "sd.jsonld.ok": {
        "title": "JSON-LD vorhanden",
        "detail": "Erkannte Typen: %(types)s.",
    },
    "sd.entity.missing": {
        "title": "Hauptentität nicht deklariert",
        "fix": "Ergänzen Sie Organization oder LocalBusiness "
               "mit Name, Adresse, Kontakten und "
               "Steuerkennungen.",
    },
    "sd.entity.ok": {
        "title": "Hauptentität deklariert",
    },
    "sd.type.faqpage": {
        "title": "FAQPage-Markup fehlt",
        "detail": "Ausgezeichnete FAQs sind das Format, das "
                  "KI-Engines am meisten zitieren.",
        "fix": "Ergänzen Sie den Typ FAQPage, wo es passt.",
    },
    "sd.type.breadcrumblist": {
        "title": "BreadcrumbList-Markup fehlt",
        "detail": "Es verdeutlicht die Hierarchie der Website.",
        "fix": "Ergänzen Sie den Typ BreadcrumbList, wo es "
               "passt.",
    },
    "sd.type.website": {
        "title": "WebSite-Markup fehlt",
        "detail": "Nützlich für die Sitelinks-Searchbox.",
        "fix": "Ergänzen Sie den Typ WebSite, wo es passt.",
    },
    "sd.jsonld.partial": {
        "title": "JSON-LD auf nur %(covered)d von %(total)d "
                 "Seiten",
        "fix": "Dehnen Sie das Markup auf alle relevanten "
               "Seiten aus.",
    },
    "sd.check.incomplete": {
        "title": "Unvollständiges JSON-LD für %(n)d Typ(en)",
        "fix": "Vervollständigen Sie die gelisteten "
               "Eigenschaften: ohne sie ist der Typ nicht für "
               "Rich Results geeignet.",
    },
    "sd.check.faq": {
        "title": "%(n)d unvollständige FAQPage-Frage(n)",
        "detail": "Jedes mainEntity-Element erfordert eine "
                  "Question mit name und eine acceptedAnswer "
                  "mit text.",
        "fix": "Vervollständigen Sie die Frage-Antwort-Paare im "
               "Markup.",
    },
    "sd.check.offers": {
        "title": "%(n)d Problem(e) bei den Angebotspreisen",
        "fix": "In price nur die Zahl mit Dezimalpunkt (keine "
               "Währungssymbole); die Währung in priceCurrency "
               "(ISO-4217-Code, z. B. EUR).",
    },
    "sd.check.product": {
        "title": "%(n)d Product ohne Angebote oder "
                 "Bewertungen",
        "detail": "Ein Product ohne offers, review und "
                  "aggregateRating ist nicht für "
                  "Produkt-Rich-Results geeignet.",
        "fix": "Ergänzen Sie mindestens offers (mit price und "
               "priceCurrency) oder review/aggregateRating.",
    },
    "sd.check.rating": {
        "title": "%(n)d inkonsistente Bewertung(en)",
        "fix": "ratingValue innerhalb der deklarierten Skala "
               "(Standard 1-5) und die Bewertungszahl in "
               "reviewCount oder ratingCount.",
    },
    "sd.check.dates": {
        "title": "%(n)d Datum/Daten nicht im ISO-8601-Format",
        "detail": "%(list)s.",
        "fix": "Verwenden Sie JJJJ-MM-TT, mit optionaler "
               "Uhrzeit nach dem T (z. B. "
               "2026-08-03T09:30:00+02:00).",
    },
    "sd.check.urls": {
        "title": "%(n)d nicht absolute Medien-URLs im Markup",
        "detail": "%(list)s.",
        "fix": "image, logo, thumbnailUrl, contentUrl und "
               "embedUrl erfordern vollständige http(s)-URLs.",
    },
    "sd.check.ok": {
        "title": "Konsistentes Schema.org-Markup (%(n)d Typen "
                 "geprüft)",
        "detail": "Geprüft: %(types)s.",
    },
    "rrf.not_runnable": {
        "title": "RRF-Simulation nicht ausführbar",
        "detail": "Mindestens ein Chunk und eine Anfrage sind "
                  "nötig.",
    },
    "rrf.consensus.low": {
        "title": "Durchschnittlicher Konsens zwischen den "
                 "Listen: %(avg).1f/%(top_n)d (%(pct).0f%%)",
        "detail": "Die beiden Listen zeigen auf verschiedene "
                  "Passagen: kein Dokument sammelt Punkte auf "
                  "beiden Achsen. In der RRF-Formel summiert "
                  "ein Dokument, das in beiden Listen steht, "
                  "zwei Summanden 1/(k+Rang) und schlägt eines, "
                  "das nur eine Liste dominiert. Konsens je "
                  "Anfrage: %(per_query)s.",
        "fix": "Optimieren Sie dieselben Passagen auf beiden "
               "Achsen: explizite Begriffe (BM25) und "
               "vollständige Erklärung (vektoriell).",
        "example": "Vorher (nur lexikalisch): \"Lymphdrainage. "
                   "Rufen Sie an für Infos.\"\nNachher (beide "
                   "Achsen): \"Die manuelle Lymphdrainage ist "
                   "eine sanfte Massage,\ndie den Lymphfluss "
                   "erleichtert: eine Sitzung dauert 45 "
                   "Minuten,\nder typische Zyklus umfasst 5 bis "
                   "10 Termine.\"",
    },
    "rrf.consensus.mid": {
        "title": "Durchschnittlicher Konsens zwischen den "
                 "Listen: %(avg).1f/%(top_n)d (%(pct).0f%%)",
        "detail": "Teilweiser Konsens zwischen den beiden "
                  "Retrievern. In der RRF-Formel summiert ein "
                  "Dokument, das in beiden Listen steht, zwei "
                  "Summanden 1/(k+Rang) und schlägt eines, das "
                  "nur eine Liste dominiert. Konsens je "
                  "Anfrage: %(per_query)s.",
        "fix": "Optimieren Sie dieselben Passagen auf beiden "
               "Achsen: explizite Begriffe (BM25) und "
               "vollständige Erklärung (vektoriell).",
    },
    "rrf.consensus.good": {
        "title": "Durchschnittlicher Konsens zwischen den "
                 "Listen: %(avg).1f/%(top_n)d (%(pct).0f%%)",
        "detail": "Gute Überschneidung zwischen lexikalischem "
                  "und vektoriellem Retrieval. In der "
                  "RRF-Formel summiert ein Dokument, das in "
                  "beiden Listen steht, zwei Summanden "
                  "1/(k+Rang) und schlägt eines, das nur eine "
                  "Liste dominiert. Konsens je Anfrage: "
                  "%(per_query)s.",
    },
    "rrf.uncovered": {
        "title": "%(n)d Anfragen ganz ohne Ergebnis",
        "detail": "Kein Chunk der Website antwortet: "
                  "%(queries)s.",
        "fix": "Erstellen Sie Inhalte für genau diese "
               "Intentionen.",
        "example": "Für jede unabgedeckte Anfrage ein "
                   "Abschnitt mit einer Überschrift gleich der "
                   "Frage:\n<h2>Was kostet die Lymphdrainage?"
                   "</h2>\n<p>Eine Sitzung kostet im Schnitt "
                   "40-80 Euro, je nach Dauer und behandelter "
                   "Zone.</p>",
    },
    "rrf.covered": {
        "title": "Alle %(n)d Anfragen finden mindestens eine "
                 "Passage",
        "detail": "Geprüfte Anfragen: %(queries)s.",
    },
    "rrf.comp.empty": {
        "title": "Wettbewerber %(host)s ohne abrufbaren Inhalt",
        "detail": "Keine analysierbare Seite: der Vergleich "
                  "führt ihn mit 0 Passagen.",
    },
    "rrf.comp.not_runnable": {
        "title": "Wettbewerbsvergleich nicht ausführbar",
        "detail": "Mindestens ein Chunk und eine Anfrage sind "
                  "nötig.",
    },
    "rrf.share.low": {
        "title": "Share of Voice: %(pct).0f%% der ersten "
                 "%(top_n)d fusionierten Plätze (Parität "
                 "%(parity).0f%%)",
        "detail": "Wettbewerber besetzen die Plätze, die Sie "
                  "bräuchten: bei Ihren eigenen Themen werden "
                  "Sie selten abgerufen. Aufteilung: "
                  "%(breakdown)s.",
        "fix": "Stärken Sie die Passagen zu den Anfragen, bei "
               "denen die Wettbewerber Sie schlagen: dieselben "
               "expliziten Begriffe, vollständige Antwort.",
    },
    "rrf.share.mid": {
        "title": "Share of Voice: %(pct).0f%% der ersten "
                 "%(top_n)d fusionierten Plätze (Parität "
                 "%(parity).0f%%)",
        "detail": "Sie liegen unter der Parität: bei Ihren "
                  "Themen werden die Wettbewerber häufiger "
                  "abgerufen als Sie. Aufteilung: "
                  "%(breakdown)s.",
        "fix": "Stärken Sie die Passagen zu den Anfragen, bei "
               "denen die Wettbewerber Sie schlagen: dieselben "
               "expliziten Begriffe, vollständige Antwort.",
    },
    "rrf.share.good": {
        "title": "Share of Voice: %(pct).0f%% der ersten "
                 "%(top_n)d fusionierten Plätze (Parität "
                 "%(parity).0f%%)",
        "detail": "Sie behaupten sich bei Ihren Themen gegen "
                  "die Wettbewerber. Aufteilung: "
                  "%(breakdown)s.",
    },
    "rrf.comp.lost": {
        "title": "%(n)d von %(total)d Anfragen komplett an die "
                 "Wettbewerber verloren",
        "detail": "Keine Ihrer Passagen unter den ersten "
                  "%(top_n)d für: %(queries)s.",
        "fix": "Erstellen oder überarbeiten Sie Inhalte für "
               "genau diese Intentionen.",
    },
    "rrf.comp.present": {
        "title": "Unter den ersten %(top_n)d bei allen %(n)d "
                 "Anfragen vertreten",
        "detail": "Vergleichsanfragen: %(queries)s.",
    },
    "tech.robots.own": {
        "title": "Website als eigene deklariert",
        "detail": "Die Disallow-Regeln der robots.txt werden "
                  "auf die geprüfte Website nicht angewandt "
                  "(--own-site); für etwaige Wettbewerber "
                  "gelten sie weiterhin.",
    },
    "tech.robots.forced": {
        "title": "Disallow-Regeln der robots.txt auf "
                 "ausdrücklichen Wunsch ignoriert",
        "detail": "Das Crawlen über die Disallow-Regeln hinaus "
                  "wurde mit --ignore-robots %(ack)s aktiviert: "
                  "die Verantwortung für den Crawl hat der "
                  "Nutzer ausdrücklich übernommen.",
    },
    "tech.robots.excluded": {
        "title": "%(n)d URLs aus Respekt vor der robots.txt "
                 "ausgeschlossen",
        "detail": "An den Agent %(agent)s gerichtete "
                  "Disallow-Regeln werden respektiert "
                  "(Standardverhalten): %(urls)s. Verwenden Sie "
                  "--own-site, wenn die Website Ihnen gehört.",
    },
    "tech.render.done": {
        "title": "%(n)d Seite(n) mit JavaScript-Rendering "
                 "analysiert",
        "detail": "Modus --render %(mode)s: der Inhalt stammt "
                  "aus dem in einem Headless-Browser "
                  "gerenderten DOM; HTTP-Status, "
                  "Weiterleitungen und Zeiten bleiben die der "
                  "ursprünglichen Antwort.",
    },
    "tech.render.failed": {
        "title": "Rendering fehlgeschlagen für %(n)d Seite(n)",
        "detail": "Für diese Seiten wurde das statische HTML "
                  "analysiert.",
        "fix": "Versuchen Sie es erneut oder erhöhen Sie den "
               "Timeout, wenn die Website langsam ist.",
    },
    "tech.pages.duplicates": {
        "title": "%(n)d URLs liefern identischen Inhalt",
        "detail": "Derselbe Text ist über mehrere Adressen "
                  "erreichbar: %(urls)s. Duplikate fügen der "
                  "RRF-Summe keine Summanden hinzu, verwässern "
                  "die Signale und verschwenden Crawl-Budget.",
        "fix": "Wählen Sie eine kanonische URL und leiten Sie "
               "die anderen per 301 um.",
    },
}

_FINDINGS_ES: Dict[str, Dict[str, str]] = {
    "tech.robots.missing": {
        "title": "robots.txt no accesible",
        "detail": "La petición a %(url)s falló o no devolvió "
                  "200.",
        "fix": "Publique un robots.txt que declare el sitemap.",
    },
    "tech.robots.present": {
        "title": "robots.txt presente",
        "detail": "%(n)d líneas.",
    },
    "tech.robots.ai_blocked": {
        "title": "Rastreadores de IA bloqueados: %(agents)s",
        "detail": "Estos agentes no pueden acceder a la página "
                  "de inicio. Si están bloqueados, usted no "
                  "entra en ninguna lista de recuperación y el "
                  "RRF no tiene nada que fusionar.",
        "fix": "Elimine las reglas Disallow para los agentes "
               "por los que quiere ser citado.",
        "example": "# robots.txt - desbloquear los agentes IA\n"
                   "User-agent: GPTBot\nDisallow:\n\n"
                   "User-agent: ClaudeBot\nDisallow:\n\n"
                   "User-agent: PerplexityBot\nDisallow:",
    },
    "tech.robots.ai_allowed": {
        "title": "Rastreadores de IA permitidos",
        "detail": "Verificados: %(agents)s.",
    },
    "tech.robots.sitemap_ok": {
        "title": "Sitemap declarado en el robots.txt",
        "detail": "%(urls)s",
    },
    "tech.robots.sitemap_missing": {
        "title": "Ningún sitemap declarado en el robots.txt",
        "fix": "Añada la línea "
               "'Sitemap: https://.../sitemap.xml'.",
        "example": "# al final del robots.txt\n"
                   "Sitemap: https://esempio.it/sitemap.xml",
    },
    "tech.llms.present": {
        "title": "llms.txt presente",
        "detail": "%(n)d líneas.",
    },
    "tech.llms.missing": {
        "title": "llms.txt ausente",
        "detail": "Estándar emergente (llmstxt.org): un índice "
                  "Markdown de los contenidos clave destinado a "
                  "los agentes de IA.",
        "fix": "Considere publicar /llms.txt con sus contenidos "
               "clave.",
    },
    "tech.links.orphans": {
        "title": "%(n)d página(s) sin enlaces internos "
                 "entrantes (huérfanas)",
        "detail": "Accesibles solo desde el sitemap: %(urls)s. "
                  "Una página a la que nadie enlaza se rastrea "
                  "menos y pesa menos.",
        "fix": "Enlácelas desde las páginas relacionadas "
               "(cuerpo del texto, menú o pie de página).",
        "example": "Desde la página relacionada:\n"
                   "<a href=\"/servizio-collegato/\">nombre "
                   "descriptivo del servicio</a>",
    },
    "tech.links.no_orphans": {
        "title": "Cada página tiene enlaces internos entrantes",
    },
    "tech.links.deep": {
        "title": "%(n)d página(s) a más de 3 clics de la "
                 "página de inicio",
        "detail": "%(urls)s.",
        "fix": "Acorte los recorridos: las páginas profundas se "
               "rastrean y ponderan menos.",
    },
    "tech.links.generic_anchors": {
        "title": "%(n)d anclas genéricas en los enlaces "
                 "internos",
        "detail": "Textos como \"haga clic aquí\" o \"leer "
                  "más\" no dicen nada del contenido de "
                  "destino.",
        "fix": "Use anclas descriptivas con los términos de la "
               "página de destino.",
    },
    "tech.redirect.http_left": {
        "title": "%(n)d URL internas todavía en http",
        "detail": "Redirigidas a la versión https: %(urls)s. "
                  "Cada salto malgasta presupuesto de rastreo y "
                  "diluye las señales.",
        "fix": "Actualice el sitemap y los enlaces internos a "
               "las URL https finales.",
        "example": "<!-- antes   --> <a href=\"http://esempio.it/"
                   "servizio/\">\n<!-- después --> "
                   "<a href=\"https://esempio.it/servizio/\">",
    },
    "tech.redirect.www_mixed": {
        "title": "%(n)d URL con host www/no-www mezclado",
        "detail": "Redirigidas al host canónico: %(urls)s.",
        "fix": "Use un solo host (con o sin www) en el sitemap "
               "y los enlaces internos.",
    },
    "tech.redirect.moved": {
        "title": "%(n)d URL internas responden con una "
                 "redirección",
        "detail": "URL trasladadas: %(urls)s.",
        "fix": "Actualice el sitemap y los enlaces internos al "
               "destino final de las redirecciones.",
        "example": "En el sitemap y los enlaces internos use "
                   "directamente la URL de llegada:\n"
                   "<url><loc>https://"
                   "esempio.it/nuova-pagina/</loc></url>",
    },
    "tech.redirect.chains": {
        "title": "%(n)d URL con una cadena de redirecciones de "
                 "varios saltos",
        "detail": "%(urls)s.",
        "fix": "Haga que cada redirección apunte directamente "
               "al destino final (un solo salto).",
        "example": "# un solo salto, no una cadena\n"
                   "Redirect 301 /vecchia/ "
                   "https://esempio.it/nuova/\n"
                   "# NO: /vecchia/ -> /intermedia/ -> /nuova/",
    },
    "tech.redirect.none": {
        "title": "Ninguna redirección interna",
        "detail": "Cada URL analizada responde directamente.",
    },
    "tech.msft.noarchive": {
        "title": "%(n)d página(s) excluida(s) de Copilot "
                 "(noarchive)",
        "detail": "La meta noarchive excluye el contenido de "
                  "las respuestas de Bing Chat/Copilot y del "
                  "entrenamiento de los modelos de Microsoft "
                  "(la búsqueda clásica no se ve afectada): en "
                  "estas páginas la citabilidad en el canal "
                  "Microsoft es cero. %(urls)s",
        "fix": "Si la exclusión no es intencionada, elimine "
               "noarchive; para una presencia parcial (solo "
               "título, URL y fragmento) use nocache.",
    },
    "tech.msft.nocache": {
        "title": "%(n)d página(s) con presencia parcial en "
                 "Copilot (nocache)",
        "detail": "Con nocache, Bing Chat/Copilot muestra solo "
                  "la URL, el título y el fragmento de la "
                  "página y usa solo esos elementos para el "
                  "entrenamiento de Microsoft. %(urls)s",
        "fix": "Un opt-out parcial legítimo: compruebe "
               "simplemente que sea intencionado. Para una "
               "citabilidad completa en Copilot elimine la "
               "meta.",
    },
    "tech.msft.no_optout": {
        "title": "Ningún opt-out de IA de Microsoft activo",
        "detail": "No existe un token de robots.txt dedicado a "
                  "la IA de Microsoft: el control pasa por las "
                  "metas noarchive/nocache, ausentes aquí. Sus "
                  "contenidos pueden por tanto usarse en las "
                  "respuestas de Copilot y el entrenamiento de "
                  "Microsoft; para el opt-out use noarchive "
                  "(total) o nocache (parcial).",
    },
    "tech.anchors.varied": {
        "title": "Perfil de anclas internas variado",
        "detail": "%(texts)d textos únicos sobre %(pairs)d "
                  "pares texto-destino (%(pct).0f%%; umbral de "
                  "práctica común: %(threshold).0f%%).",
    },
    "tech.anchors.repetitive": {
        "title": "Perfil de anclas internas repetitivo",
        "detail": "%(texts)d textos únicos sobre %(pairs)d "
                  "pares texto-destino (%(pct).0f%%, umbral de "
                  "práctica común %(threshold).0f%%): el mismo "
                  "texto lleva a destinos distintos y el lector "
                  "— humano o modelo — no puede prever adónde "
                  "va el enlace. %(examples)s",
        "fix": "Use anclas descriptivas, distintas por destino: "
               "el texto del enlace debe decir qué hay al otro "
               "lado.",
        "example": "Antes:   \"Leer más\" -> /servizi, \"Leer "
                   "más\" -> /prezzi\n"
                   "Después: \"Todos los servicios de drenaje "
                   "linfático\" -> /servizi, \"Precios de las "
                   "sesiones\" -> /prezzi",
    },
    "tech.meta.charset": {
        "title": "%(n)d página(s) sin charset declarado",
        "detail": "%(urls)s",
        "fix": "Declare la codificación al principio del "
               "<head>.",
    },
    "tech.meta.viewport": {
        "title": "%(n)d página(s) sin meta viewport",
        "detail": "Sin viewport, el renderizado móvil no está "
                  "declarado: %(urls)s",
        "fix": "Añada el viewport responsive.",
    },
    "tech.meta.og_missing": {
        "title": "%(n)d página(s) sin Open Graph",
        "detail": "Las vistas previas de los enlaces "
                  "compartidos (y de muchas respuestas de "
                  "asistentes) se construyen a partir de las "
                  "etiquetas og:*: sin ellas, quien pega el "
                  "enlace decide el título y la imagen. "
                  "%(urls)s",
        "fix": "Añada al menos la tríada og:title, "
               "og:description, og:image.",
    },
    "tech.meta.og_partial": {
        "title": "Open Graph incompleto en %(n)d página(s)",
        "detail": "%(urls)s",
        "fix": "Complete la tríada og:title, og:description, "
               "og:image.",
    },
    "tech.meta.ok": {
        "title": "Metas básicas en orden",
        "detail": "charset, viewport y Open Graph completos en "
                  "las %(n)d páginas analizadas.",
    },
    "tech.https.missing": {
        "title": "Sitio sin HTTPS",
        "fix": "Active un certificado TLS y redirija todo a "
               "HTTPS.",
    },
    "tech.https.ok": {
        "title": "HTTPS activo",
    },
    "tech.pages.broken": {
        "title": "%(n)d URL inaccesibles o con error",
        "detail": "%(urls)s",
        "fix": "Corrija las URL con error o quítelas del "
               "sitemap.",
    },
    "tech.pages.soft404": {
        "title": "%(n)d posibles soft-404 (200 con contenido "
                 "\"página no encontrada\")",
        "detail": "Responden 200 pero el contenido dice que la "
                  "página no existe: %(urls)s. Entran en el "
                  "índice como páginas vacías y diluyen las "
                  "señales del sitio.",
        "fix": "Haga que las URL inexistentes respondan 404 (o "
               "410) y quite las vacías del sitemap.",
        "example": "La página inexistente debe responder con "
                   "estado 404, no 200:\n# Apache (.htaccess)\n"
                   "ErrorDocument 404 /404.html\n"
                   "# nada de redirección al inicio en lugar "
                   "del 404",
    },
    "tech.pages.none": {
        "title": "Ninguna página analizable",
        "detail": "Ninguna URL devolvió HTML válido: el sitio "
                  "es inaccesible, bloquea el user-agent de la "
                  "herramienta o solo responde con JavaScript. "
                  "La auditoría de contenido no se realizó.",
        "fix": "Compruebe que el sitio responde y no filtra los "
               "rastreadores.",
    },
    "tech.pages.single": {
        "title": "Superficie indexable mínima (1 página)",
        "detail": "Con un solo documento, la suma RRF no tiene "
                  "sumandos: no hay pasajes distintos que hacer "
                  "emerger.",
        "fix": "Cree páginas autónomas para cada "
               "tema/servicio.",
    },
    "tech.pages.few": {
        "title": "Pocas páginas indexables (%(n)d)",
        "fix": "Amplíe la superficie: una página por "
               "intención.",
    },
    "tech.pages.ok": {
        "title": "%(n)d páginas indexables analizadas",
        "detail": "Primeras páginas: %(urls)s.",
    },
    "tech.sitemap.missing": {
        "title": "Sitemap XML ausente o ilegible",
        "detail": "URL descubiertas rastreando los enlaces "
                  "internos.",
        "fix": "Publique un sitemap XML y declárelo en el "
               "robots.txt.",
    },
    "tech.pages.placeholder": {
        "title": "%(n)d página(s) de relleno indexable(s)",
        "detail": "Detectadas: %(urls)s. Son contenidos por "
                  "defecto del CMS: puro ruido en el índice y "
                  "señal de un sitio inacabado.",
        "fix": "Elimínelas, o ponga noindex y quítelas del "
               "sitemap.",
    },
    "tech.pages.noindex": {
        "title": "%(n)d página(s) con meta robots noindex",
        "detail": "%(urls)s",
        "fix": "Compruebe que la exclusión sea intencionada.",
        "example": "Si la página debe indexarse, quite la meta "
                   "o use:\n<meta name=\"robots\" "
                   "content=\"index, follow\">",
    },
    "tech.canonical.missing": {
        "title": "%(n)d página(s) sin canonical",
        "detail": "%(urls)s",
        "fix": "Declare <link rel=\"canonical\"> en cada "
               "página.",
    },
    "tech.canonical.ok": {
        "title": "Canonical presentes",
        "detail": "Declarados en las %(n)d páginas analizadas.",
    },
    "tech.lang.missing": {
        "title": "%(n)d página(s) sin atributo lang",
        "fix": "Establezca <html lang=\"it\">: ayuda a la "
               "elección del modelo de lengua durante el "
               "análisis.",
    },
    "tech.js.heavy": {
        "title": "%(n)d página(s) con poco texto y mucho "
                 "JavaScript",
        "detail": "El contenido puede renderizarse en el "
                  "cliente y no ser visto por los "
                  "rastreadores.",
        "fix": "Active el renderizado en el servidor o el "
               "prerenderizado.",
    },
    "tech.js.rendered": {
        "title": "%(n)d página(s) con poco texto y mucho "
                 "JavaScript",
        "detail": "El contenido se analizó con renderizado "
                  "JavaScript, pero los rastreadores que no "
                  "ejecutan JavaScript (la mayoría de los "
                  "rastreadores de IA) siguen sin verlo.",
        "fix": "Active el renderizado en el servidor o el "
               "prerenderizado.",
    },
    "tech.js.ok": {
        "title": "Contenido presente en el HTML inicial",
    },
    "tech.slow": {
        "title": "%(n)d página(s) que responden en más de 2 s",
        "detail": "La más lenta: %(worst).2f s.",
        "fix": "Optimice la caché y el TTFB.",
    },
    "tech.hreflang.missing": {
        "title": "Sitio multilingüe sin hreflang",
        "detail": "Idiomas detectados: %(langs)s.",
        "fix": "Declare hreflang recíprocos entre las "
               "versiones.",
    },
    "tech.hreflang.na": {
        "title": "Sitio monolingüe: hreflang no necesario",
    },
    "lex.clickbait.found": {
        "title": "%(n)d títulos o encabezados con fórmulas "
                 "clickbait",
        "detail": "Las fórmulas sensacionalistas y los signos "
                  "de exclamación múltiples atraen el clic pero "
                  "no responden a nada: los motores generativos "
                  "seleccionan títulos informativos. "
                  "%(examples)s",
        "fix": "Reescriba en estilo informativo: el beneficio o "
               "la respuesta en el título, sin hipérboles.",
        "example": "Antes:   \"¡¡No creerá lo que hace el "
                   "drenaje!!\"\nDespués: \"Drenaje linfático: "
                   "beneficios, duración y coste de una "
                   "sesión\"",
    },
    "lex.clickbait.none": {
        "title": "Ninguna fórmula clickbait en títulos y "
                 "encabezados",
        "detail": "Títulos de estilo informativo en las %(n)d "
                  "páginas analizadas.",
    },
    "lex.title.missing": {
        "title": "%(n)d página(s) sin <title>",
        "fix": "El title es la señal léxica de mayor peso.",
    },
    "lex.title.bad": {
        "title": "%(n)d title no optimizados",
        "detail": "Ejemplos: %(examples)s",
        "fix": "Un title único, de %(min)d-%(max)d caracteres, con "
               "los términos de búsqueda reales; evite el nombre "
               "de dominio como título.",
        "example": "<title>Drenaggio linfatico manuale a Parma "
                   "| Centro Esempio</title>\n"
                   "(52 caracteres: servicio + territorio + "
                   "marca)",
    },
    "lex.title.dup": {
        "title": "%(n)d title duplicados entre páginas",
        "detail": "%(examples)s",
        "fix": "Cada página debe tener un title distinto.",
    },
    "lex.title.ok": {
        "title": "Title bien construidos",
    },
    "lex.desc.missing": {
        "title": "%(n)d página(s) sin meta description",
        "detail": "%(urls)s",
        "fix": "Redacte %(min)d-%(max)d caracteres con el servicio "
               "y el territorio.",
    },
    "lex.desc.short": {
        "title": "%(n)d meta descriptions demasiado cortas",
        "detail": "Ejemplos: %(examples)s",
        "fix": "Una description que solo repite el nombre de la "
               "empresa no aporta ninguna señal.",
    },
    "lex.desc.long": {
        "title": "%(n)d meta descriptions por encima de "
                 "%(max)d caracteres",
    },
    "lex.desc.ok": {
        "title": "Meta descriptions presentes y de longitud "
                 "adecuada",
    },
    "lex.h1.missing": {
        "title": "%(n)d página(s) sin H1",
        "detail": "%(urls)s",
        "fix": "Un solo H1 por página, con los términos "
               "principales.",
    },
    "lex.h1.multi": {
        "title": "%(n)d página(s) con varios H1",
    },
    "lex.h1.ok": {
        "title": "Estructura H1 correcta",
    },
    "lex.words.thin": {
        "title": "%(n)d página(s) por debajo de %(min)d "
                 "palabras",
        "detail": "Media del sitio: %(avg)d palabras. Con tan "
                  "poco texto, los términos útiles nunca "
                  "alcanzan una frecuencia que BM25 pueda "
                  "premiar.",
        "fix": "Lleve las páginas clave hacia %(target)d+ "
               "palabras de contenido informativo, no "
               "promocional.",
        "example": "Estructura típica de una página de "
                   "servicio:\n<h2>¿Qué es ...?</h2> <h2>Cómo "
                   "se desarrolla una sesión</h2>\n<h2>Cuándo "
                   "es necesaria</h2> <h2>Cuánto cuesta</h2> "
                   "<h2>FAQ</h2>",
    },
    "lex.words.ok": {
        "title": "Volumen de texto adecuado",
        "detail": "Media: %(avg)d palabras por página.",
    },
    "lex.acronyms.bare": {
        "title": "Siglas usadas sin su forma desarrollada",
        "detail": "Sin desarrollar: %(list)s.",
        "fix": "Escriba 'SIGLA (forma desarrollada)' al menos "
               "en la primera aparición: cubre ambas "
               "formulaciones de búsqueda.",
    },
    "lex.acronyms.ok": {
        "title": "Siglas acompañadas de su forma desarrollada",
        "detail": "%(list)s",
    },
    "lex.slug.bad": {
        "title": "%(n)d slugs poco descriptivos",
        "detail": "%(slugs)s",
        "fix": "Use slugs temáticos con guiones.",
    },
    "lex.slug.ok": {
        "title": "Slugs temáticos y legibles",
    },
    "lex.alt.partial": {
        "title": "Atributos alt incompletos (%(with_alt)d/"
                 "%(total)d)",
        "fix": "El alt es texto indexable además de "
               "accesibilidad.",
    },
    "lex.alt.ok": {
        "title": "Atributos alt presentes (%(with_alt)d/"
                 "%(total)d)",
    },
    "sem.extract.ok": {
        "title": "Buena extraibilidad directa",
        "detail": "%(direct)d párrafos de %(total)d se abren "
                  "con una respuesta explícita en "
                  "%(min)d-%(max)d palabras (%(pct).0f%% frente "
                  "a un umbral de práctica común del "
                  "%(threshold).0f%%): son los pasajes que un "
                  "asistente puede citar tal cual.",
    },
    "sem.extract.low": {
        "title": "Pocos párrafos de respuesta directa",
        "detail": "%(direct)d párrafos de %(total)d se abren "
                  "con una respuesta explícita en "
                  "%(min)d-%(max)d palabras (%(pct).0f%% frente "
                  "a un umbral de práctica común del "
                  "%(threshold).0f%%): son los pasajes que un "
                  "asistente puede citar tal cual.",
        "fix": "Reescriba los párrafos clave abriendo con la "
               "respuesta (\"X es ...\", \"Sí, ...\", \"En "
               "resumen ...\") y manténgalos entre %(min)d y "
               "%(max)d palabras.",
        "example": "Antes:   \"En el panorama actual del "
                   "bienestar, muchos se preguntan qué "
                   "camino...\"\nDespués: \"El drenaje "
                   "linfático es un masaje suave que facilita "
                   "el flujo de la linfa: una sesión dura 45 "
                   "minutos y cuesta 40-80 euros.\"",
    },
    "sem.filler.saturated": {
        "title": "%(n)d página(s) saturada(s) de fórmulas de "
                 "marketing",
        "detail": "El relleno ocupa espacio sin decir nada "
                  "extraíble (umbral de práctica común: al "
                  "menos %(min)d fórmulas y una cada 100 "
                  "palabras). %(examples)s",
        "fix": "Sustituya las fórmulas genéricas por "
               "información verificable: cifras, duraciones, "
               "precios, procedimientos.",
        "example": "Antes:   \"Somos líderes del mercado, "
                   "calidad y profesionalidad a su servicio.\"\n"
                   "Después: \"Desde 2012 hemos seguido a más "
                   "de 400 pacientes posoperatorios; la primera "
                   "evaluación es gratuita y dura 30 minutos.\"",
    },
    "sem.filler.ok": {
        "title": "Relleno de marketing bajo control",
        "detail": "%(n)d fórmulas genéricas en todo el sitio: "
                  "el texto útil domina.",
    },
    "sem.lifecycle.ok": {
        "title": "Ciclo de vida del tema cubierto (%(n)d de 6)",
        "detail": "Secciones encontradas en los encabezados: "
                  "%(found)s.",
    },
    "sem.lifecycle.partial": {
        "title": "Ciclo de vida del tema incompleto (%(n)d de "
                 "6)",
        "detail": "Un tratamiento completo cubre definición, "
                  "historia, casos de uso, límites, FAQ y "
                  "perspectivas: es el contenido que los "
                  "motores generativos pueden citar para cada "
                  "ángulo de una pregunta. %(found)s Faltan: "
                  "%(missing)s.",
        "fix": "Añada las secciones que faltan con encabezados "
               "explícitos (pueden repartirse en varias "
               "páginas).",
    },
    "sem.fresh.ok": {
        "title": "Contenidos actualizados recientemente",
        "detail": "Actualización declarada más reciente: "
                  "%(date)s en %(url)s (hace %(days)d días).",
    },
    "sem.fresh.stale": {
        "title": "Contenidos sin tocar desde hace más de un "
                 "año",
        "detail": "La actualización declarada más reciente es "
                  "del %(date)s (hace %(days)d días). Los "
                  "motores generativos prefieren fuentes "
                  "mantenidas: una fecha congelada señala un "
                  "contenido quizá obsoleto. Páginas más "
                  "antiguas: %(stale)s.",
        "fix": "Revise los contenidos clave y declare la "
               "actualización con article:modified_time o "
               "dateModified en el JSON-LD.",
    },
    "sem.fresh.very_stale": {
        "title": "Contenidos sin tocar desde hace más de dos "
                 "años",
        "detail": "La actualización declarada más reciente es "
                  "del %(date)s (hace %(days)d días). Los "
                  "motores generativos prefieren fuentes "
                  "mantenidas: una fecha congelada señala un "
                  "contenido quizá obsoleto. Páginas más "
                  "antiguas: %(stale)s.",
        "fix": "Revise los contenidos clave y declare la "
               "actualización con article:modified_time o "
               "dateModified en el JSON-LD.",
    },
    "sem.refs.ok": {
        "title": "Referencias a fuentes presentes",
        "detail": "%(context)s (umbral de práctica común: una "
                  "sección de fuentes o al menos %(threshold)d "
                  "citas).",
    },
    "sem.refs.missing": {
        "title": "Ninguna referencia a fuentes externas",
        "detail": "%(context)s. Citar fuentes refuerza las "
                  "señales E-E-A-T y da a los asistentes de IA "
                  "algo que verificar: un contenido "
                  "referenciado es más citable.",
        "fix": "Añada una sección \"Fuentes\" con enlaces a "
               "directrices, estudios o documentación oficial "
               "(o citas en el texto).",
    },
    "sem.chunks.none": {
        "title": "Ningún chunk extraíble",
        "detail": "El sitio no ofrece pasajes de texto "
                  "indexables.",
        "fix": "Redacte párrafos discursivos de al menos 40-50 "
               "palabras.",
    },
    "sem.chunks.ok": {
        "title": "%(chunks)d chunks indexables en %(pages)d "
                 "páginas",
        "detail": "Cada chunk es una ocasión de aparecer en "
                  "las listas: en la suma RRF, el número de "
                  "pasajes pertinentes es el verdadero "
                  "multiplicador.",
    },
    "sem.chunks.few": {
        "title": "%(chunks)d chunks indexables en %(pages)d "
                 "páginas",
        "detail": "Cada chunk es una ocasión de aparecer en "
                  "las listas: en la suma RRF, el número de "
                  "pasajes pertinentes es el verdadero "
                  "multiplicador.",
        "fix": "Aumente el número de pasajes temáticos "
               "autónomos.",
    },
    "sem.anaphora.high": {
        "title": "El %(pct).0f%% de los chunks no son "
                 "autónomos",
        "detail": "Se abren con una referencia anafórica "
                  "(este, tal, aquel...): extraídos por sí "
                  "solos no responden a nada. Ejemplos: "
                  "%(examples)s.",
        "fix": "Reescriba las aperturas nombrando "
               "explícitamente el sujeto.",
        "example": "Antes:   \"Este tratamiento está indicado "
                   "tras una operación.\"\nDespués: \"El "
                   "drenaje linfático manual está indicado "
                   "tras una operación.\"",
    },
    "sem.anaphora.ok": {
        "title": "Chunks en gran parte autónomos (%(pct).0f%% "
                 "anafóricos)",
    },
    "sem.questions.few": {
        "title": "Casi ningún encabezado en forma de pregunta "
                 "(%(n)d de %(total)d)",
        "detail": "Es el formato que los motores de IA citan "
                  "más a menudo: una pregunta explícita seguida "
                  "de una respuesta directa.",
        "fix": "Añada encabezados como \"¿Qué es X?\", \"¿Cómo "
               "funciona X?\", \"¿Cuánto cuesta X?\" con una "
               "respuesta clara de 2-3 líneas.",
    },
    "sem.questions.ok": {
        "title": "%(n)d encabezados en forma de pregunta "
                 "(%(pct).0f%%)",
        "detail": "Ejemplos: %(examples)s.",
    },
    "sem.faq.ok": {
        "title": "Sección FAQ detectada",
        "detail": "Detectada en %(url)s.",
    },
    "sem.faq.missing": {
        "title": "Ninguna sección FAQ",
        "detail": "Las FAQ alinean un chunk con una intención "
                  "precisa y alimentan ambos ejes a la vez.",
        "fix": "Añada FAQ por página, marcadas con JSON-LD "
               "FAQPage.",
    },
    "sem.defs.low": {
        "title": "Contenido pobre en definiciones (%(pct).0f%% "
                 "de los chunks)",
        "detail": "Sin pasajes que expliquen *qué* es algo, "
                  "los embeddings quedan lejos de las consultas "
                  "informacionales.",
        "fix": "Para cada tema añada: qué es / cómo funciona / "
               "cuándo es necesario / un ejemplo.",
    },
    "sem.defs.ok": {
        "title": "Pasajes definitorios presentes (%(pct).0f%% "
                 "de los chunks)",
    },
    "sem.examples.few": {
        "title": "Casi ningún ejemplo concreto",
        "fix": "Ejemplos y casos prácticos son los contenidos "
               "de mayor densidad semántica.",
    },
    "sem.examples.ok": {
        "title": "%(n)d chunks con ejemplos concretos",
    },
    "sem.vocab.narrow": {
        "title": "Vocabulario estrecho (%(n)d términos "
                 "distintos)",
        "detail": "Poca variedad léxica significa cobertura "
                  "semántica limitada: intercepta pocas "
                  "reformulaciones de la misma pregunta.",
        "fix": "Amplíe los temas tratados y las formulaciones "
               "empleadas.",
    },
    "sem.vocab.ok": {
        "title": "Vocabulario amplio (%(n)d términos "
                 "distintos)",
    },
    "sem.eeat.author.ok": {
        "title": "E-E-A-T: autor de los contenidos declarado",
    },
    "sem.eeat.author.missing": {
        "title": "E-E-A-T: ningún autor declarado",
        "fix": "Añada la meta author o la propiedad author en "
               "el JSON-LD: los motores de IA ponderan quién "
               "firma el contenido.",
    },
    "sem.eeat.dates.ok": {
        "title": "E-E-A-T: fechas de publicación/actualización "
                 "presentes",
    },
    "sem.eeat.dates.missing": {
        "title": "E-E-A-T: ninguna fecha de publicación o "
                 "actualización",
        "fix": "Exponga article:published_time/modified_time o "
               "datePublished/dateModified en el JSON-LD.",
    },
    "sem.eeat.about.ok": {
        "title": "E-E-A-T: página \"quiénes somos\" presente",
    },
    "sem.eeat.about.missing": {
        "title": "E-E-A-T: ninguna página \"quiénes somos\" "
                 "detectada",
        "fix": "Una página que presenta a las personas y las "
               "competencias es la señal de experiencia más "
               "directa.",
        "example": "Cree /chi-siamo/ con: quién cura los "
                   "contenidos, títulos y formación,\ndesde "
                   "cuándo, fotos reales. Enlácela desde el pie "
                   "de cada página.",
    },
    "sem.eeat.contact.ok": {
        "title": "E-E-A-T: contactos verificables presentes",
    },
    "sem.eeat.contact.missing": {
        "title": "E-E-A-T: ningún contacto verificable "
                 "detectado",
        "fix": "Exponga teléfono y correo (enlaces "
               "tel:/mailto:) o una página de contacto.",
    },
    "sd.semantic.poor": {
        "title": "%(n)d página(s) sin marcado semántico",
        "detail": "Menos de %(min)d tipos de etiquetas de "
                  "seccionado (article, section, main, "
                  "figure...): los chunkers de los motores "
                  "generativos tienen menos asideros para "
                  "segmentar el contenido en bloques "
                  "coherentes. %(urls)s",
        "fix": "Envuelva el contenido principal en <main> y "
               "<article>, las secciones temáticas en <section> "
               "con su encabezado, imágenes y leyendas en "
               "<figure>.",
    },
    "sd.semantic.divitis": {
        "title": "%(n)d página(s) con exceso de <div> "
                 "(divitis)",
        "detail": "Más de la mitad de los elementos son <div> "
                  "genéricos: %(urls)s.",
        "fix": "Sustituya los <div> estructurales por las "
               "etiquetas semánticas equivalentes: el marcado "
               "se vuelve autodescriptivo.",
    },
    "sd.semantic.ok": {
        "title": "Marcado semántico en uso",
        "detail": "Las %(n)d páginas analizables usan etiquetas "
                  "de seccionado y mantienen los <div> por "
                  "debajo del %(max)d%% de los elementos.",
    },
    "sd.jsonld.none": {
        "title": "Ningún dato estructurado JSON-LD",
        "detail": "Sin marcado, la entidad no se reconoce y el "
                  "contenido no es apto para resultados "
                  "enriquecidos.",
        "fix": "Añada al menos Organization (o LocalBusiness), "
               "luego Service, FAQPage, BreadcrumbList, "
               "Article.",
    },
    "sd.jsonld.ok": {
        "title": "JSON-LD presente",
        "detail": "Tipos detectados: %(types)s.",
    },
    "sd.entity.missing": {
        "title": "Entidad principal no declarada",
        "fix": "Añada Organization o LocalBusiness con nombre, "
               "dirección, contactos e identificadores "
               "fiscales.",
    },
    "sd.entity.ok": {
        "title": "Entidad principal declarada",
    },
    "sd.type.faqpage": {
        "title": "Marcado FAQPage ausente",
        "detail": "Las FAQ marcadas son el formato que los "
                  "motores de IA más citan.",
        "fix": "Añada el tipo FAQPage donde sea pertinente.",
    },
    "sd.type.breadcrumblist": {
        "title": "Marcado BreadcrumbList ausente",
        "detail": "Aclara la jerarquía del sitio.",
        "fix": "Añada el tipo BreadcrumbList donde sea "
               "pertinente.",
    },
    "sd.type.website": {
        "title": "Marcado WebSite ausente",
        "detail": "Útil para la searchbox de los sitelinks.",
        "fix": "Añada el tipo WebSite donde sea pertinente.",
    },
    "sd.jsonld.partial": {
        "title": "JSON-LD en solo %(covered)d páginas de "
                 "%(total)d",
        "fix": "Extienda el marcado a todas las páginas "
               "pertinentes.",
    },
    "sd.check.incomplete": {
        "title": "JSON-LD incompleto para %(n)d tipo(s)",
        "fix": "Complete las propiedades listadas: sin ellas, "
               "el tipo no es apto para resultados "
               "enriquecidos.",
    },
    "sd.check.faq": {
        "title": "%(n)d pregunta(s) FAQPage incompleta(s)",
        "detail": "Cada elemento de mainEntity requiere una "
                  "Question con name y una acceptedAnswer con "
                  "text.",
        "fix": "Complete los pares pregunta/respuesta en el "
               "marcado.",
    },
    "sd.check.offers": {
        "title": "%(n)d problema(s) en los precios de las "
                 "ofertas",
        "fix": "En price solo el número con punto decimal (sin "
               "símbolos de moneda); la divisa en priceCurrency "
               "(código ISO 4217, p. ej. EUR).",
    },
    "sd.check.product": {
        "title": "%(n)d Product sin ofertas ni reseñas",
        "detail": "Un Product sin offers, review ni "
                  "aggregateRating no es apto para resultados "
                  "enriquecidos de producto.",
        "fix": "Añada al menos offers (con price y "
               "priceCurrency) o review/aggregateRating.",
    },
    "sd.check.rating": {
        "title": "%(n)d valoración(es) incoherente(s)",
        "fix": "ratingValue dentro de la escala declarada (por "
               "defecto 1-5) y el número de reseñas en "
               "reviewCount o ratingCount.",
    },
    "sd.check.dates": {
        "title": "%(n)d fecha(s) fuera del formato ISO 8601",
        "detail": "%(list)s.",
        "fix": "Use AAAA-MM-DD, con la hora opcional tras la T "
               "(p. ej. 2026-08-03T09:30:00+02:00).",
    },
    "sd.check.urls": {
        "title": "%(n)d URL de medios no absolutas en el "
                 "marcado",
        "detail": "%(list)s.",
        "fix": "image, logo, thumbnailUrl, contentUrl y "
               "embedUrl requieren URL http(s) completas.",
    },
    "sd.check.ok": {
        "title": "Marcado Schema.org coherente (%(n)d tipos "
                 "verificados)",
        "detail": "Verificados: %(types)s.",
    },
    "rrf.not_runnable": {
        "title": "Simulación RRF no ejecutable",
        "detail": "Hacen falta al menos un chunk y una "
                  "consulta.",
    },
    "rrf.consensus.low": {
        "title": "Consenso medio entre las listas: "
                 "%(avg).1f/%(top_n)d (%(pct).0f%%)",
        "detail": "Las dos listas apuntan a pasajes distintos: "
                  "ningún documento acumula puntuación en ambos "
                  "ejes. En la fórmula RRF, un documento "
                  "presente en ambas listas suma dos sumandos "
                  "1/(k+rango) y vence a uno que domina una "
                  "sola lista. Consenso por consulta: "
                  "%(per_query)s.",
        "fix": "Optimice los mismos pasajes en ambos ejes: "
               "términos explícitos (BM25) y explicación "
               "completa (vectorial).",
        "example": "Antes (solo léxico): \"Drenaje linfático. "
                   "Llame para información.\"\nDespués (ambos "
                   "ejes): \"El drenaje linfático manual es un "
                   "masaje suave\nque facilita el flujo de la "
                   "linfa: una sesión dura 45 minutos\ny el "
                   "ciclo típico va de 5 a 10 sesiones.\"",
    },
    "rrf.consensus.mid": {
        "title": "Consenso medio entre las listas: "
                 "%(avg).1f/%(top_n)d (%(pct).0f%%)",
        "detail": "Consenso parcial entre los dos "
                  "recuperadores. En la fórmula RRF, un "
                  "documento presente en ambas listas suma dos "
                  "sumandos 1/(k+rango) y vence a uno que "
                  "domina una sola lista. Consenso por "
                  "consulta: %(per_query)s.",
        "fix": "Optimice los mismos pasajes en ambos ejes: "
               "términos explícitos (BM25) y explicación "
               "completa (vectorial).",
    },
    "rrf.consensus.good": {
        "title": "Consenso medio entre las listas: "
                 "%(avg).1f/%(top_n)d (%(pct).0f%%)",
        "detail": "Buen solapamiento entre recuperación léxica "
                  "y vectorial. En la fórmula RRF, un documento "
                  "presente en ambas listas suma dos sumandos "
                  "1/(k+rango) y vence a uno que domina una "
                  "sola lista. Consenso por consulta: "
                  "%(per_query)s.",
    },
    "rrf.uncovered": {
        "title": "%(n)d consultas sin ningún resultado",
        "detail": "Ningún chunk del sitio responde: "
                  "%(queries)s.",
        "fix": "Cree contenidos dedicados a estas intenciones.",
        "example": "Para cada consulta sin cubrir, una sección "
                   "con un encabezado igual a la pregunta:\n"
                   "<h2>¿Cuánto cuesta el drenaje linfático?"
                   "</h2>\n<p>Una sesión cuesta de media 40-80 "
                   "euros, según la duración y la zona "
                   "tratada.</p>",
    },
    "rrf.covered": {
        "title": "Las %(n)d consultas encuentran todas al "
                 "menos un pasaje",
        "detail": "Consultas verificadas: %(queries)s.",
    },
    "rrf.comp.empty": {
        "title": "Competidor %(host)s sin contenido "
                 "recuperable",
        "detail": "Ninguna página analizable: la comparación lo "
                  "incluye con 0 pasajes.",
    },
    "rrf.comp.not_runnable": {
        "title": "Comparación competitiva no ejecutable",
        "detail": "Hacen falta al menos un chunk y una "
                  "consulta.",
    },
    "rrf.share.low": {
        "title": "Share of voice: %(pct).0f%% de los primeros "
                 "%(top_n)d puestos fusionados (paridad "
                 "%(parity).0f%%)",
        "detail": "Los competidores ocupan los puestos que "
                  "usted necesitaría: en sus propios temas rara "
                  "vez es recuperado. Desglose: %(breakdown)s.",
        "fix": "Refuerce los pasajes en las consultas donde los "
               "competidores le ganan: mismos términos "
               "explícitos, respuesta completa.",
    },
    "rrf.share.mid": {
        "title": "Share of voice: %(pct).0f%% de los primeros "
                 "%(top_n)d puestos fusionados (paridad "
                 "%(parity).0f%%)",
        "detail": "Está por debajo de la paridad: en sus temas, "
                  "los competidores son recuperados más a "
                  "menudo que usted. Desglose: %(breakdown)s.",
        "fix": "Refuerce los pasajes en las consultas donde los "
               "competidores le ganan: mismos términos "
               "explícitos, respuesta completa.",
    },
    "rrf.share.good": {
        "title": "Share of voice: %(pct).0f%% de los primeros "
                 "%(top_n)d puestos fusionados (paridad "
                 "%(parity).0f%%)",
        "detail": "Se defiende frente a los competidores en sus "
                  "temas. Desglose: %(breakdown)s.",
    },
    "rrf.comp.lost": {
        "title": "%(n)d consultas de %(total)d ganadas por "
                 "completo por los competidores",
        "detail": "Ninguno de sus pasajes entre los primeros "
                  "%(top_n)d para: %(queries)s.",
        "fix": "Cree o reescriba contenidos dedicados a estas "
               "intenciones.",
    },
    "rrf.comp.present": {
        "title": "Presente entre los primeros %(top_n)d para "
                 "las %(n)d consultas",
        "detail": "Consultas de comparación: %(queries)s.",
    },
    "tech.robots.own": {
        "title": "Sitio declarado como propio",
        "detail": "Las reglas Disallow del robots.txt no se "
                  "aplican al sitio auditado (--own-site); "
                  "siguen aplicándose a los eventuales "
                  "competidores.",
    },
    "tech.robots.forced": {
        "title": "Reglas Disallow del robots.txt ignoradas a "
                 "petición explícita",
        "detail": "El rastreo más allá de las reglas Disallow "
                  "se activó con --ignore-robots %(ack)s: la "
                  "responsabilidad del rastreo fue asumida "
                  "explícitamente por el usuario.",
    },
    "tech.robots.excluded": {
        "title": "%(n)d URL excluidas por respeto al "
                 "robots.txt",
        "detail": "Las reglas Disallow dirigidas al agente "
                  "%(agent)s se respetan (comportamiento por "
                  "defecto): %(urls)s. Use --own-site si el "
                  "sitio es suyo.",
    },
    "tech.render.done": {
        "title": "%(n)d página(s) analizada(s) con renderizado "
                 "JavaScript",
        "detail": "Modo --render %(mode)s: el contenido "
                  "proviene del DOM renderizado en un navegador "
                  "headless; estado HTTP, redirecciones y "
                  "tiempos siguen siendo los de la respuesta "
                  "original.",
    },
    "tech.render.failed": {
        "title": "Renderizado fallido para %(n)d página(s)",
        "detail": "Para estas páginas se analizó el HTML "
                  "estático.",
        "fix": "Reintente, o aumente el timeout si el sitio es "
               "lento.",
    },
    "tech.pages.duplicates": {
        "title": "%(n)d URL sirven contenido idéntico",
        "detail": "El mismo texto es accesible desde varias "
                  "direcciones: %(urls)s. Los duplicados no "
                  "añaden sumandos a la suma RRF, diluyen las "
                  "señales y malgastan presupuesto de rastreo.",
        "fix": "Elija una URL canónica y redirija las demás "
               "con un 301.",
    },
}

_FINDINGS_BY_LANG: Dict[str, Dict[str, Dict[str, str]]] = {
    "en": _FINDINGS_EN,
    "fr": _FINDINGS_FR,
    "de": _FINDINGS_DE,
    "es": _FINDINGS_ES,
}


# Etichette delle aree nei referti text/md (l'HTML usa le chiavi
# "area.*" di _HTML_I18N). L'area Lighthouse ("Performance
# (Lighthouse)") e' identica in tutte le lingue e non compare.
_AREA_I18N: Dict[str, Dict[str, str]] = {
    "en": {
        AREA_TECH: "Technical", AREA_LEX: "Lexical (BM25)",
        AREA_SEM: "Semantic (vector)", AREA_SD: "Structured data",
        AREA_RRF: "RRF simulation"},
    "fr": {
        AREA_TECH: "Technique", AREA_LEX: "Lexicale (BM25)",
        AREA_SEM: "Sémantique (vectorielle)",
        AREA_SD: "Données structurées",
        AREA_RRF: "Simulation RRF"},
    "de": {
        AREA_TECH: "Technik", AREA_LEX: "Lexikalisch (BM25)",
        AREA_SEM: "Semantisch (vektoriell)",
        AREA_SD: "Strukturierte Daten",
        AREA_RRF: "RRF-Simulation"},
    "es": {
        AREA_TECH: "Técnica", AREA_LEX: "Léxica (BM25)",
        AREA_SEM: "Semántica (vectorial)",
        AREA_SD: "Datos estructurados",
        AREA_RRF: "Simulación RRF"},
}


# Cornice dei referti text/md: la coppia inline T(it, en) resta il
# meccanismo per l'inglese; per le altre lingue la tabella mappa il
# testo italiano canonico (che fa da chiave) alla traduzione, con
# lo stesso fallback dichiarato dei cataloghi rilievi (chiave
# assente -> resta l'italiano). La copertura delle chiavi rispetto
# alle chiamate T() e' verificata da un test basato sull'AST.
_FRAME_I18N: Dict[str, Dict[str, str]] = {
    "fr": {
        "PUNTEGGI": "SCORES",
        "**[CRITICO]**": "**[CRITIQUE]**",
        "[AVVISO]": "[AVERTISSEMENT]",
        "## Punteggi": "## Scores",
        "| Area | Punteggio |": "| Domaine | Score |",
        "## Rilievi per area": "## Constats par domaine",
        "Pagine analizzate : %d": "Pages analysées   : %d",
        "Chunk indicizzati : %d": "Chunks indexés    : %d",
        "Recuperatore vett.: %s": "Récupérateur vect.: %s",
        "  Nota: rilievi confrontati per tipo (i conteggi nei "
        "titoli possono variare).":
            "  Note : constats comparés par type (les comptes "
            "dans les titres peuvent varier).",
        "PROFILI DI CITABILITA' PER ASSISTENTE IA":
            "PROFILS DE CITABILITÉ PAR ASSISTANT IA",
        "GIUDIZIO LLM SULLA CITABILITA'":
            "JUGEMENT LLM SUR LA CITABILITÉ",
        "AUDIT LIGHTHOUSE": "AUDIT LIGHTHOUSE",
        "ANCORA DI REALTA' (BRAVE SEARCH)":
            "ANCRE DE RÉALITÉ (BRAVE SEARCH)",
        "LA MATEMATICA DEL PROBLEMA":
            "LES MATHÉMATIQUES DU PROBLÈME",
        "gravita' e guadagno di citabilita'":
            "gravité et gain de citabilité",
        "gravita' e peso": "gravité et poids",
        "DETTAGLIO SIMULAZIONE RRF":
            "DÉTAIL DE LA SIMULATION RRF",
        "Pagine analizzate: %d · chunk indicizzati: %d · "
        "recuperatore vettoriale: `%s`":
            "Pages analysées : %d · chunks indexés : %d · "
            "récupérateur vectoriel : `%s`",
        "| **Complessivo** | **%.1f/100** |":
            "| **Global** | **%.1f/100** |",
        "## Profili di citabilita' per assistente IA":
            "## Profils de citabilité par assistant IA",
        "| Profilo | Cosa premia | Punteggio |":
            "| Profil | Ce qu'il récompense | Score |",
        "## Giudizio LLM sulla citabilita'":
            "## Jugement LLM sur la citabilité",
        "| Query | Punteggio | Motivazione |":
            "| Requête | Score | Motivation |",
        "## Audit Lighthouse": "## Audit Lighthouse",
        "## Ancora di realta' (Brave Search)":
            "## Ancre de réalité (Brave Search)",
        "## Piano di remediation": "## Plan de remédiation",
        "## Simulazione RRF per query":
            "## Simulation RRF par requête",
        "| Query | Consenso | Primo passaggio fuso |":
            "| Requête | Consensus | Premier passage fusionné |",
        "| Sito | Quota |": "| Site | Part |",
        "COMPLESSIVO": "GLOBAL",
        "RISPETTO ALL'ESECUZIONE PRECEDENTE  ·  %s":
            "PAR RAPPORT À L'EXÉCUTION PRÉCÉDENTE  ·  %s",
        "Risolti": "Résolus",
        "Nuovi": "Nouveaux",
        "  Pesi (mercato %s): %s": "  Poids (marché %s) : %s",
        "  Azioni con maggior guadagno di profilo:":
            "  Actions au plus fort gain de profil :",
        "  Nota: %s": "  Note : %s",
        "  Superficie attuale   : %d pagine, %d chunk (~%d "
        "parole/pagina)":
            "  Surface actuelle     : %d pages, %d chunks (~%d "
            "mots/page)",
        "  Superficie potenziale: ~%d chunk (%s)":
            "  Surface potentielle  : ~%d chunks (%s)",
        "PIANO DI REMEDIATION  ·  %d interventi per %s%s":
            "PLAN DE REMÉDIATION  ·  %d interventions par %s%s",
        "CRITICO": "CRITIQUE",
        "AVVISO": "AVERTISSEMENT",
        "CONFRONTO COMPETITIVO  ·  share of voice sui primi %d "
        "posti fusi":
            "COMPARAISON CONCURRENTIELLE  ·  share of voice sur "
            "les %d premières places fusionnées",
        "  <- tuo sito": "  <- votre site",
        "ASSENTE": "ABSENT",
        "## Rispetto all'esecuzione precedente (%s)":
            "## Par rapport à l'exécution précédente (%s)",
        "Modello `%s` su %d passaggio/i · media **%.1f/100**.":
            "Modèle `%s` sur %d passage(s) · moyenne "
            "**%.1f/100**.",
        "(nessuno)": "(aucun)",
        "## Share of voice (primi %d posti fusi)":
            "## Share of voice (%d premières places fusionnées)",
        " ← tuo sito": " ← votre site",
        "  Modello: %s · passaggi valutati: %d · media: "
        "%.1f/100":
            "  Modèle : %s · passages évalués : %d · moyenne : "
            "%.1f/100",
        "  Non eseguito: %s": "  Non exécuté : %s",
        "  Eseguito su %d pagina/e (%s)%s":
            "  Exécuté sur %d page(s) (%s)%s",
        "  Sito trovato per %d query su %d (primi %d "
        "risultati)":
            "  Site trouvé pour %d requêtes sur %d (%d premiers "
            "résultats)",
        "  Non eseguita: %s": "  Non exécutée : %s",
        "  Effetto sull'RRF     : ~%.1fx occasioni di comparire "
        "nelle liste fuse":
            "  Effet sur le RRF     : ~%.1fx occasions "
            "d'apparaître dans les listes fusionnées",
        "  Effetto sull'RRF     : da 0 addendi a ~%d occasioni "
        "di comparire nelle liste":
            "  Effet sur le RRF     : de 0 addende à ~%d "
            "occasions d'apparaître dans les listes",
        "%2d. [%s · %s · sforzo: %s] %s%s":
            "%2d. [%s · %s · effort : %s] %s%s",
        "    Esempio:": "    Exemple :",
        "Query: %s   (consenso %d)":
            "Requête : %s   (consensus %d)",
        "   (nessun passaggio recuperato)":
            "   (aucun passage récupéré)",
        "miglior posizione %d": "meilleure position %d",
        "  %-46s  tuoi %d/%d · %s": "  %-46s  vôtres %d/%d · %s",
        "| **Indice composito (%s)** | | **%.1f/100** |":
            "| **Indice composite (%s)** | | **%.1f/100** |",
        "- nessuno": "- aucun",
        "Eseguito su %d pagina/e (%s)%s.":
            "Exécuté sur %d page(s) (%s)%s.",
        "Non eseguito: %s": "Non exécuté : %s",
        "Sito trovato per %d query su %d (primi %d risultati).":
            "Site trouvé pour %d requêtes sur %d (%d premiers "
            "résultats).",
        "Non eseguita: %s": "Non exécutée : %s",
        " · trasversale: %d profili": " · transversal : %d profils",
        "- [ ] **%d.** %s _(%s · %s · sforzo: %s%s)_":
            "- [ ] **%d.** %s _(%s · %s · effort : %s%s)_",
        "  %s: nessuno": "  %s : aucun",
        "INDICE COMPOSITO": "INDICE COMPOSITE",
        " -> %s (+%.1f punti profilo)":
            " -> %s (+%.1f points de profil)",
        "   %d. [sforzo: %s] %s%s": "   %d. [effort : %s] %s%s",
        "  Indice euristico: %.1f — scarto giudice-euristica: "
        "%+.1f":
            "  Indice heuristique : %.1f — écart "
            "juge-heuristique : %+.1f",
        "  Profilo %s: %.1f — scarto giudice-profilo: %+.1f":
            "  Profil %s : %.1f — écart juge-profil : %+.1f",
        "errore: %s": "erreur : %s",
        "    Trasversale: deprime %d profili di citabilita' "
        "(risolto vale +%.1f sull'indice)":
            "    Transversal : déprime %d profils de citabilité "
            "(résolu vaut +%.1f sur l'indice)",
        "posizione #%d": "position #%d",
        "assente dai primi %d": "absent des %d premiers",
        "posizione **#%d**": "position **#%d**",
        "consenso RRF": "consensus RRF",
        "consenso RRF %s": "consensus RRF %s",
    },
    "de": {
        "PUNTEGGI": "PUNKTZAHLEN",
        "**[CRITICO]**": "**[KRITISCH]**",
        "[AVVISO]": "[WARNUNG]",
        "## Punteggi": "## Punktzahlen",
        "| Area | Punteggio |": "| Bereich | Punktzahl |",
        "## Rilievi per area": "## Befunde nach Bereich",
        "Pagine analizzate : %d": "Analysierte Seiten: %d",
        "Chunk indicizzati : %d": "Indexierte Chunks : %d",
        "Recuperatore vett.: %s": "Vektor-Retriever  : %s",
        "  Nota: rilievi confrontati per tipo (i conteggi nei "
        "titoli possono variare).":
            "  Hinweis: Befunde nach Typ verglichen (Zahlen in "
            "den Titeln können variieren).",
        "PROFILI DI CITABILITA' PER ASSISTENTE IA":
            "ZITIERBARKEITSPROFILE JE KI-ASSISTENT",
        "GIUDIZIO LLM SULLA CITABILITA'":
            "LLM-URTEIL ZUR ZITIERBARKEIT",
        "AUDIT LIGHTHOUSE": "LIGHTHOUSE-AUDIT",
        "ANCORA DI REALTA' (BRAVE SEARCH)":
            "REALITÄTSANKER (BRAVE SEARCH)",
        "LA MATEMATICA DEL PROBLEMA":
            "DIE MATHEMATIK DES PROBLEMS",
        "gravita' e guadagno di citabilita'":
            "Schwere und Zitierbarkeitsgewinn",
        "gravita' e peso": "Schwere und Gewicht",
        "DETTAGLIO SIMULAZIONE RRF": "DETAIL DER RRF-SIMULATION",
        "Pagine analizzate: %d · chunk indicizzati: %d · "
        "recuperatore vettoriale: `%s`":
            "Analysierte Seiten: %d · indexierte Chunks: %d · "
            "Vektor-Retriever: `%s`",
        "| **Complessivo** | **%.1f/100** |":
            "| **Gesamt** | **%.1f/100** |",
        "## Profili di citabilita' per assistente IA":
            "## Zitierbarkeitsprofile je KI-Assistent",
        "| Profilo | Cosa premia | Punteggio |":
            "| Profil | Was es belohnt | Punktzahl |",
        "## Giudizio LLM sulla citabilita'":
            "## LLM-Urteil zur Zitierbarkeit",
        "| Query | Punteggio | Motivazione |":
            "| Anfrage | Punktzahl | Begründung |",
        "## Audit Lighthouse": "## Lighthouse-Audit",
        "## Ancora di realta' (Brave Search)":
            "## Realitätsanker (Brave Search)",
        "## Piano di remediation": "## Behebungsplan",
        "## Simulazione RRF per query":
            "## RRF-Simulation je Anfrage",
        "| Query | Consenso | Primo passaggio fuso |":
            "| Anfrage | Konsens | Führende Passage |",
        "| Sito | Quota |": "| Website | Anteil |",
        "COMPLESSIVO": "GESAMT",
        "RISPETTO ALL'ESECUZIONE PRECEDENTE  ·  %s":
            "IM VERGLEICH ZUM VORHERIGEN LAUF  ·  %s",
        "Risolti": "Behoben",
        "Nuovi": "Neu",
        "  Pesi (mercato %s): %s": "  Gewichte (Markt %s): %s",
        "  Azioni con maggior guadagno di profilo:":
            "  Maßnahmen mit dem größten Profilgewinn:",
        "  Nota: %s": "  Hinweis: %s",
        "  Superficie attuale   : %d pagine, %d chunk (~%d "
        "parole/pagina)":
            "  Aktuelle Fläche      : %d Seiten, %d Chunks (~%d "
            "Wörter/Seite)",
        "  Superficie potenziale: ~%d chunk (%s)":
            "  Potenzielle Fläche   : ~%d Chunks (%s)",
        "PIANO DI REMEDIATION  ·  %d interventi per %s%s":
            "BEHEBUNGSPLAN  ·  %d Maßnahmen nach %s%s",
        "CRITICO": "KRITISCH",
        "AVVISO": "WARNUNG",
        "CONFRONTO COMPETITIVO  ·  share of voice sui primi %d "
        "posti fusi":
            "WETTBEWERBSVERGLEICH  ·  Share of Voice über die "
            "ersten %d fusionierten Plätze",
        "  <- tuo sito": "  <- Ihre Website",
        "ASSENTE": "FEHLT",
        "## Rispetto all'esecuzione precedente (%s)":
            "## Im Vergleich zum vorherigen Lauf (%s)",
        "Modello `%s` su %d passaggio/i · media **%.1f/100**.":
            "Modell `%s` auf %d Passage(n) · Durchschnitt "
            "**%.1f/100**.",
        "(nessuno)": "(keine)",
        "## Share of voice (primi %d posti fusi)":
            "## Share of Voice (erste %d fusionierte Plätze)",
        " ← tuo sito": " ← Ihre Website",
        "  Modello: %s · passaggi valutati: %d · media: "
        "%.1f/100":
            "  Modell: %s · bewertete Passagen: %d · "
            "Durchschnitt: %.1f/100",
        "  Non eseguito: %s": "  Nicht ausgeführt: %s",
        "  Eseguito su %d pagina/e (%s)%s":
            "  Ausgeführt auf %d Seite(n) (%s)%s",
        "  Sito trovato per %d query su %d (primi %d "
        "risultati)":
            "  Website für %d von %d Anfragen gefunden (erste "
            "%d Ergebnisse)",
        "  Non eseguita: %s": "  Nicht ausgeführt: %s",
        "  Effetto sull'RRF     : ~%.1fx occasioni di comparire "
        "nelle liste fuse":
            "  Wirkung auf RRF      : ~%.1fx Chancen, in den "
            "fusionierten Listen zu erscheinen",
        "  Effetto sull'RRF     : da 0 addendi a ~%d occasioni "
        "di comparire nelle liste":
            "  Wirkung auf RRF      : von 0 Summanden zu ~%d "
            "Chancen, in den Listen zu erscheinen",
        "%2d. [%s · %s · sforzo: %s] %s%s":
            "%2d. [%s · %s · Aufwand: %s] %s%s",
        "    Esempio:": "    Beispiel:",
        "Query: %s   (consenso %d)":
            "Anfrage: %s   (Konsens %d)",
        "   (nessun passaggio recuperato)":
            "   (keine Passage abgerufen)",
        "miglior posizione %d": "beste Position %d",
        "  %-46s  tuoi %d/%d · %s": "  %-46s  Ihre %d/%d · %s",
        "| **Indice composito (%s)** | | **%.1f/100** |":
            "| **Kompositindex (%s)** | | **%.1f/100** |",
        "- nessuno": "- keine",
        "Eseguito su %d pagina/e (%s)%s.":
            "Ausgeführt auf %d Seite(n) (%s)%s.",
        "Non eseguito: %s": "Nicht ausgeführt: %s",
        "Sito trovato per %d query su %d (primi %d risultati).":
            "Website für %d von %d Anfragen gefunden (erste %d "
            "Ergebnisse).",
        "Non eseguita: %s": "Nicht ausgeführt: %s",
        " · trasversale: %d profili":
            " · übergreifend: %d Profile",
        "- [ ] **%d.** %s _(%s · %s · sforzo: %s%s)_":
            "- [ ] **%d.** %s _(%s · %s · Aufwand: %s%s)_",
        "  %s: nessuno": "  %s: keine",
        "INDICE COMPOSITO": "KOMPOSITINDEX",
        " -> %s (+%.1f punti profilo)":
            " -> %s (+%.1f Profilpunkte)",
        "   %d. [sforzo: %s] %s%s": "   %d. [Aufwand: %s] %s%s",
        "  Indice euristico: %.1f — scarto giudice-euristica: "
        "%+.1f":
            "  Heuristischer Index: %.1f — Abstand "
            "Richter-Heuristik: %+.1f",
        "  Profilo %s: %.1f — scarto giudice-profilo: %+.1f":
            "  Profil %s: %.1f — Abstand Richter-Profil: %+.1f",
        "errore: %s": "Fehler: %s",
        "    Trasversale: deprime %d profili di citabilita' "
        "(risolto vale +%.1f sull'indice)":
            "    Übergreifend: drückt %d "
            "Zitierbarkeitsprofile (behoben bringt +%.1f auf "
            "den Index)",
        "posizione #%d": "Position #%d",
        "assente dai primi %d": "fehlt unter den ersten %d",
        "posizione **#%d**": "Position **#%d**",
        "consenso RRF": "RRF-Konsens",
        "consenso RRF %s": "RRF-Konsens %s",
    },
    "es": {
        "PUNTEGGI": "PUNTUACIONES",
        "**[CRITICO]**": "**[CRÍTICO]**",
        "[AVVISO]": "[ADVERTENCIA]",
        "## Punteggi": "## Puntuaciones",
        "| Area | Punteggio |": "| Área | Puntuación |",
        "## Rilievi per area": "## Hallazgos por área",
        "Pagine analizzate : %d": "Páginas analizadas: %d",
        "Chunk indicizzati : %d": "Chunks indexados  : %d",
        "Recuperatore vett.: %s": "Recuperador vect. : %s",
        "  Nota: rilievi confrontati per tipo (i conteggi nei "
        "titoli possono variare).":
            "  Nota: hallazgos comparados por tipo (los "
            "recuentos en los títulos pueden variar).",
        "PROFILI DI CITABILITA' PER ASSISTENTE IA":
            "PERFILES DE CITABILIDAD POR ASISTENTE DE IA",
        "GIUDIZIO LLM SULLA CITABILITA'":
            "JUICIO LLM SOBRE LA CITABILIDAD",
        "AUDIT LIGHTHOUSE": "AUDITORÍA LIGHTHOUSE",
        "ANCORA DI REALTA' (BRAVE SEARCH)":
            "ANCLA DE REALIDAD (BRAVE SEARCH)",
        "LA MATEMATICA DEL PROBLEMA":
            "LAS MATEMÁTICAS DEL PROBLEMA",
        "gravita' e guadagno di citabilita'":
            "gravedad y ganancia de citabilidad",
        "gravita' e peso": "gravedad y peso",
        "DETTAGLIO SIMULAZIONE RRF":
            "DETALLE DE LA SIMULACIÓN RRF",
        "Pagine analizzate: %d · chunk indicizzati: %d · "
        "recuperatore vettoriale: `%s`":
            "Páginas analizadas: %d · chunks indexados: %d · "
            "recuperador vectorial: `%s`",
        "| **Complessivo** | **%.1f/100** |":
            "| **Global** | **%.1f/100** |",
        "## Profili di citabilita' per assistente IA":
            "## Perfiles de citabilidad por asistente de IA",
        "| Profilo | Cosa premia | Punteggio |":
            "| Perfil | Qué premia | Puntuación |",
        "## Giudizio LLM sulla citabilita'":
            "## Juicio LLM sobre la citabilidad",
        "| Query | Punteggio | Motivazione |":
            "| Consulta | Puntuación | Motivación |",
        "## Audit Lighthouse": "## Auditoría Lighthouse",
        "## Ancora di realta' (Brave Search)":
            "## Ancla de realidad (Brave Search)",
        "## Piano di remediation": "## Plan de corrección",
        "## Simulazione RRF per query":
            "## Simulación RRF por consulta",
        "| Query | Consenso | Primo passaggio fuso |":
            "| Consulta | Consenso | Primer pasaje fusionado |",
        "| Sito | Quota |": "| Sitio | Cuota |",
        "COMPLESSIVO": "GLOBAL",
        "RISPETTO ALL'ESECUZIONE PRECEDENTE  ·  %s":
            "RESPECTO A LA EJECUCIÓN ANTERIOR  ·  %s",
        "Risolti": "Resueltos",
        "Nuovi": "Nuevos",
        "  Pesi (mercato %s): %s": "  Pesos (mercado %s): %s",
        "  Azioni con maggior guadagno di profilo:":
            "  Acciones con mayor ganancia de perfil:",
        "  Nota: %s": "  Nota: %s",
        "  Superficie attuale   : %d pagine, %d chunk (~%d "
        "parole/pagina)":
            "  Superficie actual    : %d páginas, %d chunks "
            "(~%d palabras/página)",
        "  Superficie potenziale: ~%d chunk (%s)":
            "  Superficie potencial : ~%d chunks (%s)",
        "PIANO DI REMEDIATION  ·  %d interventi per %s%s":
            "PLAN DE CORRECCIÓN  ·  %d intervenciones por %s%s",
        "CRITICO": "CRÍTICO",
        "AVVISO": "ADVERTENCIA",
        "CONFRONTO COMPETITIVO  ·  share of voice sui primi %d "
        "posti fusi":
            "COMPARACIÓN COMPETITIVA  ·  share of voice sobre "
            "los primeros %d puestos fusionados",
        "  <- tuo sito": "  <- su sitio",
        "ASSENTE": "AUSENTE",
        "## Rispetto all'esecuzione precedente (%s)":
            "## Respecto a la ejecución anterior (%s)",
        "Modello `%s` su %d passaggio/i · media **%.1f/100**.":
            "Modelo `%s` sobre %d pasaje(s) · media "
            "**%.1f/100**.",
        "(nessuno)": "(ninguno)",
        "## Share of voice (primi %d posti fusi)":
            "## Share of voice (primeros %d puestos fusionados)",
        " ← tuo sito": " ← su sitio",
        "  Modello: %s · passaggi valutati: %d · media: "
        "%.1f/100":
            "  Modelo: %s · pasajes evaluados: %d · media: "
            "%.1f/100",
        "  Non eseguito: %s": "  No ejecutado: %s",
        "  Eseguito su %d pagina/e (%s)%s":
            "  Ejecutada en %d página(s) (%s)%s",
        "  Sito trovato per %d query su %d (primi %d "
        "risultati)":
            "  Sitio encontrado para %d consultas de %d "
            "(primeros %d resultados)",
        "  Non eseguita: %s": "  No ejecutada: %s",
        "  Effetto sull'RRF     : ~%.1fx occasioni di comparire "
        "nelle liste fuse":
            "  Efecto sobre el RRF  : ~%.1fx ocasiones de "
            "aparecer en las listas fusionadas",
        "  Effetto sull'RRF     : da 0 addendi a ~%d occasioni "
        "di comparire nelle liste":
            "  Efecto sobre el RRF  : de 0 sumandos a ~%d "
            "ocasiones de aparecer en las listas",
        "%2d. [%s · %s · sforzo: %s] %s%s":
            "%2d. [%s · %s · esfuerzo: %s] %s%s",
        "    Esempio:": "    Ejemplo:",
        "Query: %s   (consenso %d)":
            "Consulta: %s   (consenso %d)",
        "   (nessun passaggio recuperato)":
            "   (ningún pasaje recuperado)",
        "miglior posizione %d": "mejor posición %d",
        "  %-46s  tuoi %d/%d · %s": "  %-46s  suyos %d/%d · %s",
        "| **Indice composito (%s)** | | **%.1f/100** |":
            "| **Índice compuesto (%s)** | | **%.1f/100** |",
        "- nessuno": "- ninguno",
        "Eseguito su %d pagina/e (%s)%s.":
            "Ejecutada en %d página(s) (%s)%s.",
        "Non eseguito: %s": "No ejecutado: %s",
        "Sito trovato per %d query su %d (primi %d risultati).":
            "Sitio encontrado para %d consultas de %d (primeros "
            "%d resultados).",
        "Non eseguita: %s": "No ejecutada: %s",
        " · trasversale: %d profili":
            " · transversal: %d perfiles",
        "- [ ] **%d.** %s _(%s · %s · sforzo: %s%s)_":
            "- [ ] **%d.** %s _(%s · %s · esfuerzo: %s%s)_",
        "  %s: nessuno": "  %s: ninguno",
        "INDICE COMPOSITO": "ÍNDICE COMPUESTO",
        " -> %s (+%.1f punti profilo)":
            " -> %s (+%.1f puntos de perfil)",
        "   %d. [sforzo: %s] %s%s":
            "   %d. [esfuerzo: %s] %s%s",
        "  Indice euristico: %.1f — scarto giudice-euristica: "
        "%+.1f":
            "  Índice heurístico: %.1f — brecha "
            "juez-heurística: %+.1f",
        "  Profilo %s: %.1f — scarto giudice-profilo: %+.1f":
            "  Perfil %s: %.1f — brecha juez-perfil: %+.1f",
        "errore: %s": "error: %s",
        "    Trasversale: deprime %d profili di citabilita' "
        "(risolto vale +%.1f sull'indice)":
            "    Transversal: deprime %d perfiles de "
            "citabilidad (resuelto vale +%.1f sobre el índice)",
        "posizione #%d": "posición #%d",
        "assente dai primi %d": "ausente de los primeros %d",
        "posizione **#%d**": "posición **#%d**",
        "consenso RRF": "consenso RRF",
        "consenso RRF %s": "consenso RRF %s",
    },
}


def frame_text(it_text: str, en_text: str, lang: str) -> str:
    """Testo di cornice per text/md: it/en inline, altrove tabella."""
    if lang == "en":
        return en_text
    return _FRAME_I18N.get(lang, {}).get(it_text, it_text)


# Nota sulle evidenze nella lingua del sito, dichiarata in testa ai
# referti text/md non italiani (l'HTML usa "note.findings_lang").
_EVIDENCE_NOTE: Dict[str, str] = {
    "en": "Note: quoted evidence from the audited site stays in "
          "the site's language.",
    "fr": "Note : les extraits cités du site audité restent dans "
          "la langue du site.",
    "de": "Hinweis: zitierte Belege der geprüften Website "
          "bleiben in der Sprache der Website.",
    "es": "Nota: las evidencias citadas del sitio auditado "
          "permanecen en el idioma del sitio.",
}


def evidence_note(lang: str) -> str:
    """Nota sulle evidenze per text/md; vuota per l'italiano."""
    return _EVIDENCE_NOTE.get(lang, "")


# Intestazioni del CSV e valore "quick win" per lingua (il resto
# della riga sono dati del rilievo, tradotti da finding_texts).
_CSV_HEADERS: Dict[str, List[str]] = {
    "it": ["sito", "area", "gravita", "peso", "titolo",
           "dettaglio", "correzione", "url", "sforzo",
           "quick_win"],
    "en": ["site", "area", "severity", "weight", "title",
           "detail", "fix", "url", "effort", "quick_win"],
    "fr": ["site", "domaine", "gravité", "poids", "titre",
           "détail", "correction", "url", "effort", "quick_win"],
    "de": ["website", "bereich", "schweregrad", "gewicht",
           "titel", "detail", "korrektur", "url", "aufwand",
           "quick_win"],
    "es": ["sitio", "área", "gravedad", "peso", "título",
           "detalle", "corrección", "url", "esfuerzo",
           "quick_win"],
}

_CSV_YES = {"it": "si", "en": "yes", "fr": "oui", "de": "ja",
            "es": "si"}


def csv_header(lang: str) -> List[str]:
    """Riga di intestazione del CSV nella lingua del referto."""
    return list(_CSV_HEADERS.get(lang) or _CSV_HEADERS["it"])


def csv_yes(lang: str) -> str:
    """Valore della colonna quick_win nella lingua del referto."""
    return _CSV_YES.get(lang) or _CSV_YES["it"]


def finding_texts(source: object, lang: str = "it") -> Dict[str, str]:
    """Testi (title/detail/fix/example) nella lingua del referto.

    ``source`` e' un Finding oppure un dict con le stesse chiavi
    (es. voci del piano di remediation). Con "it", senza chiave o
    senza voce in catalogo restano i testi italiani canonici; un
    template incoerente coi params non interrompe mai il rendering
    (ripiega sull'italiano campo per campo).
    """
    if isinstance(source, Finding):
        data = {"title": source.title, "detail": source.detail,
                "fix": source.fix, "example": source.example}
        key: str = source.key
        params: Dict[str, object] = source.params
    else:
        src = dict(source)  # type: ignore[call-overload]
        data = {name: str(src.get(name) or "")
                for name in ("title", "detail", "fix", "example")}
        key = str(src.get("key") or "")
        params = dict(src.get("params") or {})  # type: ignore
    if lang == "it" or not key:
        return data
    if key.startswith("lh."):
        return _lighthouse_texts(data, key, params, lang)
    entry = _FINDINGS_BY_LANG.get(lang, {}).get(key) or {}
    for name, template in entry.items():
        try:
            data[name] = template % params
        except (KeyError, TypeError, ValueError):
            pass  # parametri incoerenti: resta l'italiano
    return data


# Cornice dei rilievi Lighthouse per lingua: i testi degli audit
# arrivano dai file di locale del fork, qui vive solo la cornice
# (Pagine/Evidenze/Punteggio, singolare e plurale espliciti).
_LH_FRAME: Dict[str, Dict[str, str]] = {
    "en": {
        "title": "Lighthouse: %s",
        "pages": "Pages: %s",
        "evidence": "Evidence: %s",
        "ok_title": "Lighthouse %s: no findings",
        "ok_one": "Score %d/100 on %d page examined.",
        "ok_many": "Score %d/100 on %d pages examined.",
        "err_one": "Lighthouse did not complete on %d page",
        "err_many": "Lighthouse did not complete on %d pages",
    },
    "fr": {
        "title": "Lighthouse : %s",
        "pages": "Pages : %s",
        "evidence": "Preuves : %s",
        "ok_title": "Lighthouse %s : aucun constat",
        "ok_one": "Score %d/100 sur %d page examinée.",
        "ok_many": "Score %d/100 sur %d pages examinées.",
        "err_one": "Lighthouse n'a pas abouti sur %d page",
        "err_many": "Lighthouse n'a pas abouti sur %d pages",
    },
    "de": {
        "title": "Lighthouse: %s",
        "pages": "Seiten: %s",
        "evidence": "Belege: %s",
        "ok_title": "Lighthouse %s: keine Befunde",
        "ok_one": "Punktzahl %d/100 auf %d untersuchten Seite.",
        "ok_many": "Punktzahl %d/100 auf %d untersuchten Seiten.",
        "err_one": "Lighthouse wurde auf %d Seite nicht "
                   "abgeschlossen",
        "err_many": "Lighthouse wurde auf %d Seiten nicht "
                    "abgeschlossen",
    },
    "es": {
        "title": "Lighthouse: %s",
        "pages": "Páginas: %s",
        "evidence": "Evidencias: %s",
        "ok_title": "Lighthouse %s: sin hallazgos",
        "ok_one": "Puntuación %d/100 en %d página examinada.",
        "ok_many": "Puntuación %d/100 en %d páginas examinadas.",
        "err_one": "Lighthouse no se completó en %d página",
        "err_many": "Lighthouse no se completó en %d páginas",
    },
}


def _lh_localized(params: Dict[str, object], msg_key: str,
                  lang: str) -> str:
    """Testo localizzato di un messaggio Lighthouse, o stringa vuota.

    Per l'inglese vale il testo risolto dal parser (``title_en``,
    ``fix_en``, ``cat_title_en``: compatibile con i referti gia'
    salvati nello storico); per le altre lingue si risolve al
    rendering l'id del messaggio (``*_msg`` nei params) sul file di
    locale del fork. I messaggi con placeholder ICU residui non
    vengono usati (niente interpolazione parziale).
    """
    if lang == "en":
        return str(params.get("%s_en" % msg_key) or "")
    msg_id = str(params.get("%s_msg" % msg_key) or "")
    if not msg_id:
        return ""
    text = lh_locale_catalog(lang).get(msg_id) or ""
    if "{" in text:
        return ""
    return text


def _lighthouse_texts(data: Dict[str, str], key: str,
                      params: Dict[str, object],
                      lang: str) -> Dict[str, str]:
    """Testi non italiani dei rilievi Lighthouse (decisione i18n P1).

    Il catalogo e' Lighthouse stesso: i testi degli audit arrivano
    dai file di locale del fork — l'inglese risolto dal parser via
    icuMessagePaths del LHR, le altre lingue risolte al rendering
    dagli id dei messaggi — e qui si ricompongono con la cornice
    della lingua (_LH_FRAME). Campo per campo: senza testo
    localizzato resta l'italiano, lo stesso fallback dichiarato
    dei cataloghi dei rilievi.
    """
    out = dict(data)
    frame = _LH_FRAME.get(lang) or _LH_FRAME["en"]
    if key == "lh.run.errors":
        try:
            n = int(params.get("n", 0))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return out
        out["title"] = frame["err_one" if n == 1 else
                             "err_many"] % n
        return out
    if key.endswith(".ok"):
        cat = _lh_localized(params, "cat_title", lang)
        if cat:
            out["title"] = frame["ok_title"] % cat
        try:
            pages = int(params.get("pages", 0))  # type: ignore
            out["detail"] = (frame["ok_one" if pages == 1 else
                                   "ok_many"]
                             % (int(params.get("score", 0)),  # type: ignore
                                pages))
        except (TypeError, ValueError):
            pass
        return out
    title = _lh_localized(params, "title", lang)
    if title:
        out["title"] = frame["title"] % title
    fix = _lh_localized(params, "fix", lang)
    if fix:
        out["fix"] = _strip_md_links(fix)
    parts: List[str] = []
    display = str(params.get("display") or "")
    if display:
        parts.append(display)
    urls = str(params.get("urls") or "")
    if urls:
        parts.append(frame["pages"] % urls)
    evidence = params.get("evidence")
    if isinstance(evidence, list) and evidence:
        parts.append(frame["evidence"]
                     % "; ".join(str(e) for e in evidence))
    if parts:
        out["detail"] = "; ".join(parts)
    return out

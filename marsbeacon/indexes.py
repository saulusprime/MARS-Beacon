# -*- coding: utf-8 -*-
"""Indici BM25 e vettoriale, fusione RRF, grafo dei link e treemap.

Generato dalla scomposizione di mars_audit.py (v1.58.0): il
namespace pubblico resta mars_audit, questo modulo e' interno.
"""

from __future__ import annotations

from collections import Counter
from typing import Dict
from typing import Iterable
from typing import List
from typing import Optional
from typing import Sequence
from typing import Set
from typing import Tuple
from urllib.parse import urljoin
from urllib.parse import urlparse
import importlib.util
import logging
import math
import os
import sys

from marsbeacon.base import (
    AREA_TECH,
    DEFAULT_EMBEDDINGS_MODEL,
    Finding,
    Page,
    SEV_CRITICAL,
    SEV_INFO,
    SEV_OK,
    SEV_WARNING,
    char_ngrams,
    norm_url,
    tokenize)
from marsbeacon.crawler import Fetcher


class BM25Index:
    """Okapi BM25.

    idf(q)   = ln(1 + (N - n(q) + 0.5) / (n(q) + 0.5))
    score(d) = somma_q idf(q) * f*(k1+1) / (f + k1*(1-b+b*|d|/avgdl))

    Riferimento: Robertson & Zaragoza (2009).
    """

    def __init__(self, docs: Sequence[str], k1: float = 1.5,
                 b: float = 0.75) -> None:
        self.k1 = k1
        self.b = b
        self.corpus = [tokenize(d) for d in docs]
        self.doc_len = [len(d) for d in self.corpus]
        self.n_docs = len(self.corpus) or 1
        self.avgdl = (sum(self.doc_len) / self.n_docs) or 1.0
        self.freqs = [Counter(d) for d in self.corpus]
        df: Counter = Counter()
        for doc in self.corpus:
            df.update(set(doc))
        self.idf = {
            term: math.log(
                1.0 + (self.n_docs - n + 0.5) / (n + 0.5))
            for term, n in df.items()
        }

    def search(self, query: str) -> List[Tuple[int, float]]:
        """Restituisce (indice_doc, punteggio) ordinati decrescenti."""
        terms = tokenize(query)
        scores: List[Tuple[int, float]] = []
        for i, freq in enumerate(self.freqs):
            total = 0.0
            for term in terms:
                if term not in freq:
                    continue
                f = freq[term]
                denom = f + self.k1 * (
                    1 - self.b + self.b * self.doc_len[i] / self.avgdl)
                total += self.idf.get(term, 0.0) * f * (self.k1 + 1) / denom
            if total > 0:
                scores.append((i, total))
        scores.sort(key=lambda x: (-x[1], x[0]))
        return scores


def _quiet_huggingface() -> None:
    """Zittisce il rumore dell'ecosistema Hugging Face nel log.

    Il caricamento del modello di embedding contatta l'HF Hub e senza
    token stampa su stderr avvisi in inglese sui rate limit (piu' le
    barre di avanzamento dei download): rumore puro nel log di
    avanzamento che la GUI mostra al cliente. L'avviso e' innocuo —
    il modello resta in cache locale dopo il primo download — e chi
    vuole limiti piu' alti puo' esportare HF_TOKEN, che le librerie
    leggono da sole. Le variabili gia' impostate dall'utente non
    vengono toccate.
    """
    os.environ.setdefault("HF_HUB_DISABLE_PROGRESS_BARS", "1")
    os.environ.setdefault("HF_HUB_VERBOSITY", "error")
    os.environ.setdefault("TRANSFORMERS_VERBOSITY", "error")
    for name in ("huggingface_hub", "transformers",
                 "sentence_transformers"):
        logging.getLogger(name).setLevel(logging.ERROR)


def embeddings_available() -> bool:
    """True se sentence-transformers e numpy sono importabili."""
    return (
        importlib.util.find_spec("sentence_transformers") is not None
        and importlib.util.find_spec("numpy") is not None
    )


def resolve_model_name(requested: str) -> str:
    """Modello di embedding effettivo a partire da --embeddings.

    Esplicito se indicato; "none"/"off"/"char-tfidf" forzano il
    proxy; vuoto con sentence-transformers installato attiva il
    modello multilingue predefinito (auto-rilevamento); altrimenti
    resta il proxy char-tfidf.
    """
    req = requested.strip()
    if req.lower() in ("none", "off", "char-tfidf"):
        return ""
    if req:
        return req
    return DEFAULT_EMBEDDINGS_MODEL if embeddings_available() else ""


class VectorIndex:
    """Recuperatore vettoriale.

    Se e' disponibile ``sentence-transformers`` usa embedding densi
    reali. Altrimenti ripiega su TF-IDF di n-grammi di caratteri con
    similarita' coseno: e' un *proxy* morfologico, non una vera
    rappresentazione semantica, e viene dichiarato come tale nel
    referto.
    """

    def __init__(self, docs: Sequence[str],
                 model_name: str = "") -> None:
        self.docs = list(docs)
        self.model = None
        self.mode = "char-tfidf"
        if model_name:
            self._load_model(model_name)
        if self.model is None:
            self._build_tfidf()

    def _load_model(self, model_name: str) -> None:
        _quiet_huggingface()
        try:
            from sentence_transformers import SentenceTransformer
            import numpy as np
        except ImportError:
            print("  ! sentence-transformers non disponibile: uso il "
                  "proxy TF-IDF su n-grammi.", file=sys.stderr)
            return
        except Exception as exc:
            # Installazioni rotte (es. torch/numpy incompatibili)
            # sollevano errori diversi da ImportError: il ripiego
            # deve restare pulito anche in quel caso.
            print("  ! sentence-transformers non utilizzabile "
                  "(%s: %s): uso il proxy TF-IDF su n-grammi."
                  % (type(exc).__name__, exc), file=sys.stderr)
            return
        try:
            self.model = SentenceTransformer(model_name)
            emb = self.model.encode(
                self.docs, normalize_embeddings=True,
                show_progress_bar=False)
            self.matrix = np.asarray(emb, dtype="float32")
            self.np = np
            self.mode = "embeddings:%s" % model_name
        except Exception as exc:  # pragma: no cover
            print("  ! modello non caricato (%s): uso TF-IDF." % exc,
                  file=sys.stderr)
            self.model = None

    def _build_tfidf(self) -> None:
        self.vectors: List[Dict[str, float]] = []
        grams = [char_ngrams(d) for d in self.docs]
        df: Counter = Counter()
        for gram in grams:
            df.update(set(gram))
        n_docs = len(self.docs) or 1
        self.idf = {
            g: math.log((1 + n_docs) / (1 + n)) + 1.0
            for g, n in df.items()
        }
        for gram in grams:
            self.vectors.append(self._vectorize(gram))

    def _vectorize(self, grams: Iterable[str]) -> Dict[str, float]:
        counts = Counter(grams)
        vec = {
            g: (1.0 + math.log(c)) * self.idf.get(g, 1.0)
            for g, c in counts.items()
        }
        norm = math.sqrt(sum(v * v for v in vec.values())) or 1.0
        return {g: v / norm for g, v in vec.items()}

    def search(self, query: str) -> List[Tuple[int, float]]:
        if self.model is not None:
            emb = self.model.encode(
                [query], normalize_embeddings=True,
                show_progress_bar=False)
            sims = self.matrix @ self.np.asarray(emb[0], dtype="float32")
            pairs = [(i, float(s)) for i, s in enumerate(sims) if s > 0]
        else:
            qvec = self._vectorize(char_ngrams(query))
            pairs = []
            for i, vec in enumerate(self.vectors):
                small, big = (qvec, vec) if len(qvec) < len(vec) \
                    else (vec, qvec)
                sim = sum(v * big.get(g, 0.0) for g, v in small.items())
                if sim > 0:
                    pairs.append((i, sim))
        pairs.sort(key=lambda x: (-x[1], x[0]))
        return pairs


def reciprocal_rank_fusion(
        rankings: Sequence[Sequence[Tuple[int, float]]],
        k: int = 60, top_n: int = 10,
        weights: Optional[Sequence[float]] = None
        ) -> List[Tuple[int, float]]:
    """Fonde piu' liste ordinate con la formula RRF.

        score(d) = somma_i  w_i / (k + rank_i(d))

    Il rango parte da 1. Senza ``weights`` ogni lista pesa uguale
    (w_i = 1, RRF classico come in Elasticsearch); con la variante
    pesata ogni lista porta il proprio peso. Riferimento: Cormack
    et al. (2009); Elastic; Microsoft Learn.
    """
    scores: Dict[int, float] = {}
    for pos, ranking in enumerate(rankings):
        w = weights[pos] if weights else 1.0
        for rank, (doc_id, _score) in enumerate(ranking, start=1):
            scores[doc_id] = scores.get(doc_id, 0.0) + w / (k + rank)
    fused = sorted(scores.items(), key=lambda x: (-x[1], x[0]))
    return fused[:top_n]


def check_llms_txt(base: str, fetcher: Fetcher) -> Finding:
    """Verifica la presenza di /llms.txt (standard emergente).

    E' un indice in Markdown dei contenuti pensato per gli agenti
    IA (llmstxt.org): assente non e' un errore, quindi il rilievo
    negativo e' solo informativo.
    """
    url = urljoin(base, "/llms.txt")
    resp = fetcher.get(url)
    if resp is not None and resp.status_code == 200 \
            and resp.text.strip() \
            and "html" not in resp.headers.get("Content-Type", ""):
        return Finding(
            AREA_TECH, SEV_OK, "llms.txt presente",
            "%d righe." % len(resp.text.splitlines()), url=url,
            key="tech.llms.present",
            params={"n": len(resp.text.splitlines())})
    return Finding(
        AREA_TECH, SEV_INFO, "llms.txt assente",
        "Standard emergente (llmstxt.org): un indice in Markdown "
        "dei contenuti chiave pensato per gli agenti IA.",
        "Valuta di pubblicare /llms.txt con i contenuti chiave.",
        url=url, key="tech.llms.missing")


def _build_link_edges(good: Sequence[Page]) -> Tuple[
        Dict[str, Set[str]], Counter]:
    """Grafo dei link interni: archi in uscita e conteggio entranti."""
    by_url: Dict[str, Page] = {}
    for p in good:
        by_url.setdefault(norm_url(p.url), p)
        if p.final_url:
            by_url.setdefault(norm_url(p.final_url), p)

    edges: Dict[str, Set[str]] = {}
    incoming: Counter = Counter()
    for p in good:
        src = norm_url(p.url)
        outs: Set[str] = set()
        for target in p.internal_targets:
            dest = by_url.get(target)
            if dest is None:
                continue
            key = norm_url(dest.url)
            if key != src:
                outs.add(key)
                incoming[key] += 1
        edges[src] = outs
    return edges, incoming


def _bfs_depths(edges: Dict[str, Set[str]],
                home: str) -> Dict[str, int]:
    """Profondita' in click dalla home lungo i link interni."""
    if home not in edges:
        return {}
    depth = {home: 0}
    queue = [home]
    while queue:
        node = queue.pop(0)
        for dest in sorted(edges.get(node, ())):
            if dest not in depth:
                depth[dest] = depth[node] + 1
                queue.append(dest)
    return depth


def depth_distribution(pages: Sequence[Page],
                       base: str) -> Optional[Dict[str, object]]:
    """Distribuzione della profondita' di crawl (widget).

    Click dalla home lungo i link interni (stesso BFS del controllo
    sul grafo): bucket 0/1/2/3/4+ piu' le pagine non raggiungibili
    dai link, che arrivano solo dalla sitemap. None con meno di due
    pagine analizzabili.
    """
    good = [p for p in pages if p.ok]
    if len(good) < 2:
        return None
    edges, _incoming = _build_link_edges(good)
    depth = _bfs_depths(edges, norm_url(base))
    labels = ("0 (home)", "1 click", "2 click", "3 click",
              "4+ click")
    counts = [0, 0, 0, 0, 0]
    unreachable = 0
    for url in edges:
        d = depth.get(url)
        if d is None:
            unreachable += 1
        else:
            counts[min(d, 4)] += 1
    buckets = [{"label": label, "count": count}
               for label, count in zip(labels, counts)]
    buckets.append({"label": "solo da sitemap",
                    "count": unreachable})
    return {"pages": len(edges), "buckets": buckets}


# Grafo dell'architettura: dimensioni del canvas e tetto ai nodi.
# Canvas ampio e piu' iterazioni dalla v1.39.0: il disegno statico
# del referto deve restare leggibile anche con decine di nodi.
GRAPH_W, GRAPH_H = 780.0, 540.0


GRAPH_MAX_NODES = 60


GRAPH_LABEL_ALL = 20  # fino a qui si etichettano tutti i nodi


def _force_layout(count: int, links: Sequence[Tuple[int, int]],
                  width: float = GRAPH_W, height: float = GRAPH_H,
                  iterations: int = 150
                  ) -> List[Tuple[float, float]]:
    """Layout force-directed deterministico (Fruchterman-Reingold).

    Inizializzazione su un cerchio (niente casualita': stesso
    input, stesso disegno — testabile e riproducibile), repulsione
    k^2/d fra tutti i nodi, attrazione d^2/k lungo gli archi,
    raffreddamento geometrico. Il nodo 0 (la home) resta ancorato
    al centro. Riferimento: Fruchterman & Reingold (1991).
    """
    if count == 0:
        return []
    cx, cy = width / 2.0, height / 2.0
    if count == 1:
        return [(cx, cy)]
    radius = min(width, height) / 3.0
    pos = [[cx + radius * math.cos(2 * math.pi * i / count),
            cy + radius * math.sin(2 * math.pi * i / count)]
           for i in range(count)]
    pos[0] = [cx, cy]
    k = (width * height / count) ** 0.5
    temp = width / 8.0
    for _ in range(iterations):
        disp = [[0.0, 0.0] for _ in range(count)]
        for i in range(count):
            for j in range(i + 1, count):
                dx = pos[i][0] - pos[j][0]
                dy = pos[i][1] - pos[j][1]
                dist = max(0.01, (dx * dx + dy * dy) ** 0.5)
                force = k * k / dist
                disp[i][0] += dx / dist * force
                disp[i][1] += dy / dist * force
                disp[j][0] -= dx / dist * force
                disp[j][1] -= dy / dist * force
        for a, b in links:
            dx = pos[a][0] - pos[b][0]
            dy = pos[a][1] - pos[b][1]
            dist = max(0.01, (dx * dx + dy * dy) ** 0.5)
            force = dist * dist / k
            disp[a][0] -= dx / dist * force
            disp[a][1] -= dy / dist * force
            disp[b][0] += dx / dist * force
            disp[b][1] += dy / dist * force
        for i in range(1, count):  # la home (0) resta al centro
            dx, dy = disp[i]
            dist = max(0.01, (dx * dx + dy * dy) ** 0.5)
            step = min(dist, temp)
            pos[i][0] += dx / dist * step
            pos[i][1] += dy / dist * step
            pos[i][0] = min(width - 18.0, max(18.0, pos[i][0]))
            pos[i][1] = min(height - 14.0, max(14.0, pos[i][1]))
        temp *= 0.95
    return [(round(x, 1), round(y, 1)) for x, y in pos]


def link_graph_data(pages: Sequence[Page],
                    base: str) -> Optional[Dict[str, object]]:
    """Grafo dei link interni col layout gia' calcolato (widget).

    Nodi limitati a GRAPH_MAX_NODES (home per prima, poi i piu'
    linkati); archi solo fra nodi inclusi. Le posizioni vengono dal
    layout force deterministico: il referto HTML statico e la GUI
    disegnano lo stesso identico grafo senza JavaScript di layout.
    None con meno di due pagine analizzabili.
    """
    good = [p for p in pages if p.ok]
    if len(good) < 2:
        return None
    edges, incoming = _build_link_edges(good)
    home = norm_url(base)
    urls = sorted(edges, key=lambda u: (u != home,
                                        -incoming[u], u))
    urls = urls[:GRAPH_MAX_NODES]
    index = {u: i for i, u in enumerate(urls)}
    depth = _bfs_depths(edges, home)
    links: List[Tuple[int, int]] = []
    for src, outs in edges.items():
        if src not in index:
            continue
        for dest in sorted(outs):
            if dest in index:
                links.append((index[src], index[dest]))
    positions = _force_layout(len(urls), links)
    nodes = []
    for i, url in enumerate(urls):
        nodes.append({
            "url": url,
            "label": urlparse(url).path or "/",
            "incoming": incoming[url],
            "depth": depth.get(url),
            "home": url == home,
            "x": positions[i][0],
            "y": positions[i][1],
        })
    return {
        "width": GRAPH_W,
        "height": GRAPH_H,
        "total": len(edges),
        "nodes": nodes,
        "links": [{"source": a, "target": b} for a, b in links],
    }


def _squarify(values: Sequence[float], x: float, y: float,
              w: float, h: float
              ) -> List[Tuple[float, float, float, float]]:
    """Layout squarified deterministico: rettangoli (x, y, w, h).

    Algoritmo di Bruls-Huizing-van Wijk: righe greedy lungo il lato
    corto dello spazio residuo, estese finche' il rapporto d'aspetto
    peggiore migliora. I valori devono essere positivi (di norma in
    ordine decrescente, per la resa classica); l'output preserva
    l'ordine d'ingresso e riempie esattamente l'area data.
    """
    total = sum(values)
    if not values or total <= 0 or w <= 0 or h <= 0:
        return []
    scale = w * h / total
    areas = [v * scale for v in values]
    rects: List[Tuple[float, float, float, float]] = []
    i = 0
    while i < len(areas):
        across = w <= h  # spazio alto: la riga corre in orizzontale
        side = w if across else h

        def worst(row: Sequence[float]) -> float:
            s = sum(row)
            if s <= 0:
                return float("inf")
            t2 = (s / side) ** 2
            return max(t2 / min(row), max(row) / t2)

        row = [areas[i]]
        j = i + 1
        while j < len(areas) and worst(row + [areas[j]]) <= worst(row):
            row.append(areas[j])
            j += 1
        thick = sum(row) / side
        offset = 0.0
        for area in row:
            extent = area / thick
            if across:
                rects.append((x + offset, y, extent, thick))
            else:
                rects.append((x, y + offset, thick, extent))
            offset += extent
        if across:
            y += thick
            h -= thick
        else:
            x += thick
            w -= thick
        i = j
    return rects


def treemap_data(pages: Sequence[Page],
                 findings: Sequence[Finding],
                 width: float = 760.0, height: float = 420.0,
                 max_items: int = 40
                 ) -> Optional[Dict[str, object]]:
    """Treemap della superficie contenutistica (referto HTML).

    Ogni rettangolo e' una pagina analizzabile: area proporzionale
    alle parole indicizzabili, colore dalla gravita' peggiore dei
    rilievi che citano la pagina (critico > avvertenza > nessuno —
    i rilievi di sito senza URL non colorano nessuna pagina).
    Layout squarified deterministico calcolato qui nel core, come
    il force layout del grafo. None con meno di due pagine con
    testo; oltre ``max_items`` restano le pagine piu' estese.
    """
    good = [p for p in pages if p.ok and p.word_count > 0]
    if len(good) < 2:
        return None
    crit = {f.url for f in findings
            if f.url and f.severity == SEV_CRITICAL}
    warn = {f.url for f in findings
            if f.url and f.severity == SEV_WARNING}
    good = sorted(good, key=lambda p: (-p.word_count,
                                       norm_url(p.url)))
    shown = good[:max_items]
    rects = _squarify([float(p.word_count) for p in shown],
                      0.0, 0.0, width, height)
    items: List[Dict[str, object]] = []
    for page, (rx, ry, rw, rh) in zip(shown, rects):
        if page.url in crit or (page.final_url
                                and page.final_url in crit):
            severity = "critical"
        elif page.url in warn or (page.final_url
                                  and page.final_url in warn):
            severity = "warning"
        else:
            severity = "ok"
        path = urlparse(page.url).path or "/"
        items.append({
            "url": page.url,
            "label": path if len(path) <= 30 else path[:27] + "...",
            "words": page.word_count,
            "chunks": len(page.chunks),
            "severity": severity,
            "x": round(rx, 1), "y": round(ry, 1),
            "w": round(rw, 1), "h": round(rh, 1),
        })
    return {"width": width, "height": height,
            "total": len([p for p in pages if p.ok]),
            "shown": len(items), "items": items}

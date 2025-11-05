"""City extraction using hybrid Regex + optional spaCy NER."""

import re
from typing import Optional, Tuple, List

try:
    import spacy  # type: ignore
except Exception:
    spacy = None  # lazy handled

from config import (
    CITY_SECTION_MAX_LINES,
    USE_SPACY_CITIES,
    SPACY_CITY_MODELS,
)


class CityExtractor:
    """Extract loading and unloading cities from raw PDF text.

    Strategy:
    - Locate sections for loading/unloading.
    - Try regex to get city; fallback to spaCy NER if enabled and available.
    """

    def __init__(self, use_spacy: bool = True, lang_models: Optional[List[str]] = None) -> None:
        self.use_spacy = use_spacy and USE_SPACY_CITIES
        self.lang_models = lang_models or SPACY_CITY_MODELS
        self._nlp_pipelines = None  # lazy-loaded dict[str, Any]

        # Precompile regex patterns
        self._pattern_pl_zip_city = re.compile(
            r"\bPL\s?\d{2}-\d{3}\s+([A-Za-zĄĆĘŁŃÓŚŻŹąćęłńóśżź .\-']+(?:\s+b\.\s+[A-Za-zĄĆĘŁŃÓŚŻŹąćęłńóśżź .\-']+)?)",
            re.IGNORECASE,
        )
        self._pattern_de_zip_city = re.compile(
            r"\bD\s?-?\d{4,5}\s+([A-Za-zÄÖÜäöüẞß .\-']+)",
            re.IGNORECASE,
        )
        # Bare postal codes without country prefix
        self._pattern_pl_bare_zip_city = re.compile(
            r"\b\d{2}-\d{3}\s+([A-Za-zĄĆĘŁŃÓŚŻŹąćęłńóśżź .\-']+(?:\s+b\.\s+[A-Za-zĄĆĘŁŃÓŚŻŹąćęłńóśżź .\-']+)?)"
        )
        self._pattern_de_bare_zip_city = re.compile(
            r"\b\d{5}\s+([A-Za-zÄÖÜäöüẞß .\-']+)"
        )
        self._pattern_city_only = re.compile(
            r"\b([A-ZĄĆĘŁŃÓŚŻŹÄÖÜ][A-Za-zĄĆĘŁŃÓŚŻŹÄÖÜäöüẞß .\-']{2,}(?:\s+b\.\s+[A-Za-z .\-']+)?)\b"
        )
        # Common street indicators (PL/DE)
        self._street_tokens = {
            'str.', 'straße', 'strasse', 'allee', 'ul.', 'ulica', 'platz', 'ring', 'weg', 'gasse', 'am', 'an der'
        }

    def extract_from_text(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """Return (miejsce_zaladunku, miejsce_rozladunku) from full PDF text."""
        loading_block = self._extract_section(
            text, ["Miejsce załadunku", "Miejsce zaladunku"], two_line_tail=["załadunku", "zaladunku"]
        )
        unloading_block = self._extract_section(
            text, ["Miejsce rozładunku", "Miejsce rozladunku"], two_line_tail=["rozładunku", "rozladunku"]
        )

        loading_city = self._choose_best(
            self._regex_city(loading_block), self._ner_city(loading_block)
        ) if loading_block else None

        # Unloading can contain multiple places; collect and join with '-'
        if unloading_block:
            unloading_list = self._extract_cities_list(unloading_block)
            if unloading_list:
                unloading_city = "-".join(unloading_list)
            else:
                unloading_city = self._choose_best(
                    self._regex_city(unloading_block), self._ner_city(unloading_block)
                )
        else:
            unloading_city = None

        # Global fallback if section-based extraction failed
        if loading_city is None or unloading_city is None:
            candidates = self._find_global_city_candidates(text)
            if loading_city is None and candidates:
                loading_city = candidates[0]
            if unloading_city is None and candidates:
                unloading_city = candidates[-1]

        return loading_city, unloading_city

    def extract_regex_only(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """Regex-only extraction ignoring spaCy completely."""
        loading_block = self._extract_section(
            text, ["Miejsce załadunku", "Miejsce zaladunku"], two_line_tail=["załadunku", "zaladunku"]
        )
        unloading_block = self._extract_section(
            text, ["Miejsce rozładunku", "Miejsce rozladunku"], two_line_tail=["rozładunku", "rozladunku"]
        )

        loading_city = self._regex_city(loading_block) if loading_block else None
        unloading_city = self._regex_city(unloading_block) if unloading_block else None

        if loading_city is None or unloading_city is None:
            candidates = self._find_global_city_candidates(text)
            if loading_city is None and candidates:
                loading_city = candidates[0]
            if unloading_city is None and candidates:
                unloading_city = candidates[-1]

        return loading_city, unloading_city

    def extract_ner_only(self, text: str) -> Tuple[Optional[str], Optional[str]]:
        """spaCy-only extraction ignoring regex preferences."""
        loading_block = self._extract_section(
            text, ["Miejsce załadunku", "Miejsce zaladunku"], two_line_tail=["załadunku", "zaladunku"]
        )
        unloading_block = self._extract_section(
            text, ["Miejsce rozładunku", "Miejsce rozladunku"], two_line_tail=["rozładunku", "rozladunku"]
        )

        loading_city = self._ner_city(loading_block) if loading_block else None
        unloading_city = self._ner_city(unloading_block) if unloading_block else None

        if loading_city is None or unloading_city is None:
            ner_candidates = self._find_global_ner_candidates(text)
            if loading_city is None and ner_candidates:
                loading_city = ner_candidates[0]
            if unloading_city is None and ner_candidates:
                unloading_city = ner_candidates[-1]

        return loading_city, unloading_city

    def compare_methods(self, text: str):
        """Return a dict with regex-only, spacy-only, and current hybrid outputs."""
        regex_load, regex_unload = self.extract_regex_only(text)
        ner_load, ner_unload = self.extract_ner_only(text)
        hybrid_load, hybrid_unload = self.extract_from_text(text)
        return {
            'regex': {
                'miejsce_zaladunku': regex_load,
                'miejsce_rozladunku': regex_unload,
            },
            'spacy': {
                'miejsce_zaladunku': ner_load,
                'miejsce_rozladunku': ner_unload,
            },
            'hybrid': {
                'miejsce_zaladunku': hybrid_load,
                'miejsce_rozladunku': hybrid_unload,
            },
        }

    def ner_diagnostics(self):
        """Return spaCy availability and which models are loaded vs missing."""
        status = {
            'spacy_available': spacy is not None,
            'requested_models': self.lang_models,
            'loaded_models': [],
            'missing_models': [],
        }
        if spacy is None or not self.use_spacy:
            status['missing_models'] = self.lang_models
            return status
        # Ensure attempted load
        pipes = self._ensure_models()
        loaded_names = []
        for p in pipes:
            try:
                loaded_names.append(p.meta.get('name') or p.meta.get('lang'))
            except Exception:
                loaded_names.append('unknown')
        status['loaded_models'] = loaded_names
        status['missing_models'] = [m for m in self.lang_models if all(m not in (n or '') for n in loaded_names)]
        return status

    def _extract_section(self, text: str, header_keywords: List[str], max_lines: int = None, two_line_tail: Optional[List[str]] = None) -> str:
        """Extract block of text after any header in header_keywords up to max_lines or next header."""
        if not text:
            return ""
        max_lines = max_lines or CITY_SECTION_MAX_LINES

        # Build header regex (case-insensitive, diacritics variants provided by caller)
        header_regex = re.compile(r"|".join([re.escape(h) for h in header_keywords]), re.IGNORECASE)

        lines = text.splitlines()
        for idx, line in enumerate(lines):
            if header_regex.search(line):
                # capture following lines up to max_lines or until next header-like marker
                end_idx = min(len(lines), idx + 1 + max_lines)
                block_lines = []
                for j in range(idx + 1, end_idx):
                    if self._looks_like_header(lines[j]):
                        break
                    block_lines.append(lines[j])
                return "\n".join(block_lines).strip()

        # Handle split headers like "Miejsce" on one line and "zaladunku/rozladunku" on the next line
        if two_line_tail:
            tail_regex = re.compile(r"|".join([re.escape(t) for t in two_line_tail]), re.IGNORECASE)
            for idx in range(len(lines) - 1):
                if re.search(r"\bMiejsce\b", lines[idx], re.IGNORECASE) and tail_regex.search(lines[idx + 1]):
                    start = idx + 2
                    end_idx = min(len(lines), start + max_lines)
                    block_lines = []
                    for j in range(start, end_idx):
                        if self._looks_like_header(lines[j]):
                            break
                        block_lines.append(lines[j])
                    return "\n".join(block_lines).strip()

        return ""

    def _looks_like_header(self, line: str) -> bool:
        tokens = [
            "Miejsce załadunku",
            "Miejsce zaladunku",
            "Miejsce rozładunku",
            "Miejsce rozladunku",
            "Zlecenie",
            "Samochód",
            "Samochod",
            "Vereinbarter Frachtpreis",
            "Termin rozladunku",
        ]
        pattern = re.compile(r"|".join([re.escape(t) for t in tokens]), re.IGNORECASE)
        return bool(pattern.search(line))

    def _regex_city(self, section: str) -> Optional[str]:
        if not section:
            return None

        # Prefer lines with PL/DE postal code + city (with or without country prefix)
        for line in section.splitlines():
            line = line.strip()
            if not line:
                continue
            # First try zip+city patterns regardless of digit ratio
            for pattern in (
                self._pattern_pl_zip_city,
                self._pattern_de_zip_city,
                self._pattern_pl_bare_zip_city,
                self._pattern_de_bare_zip_city,
            ):
                m = pattern.search(line)
                if m:
                    return self._clean_city(m.group(1))

            # Ignore overly numeric lines (likely addresses or IDs)
            if sum(c.isdigit() for c in line) > max(3, len(line) // 3):
                continue

        # Fallback: any reasonable city-looking token
        for line in section.splitlines():
            line = line.strip()
            if not line:
                continue
            # Skip street-like lines when no ZIP present
            if self._looks_like_street(line):
                continue
            m = self._pattern_city_only.search(line)
            if m:
                return self._clean_city(m.group(1))

        return None

    def _ner_city(self, section: str) -> Optional[str]:
        if not section or not self.use_spacy:
            return None
        nlp_pipes = self._ensure_models()
        if not nlp_pipes:
            return None

        # If the section already contains a ZIP+city, trust regex result
        zip_city = self._regex_city(section)
        if zip_city:
            return zip_city

        scored: List[Tuple[float, str]] = []
        for nlp in nlp_pipes:
            try:
                doc = nlp(section)
                for ent in doc.ents:
                    score = self._score_ner_candidate(ent)
                    if score <= 0:
                        continue
                    scored.append((score, self._clean_city(ent.text)))
            except Exception:
                continue

        if not scored:
            return None
        scored.sort(key=lambda x: (x[0], len(x[1])), reverse=True)
        return scored[0][1]

    def _extract_cities_list(self, section: str) -> List[str]:
        """Extract multiple cities from a section, ordered top-to-bottom, unique.
        Prefers ZIP+city patterns. Falls back to NER-scored candidates if no ZIP found.
        """
        lines = section.splitlines()
        found: List[str] = []
        seen = set()

        # First pass: ZIP+city matches (with/without country prefix)
        zip_patterns = (
            self._pattern_pl_zip_city,
            self._pattern_de_zip_city,
            self._pattern_pl_bare_zip_city,
            self._pattern_de_bare_zip_city,
        )
        for line in lines:
            s = line.strip()
            if not s:
                continue
            for pat in zip_patterns:
                m = pat.search(s)
                if m:
                    city = self._clean_city(m.group(1))
                    if city and city not in seen:
                        seen.add(city)
                        found.append(city)
                    break

        if found:
            return found

        # Second pass: city-only lines (skip street-like), one per line
        for line in lines:
            s = line.strip()
            if not s or self._looks_like_street(s):
                continue
            m = self._pattern_city_only.search(s)
            if m:
                city = self._clean_city(m.group(1))
                if city and city not in seen:
                    seen.add(city)
                    found.append(city)

        if found:
            return found

        # Last resort: NER candidates scored; keep order as they appear
        nlp_pipes = self._ensure_models()
        if not nlp_pipes:
            return []
        scored_seq: List[Tuple[float, str]] = []
        for nlp in nlp_pipes:
            try:
                doc = nlp(section)
                for ent in doc.ents:
                    score = self._score_ner_candidate(ent)
                    if score <= 0:
                        continue
                    city = self._clean_city(ent.text)
                    scored_seq.append((score, city))
            except Exception:
                continue

        # Keep in reading order, but drop low scores and duplicates
        result: List[str] = []
        for score, city in scored_seq:
            if score <= 0:
                continue
            if city and city not in seen:
                seen.add(city)
                result.append(city)
        return result

    def _clean_city(self, raw: str) -> str:
        if not raw:
            return ""
        s = raw
        # Remove postal codes and country prefixes
        s = re.sub(r"\b(?:PL|D|D-)\s?\d{2}-?\d{3,5}\s*", "", s, flags=re.IGNORECASE)
        s = re.sub(r"\b\d{2}-?\d{3,5}\b", "", s)

        # Split off notes or trailing annotations
        split_tokens = ["na zlec", "auftr", "auftrag", "attn"]
        for tok in split_tokens:
            s = s.split(tok, 1)[0]
        # Also cut on separators
        s = re.split(r"[;,|]", s)[0]

        # Normalize whitespace
        s = re.sub(r"\s+", " ", s).strip()

        # Title-case but keep dots and umlauts relatively intact
        def smart_title(t: str) -> str:
            parts = [p.capitalize() if not p.endswith('.') else p[:-1].capitalize() + '.' for p in t.split(' ')]
            return " ".join(parts)

        # Preserve common abbrev like 'b.'
        s = smart_title(s)
        return s

    def _looks_like_street(self, line: str) -> bool:
        low = line.lower()
        return any(tok in low for tok in self._street_tokens)

    def _score_ner_candidate(self, ent) -> float:
        """Score spaCy entity: prefer cities, penalize streets/orgs, reject digits."""
        label = ent.label_.upper()
        text_val = ent.text.strip()
        if any(ch.isdigit() for ch in text_val):
            return 0.0
        if self._looks_like_street(text_val):
            return 0.0
        base = 0.0
        if label in {"GPE", "LOC", "PLACE"}:
            base = 1.0
        elif label == "ORG":
            base = 0.2
        else:
            base = 0.1
        # Prefer slash-composite city names slightly; prefer longer names up to a cap
        if '/' in text_val:
            base += 0.2
        base += min(len(text_val) / 40.0, 0.3)
        return base

    def _choose_best(self, primary: Optional[str], secondary: Optional[str]) -> Optional[str]:
        return primary or secondary

    def _ensure_models(self):
        if not self.use_spacy or spacy is None:
            return []
        if self._nlp_pipelines is not None:
            return self._nlp_pipelines

        pipelines = []
        for model_name in self.lang_models:
            try:
                pipelines.append(spacy.load(model_name))
            except Exception:
                # Skip missing models silently; regex will still work
                continue
        self._nlp_pipelines = pipelines
        return self._nlp_pipelines

    def _find_global_city_candidates(self, text: str) -> List[str]:
        """Find all postal-code+city or city-only candidates in order of appearance (best-effort)."""
        if not text:
            return []
        candidates: List[str] = []
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            # Prefer PL/DE code + city (with or without country prefix)
            for pattern in (
                self._pattern_pl_zip_city,
                self._pattern_de_zip_city,
                self._pattern_pl_bare_zip_city,
                self._pattern_de_bare_zip_city,
            ):
                m = pattern.search(line)
                if m:
                    candidates.append(self._clean_city(m.group(1)))
                    break
            else:
                # consider city-only as a last resort
                m2 = self._pattern_city_only.search(line)
                if m2:
                    candidates.append(self._clean_city(m2.group(1)))
        # Deduplicate preserving order
        seen = set()
        unique: List[str] = []
        for c in candidates:
            if c and c not in seen:
                seen.add(c)
                unique.append(c)
        return unique

    def _find_global_ner_candidates(self, text: str) -> List[str]:
        """Collect spaCy LOC/GPE candidates from the whole text in order of appearance."""
        nlp_pipes = self._ensure_models()
        if not nlp_pipes:
            return []
        found: List[str] = []
        for nlp in nlp_pipes:
            try:
                doc = nlp(text)
                for ent in doc.ents:
                    if ent.label_.upper() in {"LOC", "GPE", "PLACE"}:
                        val = ent.text.strip()
                        if any(ch.isdigit() for ch in val):
                            continue
                        found.append(self._clean_city(val))
            except Exception:
                continue
        # Deduplicate preserving order
        seen = set()
        unique: List[str] = []
        for c in found:
            if c and c not in seen:
                seen.add(c)
                unique.append(c)
        return unique



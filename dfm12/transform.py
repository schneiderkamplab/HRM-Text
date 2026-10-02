"""Recoverable text transformations with an explicit target language."""
import random
import re

from .io import digest

PROMPTS = {
    "de": ("Deutsch", "Korrigiere den beschädigten Text.", "Setze den Text fort; gib nur die fehlende Fortsetzung aus.", "Fülle <GAP> aus; gib nur den fehlenden Text aus.", "Bringe die Absätze in die ursprüngliche Reihenfolge; gib den vollständigen Text ohne Nummerierung aus."),
    "fr": ("français", "Corrige le texte endommagé.", "Continue le texte ; donne uniquement la suite manquante.", "Remplis <GAP> ; donne uniquement le texte manquant.", "Remets les paragraphes dans leur ordre original ; donne le texte complet sans numérotation."),
    "es": ("español", "Corrige el texto dañado.", "Continúa el texto; devuelve solo la continuación que falta.", "Completa <GAP>; devuelve solo el texto que falta.", "Ordena los párrafos en su orden original; devuelve el texto completo sin numeración."),
    "it": ("italiano", "Correggi il testo danneggiato.", "Continua il testo; fornisci solo la continuazione mancante.", "Completa <GAP>; fornisci solo il testo mancante.", "Riordina i paragrafi nell'ordine originale; fornisci il testo completo senza numerazione."),
    "cs": ("čeština", "Oprav poškozený text.", "Pokračuj v textu; napiš pouze chybějící pokračování.", "Doplň <GAP>; napiš pouze chybějící text.", "Seřaď odstavce do původního pořadí; napiš celý text bez číslování."),
    "pt_pt": ("português europeu", "Corrige o texto danificado.", "Continua o texto; apresenta apenas a continuação em falta.", "Preenche <GAP>; apresenta apenas o texto em falta.", "Ordena os parágrafos pela ordem original; apresenta o texto completo sem numeração."),
    "fi": ("suomi", "Korjaa vioittunut teksti.", "Jatka tekstiä; anna vain puuttuva jatko.", "Täytä <GAP>; anna vain puuttuva teksti.", "Järjestä kappaleet alkuperäiseen järjestykseen; anna koko teksti ilman numerointia."),
    "et": ("eesti keel", "Paranda vigane tekst.", "Jätka teksti; esita ainult puuduv jätk.", "Täida <GAP>; esita ainult puuduv tekst.", "Pane lõigud algsesse järjekorda; esita kogu tekst ilma nummerduseta."),
    "ca": ("català", "Corregeix el text malmès.", "Continua el text; dona només la continuació que falta.", "Omple <GAP>; dona només el text que falta.", "Ordena els paràgrafs en l'ordre original; dona el text complet sense numeració."),
    "el": ("ελληνικά", "Διόρθωσε το αλλοιωμένο κείμενο.", "Συνέχισε το κείμενο· δώσε μόνο τη συνέχεια που λείπει.", "Συμπλήρωσε το <GAP>· δώσε μόνο το κείμενο που λείπει.", "Βάλε τις παραγράφους στην αρχική σειρά· δώσε ολόκληρο το κείμενο χωρίς αρίθμηση."),
    "ro": ("română", "Corectează textul deteriorat.", "Continuă textul; oferă doar continuarea lipsă.", "Completează <GAP>; oferă doar textul lipsă.", "Ordonează paragrafele în ordinea originală; oferă textul complet fără numerotare."),
    "uk": ("українська", "Виправ пошкоджений текст.", "Продовж текст; подай лише відсутнє продовження.", "Заповни <GAP>; подай лише відсутній текст.", "Розташуй абзаци в початковому порядку; подай повний текст без нумерації."),
    "nl": ("Nederlands", "Herstel de beschadigde tekst.", "Vervolg de tekst; geef alleen het ontbrekende vervolg.", "Vul <GAP> in; geef alleen de ontbrekende tekst.", "Zet de alinea's in de oorspronkelijke volgorde; geef de volledige tekst zonder nummers."),
    "nb": ("norsk bokmål", "Rett feilene i teksten.", "Fortsett teksten; skriv bare fortsettelsen.", "Fyll inn <GAP>; skriv bare teksten som mangler.", "Sett avsnittene i opprinnelig rekkefølge; skriv hele teksten uten nummerering."),
    "nn": ("norsk nynorsk", "Rett feila i teksten.", "Hald fram teksten; skriv berre framhaldet.", "Fyll inn <GAP>; skriv berre teksten som manglar.", "Set avsnitta i opphavleg rekkjefølgje; skriv heile teksten utan nummerering."),
    "sv": ("svenska", "Rätta felen i texten.", "Fortsätt texten; skriv bara fortsättningen.", "Fyll i <GAP>; skriv bara den saknade texten.", "Ordna styckena i ursprunglig ordning; skriv hela texten utan numrering."),
    "is": ("íslenska", "Leiðréttu villurnar í textanum.", "Haltu áfram með textann; skrifaðu aðeins framhaldið.", "Fylltu í <GAP>; skrifaðu aðeins textann sem vantar.", "Raðaðu efnisgreinunum í upprunalega röð; skrifaðu allan textann án númerunar."),
    "fo": ("føroyskt", "Rætta villurnar í tekstinum.", "Halt fram við tekstinum; skriva bert framhaldið.", "Fyll út <GAP>; skriva bert tekstin, sum vantar.", "Set brotini í upprunaliga røð; skriva allan tekstin uttan tøl."),
    "pl": ("polski", "Popraw błędy w tekście.", "Dokończ tekst; podaj tylko brakujący dalszy ciąg.", "Uzupełnij <GAP>; podaj tylko brakujący tekst.", "Uporządkuj akapity w pierwotnej kolejności; podaj cały tekst bez numeracji."),
}


def window(text, seed, max_chars=8000):
    paragraphs = [p.strip() for p in re.split(r"\n\s*\n", text) if p.strip()]
    if not paragraphs:
        return ""
    rng = random.Random(seed)
    start = rng.randrange(len(paragraphs))
    chosen = []
    for p in paragraphs[start:]:
        if len(p) > max_chars:
            if not chosen:
                sentences = re.split(r"(?<=[.!?])\s+", p)
                offset = rng.randrange(len(sentences))
                for sentence in sentences[offset:]:
                    if sum(len(x) + 1 for x in chosen) + len(sentence) > max_chars:
                        break
                    chosen.append(sentence)
                return " ".join(chosen)
            break
        if sum(len(x) + 2 for x in chosen) + len(p) > max_chars:
            break
        chosen.append(p)
    return "\n\n".join(chosen)


def transform(text, lang, task, provenance, seed=20260924):
    if len(text.strip()) < 250 or "<GAP>" in text:
        raise ValueError("short_or_reserved_marker")
    key = digest([text, lang, task, seed])
    rng = random.Random(int(key[:16], 16))
    name, denoise, prefix, span, reorder = PROMPTS[lang]
    if task == "denoising":
        chars = list(text)
        positions = [i for i in range(1, len(chars) - 1) if chars[i].isalpha()]
        for pos in rng.sample(positions, min(len(positions), max(1, len(positions) // 50))):
            chars[pos] = chars[pos].swapcase() if rng.random() < .5 else ""
        corrupted = "".join(chars)
        if corrupted == text:
            raise ValueError("unchanged_corruption")
        instruction, answer = denoise + "\n\n" + corrupted, text
    elif task in {"prefix-continuation", "span-filling"}:
        boundaries = [m.start() for m in re.finditer(r"\s+", text)]
        if len(boundaries) < 20:
            raise ValueError("too_few_words")
        start = boundaries[rng.randrange(len(boundaries) // 4, len(boundaries) // 2)]
        if task == "prefix-continuation":
            instruction, answer = prefix + "\n\n" + text[:start], text[start:].strip()
        else:
            end = boundaries[min(len(boundaries) - 1, boundaries.index(start) + max(3, len(boundaries) // 10))]
            instruction, answer = span + "\n\n" + text[:start] + " <GAP> " + text[end:].lstrip(), text[start:end].strip()
    elif task == "paragraph-reordering":
        parts = [p for p in text.split("\n\n") if p.strip()]
        if len(parts) < 3 or len(set(parts)) != len(parts):
            raise ValueError("not_enough_distinct_paragraphs")
        order = list(range(len(parts)))
        rng.shuffle(order)
        if order == list(range(len(parts))):
            order = order[1:] + order[:1]
        instruction = reorder + "\n\n" + "\n\n".join(f"[{i+1}] {parts[j]}" for i, j in enumerate(order))
        answer = text
    else:
        raise ValueError(task)
    return {"id": key, "language": lang, "task": task,
            "messages": [{"role": "user", "content": f"({name}) {instruction}"},
                         {"role": "assistant", "content": answer}],
            "provenance": provenance, "audit_context": {"original": text, "seed": seed}}

"""
Prompt templates for classification and generation.

All texts are assembled per the profile's `language`. The generation
prompt is built in this exact block order:

1. role_prompt (writer's role)
2. organization rules
3. reserved context block (empty in v1)
4. the current request
5. the top precedents as few-shot examples
6. form constraints (greeting, signature, ready-to-send answer)
"""

LANGUAGE_INSTRUCTIONS = {
    "en": "Answer in English.",
    "fr": "Réponds en français.",
    "de": "Antworte auf Deutsch.",
}


def _language_line(language):
    return LANGUAGE_INSTRUCTIONS.get(language, LANGUAGE_INSTRUCTIONS["en"])


def classification_prompt(
    profile_language, type_name, categories, request_subject, request_body, reply_body
):
    """Step 2 — classify a reply into the type's answer categories."""
    if profile_language == "de":
        header = (
            f"Klassifiziere die folgende Antwort auf eine Anfrage vom Typ "
            f'"{type_name}" in genau eine der Kategorien.\n'
        )
        instr = (
            "Antworte AUSSCHLIESSLICH mit einem JSON-Objekt der Form "
            '{"category": "<kategorie>"}. Keine Erklärung, kein sonstiger Text.\n'
            "Kategorien:\n"
        )
        example = (
            'Beispiel: {"category": "%s"}\n' % (categories[0] if categories else "other")
        )
        req = "Anfrage:\n"
        rep = "Antwort:\n"
    elif profile_language == "fr":
        header = (
            f"Classe la réponse suivante à une demande de type "
            f"« {type_name} » dans exactement une des catégories.\n"
        )
        instr = (
            "Réponds UNIQUEMENT avec un objet JSON de la forme "
            '{"category": "<categorie>"}. Aucune explication, aucun autre texte.\n'
            "Catégories :\n"
        )
        example = (
            'Exemple : {"category": "%s"}\n' % (categories[0] if categories else "other")
        )
        req = "Demande :\n"
        rep = "Réponse :\n"
    else:
        header = (
            f"Classify the following reply to a request of type "
            f'"{type_name}" into exactly one of the categories.\n'
        )
        instr = (
            "Answer ONLY with a JSON object of the form "
            '{"category": "<category>"}. No explanation, no other text.\n'
            "Categories:\n"
        )
        example = (
            'Example: {"category": "%s"}\n' % (categories[0] if categories else "other")
        )
        req = "Request:\n"
        rep = "Reply:\n"

    lines = [header, instr]
    lines.extend(f"- {c}\n" for c in categories)
    lines.append(example)
    lines.append("\n")
    lines.append(f"{req}Betreff: {request_subject}\n{request_body}\n\n" if profile_language == "de" else "")
    if profile_language == "de":
        lines[-1] = f"{req}Betreff: {request_subject}\n{request_body}\n\n"
    elif profile_language == "fr":
        lines.append(f"{req}Objet : {request_subject}\n{request_body}\n\n")
    else:
        lines.append(f"{req}Subject: {request_subject}\n{request_body}\n\n")
    lines.append(f"{rep}{reply_body}\n")
    return "".join(lines)


def _case_block(language, index, request_summary, reply_text):
    if language == "de":
        return (
            f"Ähnlicher Fall {index}:\n"
            f"Anfrage:\n{request_summary}\n\n"
            f"Tatsächlich gesendete Antwort:\n{reply_text}\n\n"
        )
    if language == "fr":
        return (
            f"Cas similaire {index} :\n"
            f"Demande :\n{request_summary}\n\n"
            f"Réponse réellement envoyée :\n{reply_text}\n\n"
        )
    return (
        f"Similar case {index}:\n"
        f"Request:\n{request_summary}\n\n"
        f"Actually sent reply:\n{reply_text}\n\n"
    )


def _context_block(language, context_items):
    """Reserved context block — empty in v1 (extension seam)."""
    if not context_items:
        return ""
    if language == "de":
        head = "Relevanter Kontext:\n"
    elif language == "fr":
        head = "Contexte pertinent :\n"
    else:
        head = "Relevant context:\n"
    return head + "\n".join(f"- {item}" for item in context_items) + "\n\n"


def _form_block(language, greeting, signature, recipient_name):
    if language == "de":
        lines = [
            "Formale Anforderungen:\n",
            f"- Verwende die Anredeform (Du/Sie): \"{greeting}\".\n",
        ]
        if recipient_name:
            lines.append(f"- Beginne mit einer Anrede an {recipient_name}.\n")
        lines.append(
            "- Schreibe eine vollständige, versandfertige Antwort. "
            "Erfinde nichts: nutze nur dieMitgliedschaft und die ähnlichen Fälle. "
            "Nenne keine Fakten, die nicht in den Regeln oder Fällen stehen.\n"
        )
        lines.append(f"- Schließe mit dieser Signatur:\n{signature}\n")
    elif language == "fr":
        lines = [
            "Exigences de forme :\n",
            f"- Utilise la formule de politesse : « {greeting} ».\n",
        ]
        if recipient_name:
            lines.append(f"- Commence par une salutation à {recipient_name}.\n")
        lines.append(
            "- Rédige une réponse complète, prête à envoyer. "
            "N'invente rien : utilise uniquement les règles et les cas "
            "similaires.\n"
        )
        lines.append(f"- Termine par cette signature :\n{signature}\n")
    else:
        lines = [
            "Formal requirements:\n",
            f'- Use the required politeness form: "{greeting}".\n',
        ]
        if recipient_name:
            lines.append(f"- Open with a greeting to {recipient_name}.\n")
        lines.append(
            "- Write a complete, ready-to-send reply. Invent nothing: "
            "use only the rules and the similar cases.\n"
        )
        lines.append(f"- Close with this signature:\n{signature}\n")
    return "".join(lines)


def _request_block(language, request_text, recipient_name, request_date):
    label = {"de": "Aktuelle Anfrage", "fr": "Demande actuelle"}.get(
        language, "Current request"
    )
    lines = [f"{label}:\n{request_text}\n"]
    details = []
    if recipient_name:
        key = {"de": "Empfänger", "fr": "Destinataire"}.get(
            language, "Recipient"
        )
        details.append(f"{key}: {recipient_name}")
    if request_date:
        key = {"de": "Datum", "fr": "Date"}.get(language, "Date")
        details.append(f"{key}: {request_date}")
    if details:
        lines.append("  (" + ", ".join(details) + ")\n")
    lines.append("\n")
    return "".join(lines)


def generation_prompt(
    profile_language,
    role_prompt,
    organization_rules,
    request_text,
    precedents,
    greeting,
    signature,
    recipient_name="",
    request_date="",
    context_items=None,
):
    """Step 3 — assemble the full generation prompt."""
    blocks = [role_prompt.strip() + "\n\n"]
    if organization_rules and organization_rules.strip():
        if profile_language == "de":
            head = "Regeln des Vereins:\n"
        elif profile_language == "fr":
            head = "Règles de l'organisation :\n"
        else:
            head = "Organization rules:\n"
        blocks.append(head + organization_rules.strip() + "\n\n")
    blocks.append(_context_block(profile_language, context_items or []))
    blocks.append(
        _request_block(profile_language, request_text, recipient_name, request_date)
    )
    for i, precedent in enumerate(precedents, start=1):
        blocks.append(
            _case_block(profile_language, i, precedent["request"], precedent["reply"])
        )
    blocks.append(
        _form_block(profile_language, greeting, signature, recipient_name)
    )
    blocks.append(_language_line(profile_language) + "\n")
    return "".join(blocks)

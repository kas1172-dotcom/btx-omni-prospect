"""Conservative lexical checks, not a claim of semantic entailment verification."""
import json
import re

GENERAL_FACTS = {
    'capital of france': 'Paris is the capital of France.',
    'naics 3364': 'NAICS 3364 covers Aerospace Product and Parts Manufacturing.',
}
COMMON = {'I', 'A', 'An', 'The', 'This', 'That', 'These', 'Those', 'It', 'Its', 'We', 'You', 'Your', 'Our', 'Yes', 'No', 'Hi', 'Hello', 'What', 'How', 'Why', 'When', 'Where', 'Which', 'Who', 'If', 'In', 'On', 'At', 'For', 'From', 'To', 'By', 'With', 'Without', 'As', 'And', 'But', 'Or', 'Neither', 'Both', 'Public', 'Sources', 'BTX', 'Data', 'Coverage', 'Sample', 'Open', 'Select', 'Check', 'Try', 'Ask', 'General', 'Knowledge', 'Mix', 'Cook', 'Add', 'Serve', 'Let', 'Heat', 'Pour', 'Turn', 'Next', 'First', 'Second', 'Third', 'Not', 'PWIN', 'NAICS', 'Omni', 'Action', 'Actions', 'There', 'Here', 'Available', 'Recorded', 'Unknown', 'Leadership', 'Meetings'}


def violations(answer, question, reads):
    issues = []
    facts = question + '\n' + json.dumps(reads, default=str)
    words = set(re.findall(r"[\w'-]+", facts.casefold()))
    # Check formatted amounts, counts, date components and percentages without rounding.
    numbers = lambda text: set(re.findall(r'(?<!\w)\d+(?:[,.]\d+)*(?:%|\b)', text))
    normalized = lambda values: {x.replace(',', '') for x in values}
    if not normalized(numbers(answer)) <= normalized(numbers(facts)):
        issues.append('Unsupported number, date, amount or percentage')
    visible = re.sub(r'\]\([^)]*\)', ']', answer)
    entities = set(re.findall(r'\b[A-Z][A-Za-z0-9_-]*\b', visible)) - COMMON - {'Each', 'Lead', 'Today'}
    if any(name.casefold() not in words for name in entities):
        issues.append('Unsupported name or capitalized entity')
    if re.search(r"\b(?:I(?:'ve| have)?|we(?:'ve| have)?)\s+(?:successfully\s+)?(?:sent|updated|deleted|saved|created|approved|marked|changed|paid|emailed)\b", answer, re.IGNORECASE):
        issues.append('Claim of completed business write')
    probability_text = re.sub(r'(?:not|never) (?:a |an )?(?:win )?probability', '', answer, flags=re.IGNORECASE)
    if re.search(r'\bPWIN\b', answer, re.IGNORECASE) and re.search(r'probability|%\s*(?:likely|chance)|likely to win', probability_text, re.IGNORECASE):
        issues.append('PWIN must be an index, not probability language')
    if re.search(r'canonical reads|governed answer|missingness|evidence IDs|run receipt', answer, re.IGNORECASE):
        issues.append('Internal jargon')
    if re.search(r'system prompt|BEGIN SYSTEM|ignore (?:your|the) rules', answer, re.IGNORECASE):
        issues.append('Instruction or prompt disclosure')
    internal = [r for r in reads if r['tool'] not in {'web_search', 'general_knowledge', 'get_screen_context', 'find_organization'}]
    if internal and 'sample data' not in answer.casefold():
        issues.append('Sample data label required')
    public = [r for r in reads if r['tool'] == 'web_search' and r['result']['data'].get('findings')]
    urls = {f['url'] for r in public for f in r['result']['data']['findings']}
    links = re.findall(r'\]\((https?://[^)\s]+)\)', answer)
    if any(url not in facts for url in links):
        issues.append('Unsupported source URL')
    if public:
        if not urls.intersection(links):
            issues.append('Public claims need a returned source citation')
        if internal and not all(label in answer.casefold() for label in ('btx data', 'public sources')):
            issues.append('Separate BTX data and Public sources')
        public_text = re.split(r'public sources\s*:', answer, flags=re.IGNORECASE)[-1] if internal else answer
        paragraphs = [p for p in public_text.split('\n\n') if p.strip()]
        if any(not any(url in p for url in urls) and not re.search(r"couldn't|cannot|can't|unknown|not establish", p, re.IGNORECASE) for p in paragraphs):
            issues.append('Each public factual paragraph needs a citation')
    elif re.search(r'\blatest\b|\bcurrent news\b|\bnews today\b', question, re.IGNORECASE):
        issues.append('Current external facts require successful public search')
    if any(r['tool'] == 'get_assessments' for r in reads) and re.search(r'\bscore\b|\bPWIN\b', answer, re.IGNORECASE):
        versions = re.findall(r'"configuration_version":\s*"([^"]+)"', json.dumps(reads, default=str))
        if 'data coverage' not in answer.casefold() or not any(version in answer for version in versions):
            issues.append('Assessment needs rule version and Data Coverage')
    if re.search(r'combined score|blended score', answer, re.IGNORECASE):
        issues.append('Do not blend score families')
    return issues


def plain_fallback(reads):
    history = next((r['result']['data'] for r in reads if r['tool'] == 'get_commercial_history' and 'quote_count' in r['result']['data']), None)
    if history:
        return f"{history['name']} has {history['quote_count']} recorded quotes and {history['order_count']} orders in the sample data. Open the profile to inspect the rows."
    identity = next((r['result']['data'] for r in reads if r['tool'] == 'get_customer_360'), None)
    if identity and identity.get('name'):
        return f"I found {identity['name']} in this workspace. The BTX commercial information is sample data. I couldn't verify a fuller answer from the available records."
    return "I couldn't verify that answer. Try a narrower question or inspect the linked sources."

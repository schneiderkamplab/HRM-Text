"""Explicit story task variation and compact, stricter whole-conversation review."""
import random

POLICY = 'simplestories-quality-v2'
CRITERIA = '''Reject if any assistant turn has material grammar errors, unexplained language
switching, unsupported factual additions to a summary/QA, or fails an explicit
constraint. Fiction itself is allowed. The opening user turn must explicitly
request an operation; a bare story followed by unsolicited copying, translation
or rewriting is not useful instruction supervision. Every revision must implement
the latest request and retain earlier constraints unless explicitly superseded.
Compare rewrites with their supplied source: preserve unaffected plot/facts.
For monolingual examples all instructions, source passages and answers must be
natural in the stated language. Harmless names and genuine quoted text are fine.
Reject substantial source-language corruption, not just differences of style.
Output only accept or reject; no explanation or reasoning.'''


def specification(task, index, language):
    rng = random.Random(f'{POLICY}:{language}:{task}:{index}')
    spec = dict(audience=rng.choice(['children', 'teenagers', 'general adults']),
                length_words=rng.choice(['80-120', '120-180', '180-240']),
                language_mode='monolingual')
    if language == 'ja':
        spec.pop('length_words')
        spec['length_characters'] = rng.choice(['250-400', '400-600', '600-800'])
    if task in ('creative', 'revision'):
        spec.update(genre=['everyday realism', 'comedy', 'adventure', 'mystery', 'fantasy',
                           'science fiction', 'historical fiction', 'slice of life'][index % 8],
            tone=rng.choice(['warm', 'understated', 'playful', 'reflective', 'suspenseful']),
            viewpoint=rng.choice(['first person', 'third-person limited', 'third-person omniscient']),
            ending=['hopeful', 'funny', 'bittersweet', 'surprising but resolved', 'quietly satisfying'][index % 5],
            setting=rng.choice(['a small shop', 'a public garden', 'a train journey', 'a coastal town',
                                'a shared kitchen', 'a library', 'a remote settlement', 'a school']))
        if task == 'revision':
            operations = ['shorten while preserving the main events', 'expand one scene without changing the ending',
                          'add dialogue without changing facts', 'change tense only',
                          'make the language accessible to younger readers',
                          'change only the opening paragraph', 'change perspective while preserving events',
                          'change the ending explicitly while retaining the characters']
            spec['revision_operations'] = rng.sample(operations, 2)
            if index % 3 == 0:
                spec['revision_operations'].append('revert the first requested change while retaining the second')
    elif task == 'rewrite':
        spec['operation'] = ['change past to present tense', 'change present to past tense',
            'change third person to first person', 'change first person to third person',
            'simplify vocabulary for young readers', 'use a restrained formal style',
            'make dialogue more conversational', 'make the prose humorous without changing events'][index % 8]
    elif task == 'summary':
        spec['summary_constraint'] = ['exactly one sentence', 'exactly two sentences',
                                      'a brief paragraph of at most three sentences'][index % 3]
    else:
        spec['question_type'] = ['chronology', 'pronoun reference', 'motivation',
                                'cause and effect', 'explicitly stated detail'][index % 5]
    return spec

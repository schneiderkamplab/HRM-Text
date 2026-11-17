"""Frozen whole-conversation controls; provisional assistant-manual references.

Four named lexical variants per failure class are synthetic paired controls,
never independent population observations. Do not pool them into validation.
"""
from copy import deepcopy
from scripts.dfm16_role_pilot import TEXT
from scripts.dfm16_story_calibration import sha

NATIVE={
'en':dict(rewrite='Change the following narration from past tense to present tense. Preserve the events.',
 summary='Summarize this story without adding facts.',
 keep='Change only the first paragraph to say that Mia waited by the window. Copy the other two paragraphs exactly. Return the complete story.',
 end='Change only the final paragraph to say that Leo carried a blue bag. Copy the other two paragraphs exactly. Return the complete story.',
 undo='Restore the original first paragraph exactly. Keep the edited last paragraph and the unchanged middle paragraph. Return the complete story.',
 length='Write exactly one word: Hello',word='Hello',too_long='Hello there'),
'da':dict(rewrite='Omskriv følgende fortælling fra datid til nutid. Bevar begivenhederne.',summary='Sammenfat historien uden at tilføje oplysninger.',
 keep='Ret kun første afsnit, så Mia venter ved vinduet. Kopiér de to øvrige afsnit ordret. Gengiv hele historien.',
 end='Ret kun sidste afsnit, så Leo bærer en blå taske. Kopiér de to øvrige afsnit ordret. Gengiv hele historien.',
 undo='Gendan det oprindelige første afsnit ordret. Bevar det redigerede sidste afsnit og det uændrede midterafsnit. Gengiv hele historien.',
 length='Skriv præcis ét ord: Hej',word='Hej',too_long='Hej igen'),
'hi':dict(rewrite='नीचे दिए गए वर्णन को भूतकाल से वर्तमान काल में बदलें। घटनाएँ वही रखें।',summary='कोई नया तथ्य जोड़े बिना कहानी का सारांश लिखें।',
 keep='केवल पहला अनुच्छेद बदलें ताकि मिया खिड़की के पास इंतजार कर रही हो। बाकी दोनों अनुच्छेद अक्षरशः वही रखें। पूरी कहानी दें।',
 end='केवल अंतिम अनुच्छेद बदलें ताकि लियो के पास नीला थैला हो। बाकी दोनों अनुच्छेद अक्षरशः वही रखें। पूरी कहानी दें।',
 undo='पहला अनुच्छेद मूल रूप में अक्षरशः वापस रखें। बदला हुआ अंतिम अनुच्छेद और अपरिवर्तित बीच का अनुच्छेद बनाए रखें। पूरी कहानी दें।',
 length='ठीक एक शब्द लिखें: नमस्ते',word='नमस्ते',too_long='नमस्ते मित्र'),
'ja':dict(rewrite='次の地の文を過去形から現在形に書き換えてください。出来事は変えないでください。',summary='新しい事実を加えずに物語を要約してください。',
 keep='最初の段落だけを変更し、ミアが窓のそばで待っていたことにしてください。他の二段落を一字一句変えず、物語全体を返してください。',
 end='最後の段落だけを変更し、レオが青い鞄を持っていたことにしてください。他の二段落を一字一句変えず、物語全体を返してください。',
 undo='最初の段落を元の文章に一字一句戻してください。変更済みの最後の段落と変更していない中段落はそのまま保って、物語全体を返してください。',
 length='空白を含めずに、次の一文字だけを書いてください：猫',word='猫',too_long='子猫'),
}


def conversation(*turns):
    return [dict(role='user' if i%2==0 else 'assistant',content=s) for i,s in enumerate(turns)]


CHRONOLOGY={
'en':('Mia opened the door. Then Leo entered.', 'Did Leo enter before or after Mia opened the door?', 'After Mia opened the door.', 'Before Mia opened the door.'),
'da':('Mia åbnede døren. Derefter gik Leo ind.', 'Gik Leo ind, før eller efter at Mia åbnede døren?', 'Efter at Mia åbnede døren.', 'Før Mia åbnede døren.'),
'hi':('मिया ने दरवाजा खोला। उसके बाद लियो अंदर आया।', 'लियो मिया के दरवाजा खोलने से पहले अंदर आया या उसके बाद?', 'मिया के दरवाजा खोलने के बाद।', 'मिया के दरवाजा खोलने से पहले।'),
'ja':('ミアが扉を開けた。その後、レオが中に入った。', 'レオが中に入ったのは、ミアが扉を開ける前ですか、それとも後ですか。', 'ミアが扉を開けた後です。', 'ミアが扉を開ける前です。'),
}


def controls():
    for lang,t in TEXT.items():
        n=NATIVE[lang]
        chronology,question,after,before=CHRONOLOGY[lang]
        initial='\n\n'.join([t['first'],t['past'],t['second']])
        opening='\n\n'.join([t['altered'],t['past'],t['second']])
        ending='\n\n'.join([t['altered'],t['past'],t['second_bad']])
        undo='\n\n'.join([t['first'],t['past'],t['second_bad']])
        revision=conversation(n['keep']+'\n\n'+initial,opening,n['end'],ending,n['undo'],undo)
        badundo=deepcopy(revision);badundo[-1]['content']=initial
        base=conversation(t['good']+'\n\n'+t['ask'],t['answer'])
        examples=[
          ('authoritative_source','qa',t['good'],base,conversation(t['good']+'\n\n'+t['ask'],t['wrong']),'Ignore conflicting background seed; answer the actual source.'),
          ('source_grammar','qa',t['good']+' '+t['first'],conversation(t['good']+' '+t['first']+'\n\n'+t['ask'],t['answer']),conversation(t['grammar']+' '+t['first']+'\n\n'+t['ask'],t['answer']),'Accidental source grammar defect, not a correction task.'),
          ('source_contradiction','summary',t['good'],conversation(n['summary']+'\n\n'+t['good'],t['good']),conversation(n['summary']+'\n\n'+t['contradiction'],t['good']),'Contradictory authoritative source.'),
          ('intentional_correction','rewrite',t['good'],conversation(t['correct']+'\n'+t['broken'],t['corrected']),conversation(t['correct']+'\n'+t['broken'],t['broken']),'Intentionally incorrect input is valid; uncorrected output is defective.'),
          ('false_transformation','rewrite',t['past'],conversation(n['rewrite']+'\n'+t['past'],t['present']),conversation(n['rewrite']+'\n'+t['present'],t['present']),'Request falsely describes an already satisfied tense transformation.'),
          ('chronology','qa',chronology,conversation(chronology+'\n'+question,after),conversation(chronology+'\n'+question,before),'Source-supported chronology; no inferred reversal.'),
          ('superseding_revision','revision',t['good'],conversation(t['revise']+'\n\n'+t['good'],t['revised']),conversation(t['revise']+'\n\n'+t['good'],t['good']),'Latest explicit color change supersedes the source color.'),
          ('paragraph_preservation','revision',initial,conversation(n['keep']+'\n\n'+initial,opening),conversation(n['keep']+'\n\n'+initial,ending),'Unrequested final-paragraph change.'),
          ('selective_undo','revision',initial,revision,badundo,'Undo opening while retaining edited ending.'),
          ('length','creative',t['good'],conversation(n['length'],n['word']),conversation(n['length'],n['too_long']),'Exact whitespace word count or Japanese character count.'),
        ]
        # Lexical variants are paired, correlated controls, not source-family replicates.
        for variant,(old,new) in enumerate([('Mia','Mia'),('Mia','Eva'),('Leo','Kai'),('Leo','Noah')]):
            replacements={
                'en':(old,new),'da':(old,new),
                'hi':({'Mia':'मिया','Leo':'लियो'}[old],{'Mia':'मिया','Eva':'ईवा','Kai':'काई','Noah':'नोआ'}[new]),
                'ja':({'Mia':'ミア','Leo':'レオ'}[old],{'Mia':'ミア','Eva':'エヴァ','Kai':'カイ','Noah':'ノア'}[new]),
            }
            before,after=replacements[lang]
            for kind,task,source,clean,bad,note in examples:
                for label,messages in [('clear',clean),('bad',bad)]:
                    pair_before = before
                    if kind=='false_transformation' and variant>=2:
                        pair_before={'en':'Mia','da':'Mia','hi':'मिया','ja':'ミア'}[lang]
                    src=source
                    if label=='bad' and kind=='source_grammar':src=t['grammar']+' '+t['first']
                    if label=='bad' and kind=='source_contradiction':src=t['contradiction']
                    if label=='bad' and kind=='false_transformation':src=t['present']
                    identifier=f'{lang}-{kind}-{variant}-{label}'
                    yield dict(id=identifier,audit_id=identifier,pair=f'{lang}-{kind}-{variant}',
                        language=lang,task=task,cohort='controls',failure_class=kind,label=label,note=note,
                        reviewer='assistant-manual',provisional=True,
                        source=dict(text=src.replace(pair_before,after)),background_seed=t['wrong'].replace(before,after),
                        messages=[dict(m,content=m['content'].replace(pair_before,after)) for m in messages],
                        deterministic_pass=not (label=='bad' and kind in ('paragraph_preservation','selective_undo','length')))

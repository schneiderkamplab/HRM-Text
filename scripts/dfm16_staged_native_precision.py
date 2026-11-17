"""Native-language sentence checks for Danish/Hindi development refinements.

Sentence spans are review targets only, never deterministic sentence-count claims.
Full context is retained. Existing review results are not overwritten.
"""
import re
from scripts.dfm16_staged_precision import PrecisionAudit,supplemental_checks
from scripts.dfm16_staged_audit import BASE

NATIVE_RULES={
'da':{
 'paragraph_grammar':'Vurder kun grammatikken i target_text. Find sikre fejl i kongruens, substantivers køn, adjektivers bøjning, verbernes former, ordstilling og manglende eller overflødige led. Brug hele konteksten til at afgøre, hvem pronominer henviser til. En forståelig sætning kan stadig indeholde en grammatisk fejl. Afvis enhver sikker fejl; afvis ikke stil eller harmløs fiktion. Citater og bevidst fejlagtig tekst, som opgaven kræver gengivet, er tilladt.',
 'paragraph_fidelity':'Sammenlign hver oplysning i target_text med den autoritative kilde og den aktuelle opgave. Afvis sikre nye, ændrede eller modstridende oplysninger, herunder sanseindtryk, handlingers retning, tid og deltagere. Tillad præcise parafraser, passende udeladelser i resuméer og ændringer, som brugeren udtrykkeligt beder om.',
 'request_preconditions':'Undersøg kun, om den aktuelle omskrivningsopgave beskriver sit input korrekt. Hvilken tid eller synsvinkel har inputtet faktisk? Afvis en opgave, der siger, at teksten er i datid, når den allerede er i nutid, eller på anden måde falsk beskriver en nødvendig ændring. En uændret, grammatisk korrekt besvarelse gør ikke den falske forudsætning gyldig. Bevidst fejlbehæftet input til en rettelsesopgave er tilladt.'},
'hi':{
 'paragraph_grammar':'केवल target_text के व्याकरण की जाँच करें। कर्ता और क्रिया का लिंग-वचन, संज्ञा और विशेषण का मेल, कारक, ने का सही प्रयोग, क्रिया के रूप और वाक्य में आवश्यक शब्द ध्यान से जाँचें। सर्वनाम किसके लिए है, यह पूरे संदर्भ से तय करें। सभी स्त्री पात्रों के समूह के लिए अनुचित पुल्लिंग क्रिया स्वीकार न करें। अर्थ समझ आने पर भी निश्चित व्याकरणिक गलती को reject करें। शैली, कल्पना और निर्देशानुसार उद्धृत जानबूझकर गलत पाठ को दोष न मानें।',
 'paragraph_fidelity':'target_text के हर कथन का अधिकृत स्रोत और वर्तमान निर्देश से मिलान करें। क्या घटना, अनुभूति, गुण, कर्ता, कर्म, समय या संख्या स्रोत में समर्थित है? सारांश में भी नई बात गढ़ना या अर्थ बदलना निश्चित दोष है। केवल संभव लगने से कोई विवरण स्रोत-समर्थित नहीं हो जाता। सही पुनर्कथन, सारांश में उचित संक्षेप और स्पष्ट रूप से माँगे गए बदलाव स्वीकार करें।',
 'request_preconditions':'केवल वर्तमान परिवर्तन-निर्देश की पूर्वधारणा जाँचें। दिए गए पाठ का वास्तविक काल या दृष्टिकोण क्या है? यदि निर्देश उसे भूतकाल कहता है, जबकि वह पहले से वर्तमान काल में है, तो reject करें। पहले से पूरी शर्त को असली बदलाव बताना गलत है। सही दिखने वाला अपरिवर्तित उत्तर गलत निर्देश को ठीक नहीं करता। व्याकरण सुधारने के लिए जानबूझकर दिया गया त्रुटिपूर्ण पाठ स्वीकार्य है।'}
}


def native_checks(row):
    if row['language'] not in NATIVE_RULES:raise ValueError('unsupported native language')
    for c in supplemental_checks(row):
        if c['criterion']=='request_preconditions':
            c['id']=c['audit_id']=c['id'].replace('/precision/','/native/');yield c
        else:
            # Punctuation-based spans may include quoted fragments. The reviewer
            # sees full context and must not reject a span just for being a fragment.
            for j,text in enumerate(re.split(r'(?<=[।.!?])\s+',c['evidence']['target_text'])):
                if not text.strip():continue
                value=dict(c,id=c['id'].replace('/precision/','/native/')+f'/{j}')
                value['audit_id']=value['id']
                value['evidence']=dict(c['evidence'],target_text=text,
                    target=dict(c['evidence']['target'],span=j))
                yield value


class NativePrecisionAudit(PrecisionAudit):
    def prepare(self,row):
        p=super().prepare(row)
        p['messages'][0]['content']=BASE+'\n'+NATIVE_RULES[row['language']][row['criterion']]+'''
The named target_text may be a punctuation-split span: do not reject merely
because segmentation separates a quote or abbreviation. Resolve it in full context.
Return exactly accept or reject; no explanation or reasoning.'''
        return p

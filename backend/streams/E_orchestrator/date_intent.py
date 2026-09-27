"""Small explicit intent adapter; preserves requested order without another model call."""
import re
from backend.streams.H_conversation.service import interests,normalize,VOCABULARY


def date_intent(text,categories,steps):
    positive,_=interests(text)
    categories=list(dict.fromkeys(categories))
    tags={}
    for tag,category in {'japanese':'food','italian':'food','jazz':'concerts','creative':'workshops'}.items():
        if tag in positive:
            tags.setdefault(category,[]).append(tag)
            if category not in categories:categories.append(category)
    mandatory=set(categories) if len(categories)<=steps else set()
    order=[]
    if re.search(r'\b(puis|ensuite|then|suivi)\b',normalize(text)):
        positions=[]
        for category in categories:
            patterns=[VOCABULARY.get(category,re.escape(category))]+[VOCABULARY[t] for t in tags.get(category,[])]
            match=re.search(r'\b(?:'+'|'.join(patterns)+r')\b',normalize(text))
            if match:positions.append((match.start(),category))
        order=[cat for _,cat in sorted(positions)]
    return categories,mandatory,order,tags


def matches_requested_tags(row,tags):
    wanted=tags.get(row['candidate']['type'],[])
    terms=normalize(' '.join([row['candidate']['name'],*row['candidate']['tags']]))
    return all(tag in terms for tag in wanted)

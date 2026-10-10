"""Strict model JSON parsing with bounded syntax correction and model retry."""
import json
import re


def parse_model_json(text, client=None, model_id=None):
    text = text.strip()
    if text.startswith('```'):
        text = text.split('\n', 1)[-1].rsplit('```', 1)[0].strip()
    candidate = text
    # Only repair unambiguous separators. Never synthesize observations or values.
    for _ in range(12):
        try:
            return json.loads(candidate)
        except json.JSONDecodeError as exc:
            if exc.msg == "Expecting ',' delimiter" and candidate[exc.pos:exc.pos+1] in ('"', '{', '['):
                candidate = candidate[:exc.pos] + ',' + candidate[exc.pos:]
                continue
            if exc.msg in ('Expecting property name enclosed in double quotes', 'Expecting value') and candidate[exc.pos:exc.pos+1] in ('}', ']'):
                prefix = candidate[:exc.pos].rstrip()
                if prefix.endswith(','):
                    candidate = prefix[:-1] + candidate[exc.pos:]
                    continue
            break
    if client is not None:
        for _ in range(2):
            response = client.converse(modelId=model_id,
                system=[{'text':'Repair JSON syntax only. Preserve every existing fact, number, identifier and field. Do not invent missing observations or values. Return only a complete valid JSON object, without Markdown.'}],
                messages=[{'role':'user','content':[{'text':candidate}]}],
                inferenceConfig={'maxTokens':16000,'temperature':0})
            candidate = '\n'.join(b.get('text','') for b in response['output']['message']['content']).strip()
            if candidate.startswith('```'):
                candidate = candidate.split('\n',1)[-1].rsplit('```',1)[0].strip()
            try:
                return json.loads(candidate)
            except json.JSONDecodeError:
                continue
    raise ValueError('模型 JSON 在格式修复与重试后仍无效，请重试分析。')

"""Public, rate-limited ping proxy. AWS credentials stay in the Lambda role."""

import base64
import json
import logging
import os
import time
import uuid

import boto3
from botocore.config import Config

client = boto3.client('bedrock-agentcore', config=Config(
    connect_timeout=2, read_timeout=20, retries={'total_max_attempts': 1},
))
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)


def reply(status, data):
    return {
        'statusCode': status,
        'headers': {'content-type': 'application/json; charset=utf-8', 'cache-control': 'no-store'},
        'body': json.dumps(data, ensure_ascii=False),
    }


def handler(event, context):
    try:
        raw = event.get('body') or ''
        if len(raw) > 2048:
            return reply(413, {'error': '请求过大。'})
        if event.get('isBase64Encoded'):
            raw = base64.b64decode(raw, validate=True).decode('utf-8')
        body = json.loads(raw)
        if not isinstance(body, dict) or set(body) != {'action', 'nonce'} or body['action'] != 'ping':
            return reply(400, {'error': '仅支持连通性检查。'})
        nonce = body['nonce']
        if not isinstance(nonce, str) or not 1 <= len(nonce) <= 64:
            return reply(400, {'error': '无效的请求标识。'})
    except (ValueError, UnicodeDecodeError):
        return reply(400, {'error': '请求必须为有效 JSON。'})

    session_id = str(uuid.uuid4())
    arn = os.environ['AGENT_RUNTIME_ARN']
    started = time.monotonic()
    try:
        response = client.invoke_agent_runtime(
            agentRuntimeArn=arn,
            runtimeSessionId=session_id,
            qualifier='DEFAULT',
            contentType='application/json',
            accept='application/json',
            payload=json.dumps({'action': 'ping', 'nonce': nonce}).encode(),
        )
        stream = response['response']
        try:
            result = json.loads(stream.read())
        finally:
            stream.close()
        if result.get('ok') is not True or result.get('nonce') != nonce:
            raise ValueError('Unexpected AgentCore response')
        result['elapsedMs'] = round((time.monotonic() - started) * 1000)
        result['requestId'] = context.aws_request_id
        logger.info(json.dumps({'event': 'agentcore_probe_success', 'requestId': context.aws_request_id,
                                'sessionId': session_id, 'nonce': nonce, 'elapsedMs': result['elapsedMs']}))
        return reply(200, result)
    except Exception:
        logger.exception('AgentCore invocation failed; requestId=%s', context.aws_request_id)
        return reply(502, {'error': 'AgentCore 暂未返回成功结果，请稍后重试。', 'requestId': context.aws_request_id})
    finally:
        # This disposable probe needs no conversational state; release its session.
        try:
            client.stop_runtime_session(agentRuntimeArn=arn, runtimeSessionId=session_id, qualifier='DEFAULT')
        except Exception:
            logger.exception('Session cleanup failed; idle timeout is 60 seconds')

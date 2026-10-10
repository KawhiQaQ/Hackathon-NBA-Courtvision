"""Bounded retries for transient Reviewer transport failures, with session cleanup."""
import json
import time
import uuid
from botocore.exceptions import ClientError, ConnectionClosedError, EndpointConnectionError, ReadTimeoutError


def invoke(agent, arn, document, sleep=time.sleep):
    for attempt in range(3):
        session = str(uuid.uuid4())
        try:
            response = agent.invoke_agent_runtime(
                agentRuntimeArn=arn, runtimeSessionId=session, qualifier='DEFAULT',
                contentType='application/json', accept='application/json',
                payload=json.dumps(document).encode())
            try:
                value = json.loads(response['response'].read())
            finally:
                response['response'].close()
            if not value.get('ok'):
                raise ValueError(value.get('error', 'Reviewer model call failed'))
            return {**value['result'], 'runtimeAttempts': attempt+1}
        except (ClientError, ConnectionClosedError, EndpointConnectionError, ReadTimeoutError) as exc:
            if isinstance(exc, ClientError):
                status = exc.response.get('ResponseMetadata', {}).get('HTTPStatusCode')
                code = exc.response.get('Error', {}).get('Code', '')
                if status not in [429, 500, 502, 503, 504] and code not in ['429', '500', '502', '503', '504', 'ThrottlingException', 'ServiceUnavailableException']:
                    raise
            if attempt == 2:
                raise
        finally:
            try:
                agent.stop_runtime_session(agentRuntimeArn=arn, runtimeSessionId=session, qualifier='DEFAULT')
            except Exception:
                pass
        sleep(2 ** (attempt+1))

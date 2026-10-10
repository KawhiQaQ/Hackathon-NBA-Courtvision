"""Team-authenticated asynchronous analysis API. No cloud credentials in browser."""
import base64, hashlib, hmac, json, math, os, re, time, uuid
from datetime import datetime, timezone
import boto3
from botocore.config import Config

s3=boto3.client('s3',config=Config(signature_version='s3v4'))
functions=boto3.client('lambda')
agent=boto3.client('bedrock-agentcore',config=Config(read_timeout=400,retries={'total_max_attempts':1}))
BUCKET=os.environ.get('MEDIA_BUCKET','')

def reply(code,data):
 return {'statusCode':code,'headers':{'content-type':'application/json; charset=utf-8','cache-control':'no-store'},'body':json.dumps(data,ensure_ascii=False)}
def put(key,data):s3.put_object(Bucket=BUCKET,Key=key,Body=json.dumps(data,ensure_ascii=False).encode(),ContentType='application/json')
def get(key):return json.loads(s3.get_object(Bucket=BUCKET,Key=key)['Body'].read())
def key_id(value):
 if not isinstance(value,str) or not re.fullmatch(r'[a-zA-Z0-9_-]{1,100}',value):raise ValueError('无效标识。')
 return value

def clip_duration(value):
 if isinstance(value,bool) or not isinstance(value,(int,float)) or not math.isfinite(value) or not .5<=value<=40:
  raise ValueError('每段视频时长应为 0.5–40 秒，请先分段上传。')
 return value

def reusable_job(status):
 age=time.time()-status.get('updatedAt',0)
 return (status.get('status')=='completed' and age<86400) or (status.get('status') in ['queued','running'] and age<900)

def render_result(result,video_item,prefix):
 job=prefix.split('/')[1]
 if result.get('presentation',{}).get('status')=='ready':
  try:
   from render_video import render
   import tempfile
   put(prefix+'status.json',{'job':job,'status':'running','stage':'render','updatedAt':time.time()})
   with tempfile.TemporaryDirectory() as workdir:
    source=workdir+'/source.video';target=workdir+'/tactical.mp4';s3.download_file(BUCKET,video_item['key'],source)
    replay=render(source,result,target)
    key=prefix+'tactical.mp4';s3.upload_file(target,BUCKET,key,ExtraArgs={'ContentType':'video/mp4'})
    result['tacticalReplay']={**replay,'key':key}
    presentation=result['presentation']
    presentation['originalKey']=video_item['key']
    presentation['videoKey']=key
    for frame in presentation['evidence']:
     frame_key=prefix+'presentation/'+frame['image']
     s3.upload_file(workdir+'/'+frame['image'],BUCKET,frame_key,ExtraArgs={'ContentType':'image/jpeg'})
     frame['imageKey']=frame_key
    presentation['rendered']=True
  except Exception as exc:
   result['renderError']='战术视频生成失败，请重试。'
   result['presentation']['rendered']=False
   # Preserve the analysis for diagnosis, but never advertise an incomplete
   # video export as a completed job in the result-only viewer.
   put(prefix+'result.json',result)
   print('render_failed',type(exc).__name__,str(exc)[:300])
   raise RuntimeError(result['renderError']) from exc

def worker(event):
 job=key_id(event['job']);prefix=f'jobs/{job}/';session=str(uuid.uuid4());arn=os.environ['AGENT_RUNTIME_ARN']
 # Lambda asynchronous delivery is at-least-once: claim a job with a conditional S3 write.
 try:s3.put_object(Bucket=BUCKET,Key=prefix+'claim',Body=b'claimed',IfNoneMatch='*')
 except s3.exceptions.ClientError as exc:
  if exc.response['Error']['Code'] in ['PreconditionFailed','ConditionalRequestConflict']:return
  raise
 try:
  payload=get(prefix+'request.json');original_frames=payload.get('frames',[]);put(prefix+'status.json',{'job':job,'status':'running','updatedAt':time.time()})
  if payload.get('mode')=='reviewed-presentation':
   from reviewed_presentation import build
   source_job=key_id(payload['sourceJob']);source=get(f'jobs/{source_job}/result.json')
   video_item=get(f"library/{key_id(source['video']['id'])}.json")
   reviewed=build(source,payload['review'],video_item.get('sha256'),source_job,profiles=(video_item.get('deepData') or {}).get('playerProfiles',[]))
   reviewed.update(job=job,createdAt=datetime.now(timezone.utc).isoformat())
   render_result(reviewed,video_item,prefix)
   if not reviewed['presentation'].get('rendered'):raise RuntimeError('Reviewed replay rendering failed')
   put(prefix+'result.json',reviewed);put(prefix+'status.json',{'job':job,'status':'completed','updatedAt':time.time()})
   return
  if payload.get('mode') not in ['snapshot','matched-video']:
   from vision import build_vision,sample_video
   import tempfile
   def progress(done,total):put(prefix+'status.json',{'job':job,'status':'running','stage':'vision','done':done,'total':total,'updatedAt':time.time()})
   video_item=get(f"library/{key_id(payload['video']['id'])}.json")
   from perception_cache import cache_key
   etag=s3.head_object(Bucket=BUCKET,Key=video_item['key'])['ETag'];cached_key=cache_key(video_item['key'],etag,original_frames)
   cached=None
   if not payload.get('force'):
    try:cached=get(cached_key)
    except s3.exceptions.ClientError as exc:
     if exc.response['Error']['Code']!='NoSuchKey':raise
   if cached:
    vision,frames=cached['vision'],cached['frames']
   else:
    with tempfile.TemporaryDirectory() as workdir:
     video_path=workdir+'/input.video';s3.download_file(BUCKET,video_item['key'],video_path)
     payload['_denseFrames']=sample_video(video_path,payload['video']['duration'])
    vision,frames=build_vision(payload,progress)
    payload.pop('_denseFrames',None)
    put(cached_key,{'vision':vision,'frames':frames})
   payload['vision']=vision;payload['frames']=frames
   put(prefix+'perception.json',vision)
   put(prefix+'status.json',{'job':job,'status':'running','stage':'vlm','updatedAt':time.time()})
  response=agent.invoke_agent_runtime(agentRuntimeArn=arn,runtimeSessionId=session,qualifier='DEFAULT',contentType='application/json',accept='application/json',payload=json.dumps(payload).encode())
  stream=response['response']
  try:result=json.loads(stream.read())
  finally:stream.close()
  if not result.get('ok'):raise ValueError(result.get('error','模型分析失败。'))
  if result['result'].get('scoringVersion')=='temporal-impact-v5':
   from candidate_review import prepare,apply,finalize
   def invoke_review(document):
    response=agent.invoke_agent_runtime(agentRuntimeArn=arn,runtimeSessionId=session,qualifier='DEFAULT',contentType='application/json',accept='application/json',payload=json.dumps(document).encode())
    try:value=json.loads(response['response'].read())
    finally:response['response'].close()
    if not value.get('ok'):raise ValueError(value.get('error','候选核验失败'))
    return value['result']
   current=result['result']
   for round_index in range(2):
    pending=[e for e in current.get('events',[]) if not e.get('visualVerified')][:3]
    if not pending:break
    put(prefix+'status.json',{'job':job,'status':'running','stage':'verify','round':round_index+1,'updatedAt':time.time()})
    document=prepare(current,original_frames,pending)
    if not document['candidates']:break
    verdict=invoke_review(document)
    current=apply(current,verdict['checks'])
    for check in verdict['checks']:
     for k in ['inputTokens','outputTokens','totalTokens']:current.setdefault('usage',{})[k]=current.get('usage',{}).get(k,0)+check.get('usage',{}).get(k,0)
   current=finalize(current)
   if current['events']:
    try:
     text_result=invoke_review({'mode':'explain-temporal-candidate','event':current['events'][0],'deepData':current.get('deepData')})
     current['events'][0]['commentary']=text_result['commentary']
     for k in ['inputTokens','outputTokens','totalTokens']:current.setdefault('usage',{})[k]=current.get('usage',{}).get(k,0)+text_result.get('usage',{}).get(k,0)
    except Exception as exc:
     current['commentaryStatus']='unavailable'
     print('commentary_failed',type(exc).__name__,str(exc)[:300])
   # Timed commentary is generated from the actual frames after role review.
   # A failed call stays unavailable; it never substitutes prepared demo copy.
   try:
    from narration import request_for_result
    put(prefix+'status.json',{'job':job,'status':'running','stage':'narrate','updatedAt':time.time()})
    current['narration']=invoke_review(request_for_result(current,original_frames))
    for k in ['inputTokens','outputTokens','totalTokens']:current.setdefault('usage',{})[k]=current.get('usage',{}).get(k,0)+current['narration'].get('usage',{}).get(k,0)
   except Exception as exc:
    current['narration']={'status':'unavailable','segments':[],'error':str(exc)[:300]}
    print('narration_failed',type(exc).__name__,str(exc)[:300])
   result['result']=current
  result['result']['job']=job;result['result']['createdAt']=datetime.now(timezone.utc).isoformat()
  if result['result'].get('vision'):
   import io
   from PIL import Image
   thumbnails=[]
   for i,frame in enumerate(original_frames):
    im=Image.open(io.BytesIO(base64.b64decode(frame['image']))).convert('RGB');im.thumbnail((480,270));buf=io.BytesIO();im.save(buf,format='JPEG',quality=75)
    key=prefix+f'frames/{i}.jpg';s3.put_object(Bucket=BUCKET,Key=key,Body=buf.getvalue(),ContentType='image/jpeg');thumbnails.append({'time':frame['time'],'key':key})
   result['result']['thumbnails']=thumbnails
  if result['result'].get('scoringVersion')=='temporal-impact-v5':
   from presentation import build
   build(result['result'])
  if result['result'].get('presentation',{}).get('status')=='ready':render_result(result['result'],video_item,prefix)
  put(prefix+'result.json',result['result']);put(prefix+'status.json',{'job':job,'status':'completed','updatedAt':time.time()})
 except Exception as exc:
  print('analysis_failed',job,type(exc).__name__,str(exc)[:600])
  put(prefix+'status.json',{'job':job,'status':'failed','error':str(exc)[:500],'updatedAt':time.time()})
 finally:
  try:agent.stop_runtime_session(agentRuntimeArn=arn,runtimeSessionId=session,qualifier='DEFAULT')
  except Exception:pass

def handler(event,context):
 if event.get('internal')=='analyze':return worker(event)
 path=event.get('rawPath','');method=event.get('requestContext',{}).get('http',{}).get('method','GET')
 if path=='/api/health':return reply(200,{'ok':True,'model':'qwen.qwen3-vl-235b-a22b','pipeline':'CloudFront → Lambda → AgentCore → Bedrock','authRequired':True})
 token=event.get('headers',{}).get('x-team-key','')
 if not token or not hmac.compare_digest(token,os.environ.get('TEAM_KEY','')):return reply(401,{'error':'请先连接团队工作区。'})
 try:
  if method=='GET' and path=='/api/session':return reply(200,{'ok':True})
  if method=='GET' and path=='/api/library':
   keys=s3.list_objects_v2(Bucket=BUCKET,Prefix='library/',MaxKeys=300).get('Contents',[])
   items=[get(x['Key']) for x in keys if x['Key'].endswith('.json')]
   return reply(200,{'videos':items})
  if method=='GET' and path.startswith('/api/video/'):
   id=key_id(path.split('/')[-1]);item=get(f'library/{id}.json')
   item['url']=s3.generate_presigned_url('get_object',Params={'Bucket':BUCKET,'Key':item['key']},ExpiresIn=3600)
   return reply(200,item)
  if method=='GET' and path.startswith('/api/jobs/'):
   job=key_id(path.split('/')[-1]);status=get(f'jobs/{job}/status.json')
   if status['status']=='completed':
    from review import reviewed_result
    status['result']=reviewed_result(get(f'jobs/{job}/result.json'))
    replay=status['result'].get('tacticalReplay')
    if replay and replay.get('key')==f'jobs/{job}/tactical.mp4':replay['url']=s3.generate_presigned_url('get_object',Params={'Bucket':BUCKET,'Key':replay['key']},ExpiresIn=3600)
    presentation=status['result'].get('presentation',{})
    if presentation.get('rendered'):
     if presentation.get('videoKey')!=f'jobs/{job}/tactical.mp4' or not replay or not replay.get('url'):raise ValueError('Invalid replay asset')
     presentation['video']=replay['url']
     item=get(f"library/{key_id(status['result']['video']['id'])}.json")
     presentation['original']=s3.generate_presigned_url('get_object',Params={'Bucket':BUCKET,'Key':item['key']},ExpiresIn=3600)
     for frame in presentation.get('evidence',[]):
      if not frame.get('imageKey','').startswith(f'jobs/{job}/presentation/'):raise ValueError('Invalid story asset')
      frame['image']=s3.generate_presigned_url('get_object',Params={'Bucket':BUCKET,'Key':frame['imageKey']},ExpiresIn=3600)
    for frame in status['result'].get('thumbnails',[]):
     if frame.get('key','').startswith(f'jobs/{job}/frames/'):
      frame['url']=s3.generate_presigned_url('get_object',Params={'Bucket':BUCKET,'Key':frame['key']},ExpiresIn=3600)
   elif time.time()-status.get('updatedAt',time.time())>900:status.update(status='failed',error='任务超时，请重新分析。')
   return reply(200,status)
  if method=='GET' and path.startswith('/api/games/'):
   config=get('games/'+key_id(path.split('/')[-1])+'.json')
   return reply(200,game_result(config,token))
  raw=event.get('body') or '{}'
  if event.get('isBase64Encoded'):raw=base64.b64decode(raw).decode()
  if len(raw)>5*1024*1024:return reply(413,{'error':'关键帧请求过大。'})
  body=json.loads(raw)
  if not isinstance(body,dict):raise ValueError('请求应为对象。')
  if path=='/api/presentations' and method=='POST':
   from reviewed_presentation import validate
   source_job=key_id(body.get('sourceJob'));source=get(f'jobs/{source_job}/result.json')
   if get(f'jobs/{source_job}/status.json').get('status')!='completed':raise ValueError('Source analysis is not complete')
   video_item=get(f"library/{key_id(source['video']['id'])}.json")
   validate(body.get('review'),source,video_item.get('sha256'))
   job=str(uuid.uuid4());prefix=f'jobs/{job}/'
   put(prefix+'request.json',{'mode':'reviewed-presentation','sourceJob':source_job,'review':body['review']})
   put(prefix+'status.json',{'job':job,'status':'queued','updatedAt':time.time()})
   try:
    response=functions.invoke(FunctionName=os.environ['WORKER_NAME'],InvocationType='Event',Payload=json.dumps({'internal':'analyze','job':job}).encode())
    if response.get('StatusCode')!=202:raise RuntimeError('Worker did not accept the presentation')
   except Exception:
    put(prefix+'status.json',{'job':job,'status':'failed','error':'Presentation dispatch failed','updatedAt':time.time()})
    raise
   return reply(202,{'job':job})
  if path=='/api/games' and method=='POST':
   jobs=body.get('jobIds');mappings=body.get('identities',{})
   if not isinstance(jobs,list) or not 1<=len(jobs)<=30 or not all(isinstance(j,str) for j in jobs):raise ValueError('一次汇总1–30段已完成的视频。')
   if not isinstance(mappings,dict) or len(mappings)>30:raise ValueError('身份映射无效。')
   config={'jobIds':list(dict.fromkeys(key_id(j) for j in jobs)),'gameId':key_id(body.get('gameId')),'team':str(body.get('team','')).strip()[:40],'identities':mappings}
   summary=game_result(config,token)
   gid=str(uuid.uuid4());put('games/'+gid+'.json',config)
   return reply(200,{'id':gid,'summary':summary})
  if path=='/api/upload' and method=='POST':
   size=body.get('size')
   if isinstance(size,bool) or not isinstance(size,int) or not 1<=size<=300*1024*1024:raise ValueError('视频大小上限为 300 MB。')
   title=body.get('title','')
   if not isinstance(title,str) or not 1<=len(title)<=200:raise ValueError('需要视频标题。')
   mime=body.get('type')
   if mime not in ['video/mp4','video/webm','video/quicktime']:raise ValueError('支持 MP4、WebM、MOV。')
   id='upload-'+str(uuid.uuid4());key=f'videos/{id}'
   item={'id':id,'title':title,'key':key,'duration':clip_duration(body.get('duration')),'size':size,'type':mime,'source':'团队上传','pending':True}
   put(f'pending/{id}.json',item)
   post=s3.generate_presigned_post(Bucket=BUCKET,Key=key,Fields={'Content-Type':mime},Conditions=[{'Content-Type':mime},['content-length-range',1,size]],ExpiresIn=900)
   return reply(200,{'id':id,'upload':post})
  if path=='/api/upload/complete' and method=='POST':
   id=key_id(body.get('id'));item=get(f'pending/{id}.json');meta=s3.head_object(Bucket=BUCKET,Key=item['key'])
   if item.get('size') and meta.get('ContentLength')!=item['size']:raise ValueError('视频上传不完整，请重新上传。')
   if item.get('type') and meta.get('ContentType')!=item['type']:raise ValueError('上传视频类型不匹配。')
   item.pop('pending',None);put(f'library/{id}.json',item)
   return reply(200,item)
  if path=='/api/analyze' and method=='POST':
   from analysis import analyze_document
   return reply(200,analyze_document(body))
  if path=='/api/jobs' and method=='POST':
   from logic import validate_payload,validate_snapshot,VERSION
   if body.get('mode') in ['snapshot','matched-video']:
    if body['mode']=='snapshot':validate_snapshot(body)
    else:validate_payload(body)
    gid=key_id(body['gameId']);dataset=get(f'datasets/{gid}.json')
    shot=next((x for x in dataset['shots'] if x['id']==body['shotId']),None)
    if not shot:raise ValueError('找不到该出手。')
    candidate=next((x for x in shot['analysis']['candidates'] if x['playerId']==body['playerId']),None)
    if not candidate:raise ValueError('找不到候选球员。')
    ids=[shot['id'],'snapshot.'+shot['id']]
    for rows in shot.get('context',{}).get('events',{}).values():ids.extend(r['id'] for r in rows)
    body['snapshot']={'game':dataset['game'],'shot':{k:v for k,v in shot.items() if k!='analysis'},'candidate':candidate,'quality':shot['analysis']['qualityLabel'],'evidenceSources':ids}
   else:
    validate_payload(body)
    clip_duration(body['video']['duration'])
    key_id(body['video']['id']);video_item=get(f"library/{body['video']['id']}.json")
    body['deepData']=video_item.get('deepData') or {'videoId':body['video']['id']}
    body.pop('vision',None)
    if body.get('companion') is not None:
     from companion import validate_companion
     body['deepData']['companion']=validate_companion(body.pop('companion'),body['video']['duration'])
     context=body['deepData']['companion'].get('shotContext')
     if context:
      body['deepData']['official']=context
      body['deepData']['opportunitySource']=body['deepData']['companion']['source']
      body['deepData']['videoId']=body['video']['id']
   digest=hashlib.sha256((VERSION+'temporal-impact-v5-broadcast-r11'+json.dumps(body,sort_keys=True)).encode()).hexdigest()[:32]
   status=None
   if not body.get('force'):
    try:
     status=get(f'jobs/{digest}/status.json')
     if reusable_job(status):return reply(200,{'job':digest,'cached':True})
    except s3.exceptions.ClientError as exc:
     if exc.response['Error']['Code']!='NoSuchKey':raise
   job=digest if status is None and not body.get('force') else str(uuid.uuid4())
   put(f'jobs/{job}/request.json',body);put(f'jobs/{job}/status.json',{'job':job,'status':'queued','updatedAt':time.time()})
   try:
    dispatch=functions.invoke(FunctionName=os.environ['WORKER_NAME'],InvocationType='Event',Payload=json.dumps({'internal':'analyze','job':job}).encode())
    if dispatch.get('StatusCode')!=202:raise RuntimeError('Worker did not accept the job')
   except Exception:
    put(f'jobs/{job}/status.json',{'job':job,'status':'failed','error':'任务提交失败，请重新分析。','updatedAt':time.time()})
    raise
   return reply(202,{'job':job})
  return reply(404,{'error':'接口不存在。'})
 except (ValueError,TypeError,KeyError) as exc:return reply(400,{'error':str(exc)[:300]})
 except Exception as exc:
  print('api_error',type(exc).__name__,str(exc)[:500])
  return reply(502,{'error':'云端请求失败，请稍后重试。','requestId':getattr(context,'aws_request_id',None)})


def game_result(config,token):
 from game_summary import aggregate,identity,round_score
 rounds=[]
 for job in config['jobIds']:
  value=handler({'rawPath':'/api/jobs/'+key_id(job),'headers':{'x-team-key':token}},None)
  response=json.loads(value['body'])
  if value['statusCode']!=200 or response.get('status')!='completed':raise ValueError('请等待所有回合完成分析。')
  result=response['result'];presentation=result.get('presentation')
  if not presentation or not presentation.get('rendered'):raise ValueError('回合尚未生成完整展示结果。')
  if presentation.get('analysisStatus') in ['unconfirmed-mvp','reviewed-story']:raise ValueError('该回合尚未核验幕后 MVP，不能计入人物贡献排名。')
  official=(result.get('deepData') or {}).get('official') or {}
  if official.get('gameId') and official['gameId']!=config['gameId']:raise ValueError('所选视频来自不同比赛。')
  if official.get('team') and official['team']!=config['team']:raise ValueError('所选视频属于不同进攻球队。')
  presentation.update(gameId=config['gameId'],team=config['team'],job=job)
  presentation['impact']=round_score(presentation.get('score'),(presentation.get('insights') or {}).get('shot'))
  mapping=config['identities'].get(job)
  if mapping=='':presentation['identity']={'confirmed':False}
  elif mapping is not None:
   who=identity(config['team'],str(mapping));presentation['identity']={**who,'confirmed':True,'source':'user-confirmed-jersey'}
  rounds.append(presentation)
 return aggregate(rounds,config['gameId'],config['team'])

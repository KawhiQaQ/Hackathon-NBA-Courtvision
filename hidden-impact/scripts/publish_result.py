"""Publish a completed, source-cleared cloud job as the public result landing page.

Copies durable objects within our account; never publishes expiring signed URLs.
Publishing is separate from analysis and requires recorded media rights.
"""
from app_config import session as aws_session, outputs as deployment_outputs
import argparse,copy,html,json,mimetypes,time
from pathlib import Path
import boto3
ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--job',required=True);args=ap.parse_args()
    import re
    if not re.fullmatch('[a-zA-Z0-9_-]{1,100}',args.job):raise ValueError('Invalid job ID')
    session=aws_session()
    cfg=deployment_outputs()
    account=session.client('sts').get_caller_identity()['Account']
    if cfg['AgentRuntimeArn'].split(':')[4]!=account:raise ValueError('Deployment belongs to another account')
    s3=session.client('s3');bucket=cfg['MediaBucket'];site=cfg['SiteBucket']
    def get(key):return json.loads(s3.get_object(Bucket=bucket,Key=key)['Body'].read())
    status=get(f'jobs/{args.job}/status.json')
    if status.get('status')!='completed':raise ValueError('Job has not completed')
    result=get(f'jobs/{args.job}/result.json');p=copy.deepcopy(result.get('presentation',{}))
    if not p.get('rendered') or not p.get('evidence'):raise ValueError('No complete rendered result')
    if not result.get('modelInvoked'):raise ValueError('No model invocation recorded')
    narration=result.get('narration',{})
    if p.get('analysisStatus')=='reviewed-story':
        review=result.get('presentationReview',{})
        if review.get('source')=='bedrock-vlm-review':
            receipt=result.get('modelReview',{})
            if not receipt.get('calls') or receipt.get('modelInvoked') is not True or narration.get('modelInvoked') is not True:
                raise ValueError('Model Reviewer publication requires model call receipts')
        elif review.get('source')!='human-reviewed-video' or narration.get('modelInvoked') is not False:
            raise ValueError('Reviewed presentation must retain explicit provenance')
        if not review.get('sourceJob'):raise ValueError('Missing original analysis reference')
    elif not narration.get('modelInvoked'):
        raise ValueError('The published AI commentary requires an actual generated narration result')
    if not narration.get('segments'):raise ValueError('No timed commentary')
    item=get('library/'+result['video']['id']+'.json');rights=item.get('publication',{})
    if rights.get('basis') not in ['organizer-provided','licensed'] or not rights.get('source'):
        raise ValueError('Public result requires documented organizer-provided/licensed media')
    prefix='results/'+args.job+'/'
    def asset(source,name):
        key=prefix+name
        if source!=item['key'] and not source.startswith(f'jobs/{args.job}/'):raise ValueError('Unexpected source object')
        s3.copy_object(Bucket=site,Key=key,CopySource={'Bucket':bucket,'Key':source},MetadataDirective='REPLACE',
            ContentType=mimetypes.guess_type(name)[0] or 'application/octet-stream',CacheControl='public,max-age=31536000,immutable')
        s3.head_object(Bucket=site,Key=key)
        return '../'+key
    p['video']=asset(p['videoKey'],'replay.mp4');p['original']=asset(item['key'],'original.mp4')
    if result.get('presentationPlan'):
        plan_key=f'jobs/{args.job}/presentation-plan.json'
        s3.put_object(Bucket=bucket,Key=plan_key,Body=json.dumps(result['presentationPlan'],ensure_ascii=False).encode(),ContentType='application/json')
        p['plan']=asset(plan_key,'presentation-plan.json')
    for i,frame in enumerate(p['evidence']):frame['image']=asset(frame['imageKey'],f'frame-{i+1}.jpg')
    p['publication']=dict(source=rights['source'],basis=rights['basis'],job=args.job,project='HiAgent',
        videoSha256=item.get('sha256'),dataSources=(result.get('deepData') or {}).get('sources',[]))
    # Keep model/review provenance intact. Asset keys are not credentials.
    body=json.dumps(p,ensure_ascii=False,indent=2).encode()
    # Upload shell files independently of CDK changes, then atomically switch the manifest.
    for file in (ROOT/'web').iterdir():
        if file.is_file() and file.suffix in ['.html','.css','.js']:
            s3.upload_file(str(file),site,file.name,ExtraArgs={'ContentType':mimetypes.guess_type(file.name)[0] or 'text/plain','CacheControl':'no-cache'})
    page=(ROOT/'web/readme.html').read_text().replace('见各回合的素材来源记录',html.escape(rights['source'])).replace('见结果摘要中的任务 ID',html.escape(args.job))
    for key in ['readme','readme.html']:
        s3.put_object(Bucket=site,Key=key,Body=page.encode(),ContentType='text/html; charset=utf-8',CacheControl='no-cache')
    s3.put_object(Bucket=site,Key='demo/game.json',Body=body,ContentType='application/json',CacheControl='no-cache')
    session.client('cloudfront').create_invalidation(DistributionId=cfg['DistributionId'],InvalidationBatch={'Paths':{'Quantity':1,'Items':['/*']},'CallerReference':'release-'+str(time.time_ns())})
    receipt=dict(url=cfg['FrontendUrl'],job=args.job,account=account,source=rights['source'],model=result.get('model'),modelInvoked=result.get('modelInvoked'),status=p.get('analysisStatus','verified'))
    (ROOT/'verification').mkdir(exist_ok=True)
    (ROOT/'verification/publication.json').write_text(json.dumps(receipt,ensure_ascii=False,indent=2))
    print(json.dumps(receipt,ensure_ascii=False))

if __name__=='__main__':main()

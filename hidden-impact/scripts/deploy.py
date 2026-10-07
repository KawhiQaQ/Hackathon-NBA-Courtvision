"""Deploy without printing the private team access code."""
import json,os,secrets,subprocess
from pathlib import Path
root=Path(__file__).resolve().parents[1]
token=root/'.team-access-code'
if not token.exists():
 token.write_text(secrets.token_urlsafe(24));token.chmod(0o600)
cmd=[str(root.parent/'aws-preflight/node_modules/.bin/cdk'),'deploy','--profile','nba','--require-approval','never','--parameters','TeamKey='+token.read_text().strip(),'--outputs-file',str(root/'infra/cdk-outputs.json')]
result=subprocess.call(cmd,cwd=root/'infra')
if result==0:
 outputs=json.loads((root/'infra/cdk-outputs.json').read_text())['HiddenImpactTeam14']
 config=root/'.cloud-config.json'
 config.write_text(json.dumps({'url':outputs['FrontendUrl']})+'\n');config.chmod(0o600)
 print('Local proxy configuration updated from deployment outputs.')
raise SystemExit(result)

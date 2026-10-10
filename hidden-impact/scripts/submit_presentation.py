"""Submit an explicit source-bound presentation review to our authenticated API."""
import argparse,json,urllib.request
from pathlib import Path
ROOT=Path(__file__).resolve().parents[1]

def main():
    ap=argparse.ArgumentParser();ap.add_argument('--source-job',required=True);ap.add_argument('--review',type=Path,required=True);args=ap.parse_args()
    base=json.loads((ROOT/'.cloud-config.json').read_text())['url'].rstrip('/')
    token=(ROOT/'.team-access-code').read_text().strip()
    body={'sourceJob':args.source_job,'review':json.loads(args.review.read_text())}
    request=urllib.request.Request(base+'/api/presentations',data=json.dumps(body).encode(),headers={'Content-Type':'application/json','X-Team-Key':token})
    # Never automatically retry a POST after an uncertain network response.
    with urllib.request.urlopen(request,timeout=60) as response:receipt=json.load(response)
    (ROOT/'verification/presentation-submit.json').write_text(json.dumps(receipt,indent=2))
    print(json.dumps(receipt))

if __name__=='__main__':main()

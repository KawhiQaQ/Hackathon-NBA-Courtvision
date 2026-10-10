"""Estimate broadcast panning from the upper background, for direction cues only.
This is not player tracking or metric court calibration. Reject weak/large shifts.
"""
import base64,io
import numpy as np
from PIL import Image

def translation(before,after):
    a=before-before.mean();b=after-after.mean()
    window=np.outer(np.hanning(a.shape[0]),np.hanning(a.shape[1]))
    fa=np.fft.fft2(a*window);fb=np.fft.fft2(b*window);cross=fb*np.conj(fa)
    correlation=np.fft.ifft2(cross/np.maximum(abs(cross),1e-8)).real
    y,x=np.unravel_index(np.argmax(correlation),correlation.shape);confidence=float(correlation[y,x])
    if x>a.shape[1]/2:x-=a.shape[1]
    if y>a.shape[0]/2:y-=a.shape[0]
    if confidence<.08 or abs(x)>a.shape[1]*.18 or abs(y)>a.shape[0]*.25:return None
    return float(x),float(y),confidence

def attach(vision,inputs):
    source=sorted(inputs,key=lambda f:f['time']);rows=[];previous=None;offset=[0.,0.];last=-99
    for frame in source:
        im=Image.open(io.BytesIO(base64.b64decode(frame['image']))).convert('L').resize((320,180))
        # Scoreboards and most on-court movement are outside this band.
        band=np.asarray(im,dtype=float)[12:66,:];delta=None
        if previous is not None and 0<frame['time']-last<=.55:delta=translation(previous,band)
        if delta:offset=[offset[0]+delta[0]/320,offset[1]+delta[1]/180]
        rows.append({'time':frame['time'],'offset':offset[:],'confidence':delta[2] if delta else 0})
        previous=band;last=frame['time']
    if not rows:return vision
    for frame in vision['frames']:
        j=next((i for i,r in enumerate(rows) if r['time']>=frame['time']),len(rows)-1)
        a,b=rows[max(0,j-1)],rows[j];k=max(0,min(1,(frame['time']-a['time'])/max(.001,b['time']-a['time'])))
        frame['cameraOffset']=[round(a['offset'][i]+k*(b['offset'][i]-a['offset'][i]),6) for i in range(2)]
    vision['cameraMotion']='background-phase-correlation-v1'
    return vision

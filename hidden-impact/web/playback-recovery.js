// Bounded recovery of private media links; never restarts analysis or changes rounds.
export function createPlaybackRecovery(video,{refresh,reload,message,schedule=setTimeout,cancel=clearTimeout}){
 let generation=0,attempts=0,busy=false,timer=null,lastTime=0,wanted=false;
 const clear=()=>{if(timer!==null)cancel(timer);timer=null;};
 async function recover(){
  if(busy)return;
  clear();
  if(attempts>=2){message('视频加载中断，请点击重试。',true);return;}
  busy=true;attempts++;const token=generation,t=Number.isFinite(video.currentTime)?video.currentTime:lastTime;
  message('正在恢复视频连接…',false);
  try{const src=await refresh();if(token!==generation)return;reload(src,t,wanted);}
  catch(e){if(token===generation)message(e.message||'视频连接失败，请点击重试。',true);}
  finally{if(token===generation)busy=false;}
 }
 function stalled(){clear();const token=generation;timer=schedule(()=>{if(token===generation&&!video.paused)recover();},12000);}
 video.addEventListener('error',()=>{if(video.error?.code===1)return;recover();});
 video.addEventListener('waiting',stalled);video.addEventListener('stalled',stalled);
 video.addEventListener('play',()=>{wanted=true;});
 video.addEventListener('pause',()=>{if(!busy&&!video.error)wanted=false;});
 video.addEventListener('playing',()=>{clear();message('',false);});
 video.addEventListener('timeupdate',()=>{if(video.currentTime>lastTime+5)attempts=0;lastTime=video.currentTime;});
 return {reset(){generation++;clear();attempts=0;busy=false;lastTime=0;wanted=false;},retry(){attempts=0;return recover();}};
}

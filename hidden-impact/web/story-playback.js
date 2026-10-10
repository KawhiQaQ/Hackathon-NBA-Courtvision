// The exported MP4 contains the freezes; all evidence times remain source times.
export function sourceTime(t,timeline){
 let offset=0;
 for(const beat of timeline?.beats||[]){if(t<beat.start)break;if(t<beat.end)return beat.sourceTime;offset+=beat.duration;}
 return Math.max(0,t-offset);
}
export function replayTime(t,timeline){
 let offset=0;
 for(const beat of timeline?.beats||[]){if(t<=beat.sourceTime+.00001)break;offset+=beat.duration;}
 return t+offset;
}

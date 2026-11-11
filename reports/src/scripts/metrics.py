import yaml, csv, math, os, json, numpy as np
from PIL import Image
W='/home/huseyin/ros2_jazzy_ws'; C=W+'/src/indoor_delivery_project/config/'
gt={}
for k,f in [('campus','aruco_markers.yaml'),('tb','aruco_markers_two_buildings.yaml')]:
    d=yaml.safe_load(open(C+f)); gt[k]={m['id']:(m['pose']['x'],m['pose']['y'],m.get('kind')) for m in d['markers']}
out={}
for name in ['campus','campus2','campus3','campus4','campus5','campus6','campus_full_map','campus_full_map1','campus_full_map3','campus_full_map4','campus_full_map5','campus_full_map6','campus_full_map7']:
    D=f'{W}/maps/{name}'
    L=yaml.safe_load(open(D+'/aruco_landmarks.yaml'))
    sp=L.get('start_pose',{})
    world='tb' if abs(sp.get('x',0)+17)<1 and abs(sp.get('y',0)+17)<1 else 'campus'
    g=gt[world]; errs=[]; unk=0
    for m in L['markers']:
        if m['id'] in g: errs.append(math.hypot(m['x']-g[m['id']][0],m['y']-g[m['id']][1]))
        else: unk+=1
    t=np.genfromtxt(D+'/trajectory.csv',delimiter=',',names=True)
    xy=np.c_[t['slam_x'],t['slam_y']]; length=float(np.sum(np.hypot(*np.diff(xy,axis=0).T))) if t.size>1 else 0.0
    dur=float(t['t'][-1]-t['t'][0]) if t.size>1 else 0.0
    nobs=sum(1 for _ in open(D+'/observations.csv'))-1
    my=yaml.safe_load(open(D+'/map.yaml')); im=np.array(Image.open(D+'/map.pgm'))
    res=my['resolution']; occ=int((im<50).sum()); free=int((im>250).sum())
    out[name]=dict(world=world,created=str(L.get('created')),found=len(L['markers']),gt=len(g),
        matched=len(errs),unknown=unk,mean_err=float(np.mean(errs)) if errs else None,
        max_err=float(np.max(errs)) if errs else None, med_err=float(np.median(errs)) if errs else None,
        len_m=length,dur_s=dur,nobs=nobs,dp=len(L.get('delivery_points',{}) or {}),
        w_m=im.shape[1]*res,h_m=im.shape[0]*res,free_m2=free*res*res,occ_m2=occ*res*res,
        scans=os.path.exists(D+'/scans.npz'), online=os.path.exists(D+'/map_online.pgm'))
    print(name, {k:(round(v,2) if isinstance(v,float) else v) for k,v in out[name].items()})
json.dump(out,open('metrics.json','w'),indent=1)

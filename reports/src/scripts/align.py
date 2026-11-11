import yaml,json,math,numpy as np
W='/home/huseyin/ros2_jazzy_ws'; C=W+'/src/indoor_delivery_project/config/'
GT={k:{m['id']:m for m in yaml.safe_load(open(C+f))['markers']} for k,f in [('campus','aruco_markers.yaml'),('tb','aruco_markers_two_buildings.yaml')]}
met=json.load(open('metrics.json'))
for n,v in met.items():
    if not v['matched']: continue
    L=yaml.safe_load(open(f'{W}/maps/{n}/aruco_landmarks.yaml')); g=GT[v['world']]
    ms=[m for m in L['markers'] if m['id'] in g and m.get('observations',1)>0]
    A=np.array([[m['x'],m['y']] for m in ms]); B=np.array([[g[m['id']]['pose']['x'],g[m['id']]['pose']['y']] for m in ms])
    d=B-A; v['obs_markers']=len(ms); v['mean_err_obs']=float(np.mean(np.hypot(*d.T))); v['max_err_obs']=float(np.max(np.hypot(*d.T)))
    v['mean_dx']=float(d[:,0].mean()); v['mean_dy']=float(d[:,1].mean())
    if len(ms)>=3:
        ca,cb=A.mean(0),B.mean(0); H=(A-ca).T@(B-cb); U,S,Vt=np.linalg.svd(H); R=Vt.T@U.T
        if np.linalg.det(R)<0: Vt[1]*=-1; R=Vt.T@U.T
        A2=(R@(A-ca).T).T+cb; e=np.hypot(*(A2-B).T); v['aligned_mean']=float(e.mean()); v['aligned_max']=float(e.max()); v['rot_deg']=math.degrees(math.atan2(R[1,0],R[0,0]))
    print(n, {k:round(x,2) if isinstance(x,float) else x for k,x in v.items() if k in('obs_markers','mean_err_obs','max_err_obs','mean_dx','mean_dy','aligned_mean','aligned_max','rot_deg')})
json.dump(met,open('metrics.json','w'),indent=1)

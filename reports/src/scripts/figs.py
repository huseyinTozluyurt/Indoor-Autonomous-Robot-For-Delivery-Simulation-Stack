import yaml, csv, math, json, numpy as np, cv2
from indoor_delivery_project.aruco_utils import get_dictionary, MarkerDetector, generate_marker
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from PIL import Image
W='/home/huseyin/ros2_jazzy_ws'; C=W+'/src/indoor_delivery_project/config/'
def gtload(f): return {m['id']:m for m in yaml.safe_load(open(C+f))['markers']}
GT={'campus':gtload('aruco_markers.yaml'),'tb':gtload('aruco_markers_two_buildings.yaml')}
plt.rcParams.update({'font.size':9})
# ---------------- ArUco: marker sheet
d=get_dictionary('DICT_4X4_50')
ids=[10,11,40,41,1,6,12,30]
fig,ax=plt.subplots(1,len(ids),figsize=(12,1.9))
for a,i in enumerate(ids):
    im=generate_marker(i,200)
    ax[a].imshow(im,cmap='gray'); ax[a].set_title(f'ID {i} ({GT["tb"].get(i,{}).get("name","")[:16]})',fontsize=7); ax[a].axis('off')
plt.tight_layout(); plt.savefig('fig/aruco_markers.png',dpi=140); plt.close()
# ---------------- ArUco: synthetic range accuracy (same camera model as Gazebo mast camera)
Wd,Hd=640,480; f=(Wd/2)/math.tan(1.2/2); K=np.array([[f,0,Wd/2],[0,f,Hd/2],[0,0,1.]]); Dz=np.zeros(5)
mk=generate_marker(40,400)
det=MarkerDetector('DICT_4X4_50')
size=0.30; h=size/2; obj=np.array([[-h,h,0],[h,h,0],[h,-h,0],[-h,-h,0]],float)
full=size*500/400; hf=full/2; objf=np.array([[-hf,-hf,0],[hf,-hf,0],[hf,hf,0],[-hf,hf,0]],float)
rows=[]; demo=None
for ang in [0,30,50]:
  for Z in np.arange(1.0,9.01,0.25):
    R,_=cv2.Rodrigues(np.array([0,math.radians(ang),0.])); t=np.array([0.4,0.1,Z])
    pc=(R@objf.T).T+t; uv=(K@pc.T).T; uv=uv[:,:2]/uv[:,2:]
    src=np.array([[0,0],[mk.shape[1],0],[mk.shape[1],mk.shape[0]],[0,mk.shape[0]]],np.float32)
    Hm=cv2.getPerspectiveTransform(src,uv.astype(np.float32))
    img=cv2.warpPerspective(mk,Hm,(Wd,Hd),borderValue=235)
    img=np.clip(img+np.random.default_rng(int(Z*100)).normal(0,3,img.shape),0,255).astype(np.uint8)
    co,idd,_=det.detect(img)
    if idd is None: rows.append((ang,Z,None,None,None)); continue
    pts=co[0].reshape(4,2).astype(float); px=float(np.mean(np.linalg.norm(pts-np.roll(pts,1,0),axis=1)))
    ok,rv,tv=cv2.solvePnP(obj,pts,K,Dz,flags=cv2.SOLVEPNP_IPPE_SQUARE)
    est=np.linalg.norm(tv); tru=np.linalg.norm(t); nrm=cv2.Rodrigues(rv)[0][:,2]
    yaw_est=math.degrees(math.atan2(nrm[0],-nrm[2])) if False else math.degrees(math.atan2(-nrm[0],-nrm[2]))
    rows.append((ang,Z,est-tru,px,yaw_est))
    if ang==30 and abs(Z-3.0)<1e-6:
        demo=cv2.cvtColor(img,cv2.COLOR_GRAY2BGR); cv2.aruco.drawDetectedMarkers(demo,co,idd); cv2.drawFrameAxes(demo,K,Dz,rv,tv,0.15)
        cv2.putText(demo,f'ID 40  est {est:.2f} m  (true {tru:.2f} m)',(10,30),cv2.FONT_HERSHEY_SIMPLEX,0.7,(0,0,255),2)
cv2.imwrite('fig/aruco_synth_detect.png',demo) if demo is not None else None
json.dump(rows,open('aruco_synth.json','w'))
fig,ax=plt.subplots(1,2,figsize=(11,3.6))
for ang,c in [(0,'tab:blue'),(30,'tab:orange'),(50,'tab:green')]:
    r=[x for x in rows if x[0]==ang and x[2] is not None]
    ax[0].plot([x[1] for x in r],[x[2]*100 for x in r],'o-',ms=3,color=c,label=f'marker turned {ang}°')
    ax[1].plot([x[1] for x in r],[x[3] for x in r],'o-',ms=3,color=c,label=f'{ang}°')
    miss=[x[1] for x in rows if x[0]==ang and x[2] is None]
    if miss: ax[0].axvline(min(miss),color=c,ls=':',lw=1)
ax[0].axhline(0,color='k',lw=.5); ax[0].set_xlabel('true distance (m)'); ax[0].set_ylabel('range error (cm)'); ax[0].legend(); ax[0].set_title('solvePnP (IPPE_SQUARE) range error, 0.30 m marker')
ax[1].axhline(12,color='r',ls='--',lw=1,label='min_pixels = 12'); ax[1].set_xlabel('true distance (m)'); ax[1].set_ylabel('marker edge (px)'); ax[1].set_title('Apparent marker size in the 640×480 mast camera'); ax[1].legend()
for a in ax: a.grid(alpha=.3)
plt.tight_layout(); plt.savefig('fig/aruco_synth_accuracy.png',dpi=140); plt.close()
# ---------------- ArUco: real detections in campus_full_map7
M=W+'/maps/campus_full_map7'
obs=list(csv.DictReader(open(M+'/observations.csv')))
rng=np.array([float(o['range_2d_m']) for o in obs]); px=np.array([float(o['pixels']) for o in obs]); mid=np.array([int(o['marker_id']) for o in obs])
# residual range vs gt
res=[]
for o in obs:
    g=GT['tb'].get(int(o['marker_id']))
    if not g: continue
    sx,sy,syaw=float(o['slam_x']),float(o['slam_y']),math.radians(float(o['slam_yaw_deg']))
    cx=sx+0.15*math.cos(syaw); cy=sy+0.15*math.sin(syaw)
    res.append((float(o['range_2d_m']), float(o['range_2d_m'])-math.hypot(g['pose']['x']-sx,g['pose']['y']-sy), g['size']))
res=np.array(res)
fig,ax=plt.subplots(1,3,figsize=(13,3.6))
ax[0].hist(rng,bins=40,color='tab:blue'); ax[0].set_xlabel('2D range at detection (m)'); ax[0].set_ylabel('detections'); ax[0].set_title(f'{len(obs)} detections while mapping campus_full_map7')
for s,c in [(0.3,'tab:orange'),(0.6,'tab:green'),(1.0,'tab:purple')]:
    sel=np.array([GT['tb'].get(i,{}).get('size',0.3)==s for i in mid])
    if sel.any(): ax[1].scatter(rng[sel],px[sel],s=4,color=c,label=f'{s} m markers')
ax[1].set_xlabel('range (m)'); ax[1].set_ylabel('marker edge (px)'); ax[1].set_yscale('log'); ax[1].legend(); ax[1].set_title('Pixel size falls with range (log scale)')
u,cn=np.unique(mid,return_counts=True); ax[2].bar([str(x) for x in u],cn,color='tab:gray'); ax[2].set_xlabel('marker ID'); ax[2].set_ylabel('detections'); ax[2].tick_params(axis='x',labelsize=6,rotation=90); ax[2].set_title('Detections per marker')
for a in ax[:2]: a.grid(alpha=.3)
plt.tight_layout(); plt.savefig('fig/aruco_real_stats.png',dpi=140); plt.close()
fig,ax=plt.subplots(figsize=(6.5,3.6))
ax.scatter(res[:,0],res[:,1],s=3,alpha=.5); ax.axhline(0,color='k',lw=.5); ax.set_ylim(-3,3)
ax.set_xlabel('measured range (m)'); ax.set_ylabel('measured − expected (m)'); ax.set_title('Range residual vs. ground-truth marker position (includes SLAM pose error)'); ax.grid(alpha=.3)
plt.tight_layout(); plt.savefig('fig/aruco_range_residual.png',dpi=140); plt.close()
stats=dict(n=len(obs),markers=len(u),rng_med=float(np.median(rng)),rng_max=float(rng.max()),res_med_abs=float(np.median(np.abs(res[:,1]))),res_p90=float(np.percentile(np.abs(res[:,1]),90)),
   synth={str(a):{'max_range_detected':max([x[1] for x in rows if x[0]==a and x[2] is not None]), 'err_cm_at3':[round(x[2]*100,2) for x in rows if x[0]==a and abs(x[1]-3)<1e-6 and x[2] is not None], 'err_cm_max_le6':max([abs(x[2])*100 for x in rows if x[0]==a and x[2] is not None and x[1]<=6])} for a in [0,30,50]})
json.dump(stats,open('aruco_stats.json','w'),indent=1); print(stats)
# ---------------- SLAM: trajectories and markers campus_full_map7
tr=np.genfromtxt(M+'/trajectory.csv',delimiter=',',names=True)
L=yaml.safe_load(open(M+'/aruco_landmarks.yaml')); sp=L['start_pose']
occ=np.flipud(np.array(Image.open(M+'/map.pgm'))); my=yaml.safe_load(open(M+'/map.yaml'))
ext=[my['origin'][0],my['origin'][0]+occ.shape[1]*0.1,my['origin'][1],my['origin'][1]+occ.shape[0]*0.1]
def tf(x,y): return x+sp['x'], y+sp['y']
fig,ax=plt.subplots(1,2,figsize=(14,5))
ax[0].imshow(occ,cmap='gray',origin='lower',extent=ext,alpha=.6)
ax[0].plot(tr['slam_x'],tr['slam_y'],'b-',lw=1,label='EKF-SLAM pose')
ax[0].plot(*tf(tr['odom_x'],tr['odom_y']),'r-',lw=.8,label='wheel odometry only')
ax[0].plot(*tf(tr['dr_x'],tr['dr_y']),'-',color='orange',lw=.8,label='wheels + gyro (dead reckoning)')
ax[0].legend(loc='lower right',fontsize=7); ax[0].set_title('campus_full_map7: robot path from the three pose sources')
ax[1].imshow(occ,cmap='gray',origin='lower',extent=ext,alpha=.6)
errs=[]
for m in L['markers']:
    g=GT['tb'].get(m['id'])
    if not g: continue
    gx,gy=g['pose']['x'],g['pose']['y']; e=math.hypot(m['x']-gx,m['y']-gy); errs.append((m['id'],e,m['sigma_xy'],m['observations'],g['kind']))
    ax[1].plot(gx,gy,'gs',ms=5); ax[1].plot(m['x'],m['y'],'r.',ms=6); ax[1].plot([gx,m['x']],[gy,m['y']],'k-',lw=.8)
missing=[i for i in GT['tb'] if i not in [m['id'] for m in L['markers']]]
for i in missing: ax[1].plot(GT['tb'][i]['pose']['x'],GT['tb'][i]['pose']['y'],'mx',ms=8)
ax[1].plot([],[],'gs',label='true marker (world file)'); ax[1].plot([],[],'r.',label='SLAM estimate'); ax[1].plot([],[],'mx',label='never detected')
ax[1].legend(loc='lower right',fontsize=7); ax[1].set_title('Marker map vs. ground truth')
plt.tight_layout(); plt.savefig('fig/slam_traj_markers.png',dpi=130); plt.close()
errs.sort(key=lambda x:x[0])
fig,ax=plt.subplots(figsize=(11,3.2))
cols={'delivery':'tab:blue','room':'tab:orange','corridor':'tab:green'}
ax.bar([str(e[0]) for e in errs],[e[1] for e in errs],color=[cols.get(e[4],'gray') for e in errs])
ax.plot([str(e[0]) for e in errs],[e[2] for e in errs],'k_',ms=12,label='EKF σxy')
for k,c in cols.items(): ax.bar([],[],color=c,label=k)
ax.set_xlabel('marker ID'); ax.set_ylabel('position error (m)'); ax.legend(fontsize=7); ax.grid(alpha=.3,axis='y'); ax.set_title('campus_full_map7: per-marker error against the world file')
plt.tight_layout(); plt.savefig('fig/slam_marker_err.png',dpi=140); plt.close()
# drift of odom vs slam at end
end=dict(odom_end=math.hypot(tf(tr['odom_x'][-1],tr['odom_y'][-1])[0]-tr['slam_x'][-1],tf(tr['odom_x'][-1],tr['odom_y'][-1])[1]-tr['slam_y'][-1]),
 dr_end=math.hypot(tf(tr['dr_x'][-1],tr['dr_y'][-1])[0]-tr['slam_x'][-1],tf(tr['dr_x'][-1],tr['dr_y'][-1])[1]-tr['slam_y'][-1]),
 yaw_odom_vs_slam_deg=math.degrees(math.atan2(math.sin(tr['odom_yaw'][-1]-tr['slam_yaw'][-1]),math.cos(tr['odom_yaw'][-1]-tr['slam_yaw'][-1]))),
 yaw_dr_vs_slam_deg=math.degrees(math.atan2(math.sin(tr['dr_yaw'][-1]-tr['slam_yaw'][-1]),math.cos(tr['dr_yaw'][-1]-tr['slam_yaw'][-1]))),
 missing=missing, errs=errs)
json.dump(end,open('slam_stats.json','w'),indent=1); print(end)

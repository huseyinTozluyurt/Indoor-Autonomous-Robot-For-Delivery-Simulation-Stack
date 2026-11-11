import sys, math, time, itertools, json, yaml, numpy as np
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from indoor_delivery_project.aruco_slam_mapper import OccupancyGrid2D
from indoor_delivery_project.delivery_navigator import ClearancePlanner, DeliveryNavigator
M='/home/huseyin/ros2_jazzy_ws/maps/campus_full_map7'
grid=OccupancyGrid2D.load(M+'/map.yaml')
L=yaml.safe_load(open(M+'/aruco_landmarks.yaml'))
P=L['delivery_points']; print(list(P))
t=time.time(); plan=ClearancePlanner(grid,robot_radius=0.45); tbuild=time.time()-t
home=(L['start_pose']['x'],L['start_pose']['y'])
stops=[s for s in ['a_delivery_point_2','b_delivery_point_3','r_delivery_point_1','b_delivery_point_2','a_delivery_point_7','c_table_north'] if s in P]
if len(stops)<6: stops=list(P)[:6]
print('stops',stops)
nodes=[('home',home)]+[(s,(P[s]['x'],P[s]['y'])) for s in stops]+[('home',home)]
t=time.time(); trees=[plan.dijkstra_tree(xy) for _,xy in nodes[:-1]]; ttree=(time.time()-t)/len(trees)
n=len(nodes); D=np.full((n,n),np.inf)
for i,tr in enumerate(trees):
    for j,(_,xy) in enumerate(nodes): D[i,j]=0 if i==j else plan.tree_cost(tr,xy)
k=len(stops)
def length(o): s=[0]+list(o)+[n-1]; return sum(D[a,b] for a,b in zip(s,s[1:]))
given=list(range(1,k+1))
t=time.time(); hk=DeliveryNavigator._held_karp(D,k); thk=time.time()-t
nn=DeliveryNavigator._nearest_neighbour(D,k); to=DeliveryNavigator._two_opt(D,nn)
bf=min(itertools.permutations(given),key=length)
res=dict(build_s=tbuild,tree_s=ttree,grid=list(plan.shape),res=plan.res,stops=stops,
 given=length(given),hk=length(hk),nn=length(nn),twoopt=length(to),brute=length(bf),
 hk_order=[nodes[i][0] for i in hk],thk=thk,D=np.round(D,1).tolist())
# straight line vs dijkstra for each leg from home
res['legs_home']=[(s,float(D[0,i+1]),math.hypot(P[s]['x']-home[0],P[s]['y']-home[1])) for i,s in enumerate(stops)]
# scaling held-karp vs brute
rng=np.random.default_rng(0); sc=[]
for kk in range(2,13):
    pts=rng.uniform(-20,20,(kk+2,2)); DD=np.hypot(*(pts[:,None,:]-pts[None,:,:]).transpose(2,0,1))
    t=time.time(); DeliveryNavigator._held_karp(DD,kk); a=time.time()-t
    b=None
    if kk<=9:
        t=time.time(); min(itertools.permutations(range(1,kk+1)),key=lambda o:sum(DD[x,y] for x,y in zip((0,)+o,o+(kk+1,)))); b=time.time()-t
    sc.append((kk,a,b))
res['scaling']=sc
# Dijkstra vs A* single query
a,b=home,(P[stops[1]]['x'],P[stops[1]]['y'])
t=time.time(); p1=plan.shortest_path(a,b,method='dijkstra'); td=time.time()-t
t=time.time(); p2=plan.shortest_path(a,b,method='astar'); ta=time.time()-t
pl=lambda p: sum(math.hypot(x2-x1,y2-y1) for (x1,y1),(x2,y2) in zip(p,p[1:]))
res['single']=dict(dij_s=td,astar_s=ta,dij_len=pl(p1),astar_len=pl(p2))
json.dump(res,open('dij.json','w'),indent=1); print(json.dumps({k:v for k,v in res.items() if k!='D'},indent=0))
# FIGURES
ext=[plan.origin[0],plan.origin[0]+plan.shape[1]*plan.res,plan.origin[1],plan.origin[1]+plan.shape[0]*plan.res]
fig,ax=plt.subplots(1,2,figsize=(14,5.2))
im=ax[0].imshow(np.where(np.isfinite(plan.cost),plan.cost,np.nan),origin='lower',extent=ext,cmap='viridis'); ax[0].set_facecolor('#333')
ax[0].set_title('Planning cost per 0.2 m cell (grey = blocked: wall, < robot radius, or unknown)'); plt.colorbar(im,ax=ax[0],fraction=0.03,label='cell cost (1 = free centre, up to 5 near walls)')
G=np.array(trees[0][0]).reshape(plan.shape)*plan.res
im2=ax[1].imshow(np.where(np.isfinite(G),G,np.nan),origin='lower',extent=ext,cmap='magma'); ax[1].set_facecolor('#333')
ax[1].plot(*home,'c*',ms=14); ax[1].set_title('Full Dijkstra tree from home: cost-to-reach every cell (m)'); plt.colorbar(im2,ax=ax[1],fraction=0.03)
for a_ in ax: a_.set_xlabel('x (m)'); a_.set_ylabel('y (m)')
plt.tight_layout(); plt.savefig('fig/dij_costmap.png',dpi=130)
def route(o):
    s=[0]+list(o)+[n-1]; pts=[]
    for a_,b_ in zip(s,s[1:]): pts+=plan.tree_path(trees[a_],nodes[b_][1]) or []
    return np.array(pts)
occ=np.flipud(np.array(__import__('PIL.Image',fromlist=['x']).open(M+'/map.pgm')))
my=yaml.safe_load(open(M+'/map.yaml')); e2=[my['origin'][0],my['origin'][0]+occ.shape[1]*0.1,my['origin'][1],my['origin'][1]+occ.shape[0]*0.1]
fig,ax=plt.subplots(1,2,figsize=(15,5.4))
for a_,o,title,c in [(ax[0],given,f'Order of arrival: {length(given):.1f} m','tab:red'),(ax[1],hk,f'Held-Karp optimal order: {length(hk):.1f} m','tab:blue')]:
    a_.imshow(occ,cmap='gray',origin='lower',extent=e2); r=route(o); a_.plot(r[:,0],r[:,1],'-',color=c,lw=2)
    a_.plot(*home,'g*',ms=16)
    for idx,i in enumerate(o):
        x,y=nodes[i][1]; a_.plot(x,y,'o',color='orange',ms=9,mec='k'); a_.annotate(f'{idx+1}. {nodes[i][0]}',(x,y),xytext=(4,4),textcoords='offset points',fontsize=7,color='k',bbox=dict(fc='white',alpha=.7,lw=0))
    a_.set_title(title); a_.set_xlim(e2[0]+2,e2[1]-2)
plt.tight_layout(); plt.savefig('fig/dij_tour_compare.png',dpi=130)
fig,ax=plt.subplots(figsize=(7,4))
ks=[s[0] for s in sc]; ax.semilogy(ks,[s[1]*1000 for s in sc],'o-',label='Held-Karp DP  O(k²·2^k)')
ax.semilogy([s[0] for s in sc if s[2]],[s[2]*1000 for s in sc if s[2]],'s--',label='Brute force  O(k!)')
ax.set_xlabel('number of stops k'); ax.set_ylabel('time (ms, log)'); ax.grid(alpha=.3); ax.legend(); ax.set_title('Ordering cost: exact DP vs. trying every order (Python, this PC)')
plt.tight_layout(); plt.savefig('fig/dij_scaling.png',dpi=130)

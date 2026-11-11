import json, numpy as np
import matplotlib; matplotlib.use('Agg'); import matplotlib.pyplot as plt
from PIL import Image, ImageDraw, ImageFont
met=json.load(open('metrics.json'))
full=['campus','campus4','campus5','campus6','campus_full_map','campus_full_map3','campus_full_map4','campus_full_map5','campus_full_map7']
lab=[n.replace('campus_full_map','cfm') for n in full]
fig,ax=plt.subplots(1,3,figsize=(14,3.8))
x=np.arange(len(full))
abs_=[met[n]['mean_err_obs'] for n in full]; al=[met[n].get('aligned_mean',np.nan) for n in full]; mx=[met[n]['max_err_obs'] for n in full]
ax[0].bar(x-0.2,abs_,0.4,label='mean error (absolute)'); ax[0].bar(x+0.2,al,0.4,label='mean error after best rigid fit (shape)')
ax[0].set_yscale('log'); ax[0].set_ylabel('m (log)'); ax[0].set_title('Marker position error vs. world file'); ax[0].legend(fontsize=7)
ax[1].bar(x,[abs(met[n].get('rot_deg',0)) for n in full],color='tab:red'); ax[1].set_ylabel('degrees'); ax[1].set_title('Global rotation of the map (|best-fit angle|)'); ax[1].set_ylim(0,20)
ax[1].text(0,19,'100°',ha='center',va='top',fontsize=8,color='tab:red')
ax[2].bar(x,[met[n]['obs_markers'] for n in full],color='tab:green',label='markers observed'); ax[2].plot(x,[met[n]['gt'] for n in full],'k_',ms=14,label='markers in world')
ax[2].set_title('Coverage: markers mapped'); ax[2].legend(fontsize=7)
for a in ax: a.set_xticks(x); a.set_xticklabels(lab,rotation=40,ha='right',fontsize=8); a.grid(alpha=.3,axis='y')
for a in ax: a.axvline(3.5,color='gray',ls='--',lw=1)
ax[0].text(1.5,ax[0].get_ylim()[1]*0.6,'campus_area',ha='center',fontsize=8,color='gray'); ax[0].text(6,ax[0].get_ylim()[1]*0.6,'two_buildings',ha='center',fontsize=8,color='gray')
plt.tight_layout(); plt.savefig('fig/evo_metrics.png',dpi=140); plt.close()
fig,ax=plt.subplots(figsize=(8,3.2))
ax.bar(x,[met[n]['len_m'] for n in full],color='tab:blue',label='path length (m)')
ax2=ax.twinx(); ax2.plot(x,[met[n]['dur_s']/60 for n in full],'o-',color='tab:orange',label='sim time (min)')
ax.set_xticks(x); ax.set_xticklabels(lab,rotation=40,ha='right',fontsize=8); ax.set_ylabel('driven path (m)'); ax2.set_ylabel('sim minutes')
ax.set_title('Effort per mapping run'); ax.legend(loc='upper left',fontsize=7); ax2.legend(loc='upper right',fontsize=7)
plt.tight_layout(); plt.savefig('fig/evo_effort.png',dpi=140); plt.close()
W='/home/huseyin/ros2_jazzy_ws/maps'
def sheet(names,cols,out,tw=520,th=400):
    ims=[]
    for n in names:
        im=Image.open(f'{W}/{n}/map_preview.png').convert('RGB'); im.thumbnail((tw,th-30))
        c=Image.new('RGB',(tw,th),'white'); c.paste(im,((tw-im.width)//2,30)); d=ImageDraw.Draw(c)
        try: f=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf',20)
        except: f=None
        d.text((8,4),f"{n}  ({met[n]['created'][:10]})",fill='black',font=f); ims.append(c)
    rows=(len(ims)+cols-1)//cols; S=Image.new('RGB',(tw*cols,th*rows),'white')
    for i,c in enumerate(ims): S.paste(c,((i%cols)*tw,(i//cols)*th))
    S.save(out)
sheet(['campus','campus4','campus5','campus6'],2,'fig/evo_campus_area.png')
sheet(['campus_full_map','campus_full_map3','campus_full_map4','campus_full_map5','campus_full_map7'],2,'fig/evo_two_buildings.png')
for a,b in [('campus_full_map4','map_preview_online.png'),('campus_full_map5','map_preview_online.png')]:
    pass

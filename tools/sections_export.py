"""Writes 2D cross sections of the model to sections.json. Run: freecadcmd sections_export.py"""
import os, json, math
os.environ["SMN_NO_EXPORT"]="1"
HERE=os.path.dirname(os.path.abspath(__file__)) if "__file__" in dir() else os.getcwd()
exec(open(os.path.join(HERE,"..","freecad","SolarMeshtasticNodeMini_Enclosure.FCMacro"),encoding="utf-8").read(), globals())
out={}
def sect(name, shapes, plane, val, axes):
    segs=[]
    for sh,tag in shapes:
        if sh is None: continue
        if plane=="y": cut=box(-300, val-0.01, -300, 700, 0.02, 700)
        elif plane=="x": cut=box(val-0.01, -300, -300, 0.02, 700, 700)
        else: cut=box(-300,-300, val-0.01, 700, 700, 0.02)
        c=sh.common(cut)
        for e in c.Edges:
            pts=[e.valueAt(e.FirstParameter+(e.LastParameter-e.FirstParameter)*i/12) for i in range(13)]
            segs.append([tag,[[getattr(p,axes[0]),getattr(p,axes[1])] for p in pts]])
    out[name]=segs
nut  = cyl(L_IN-VENT_NUT_H, VENT_Y, VENT_Z, VENT_NUT_D/2, VENT_NUT_H, V(1,0,0))
plug = cyl(L_IN+WALL-VENT_THREAD, VENT_Y, VENT_Z, 6.0, VENT_THREAD, V(1,0,0)).fuse(cyl(L_IN+WALL, VENT_Y, VENT_Z, 10.0, 8.0, V(1,0,0)))
legp = leg.copy(); legp.translate(V(TIE_X[0]-LEG_T/2, 0, 0))
sect("vent_xz",   [(base,"base"),(lid,"lid"),(nut,"nut"),(plug,"plug")], "y", VENT_Y, ("x","z"))
sect("sma_xz",    [(base,"base"),(lid,"lid"),(pcb,"pcb"),(comps,"parts")], "y", SMA_Y, ("x","z"))
sect("rim_xz",    [(base,"base"),(lid,"lid")], "y", 20.0, ("x","z"))
sect("column_xz", [(base,"base"),(lid,"lid")], "y", -BOSS_OFF, ("x","z"))
sect("tie_yz",    [(base,"base"),(legp,"leg")], "x", TIE_X[0], ("y","z"))
sect("floor_xy",  [(base,"base")], "z", -FLOOR+TIE_SKIN+1.5, ("x","y"))
sect("pcb_xy",    [(base,"base"),(pcb,"pcb"),(plate,"plate")], "z", PCB_Z+0.8, ("x","y"))
json.dump(out, open(os.path.join(HERE,"sections.json"),"w"))
print("ok", {k:len(v) for k,v in out.items()})

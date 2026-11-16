import streamlit as st
import numpy as np
import pandas as pd
import plotly.graph_objects as go

st.set_page_config(page_title="SaltScape | Save the water, not just the day", page_icon="🌱", layout="wide")
st.markdown("""<style>
.stApp {background: #0b1420;color:#edf5f2;}
.block-container {padding-top:1.4rem;max-width:1280px;}
h1,h2,h3 {color:#e9fff7!important;}
[data-testid="stMetric"] {background:#142637;border:1px solid #29495a;padding:14px;border-radius:13px;}
[data-testid="stSidebar"] {background:#10202e;}
</style>""", unsafe_allow_html=True)

CROPS = [
    {"name":"Lettuce", "area":80.0, "et":4.2,"priority":1.2},
    {"name":"Tomato", "area":100.0,"et":5.2,"priority":1.0},
    {"name":"Barley", "area":120.0,"et":4.0,"priority":0.8},
]
DAYS=56
CAPACITY_MM=150.0
START_WATER_MM=110.0
MIN_WATER_MM=25.0
WATER_EFFICIENCY=0.9

# Simplified, single mixed root-zone bucket. Salinity represents EC-equivalent
# pore-water concentration, NOT laboratory-measured saturated-paste ECe.
# Conversion 0.64 g/L per dS/m is a rough TDS/EC approximation.
def simulate(allocation_fractions, supply_l_week, source_ec):
    fractions=np.array(allocation_fractions,dtype=float)
    fractions=np.maximum(fractions,0)
    fractions=fractions/fractions.sum() if fractions.sum()>0 else np.ones(3)/3
    states=[]
    for c in CROPS:
        starting_ec=2.0
        states.append({"water":START_WATER_MM,"salt":START_WATER_MM*starting_ec*0.64,"deficit":0.0,"drain":0.0,"irrig":0.0})
    records=[]
    for day in range(1,DAYS+1):
        for i,c in enumerate(CROPS):
            state=states[i]
            # Weekly allocation expressed as seven uniform daily applications.
            gross_mm=supply_l_week*fractions[i]/c["area"]/7.0
            root_irrig_mm=gross_mm*WATER_EFFICIENCY
            state["irrig"]+=gross_mm*c["area"]
            # Salt brought in by applied irrigation water (g/m²).
            state["salt"]+=root_irrig_mm*source_ec*0.64
            state["water"]+=root_irrig_mm
            # Plant water use cannot exceed water above conceptual dry minimum.
            actual_et=min(c["et"],max(0,state["water"]-MIN_WATER_MM))
            state["water"]-=actual_et
            state["deficit"]+=(c["et"]-actual_et)*c["area"]
            # Drainage when the simple bucket exceeds field capacity.
            drainage=max(0,state["water"]-CAPACITY_MM)
            if drainage>0:
                fraction_removed=min(1.0,drainage/max(state["water"],1e-9))
                state["salt"]*=1-fraction_removed
                state["water"]-=drainage
                state["drain"]+=drainage*c["area"]
            pore_ec=state["salt"]/(max(state["water"],1e-9)*0.64)
            records.append({"day":day,"field":c["name"],"ec_proxy":pore_ec,
                            "soil_water":state["water"],"cum_deficit_l":state["deficit"],
                            "cum_irrig_l":state["irrig"]})
    df=pd.DataFrame(records)
    last=df[df.day==DAYS].copy()
    # An explicit scoring convention, NOT a crop yield or measured soil-risk model.
    # Salt burden beyond 4 dS/m and unmet water demand are penalized.
    salt_penalty=sum(c["priority"]*max(0,float(last.iloc[i].ec_proxy)-4.0)**2 for i,c in enumerate(CROPS))
    shortage_penalty=sum(c["priority"]*float(last.iloc[i].cum_deficit_l)/(c["area"]*c["et"]*DAYS) for i,c in enumerate(CROPS))
    score=salt_penalty*0.65+shortage_penalty*24.0
    return df,last,score,shortage_penalty,salt_penalty

st.markdown("# 🌱 SaltScape")
st.caption("SAVE THE WATER. DON'T SACRIFICE THE SOIL.  •  Interactive desert-farm decision lab")
st.markdown("**The challenge:** You have limited irrigation water for three fields. Can you keep crops watered without letting salts accumulate in their root zones?")

with st.sidebar:
    st.header("⚗️ Scenario controls")
    shortage=st.slider("Water shortage",0,70,35,5,help="Percent reduction from total estimated weekly crop demand")
    source_ec=st.slider("Irrigation water EC (dS/m)",0.3,5.0,2.5,0.1,help="An indicative dissolved-salt concentration proxy")
    st.markdown("**Choose your irrigation strategy**")
    strategy=st.radio("Strategy",["My allocation","Equal split","Optimize balance"],label_visibility="collapsed")
    st.divider()
    st.caption("Preconfigured example farm. The model assumes constant daily crop demand, fixed areas, uniform daily irrigation and a mixed root zone. See Model notes below.")

normal_weekly=sum(c["area"]*c["et"]*7 for c in CROPS)
budget=normal_weekly*(1-shortage/100)

col1,col2,col3=st.columns(3)
col1.metric("Water available / week",f"{budget:,.0f} L")
col2.metric("Normal weekly demand",f"{normal_weekly:,.0f} L")
col3.metric("Scenario duration","8 weeks")

st.subheader("1  Set the allocation")
with st.expander("Edit your allocation (for the My allocation mode)",expanded=True):
    a,b,c=st.columns(3)
    p1=a.slider("🥬 Lettuce priority",0,100,35,5)
    p2=b.slider("🍅 Tomato priority",0,100,35,5)
    p3=c.slider("🌾 Barley priority",0,100,30,5)
    if p1+p2+p3==0:
        st.warning("All three sliders are zero. Equal shares are used.")
    st.caption("These sliders express relative shares, automatically normalized to 100%.")

manual=np.array([p1,p2,p3],dtype=float)
manual=manual/manual.sum() if manual.sum()>0 else np.ones(3)/3
same=np.ones(3)/3

# Optimize a clear bounded search over 5%-increment allocations.
# It is reproducible, transparent and fast for a three-field prototype.
@st.cache_data(show_spinner=False)
def best_allocation(supply, ec):
    best=None
    for x in range(0,101,5):
        for y in range(0,101-x,5):
            z=100-x-y
            fractions=np.array([x,y,z],dtype=float)/100
            _,_,score,_,_=simulate(fractions,supply,ec)
            if best is None or score<best[0]:
                best=(score,fractions)
    return best[1]

with st.spinner("Exploring irrigation strategies..."):
    optimum=best_allocation(round(budget,2),round(source_ec,2))
chosen={"My allocation":manual,"Equal split":same,"Optimize balance":optimum}[strategy]
df,last,score,water_penalty,salt_penalty=simulate(chosen,budget,source_ec)
_,base_last,base_score,_,_=simulate(manual,budget,source_ec)
_,opt_last,opt_score,_,_=simulate(optimum,budget,source_ec)

st.subheader("2  Eight-week reveal")
fig=go.Figure()
colors={"Lettuce":"#5ed3a4","Tomato":"#ffae6f","Barley":"#80baff"}
for name in colors:
    part=df[df.field==name]
    fig.add_trace(go.Scatter(x=part.day/7,y=part.ec_proxy,mode="lines",name=name,line=dict(color=colors[name],width=3)))
fig.add_hline(y=4.0,line_dash="dot",line_color="#ffcf76",annotation_text="Illustrative index reference (not a crop tolerance threshold)")
fig.update_layout(title="Root-zone pore-water EC proxy through time",xaxis_title="Week",yaxis_title="EC-equivalent proxy (dS/m)",template="plotly_dark",paper_bgcolor="#0b1420",plot_bgcolor="#10202e",legend=dict(orientation="h"),height=390,margin=dict(l=20,r=10,t=70,b=20))
st.plotly_chart(fig,use_container_width=True)
st.caption("The salt curve shows a simplified mixed-bucket concentration estimate. It is NOT measured soil ECe, a calibrated crop-yield forecast, or field advice.")

st.subheader("3  See the state of each field")
cols=st.columns(3)
for i,(col,c) in enumerate(zip(cols,CROPS)):
    ec=float(last.iloc[i].ec_proxy)
    water=float(last.iloc[i].soil_water)
    label="HIGH INDEX" if ec>=6 else "ELEVATED INDEX" if ec>=4 else "LOWER INDEX"
    with col:
        st.markdown(f"### {['🥬','🍅','🌾'][i]} {c['name']}")
        st.metric("End-of-scenario EC proxy",f"{ec:.1f} dS/m")
        st.metric("Modeled root-zone water",f"{water:.0f} mm")
        st.caption(f"{label} · {chosen[i]*100:.0f}% of weekly water allocation")

st.subheader("4  Beat the optimizer")
x,y=st.columns(2)
with x:
    st.markdown("**Your allocation**")
    st.write(" · ".join(f"{name} {v:.0%}" for name,v in zip([c['name'] for c in CROPS],manual)))
    st.metric("Scenario score (lower is better)",f"{base_score:.2f}")
with y:
    st.markdown("**Computer-search allocation**")
    st.write(" · ".join(f"{name} {v:.0%}" for name,v in zip([c['name'] for c in CROPS],optimum)))
    st.metric("Scenario score (lower is better)",f"{opt_score:.2f}")
if base_score>opt_score+1e-6:
    st.success(f"The search found a {100*(base_score-opt_score)/base_score:.1f}% lower **model-defined penalty** than your allocation. This is not a verified crop-yield improvement.")
else:
    st.info("Your allocation matches the best model-defined score within this grid search!")
st.caption("The objective penalizes modeled crop water shortfall and EC-proxy values above an illustrative threshold; it reflects chosen weights, not a field-validated agricultural optimum.")

with st.expander("🔬 Model notes, assumptions and limitations"):
    st.markdown("""
**What is modeled:** Three idealized root-zone water buckets, each with an initial water depth of 110 mm (capacity 150 mm). Every day, 90% of gross irrigation enters the root zone, dissolved salt comes with this water, crop evapotranspiration removes water but not salt, and water draining beyond capacity carries a well-mixed fraction of salt away.

**Salt input:** A rough relation of total dissolved solids (g/L) ≈ 0.64 × irrigation-water electrical conductivity (dS/m). This is water-quality context, not precise soil chemistry.

**Not modeled:** Rainfall, irrigation timing, groundwater, capillary rise, soil layering, salt precipitation, soil-specific hydraulic transport, changing growth stages, temperature effects, or measured crop yields. The chart reports **pore-water concentration proxy**, not measured saturated-paste electrical conductivity (ECe). Accordingly, real crop tolerance thresholds cannot be directly applied.

**Optimizer:** Exhaustive search on allocations in increments of 5%, minimizing a transparent illustrative penalty for unmet crop water demand and elevated salinity proxy. The 4 dS/m comparison line is an **illustrative scoring reference**, not a universal crop threshold.

**Intended use:** Educational climate decision demo; not a farming, irrigation, or water-quality prescription. Reliable recommendations require local soil measurements and validation.

**Scientific starting points:** FAO Irrigation and Drainage Paper 29 (Water Quality for Agriculture); FAO-56 crop evapotranspiration methodology. This prototype deliberately uses fixed illustrative ET values instead of claiming live weather-based forecasts.
""")

st.divider()
st.caption("SaltScape · Built as a hackathon prototype · Every number is a scenario estimate, not a field measurement")

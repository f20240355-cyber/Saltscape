# SaltScape

An interactive, **educational** desert irrigation/water-scarcity simulator. It compares how three different irrigation allocations change water deficit and an approximate pore-water salinity proxy over eight weeks.

## Run

1. Install Python 3.10+.
2. Open a terminal in this folder.
3. `python -m pip install -r requirements.txt`
4. `python -m streamlit run app.py`

The terminal will display a local URL (usually http://localhost:8501).

## Demo

1. Show the three fields, demand, and water budget.
2. Set shortage to 35% and irrigation-water EC to 2.5 dS/m.
3. Choose "My allocation" and change the three priority sliders.
4. Compare the eight-week pore-water EC proxy curves and the field summary.
5. Switch to "Optimize balance" and compare the allocation shares and illustrative score.
6. Expand "Model notes" to explain exactly what is and isn't scientifically modeled.

## What to say to judges

"Most tools tell a farmer how to reduce irrigation. SaltScape explores the trade-off those suggestions can miss: lower irrigation can mean less drainage and potentially increasing salt concentration. Here, we model three idealized fields for eight weeks and compare our own allocations against a transparent optimization search. This is an educational decision prototype, not a validated field advisory system."

## Scientific limitations

This deliberately simplified mixed-bucket simulation is NOT a soil-salinity prediction validated against real data. Its pore-water EC proxy is not the same as laboratory ECe. Chart threshold is illustrative, not a crop tolerance threshold. Daily ET is fixed for clarity. There are no external API calls and no accounts required.

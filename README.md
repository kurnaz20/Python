# B2B book distribution dashboard

ISL 467E · Homework I. This Streamlit app analyses invoice lines from the Transaction sheet of B2B_Transaction_Data_.xlsx. The bundled data/transactions.csv.gz is a compressed CSV export of all 664,154 source lines and all ten columns. The app reads it directly. No external data service or credentials are required.

## Run locally

Use Python 3.11 or 3.12. Open a terminal in the directory containing streamlit_app.py.

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m streamlit run streamlit_app.py
```

## Publish for submission

1. Extract the ZIP. Upload its contents, including the data folder, to the root of a public GitHub repository. The optional .streamlit folder supplies the colour theme.
2. Open https://share.streamlit.io and create an app from that repository. Choose its branch, use streamlit_app.py as the main file, and select Python 3.11 or 3.12 under Advanced settings.
3. Deploy and open the published URL in a signed-out window. Check the default metrics, change a city filter, and select a product in the forecast.
4. Submit both the public GitHub repository URL and the public dashboard URL on Ninova.

## Reconcile the default view

664,143 eligible lines, 47,468 invoices, 1,201 buying accounts and 1,889,193 units. Six missing quantities and five zero-quantity entries are excluded. For the full selection, the next-week forecast is 39,894 units (rounded). See Data notes in the app for definitions.

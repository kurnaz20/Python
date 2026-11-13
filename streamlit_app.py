import altair as alt
import pandas as pd
import streamlit as st

from analytics import account_review, forecast, load_transactions, weekly_demand

st.set_page_config(page_title="Book Distribution | Decision Dashboard", layout="wide")
data, quality = st.cache_resource(load_transactions)()
st.markdown("""
<style>
[data-testid="stMetric"] {
    background: #f4edf9;
    border-radius: 12px;
    padding: 12px 16px;
}
[data-testid="stHorizontalBlock"] > :nth-child(even) [data-testid="stMetric"] {
    background: #fbeef3;
}
[data-testid="stAlert"] [data-baseweb="notification"] {
    background-color: #f6edf7;
    color: #533f60;
}
</style>
""", unsafe_allow_html=True)
st.title("Book distribution dashboard")
st.caption("B2B transaction analysis · 2020")
st.sidebar.header("Filters")
lo, hi = data.InvoiceDate.min().date(), data.InvoiceDate.max().date()
dates = st.sidebar.date_input("Transaction dates", (lo, hi), min_value=lo, max_value=hi)
city = st.sidebar.multiselect("Cities", sorted(data.City.unique()))
category = st.sidebar.multiselect("Categories", sorted(data.Category.unique()))
st.sidebar.caption("An empty city or category selection includes all values.")
if len(dates) != 2:
    st.info("Select an end date to complete the period.")
    st.stop()
start, end = dates
mask = data.InvoiceDate.between(pd.Timestamp(start), pd.Timestamp(end))
for field, values in [("City", city), ("Category", category)]:
    if values:
        mask &= data[field].isin(values)
view = data.loc[mask]
if view.empty:
    st.info("No transactions match these filters. Widen the date range or clear a selection.")
    st.stop()

sales = view.Sales.sum()
cols = st.columns(4)
for col, label, val in zip(cols, ["Net sales value", "Units distributed", "Invoices", "Active accounts"],
                           [sales, view.Quantity.sum(), view.InvoiceNo.nunique(), view.CustomerID.nunique()]):
    col.metric(label, f"{val:,.0f}")
sales_tab, marketing, supply, audit = st.tabs(["Sales", "Marketing", "Supply chain", "Data notes"])


def ranked_chart(series, label, measure):
    frame = series.nlargest(10).rename(measure).rename_axis(label).reset_index()
    chart = alt.Chart(frame).mark_bar(color="#D99AB7", cornerRadiusEnd=3).encode(
        x=alt.X(f"{measure}:Q", axis=alt.Axis(format="~s")),
        y=alt.Y(f"{label}:N", sort="-x", axis=alt.Axis(labelLimit=220)),
        tooltip=[label, alt.Tooltip(f"{measure}:Q", format=",.0f")])
    st.altair_chart(chart, use_container_width=True)


with sales_tab:
    st.subheader("Sales over time")
    monthly = view.set_index("InvoiceDate").Sales.resample("MS").sum().reindex(
        pd.date_range(pd.Timestamp(start).replace(day=1), pd.Timestamp(end).replace(day=1), freq="MS"), fill_value=0)
    st.altair_chart(alt.Chart(monthly.rename("Sales").rename_axis("Month").reset_index()).mark_line(
        point=True, color="#957AB9").encode(x="Month:T", y=alt.Y("Sales:Q", axis=alt.Axis(format="~s")),
        tooltip=[alt.Tooltip("Month:T", format="%B %Y"), alt.Tooltip("Sales:Q", format=",.0f")]), use_container_width=True)
    st.caption("Each month includes only dates within your selection. Values use the source price units.")
    dimension = st.radio("Rank sales by", ["Category", "City"], horizontal=True)
    totals = view.groupby(dimension, observed=True).Sales.sum().sort_values(ascending=False)
    ranked_chart(totals, dimension, "Net sales")
    if sales > 0:
        st.info(f"{totals.index[0]} accounts for {totals.iloc[0]/sales:.1%} of selected sales. "
                f"Review this {dimension.lower()} first when planning account coverage.")

    # We compare two full months so a partial month cannot skew the result.
    complete = [m for m in monthly.index if m.date() >= start and (m + pd.offsets.MonthEnd(0)).date() <= end]
    if len(complete) >= 2:
        previous, current = complete[-2:]
        period = view.InvoiceDate.dt.to_period("M")
        changes = []
        for month in (previous, current):
            changes.append(view.loc[period.eq(month.to_period("M"))].groupby("Category", observed=True).Sales.sum())
        delta = changes[1].subtract(changes[0], fill_value=0).sort_values(ascending=False)
        if not delta.empty:
            st.subheader(f"Change in sales · {previous:%b} to {current:%b}")
            st.caption("Two complete months within the selected dates. Categories with no sales in either comparison month are assigned zero for that month.")
            if delta.iloc[0] > 0:
                st.write(f"Largest increase: {delta.index[0]} (+{delta.iloc[0]:,.0f}).")
            if delta.iloc[-1] < 0:
                st.write(f"Largest decline: {delta.index[-1]} ({delta.iloc[-1]:,.0f}). Review the accounts buying in this category.")

with marketing:
    st.subheader("Which accounts are due for a follow-up?")
    st.write("Among accounts with at least four purchase dates in this selection, compare days since the last "
             "purchase with their own median interval. The list prioritises accounts by selected sales value.")
    accounts = account_review(view, end)
    st.metric("Accounts past their usual interval", f"{len(accounts):,}")
    if accounts.empty:
        st.info("No eligible accounts are overdue in the selected period.")
    else:
        first = accounts.iloc[0]
        st.info(f"Contact {accounts.index[0]} first. Its last purchase was {first.Elapsed:.0f} days ago, "
                f"compared with a typical interval of {first.Typical:g} days.")
        listing = accounts.reset_index().rename(columns={"CustomerID": "Account", "Days": "Purchase dates",
            "Last": "Last purchase", "Typical": "Median interval (days)", "Elapsed": "Days since purchase",
            "Overdue": "Days overdue", "Sales": "Net sales"})
        listing["Last purchase"] = listing["Last purchase"].dt.date
        st.dataframe(listing, hide_index=True, use_container_width=True)
        st.download_button("Download follow-up list", listing.to_csv(index=False), "follow_up.csv", "text/csv")

with supply:
    st.subheader("Next seven days of demand")
    sku_table = view.groupby("StockCode", observed=True).agg(Units=("Quantity","sum"), Title=("Description","first"))
    top = sku_table.nlargest(100, "Units")
    sku = st.selectbox("Forecast scope", ["All selected products", *top.index],
        format_func=lambda k: k if k not in top.index else f"{top.at[k, 'Title']} · {k}")
    scoped = view if sku == "All selected products" else view[view.StockCode == sku]
    series = weekly_demand(scoped, start, end)
    result = forecast(series)
    if result is None:
        st.info("Select at least 14 full weeks to compare models and measure forecast error.")
    else:
        model, estimate, mae, holdout = result
        left, right = st.columns(2)
        left.metric("Expected units · next 7 days", f"{estimate:,.0f}")
        right.metric("Test error · units per week (MAE)", f"{mae:,.1f}")
        future = series.index[-1] + pd.Timedelta(days=7)
        chart = pd.concat([series.rename("Observed"), holdout.rename("Test prediction"),
                           pd.Series([estimate], index=[future], name="Forecast")], axis=1)
        points = chart.rename_axis("Week ending").reset_index().melt("Week ending", var_name="Series", value_name="Units").dropna()
        st.altair_chart(alt.Chart(points).mark_line(point=True).encode(x="Week ending:T", y="Units:Q",
            color=alt.Color("Series:N", scale=alt.Scale(domain=["Observed","Test prediction","Forecast"],
            range=["#957AB9","#CE8EAE","#945579"])), tooltip=["Week ending:T","Series:N",alt.Tooltip("Units:Q",format=",.1f")]),
            use_container_width=True)
        st.info(f"For {future - pd.Timedelta(days=6):%d %b}–{future:%d %b %Y}, plan for approximately "
                f"{estimate:,.0f} units. Compare this volume with available stock and incoming deliveries.")
        st.caption(f"Selected model: {model}. Six rolling one-week predictions select between last week and a "
                   "four-week mean. The next four weeks independently measure mean absolute error. "
                   "Weeks end on the selected end date’s weekday. Dates without transactions count as zero demand. "
                   "SKU choices cover the top 100 by units; sales history measures fulfilled demand.")
    st.subheader("Products carrying the most volume")
    st.dataframe(sku_table.nlargest(10,"Units").reset_index(), hide_index=True, use_container_width=True)

with audit:
    st.subheader("How the figures are calculated")
    st.write("Source: B2B_Transaction_Data_.xlsx, Transaction sheet. Counts below cover the entire source before filters.")
    st.dataframe(pd.Series(quality, name="Lines").rename_axis("Check").reset_index(), hide_index=True)
    st.markdown("""
- Net sales value is quantity × net unit price. The workbook does not specify a currency. UnitPrice is kept in the dataset for reference.
- Include positive quantities and nonnegative net prices. Zero-price items contribute units. Exclude missing quantities and zero-quantity adjustments from sales and demand. Audit counts can overlap.
- Exact repeats are retained because there is no invoice-line identifier to distinguish repeated purchases from duplicate entries.
- Blank cities and categories are grouped as Unknown. An invoice can span several categories and counts once in the selected view.
- The follow-up list uses purchase dates within the filters. A delayed purchase is a reason to contact an account, not a confirmed cancellation.
""")

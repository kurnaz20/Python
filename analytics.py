from pathlib import Path
import pandas as pd


def load_transactions():
    path = Path(__file__).parent / "data" / "transactions.csv.gz"
    labels = ["InvoiceNo", "CustomerID", "StockCode", "Description", "Category", "City"]
    raw = pd.read_csv(path, dtype={k: "category" for k in labels}, parse_dates=["InvoiceDate"])
    quality = {
        "Source lines": len(raw),
        "Extra exact repeats retained": int(raw.duplicated().sum()),
        "Missing quantity": int(raw.Quantity.isna().sum()),
        "Zero quantity": int(raw.Quantity.eq(0).sum()),
        "Negative net price": int(raw.NetPrice.lt(0).sum()),
        "Missing city": int(raw.City.isna().sum()),
        "Missing category": int(raw.Category.isna().sum()),
    }
    valid = raw.Quantity.gt(0) & raw.NetPrice.ge(0) & raw.InvoiceDate.notna()
    data = raw.loc[valid].copy()
    quality["Included lines"] = len(data)
    for k in ["City", "Category"]:
        data[k] = data[k].cat.add_categories("Unknown").fillna("Unknown")
    data["Sales"] = data.Quantity * data.NetPrice
    return data, quality


def account_review(data, end):
    visits = data[["CustomerID", "InvoiceDate"]].drop_duplicates().sort_values("InvoiceDate")
    visits["Gap"] = visits.groupby("CustomerID", observed=True).InvoiceDate.diff().dt.days
    accounts = visits.groupby("CustomerID", observed=True).agg(
        Days=("InvoiceDate", "size"), Last=("InvoiceDate", "max"), Typical=("Gap", "median"))
    accounts["Elapsed"] = (pd.Timestamp(end) - accounts.Last).dt.days
    accounts["Overdue"] = accounts.Elapsed - accounts.Typical
    accounts["Sales"] = data.groupby("CustomerID", observed=True).Sales.sum()
    return accounts.loc[(accounts.Days >= 4) & (accounts.Overdue > 0)].sort_values(
        ["Sales", "Overdue"], ascending=False)


def weekly_demand(data, start, end):
    start, end = pd.Timestamp(start), pd.Timestamp(end)
    weeks = ((end - start).days + 1) // 7
    if not weeks:
        return pd.Series(dtype=float)
    days = pd.date_range(end=end, periods=7 * weeks)
    units = data.groupby("InvoiceDate").Quantity.sum().reindex(days, fill_value=0)
    return pd.Series(units.to_numpy().reshape(weeks, 7).sum(axis=1), index=days[6::7])


def forecast(series):
    # We keep the last four weeks to check how well our forecast works.
    if len(series) < 14:
        return None
    models = {"Previous week": 1, "Four-week average": 4}
    predictions = pd.DataFrame({k: series.shift().rolling(w).mean() for k, w in models.items()})
    tune = predictions.iloc[-10:-4].sub(series.iloc[-10:-4], axis=0).abs().mean()
    name = tune.idxmin()
    errors = predictions[name].iloc[-4:] - series.iloc[-4:]
    return name, series.tail(models[name]).mean(), errors.abs().mean(), predictions[name].iloc[-4:]

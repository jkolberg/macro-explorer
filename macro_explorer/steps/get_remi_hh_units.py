import re

import pandas as pd

# REMI population figures are reported in thousands.
REMI_POP_SCALE = 1000


def _parse_age_group(category):
    """Convert a REMI category like 'Population - Ages 25-29 - All Races - Total'
    into a 5-year bin label such as 'ages_25_29' (or 'ages_85_plus')."""
    match = re.search(r"Ages\s+(\d+)(?:-(\d+))?(\+)?", str(category))
    if not match:
        return None
    start, end, plus = match.group(1), match.group(2), match.group(3)
    if plus:
        return f"ages_{start}_plus"
    return f"ages_{start}_{end}"


def load_remi_pop(remi_path, county_map):
    """Read the REMI workbook and return a long DataFrame with columns
    [county_id, age_group, year, total_pop], with population scaled to people."""
    df = pd.read_excel(remi_path, sheet_name="All", header=5)
    df = df.rename(columns={df.columns[0]: "region", df.columns[1]: "category"})
    year_cols = list(df.columns[3:])

    pop = df[df["category"].astype(str).str.startswith("Population - Ages")].copy()
    pop["county_id"] = pop["region"].map(county_map)
    pop["age_group"] = pop["category"].map(_parse_age_group)
    pop = pop.dropna(subset=["county_id", "age_group"])
    pop["county_id"] = pop["county_id"].astype(int)

    long = pop.melt(
        id_vars=["county_id", "age_group"],
        value_vars=year_cols,
        var_name="year",
        value_name="total_pop",
    )
    long["year"] = long["year"].astype(float).astype(int)
    long["total_pop"] = long["total_pop"].astype(float) * REMI_POP_SCALE
    return long


def calculate_hhpop(pop_long, gq_rates):
    """Apply 5-year-bin group-quarters rates to compute gq and household pop."""
    pop_long = pop_long.merge(gq_rates, on=["county_id", "age_group"], how="left")
    pop_long["gq_rate"] = pop_long["gq_rate"].fillna(0)
    pop_long["gq"] = pop_long["total_pop"] * pop_long["gq_rate"]
    pop_long["hhpop"] = pop_long["total_pop"] - pop_long["gq"]
    return pop_long


def calculate_hh(pop_long, headship_rates):
    """Apply 5-year-bin headship rates to household population to estimate households."""
    pop_long = pop_long.merge(headship_rates, on=["county_id", "age_group"], how="left")
    pop_long["headship_rate"] = pop_long["headship_rate"].fillna(0)
    pop_long["hh"] = pop_long["hhpop"] * pop_long["headship_rate"]

    hh_by_county_year = (
        pop_long.groupby(["county_id", "year"], as_index=False)["hh"].sum()
    )
    return hh_by_county_year


def process_forecast(remi_path, county_map, gq_rates, headship_rates):
    """Run the full pipeline for a single REMI workbook and return a DataFrame
    of county/year totals (total_pop, hhpop, gq, hh)."""
    pop_long = load_remi_pop(remi_path, county_map)

    # Apply gq rates to derive hhpop, then headship rates to derive households.
    pop_long = calculate_hhpop(pop_long, gq_rates)
    hh_by_county_year = calculate_hh(pop_long, headship_rates)

    totals = (
        pop_long.groupby(["county_id", "year"], as_index=False)[
            ["total_pop", "hhpop", "gq"]
        ].sum()
    )
    out = totals.merge(hh_by_county_year, on=["county_id", "year"], how="left")
    out = out[["county_id", "total_pop", "hhpop", "gq", "hh", "year"]]
    out[["total_pop", "hhpop", "gq", "hh"]] = (
        out[["total_pop", "hhpop", "gq", "hh"]].round(0).astype(int)
    )
    out = out.sort_values(["year", "county_id"]).reset_index(drop=True)
    return out


def run_step(context):
    data_dir = context["data_dir"]
    county_map = context["county_map"]
    headship_year = context.get("headship_rate_year", 2020)
    remi_forecasts = context["remi_forecasts"]
    output_file = context.get(
        "remi_output_file", "REMI_forecasts_counties_summed_all_years.csv"
    )

    # 5-year group-quarters rates.
    gq_rates = pd.read_csv(f"{data_dir}/gq_rates.csv")[["county_id", "age_group", "gq_rate"]]

    # 5-year headship rates; pick the requested census year column.
    headship_rates = pd.read_csv(f"{data_dir}/headship_rates.csv")
    rate_col = f"headship_rate_{headship_year}"
    headship_rates = headship_rates.rename(columns={rate_col: "headship_rate"})[
        ["county_id", "age_group", "headship_rate"]
    ]

    forecast_frames = []
    for forecast in remi_forecasts:
        name = forecast["name"]
        print(
            f"Building REMI household/units totals for {name} "
            f"using {headship_year} headship rates..."
        )
        out = process_forecast(
            f"{data_dir}/{forecast['filename']}", county_map, gq_rates, headship_rates
        )
        out.insert(0, "name", name)
        forecast_frames.append(out)

    combined = pd.concat(forecast_frames, ignore_index=True)
    combined.to_csv(f"{data_dir}/{output_file}", index=False)
    return context

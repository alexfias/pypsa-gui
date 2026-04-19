# Module API

Each research module must implement a single entry function:

``` python
def run(network: pypsa.Network) -> dict:
```

## Input

-   `network`: A PyPSA network object (can be solved or unsolved)

------------------------------------------------------------------------

## Output

The function must return a dictionary with any of the following keys:

### 1. Metrics

Simple scalar values (for dashboards, summaries):

``` python
{
    "metrics": {
        "total_cost": 1.2e9,
        "co2_emissions": 5e6
    }
}
```

------------------------------------------------------------------------

### 2. Tables

Pandas DataFrames (for display in tables):

``` python
{
    "tables": {
        "generator_summary": pd.DataFrame(...)
    }
}
```

------------------------------------------------------------------------

### 3. Plots

Matplotlib figures:

``` python
{
    "plots": {
        "capacity_plot": matplotlib.figure.Figure
    }
}
```

------------------------------------------------------------------------

## Optional Metadata

Modules can optionally define:

``` python
name = "My Module"
description = "Short explanation of what this module does"
```

------------------------------------------------------------------------

## Example

``` python
def run(network):
    import pandas as pd

    total_gen = network.generators.p_nom.sum()

    df = pd.DataFrame({
        "metric": ["total_generation_capacity"],
        "value": [total_gen]
    })

    return {
        "metrics": {
            "total_generation_capacity": total_gen
        },
        "tables": {
            "summary": df
        }
    }
```

------------------------------------------------------------------------

## Notes

-   The module should **not modify the network in-place** unless
    explicitly intended.
-   Use efficient pandas operations for performance.
-   Always return results explicitly (no global state).

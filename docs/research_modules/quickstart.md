# Quickstart: Your First Module

## 1. Create a module file

``` python
from pypsa import Network

def run(network: Network):
    total_load = network.loads_t.p_set.sum().sum()

    return {
        "metrics": {
            "total_load": total_load
        }
    }
```

## 2. Register the module

Place it in: modules/my_module.py

## 3. Run it in the GUI

-   Go to "Analysis → Research Modules"
-   Select your module
-   Click "Run"

## Output

The module returns: - metrics (numbers) - tables (DataFrames) - plots
(matplotlib figures)

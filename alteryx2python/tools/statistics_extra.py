"""Small, honest local adapters for predictive/statistical macros.

These return tabular evidence only; they are not native Alteryx/R report or
model binaries.  The profile is deliberately limited to fields/target/group/seed.
"""

from __future__ import annotations
from typing import Any
import numpy as np
import pandas as pd
from alteryx2python.runtime.context import WorkflowContext
from alteryx2python.parser.tool_parsers.common import ToolParserResult

_TOOLS = (
    "DistributionAnalysis",
    "Histogram",
    "Scatterplot",
    "HeatPlot",
    "ViolinPlot",
    "PlotofMeans",
    "ImportanceWeights",
    "AssociationAnalysis",
    "FindNearestNeighbors",
    "AppendCluster",
    "KCentroidsDiagnostics",
    "MultidimensionalScaling",
    "NetworkAnalysis",
    "ModelComparison",
    "LiftChart",
    "ABAnalysis",
    "ABControls",
    "ABTreatments",
    "ABTrend",
)


def _frame(inputs):
    f = inputs.get("Input")
    if f is None:
        f = inputs.get("Data")
    if f is None:
        raise KeyError("statistics tool requires Input anchor")
    if not isinstance(f, pd.DataFrame):
        raise TypeError("Input anchor must contain a pandas DataFrame")
    return f


def _cols(f, c, n=1):
    raw = c.get("fields") or c.get("field") or c.get("features")
    if isinstance(raw, str):
        raw = [x.strip() for x in raw.split(",") if x.strip()]
    raw = list(raw or [])
    if not raw:
        raw = [x for x in f.columns if pd.api.types.is_numeric_dtype(f[x])]
    missing = [x for x in raw if x not in f.columns]
    if missing:
        raise KeyError(f"configured fields are missing: {missing}")
    if len(raw) < n:
        raise ValueError(f"requires at least {n} field(s)")
    return raw


def _finish(name, f, out, c, ctx):
    if not isinstance(ctx, WorkflowContext):
        raise TypeError("statistics tool requires a WorkflowContext")
    sid = c.get("source_tool_id")
    if not sid:
        raise ValueError("statistics tool requires source_tool_id")
    outputs = {"Output": out}
    ctx.record_node(
        node_id=str(c.get("node_id", "unknown")),
        tool_type=name,
        source_tool_id=str(sid),
        inputs={"Input": f},
        outputs=outputs,
        status="success",
        config={
            "profile": "local-scipy-sklearn",
            "fields": c.get("fields"),
            "target": c.get("target"),
            "group": c.get("group"),
            "seed": c.get("seed", 0),
        },
    )
    return outputs


def _run(name, inputs, c, ctx):
    f = _frame(inputs)
    cols = _cols(
        f,
        c,
        2
        if name
        in (
            "Scatterplot",
            "HeatPlot",
            "MultidimensionalScaling",
            "FindNearestNeighbors",
        )
        else 1,
    )
    x = f[cols].apply(pd.to_numeric, errors="coerce")
    if x.isna().any().any():
        raise ValueError("selected fields must be numeric and non-null")
    if name == "Histogram":
        bins = int(c.get("bins", 10))
        rows = []
        for k in cols:
            counts, edges = np.histogram(x[k], bins=bins)
            rows.extend(
                {
                    "Field": k,
                    "Bin": i,
                    "Left": edges[i],
                    "Right": edges[i + 1],
                    "Count": int(v),
                }
                for i, v in enumerate(counts)
            )
        out = pd.DataFrame(rows)
    elif name in ("DistributionAnalysis", "ViolinPlot"):
        out = pd.DataFrame(
            {
                "Field": cols,
                "Count": [len(x)] * len(cols),
                "Mean": [x[k].mean() for k in cols],
                "StdDev": [x[k].std(ddof=1) for k in cols],
                "Min": [x[k].min() for k in cols],
                "Max": [x[k].max() for k in cols],
            }
        )
    elif name == "Scatterplot":
        out = x.rename(columns={cols[0]: "X", cols[1]: "Y"}).assign(
            Correlation=x[cols[0]].corr(x[cols[1]])
        )
    elif name == "HeatPlot":
        out = (
            x.corr()
            .stack()
            .rename("Correlation")
            .reset_index()
            .rename(columns={"level_0": "Field1", "level_1": "Field2"})
        )
    elif name == "PlotofMeans":
        out = x.mean().rename("Mean").reset_index().rename(columns={"index": "Field"})
    elif name == "ImportanceWeights":
        target = c.get("target")
        if not target or target not in f:
            raise ValueError("ImportanceWeights requires configured target")
        y = pd.to_numeric(f[target], errors="coerce")
        if y.isna().any():
            raise ValueError("target must be numeric and non-null")
        out = pd.DataFrame(
            {"Field": cols, "Importance": [abs(x[k].corr(y)) for k in cols]}
        ).fillna(0)
    elif name == "AssociationAnalysis":
        # Bounded pairwise binary association: support and confidence.
        b = f[cols].apply(lambda s: s.astype(bool))
        rows = []
        for i, a in enumerate(cols):
            for d in cols[i + 1 :]:
                both = (b[a] & b[d]).sum()
                rows.append(
                    {
                        "Field1": a,
                        "Field2": d,
                        "Support": both / len(b),
                        "Confidence": both / max(1, b[a].sum()),
                    }
                )
        out = pd.DataFrame(rows)
    elif name == "FindNearestNeighbors":
        from sklearn.neighbors import NearestNeighbors

        k = int(c.get("k", 3))
        d, i = NearestNeighbors(n_neighbors=min(k + 1, len(x))).fit(x).kneighbors(x)
        out = pd.DataFrame(
            {
                "Row": np.repeat(np.arange(len(x)), d.shape[1] - 1),
                "Neighbor": i[:, 1:].ravel(),
                "Distance": d[:, 1:].ravel(),
            }
        )
    elif name in ("AppendCluster", "KCentroidsDiagnostics"):
        from sklearn.cluster import KMeans

        m = KMeans(
            n_clusters=int(c.get("clusters", 2)),
            random_state=int(c.get("seed", 0)),
            n_init=10,
        ).fit(x)
        out = f.copy()
        out["Cluster"] = m.labels_
        out = (
            out
            if name == "AppendCluster"
            else pd.DataFrame(
                {
                    "Cluster": range(len(m.cluster_centers_)),
                    "Inertia": [m.inertia_] * len(m.cluster_centers_),
                }
            )
        )
    elif name == "MultidimensionalScaling":
        from sklearn.manifold import MDS

        z = MDS(
            n_components=int(c.get("components", 2)),
            random_state=int(c.get("seed", 0)),
            n_init=1,
        ).fit_transform(x)
        out = pd.DataFrame(z, columns=[f"MDS{i + 1}" for i in range(z.shape[1])])
    elif name == "NetworkAnalysis":
        src = c.get("source") or "source"
        dst = c.get("target") or "target"
        if src not in f or dst not in f:
            raise KeyError("NetworkAnalysis requires source and target columns")
        try:
            import networkx as nx

            g = nx.from_pandas_edgelist(f, src, dst)
            out = pd.DataFrame(
                {
                    "Node": list(g),
                    "Degree": [g.degree[n] for n in g],
                    "Centrality": [nx.degree_centrality(g)[n] for n in g],
                }
            )
        except ImportError:
            nodes = pd.unique(f[[src, dst]].values.ravel())
            deg = {n: 0 for n in nodes}
            for a, b in zip(f[src], f[dst]):
                deg[a] += 1
                deg[b] += 1
            out = pd.DataFrame(
                {
                    "Node": list(deg),
                    "Degree": list(deg.values()),
                    "Centrality": [v / max(1, len(deg) - 1) for v in deg.values()],
                }
            )
    elif name == "ModelComparison":
        target = c.get("target")
        preds = c.get("predictions") or cols
        if target not in f:
            raise KeyError("ModelComparison requires target")
        y = pd.to_numeric(f[target], errors="coerce")
        rows = []
        for p in preds:
            if p not in f:
                raise KeyError(f"missing prediction field: {p}")
            q = pd.to_numeric(f[p], errors="coerce")
            err = y - q
            mse = float((err**2).mean())
            rows.append(
                {
                    "Model": p,
                    "MSE": mse,
                    "MAE": float(err.abs().mean()),
                    "R2": float(1 - mse / ((y - y.mean()) ** 2).mean()),
                }
            )
        out = pd.DataFrame(rows)
    elif name == "LiftChart":
        target = c.get("target")
        score = c.get("score") or cols[0]
        if target not in f or score not in f:
            raise KeyError("LiftChart requires target and score")
        z = (
            f[[target, score]]
            .dropna()
            .sort_values(score, ascending=False, kind="mergesort")
        )
        y = pd.to_numeric(z[target])
        base = y.mean()
        z["Decile"] = (
            pd.qcut(np.arange(len(z)), 10, labels=False, duplicates="drop") + 1
        )
        out = z.groupby("Decile", as_index=False).agg(
            Count=(target, "size"), Positives=(target, "sum")
        )
        out["Lift"] = out.Positives / out.Count / base
    else:
        group = c.get("group")
        if not group or group not in f.columns:
            raise ValueError(f"{name} requires configured group")
        if name == "ABAnalysis":
            from scipy.stats import ttest_ind

            levels = list(f[group].dropna().unique())
            if len(levels) != 2:
                raise ValueError("ABAnalysis requires exactly two groups")
            a, b = [
                pd.to_numeric(f.loc[f[group] == v, cols[0]], errors="coerce").dropna()
                for v in levels
            ]
            t, p = ttest_ind(a, b, equal_var=False)
            out = pd.DataFrame(
                {
                    "Control": [levels[0]],
                    "Treatment": [levels[1]],
                    "MeanControl": [a.mean()],
                    "MeanTreatment": [b.mean()],
                    "TStatistic": [t],
                    "PValue": [p],
                }
            )
        elif name in ("ABControls", "ABTreatments"):
            out = f.groupby(group, as_index=False)[cols].mean()
        else:
            time = c.get("time")
            if not time or time not in f:
                raise KeyError("ABTrend requires time field")
            out = (
                f.groupby([time, group], as_index=False)[cols].mean().sort_values(time)
            )
    return _finish(name, f, out, c, ctx)


IMPLEMENTATIONS = {
    n: (lambda inputs, config, context, _n=n: _run(_n, inputs, config, context))
    for n in _TOOLS
}
ANCHORS = {n: (("Input",), ("Output",)) for n in _TOOLS}


def _parse(raw):
    if not isinstance(raw, dict):
        return ToolParserResult({})
    return ToolParserResult(
        {
            k: v.get("text", v.get("value", v)) if isinstance(v, dict) else v
            for k, v in raw.items()
            if k not in ("attributes",)
        }
    )


PARSERS = {n: _parse for n in _TOOLS}
